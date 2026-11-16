"""Archiving, compression and disk-copy commands: tar, cpio, gzip family, xz, bzip2, zip, 7z, dd, ddrescue."""
import math
import posixpath

from .shell import cmd, getopts, read_inputs, lines_of, join_lines, REGISTRY, HELP
from .vfs import Archive, Comp, FSError, inner_size


def _collect(fs, path, user, ctx=None, strip=True):
    """Return list of member dicts for path (recursing into directories), relative names as typed."""
    members = []
    name = path
    if strip and name.startswith("/"):
        name = name.lstrip("/")
    node = fs.lookup(path, follow=False)
    if node is None:
        raise FSError("No such file or directory")
    if node.kind == "d":
        members.append({"path": name.rstrip("/") + "/", "kind": "d", "data": "", "mode": node.mode & 0o777})
        for nm in sorted(node.entries):
            members.extend(_collect(fs, path.rstrip("/") + "/" + nm, user, ctx, strip))
    else:
        data = fs.read(path, user) if node.kind != "l" else node.target
        members.append({"path": name, "kind": "f", "data": data, "mode": node.mode & 0o777})
    return members


def _extract(ctx, members, dest=".", verbose=False):
    fs = ctx.fs
    for m in members:
        target = dest.rstrip("/") + "/" + m["path"] if dest not in (".", "") else m["path"]
        try:
            if m["kind"] == "d":
                if not fs.exists(target):
                    fs.mkdir(target.rstrip("/"), ctx.user, parents=True)
            else:
                parent = posixpath.dirname(fs.abspath(target))
                if not fs.exists(parent):
                    fs.mkdir(parent, ctx.user, parents=True)
                n = fs.write(target, m["data"], ctx.user)
                n.mode = m["mode"]
            if verbose:
                ctx.w(m["path"] + "\n")
        except FSError as ex:
            ctx.err("%s: Cannot open: %s" % (m["path"], ex.msg))
            return 2
    return 0


def _unwrap(obj):
    while isinstance(obj, Comp):
        obj = obj.inner
    return obj


@cmd("tar", help=("an archiving utility", "tar {options} {tarball name} {file1 file2 ...}", [
    ("-c", "create a tarball"), ("-x", "extract files from a tarball"), ("-t", "test (list) the files in a tarball"),
    ("-v", "verbose output"), ("-r", "append files to an existing archive"), ("-f", "tarball filename (required)"),
    ("-z", "filter through gzip (.tar.gz)"), ("-j", "filter through bzip2 (.tar.bz2)")]))
def c_tar(ctx):
    argv = ctx.argv[1:]
    if argv and not argv[0].startswith("-") and argv[0].isalpha():
        argv[0] = "-" + argv[0]
    opts, args = getopts(ctx, argv, flags="cxtvrzjJpP", valued="fC")
    if opts is None:
        return 2
    fs = ctx.fs
    modes = [k for k in "cxtr" if k in opts]
    if len(modes) != 1:
        ctx.e("tar: You must specify one of the '-Acdtrux', '--delete' or '--test-label' options\n")
        return 2
    if "f" not in opts:
        if modes[0] == "c":
            ctx.e("tar: Refusing to write archive contents to terminal (missing -f option?)\n")
        else:
            ctx.e("tar: Refusing to read archive contents from terminal (missing -f option?)\n")
        ctx.e("tar: Error is not recoverable: exiting now\n")
        return 2
    name = opts["f"]
    verbose = "v" in opts
    algo = "gz" if "z" in opts else "bz2" if "j" in opts else "xz" if "J" in opts else None
    mode = modes[0]
    chdir = opts.get("C")
    if mode == "c":
        if not args:
            ctx.e("tar: Cowardly refusing to create an empty archive\nTry 'tar --help' or 'tar --usage' for more information.\n")
            return 2
        members = []
        bad = 0
        for a in args:
            if a.startswith("/"):
                ctx.e("tar: Removing leading `/' from member names\n")
            try:
                if fs.abspath(a) == fs.abspath(name):
                    continue
                members.extend(_collect(fs, a, ctx.user, ctx))
            except FSError as ex:
                ctx.e("tar: %s: Cannot stat: %s\n" % (a, ex.msg))
                bad = 2
        if verbose:
            for m in members:
                ctx.w(m["path"] + "\n")
        arc = Archive("tar", members)
        obj = Comp(algo, arc, name) if algo else arc
        try:
            fs.write(name, obj, ctx.user)
        except FSError as ex:
            ctx.e("tar: %s: Cannot open: %s\n" % (name, ex.msg))
            return 2
        if bad:
            ctx.e("tar: Exiting with failure status due to previous errors\n")
        return bad
    try:
        node = fs.lookup(name)
        if node is None:
            ctx.e("tar: %s: Cannot open: No such file or directory\ntar: Error is not recoverable: exiting now\n" % name)
            return 2
        data = fs.read(name, ctx.user)
    except FSError as ex:
        ctx.e("tar: %s: Cannot open: %s\n" % (name, ex.msg))
        return 2
    if mode == "r":
        if isinstance(data, Comp):
            ctx.e("tar: Cannot update compressed archives\ntar: Error is not recoverable: exiting now\n")
            return 2
        if not isinstance(data, Archive) or data.kind != "tar":
            ctx.e("tar: This does not look like a tar archive\n")
            return 2
        for a in args:
            try:
                new = _collect(fs, a, ctx.user)
            except FSError as ex:
                ctx.e("tar: %s: Cannot stat: %s\n" % (a, ex.msg))
                continue
            data.members.extend(new)
            if verbose:
                for m in new:
                    ctx.w(m["path"] + "\n")
        fs.write(name, data, ctx.user)
        return 0
    inner = _unwrap(data)
    if not isinstance(inner, Archive) or inner.kind != "tar":
        ctx.e("tar: This does not look like a tar archive\ntar: Skipping to next header\ntar: Exiting with failure status due to previous errors\n")
        return 2
    if mode == "t":
        for m in inner.members:
            if verbose:
                ctx.w("%s%s %s/%s %9d 2026-11-15 10:00 %s\n" % ("d" if m["kind"] == "d" else "-", "rwxr-xr-x" if m["kind"] == "d" else "rw-r--r--", ctx.fs.user, ctx.fs.user, inner_size(m["data"]), m["path"]))
            else:
                ctx.w(m["path"] + "\n")
        return 0
    return _extract(ctx, inner.members, chdir or ".", verbose)


# ----------------------------------------------------------------------------- gzip / bzip2 / xz
SUFFIX = {"gz": ".gz", "bz2": ".bz2", "xz": ".xz"}


def _compress_family(ctx, algo, decompress):
    opts, args = getopts(ctx, ctx.argv[1:], flags="dfnNqrvtkc123456789zZ", numeric="level")
    if opts is None:
        return 1
    if "d" in opts:
        decompress = True
    fs = ctx.fs
    suf = SUFFIX[algo]
    if not args:
        ctx.e("%s: compressed data not written to a terminal. Use -f to force compression.\n" % ctx.name)
        return 1
    targets = []
    for a in args:
        if "r" in opts and fs.isdir(a):
            targets.extend(p for p in fs.walk(a) if fs.lookup(p, follow=False).kind == "f")
        else:
            targets.append(a)
    st = 0
    for a in targets:
        try:
            node = fs.lookup(a, follow=False)
        except FSError:
            node = None
        if node is None:
            ctx.err("%s: No such file or directory" % a)
            st = 1
            continue
        if node.kind == "d":
            ctx.e("%s: %s is a directory -- ignored\n" % (ctx.name, a) if algo == "gz" else "%s: Input file %s is a directory.\n" % (ctx.name, a))
            st = 1
            continue
        if "t" in opts:
            if isinstance(node.data, Comp) and node.data.algo == algo:
                if "v" in opts:
                    ctx.e("%s:\t OK\n" % a)
            else:
                ctx.e("%s: %s: not in %s format\n" % (ctx.name, a, algo))
                st = 1
            continue
        if decompress:
            if not a.endswith(suf) and not (algo == "gz" and a.endswith((".tgz", ".z"))):
                ctx.e("%s: %s: unknown suffix -- ignored\n" % (ctx.name, a))
                st = 1
                continue
            if not isinstance(node.data, Comp) or node.data.algo != algo:
                ctx.e("%s: %s: not in %s format\n" % (ctx.name, a, algo))
                st = 1
                continue
            outname = a[:-len(suf)] if a.endswith(suf) else a[:-4] + ".tar"
            if fs.exists(outname) and "f" not in opts:
                ctx.e("%s: %s already exists; not overwritten\n" % (ctx.name, outname))
                st = 1
                continue
            try:
                if "c" in opts:
                    ctx.w(node.data.inner if isinstance(node.data.inner, str) else "<binary data>\n")
                    continue
                fs.write(outname, node.data.inner, ctx.user)
                if "k" not in opts:
                    fs.unlink(a, ctx.user)
            except FSError as ex:
                ctx.err("%s: %s" % (a, ex.msg))
                st = 1
            continue
        if isinstance(node.data, Comp):
            ctx.e("%s: %s already has %s suffix -- unchanged\n" % (ctx.name, a, suf) if a.endswith(suf) else "%s: %s is already compressed\n" % (ctx.name, a))
            st = 1
            continue
        outname = a + suf
        if fs.exists(outname) and "f" not in opts:
            if ctx.ask("%s: %s already exists; do you wish to overwrite (y or n)? " % (ctx.name, outname)).strip().lower()[:1] != "y":
                ctx.w("\tnot overwritten\n")
                st = 2
                continue
        try:
            before = node.size()
            comp = Comp(algo, node.data, posixpath.basename(a))
            if "c" in opts:
                ctx.w(comp)
                continue
            fs.write(outname, comp, ctx.user)
            if "k" not in opts:
                fs.unlink(a, ctx.user)
            if "v" in opts:
                after = comp.size()
                pct = 100.0 * (1 - after / float(max(1, before)))
                if algo == "gz":
                    ctx.e("%s:\t%5.1f%% -- replaced with %s\n" % (a, pct, outname))
                else:
                    ctx.e("  %s: %.3f:1, %.3f bits/byte, %.2f%% saved, %d in, %d out.\n" % (a, before / float(max(1, after)), 8.0 * after / max(1, before), pct, before, after))
        except FSError as ex:
            ctx.err("%s: %s" % (a, ex.msg))
            st = 1
    return st


@cmd("gzip", help=("compress or expand files (GNU zip, .gz)", "gzip [OPTION]... [FILE]...", [
    ("-d", "decompress"), ("-f", "force"), ("-n/-N", "do not / do save the original name and timestamp"), ("-q", "suppress warnings"),
    ("-r", "operate recursively on directories"), ("-v", "verbose: show name and percent reduction"), ("-t", "test compressed file integrity"), ("-k", "keep input files")]))
def c_gzip(ctx):
    return _compress_family(ctx, "gz", False)


@cmd("gunzip", help=("decompress .gz files (same as gzip -d)", "gunzip FILE.gz", []))
def c_gunzip(ctx):
    return _compress_family(ctx, "gz", True)


@cmd("bzip2", help=("block-sorting file compressor (.bz2)", "bzip2 [OPTION]... [FILE]...", [("-d", "decompress"), ("-k", "keep input files"), ("-v", "verbose")]))
def c_bzip2(ctx):
    return _compress_family(ctx, "bz2", False)


@cmd("bunzip2", help=("decompress .bz2 files", "bunzip2 FILE.bz2", []))
def c_bunzip2(ctx):
    return _compress_family(ctx, "bz2", True)


@cmd("xz", help=("compress or decompress .xz files (best ratio, slowest)", "xz [OPTION]... [FILE]...", [("-d", "decompress"), ("-f", "force"), ("-q", "quiet"), ("-v", "verbose"), ("-t", "test integrity"), ("-k", "keep")]))
def c_xz(ctx):
    return _compress_family(ctx, "xz", False)


@cmd("unxz", help=("decompress .xz files", "unxz FILE.xz", []))
def c_unxz(ctx):
    return _compress_family(ctx, "xz", True)


def _cat_comp(ctx, algo):
    res_status = 0
    for a in ctx.argv[1:]:
        if a.startswith("-"):
            continue
        try:
            node = ctx.fs.lookup(a)
            if node is None:
                ctx.err("%s: No such file or directory" % a)
                res_status = 1
                continue
            d = ctx.fs.read(a, ctx.user)
        except FSError as ex:
            ctx.err("%s: %s" % (a, ex.msg))
            res_status = 1
            continue
        if not isinstance(d, Comp) or d.algo != algo:
            ctx.err("%s: not in %s format" % (a, algo))
            res_status = 1
            continue
        ctx.w(d.inner if isinstance(d.inner, str) else "<binary data>\n")
    return res_status


@cmd("zcat", "zless", "zmore", help=("view a .gz file without decompressing it", "zcat FILE.gz", []))
def c_zcat(ctx):
    return _cat_comp(ctx, "gz")


@cmd("bzcat", "bzless", "bzmore", help=("view a .bz2 file without decompressing it", "bzcat FILE.bz2", []))
def c_bzcat(ctx):
    return _cat_comp(ctx, "bz2")


@cmd("xzcat", help=("view a .xz file", "xzcat FILE.xz", []))
def c_xzcat(ctx):
    return _cat_comp(ctx, "xz")


@cmd("zgrep")
def c_zgrep(ctx):
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    if len(args) < 2:
        ctx.e("usage: zgrep pattern file.gz\n")
        return 2
    d = ctx.fs.read(args[1], ctx.user)
    text = d.inner if isinstance(d, Comp) and isinstance(d.inner, str) else ""
    import re
    rx = re.compile(args[0], re.I if "-i" in ctx.argv else 0)
    found = False
    for l in lines_of(text):
        if rx.search(l):
            ctx.w(l + "\n")
            found = True
    return 0 if found else 1


# ----------------------------------------------------------------------------- zip / 7z
@cmd("zip", help=("package and compress (archive) files into a .zip", "zip [OPTION]... archive.zip file...", [
    ("-d", "delete entries from the archive"), ("-e", "encrypt the entries"), ("-F", "fix a corrupted archive"),
    ("-r", "recurse into directories"), ("-T", "test the integrity of the archive")]))
def c_zip(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="rdeFTqv9")
    if opts is None:
        return 1
    fs = ctx.fs
    if not args:
        ctx.e("zip error: Nothing to do!\n")
        return 12
    name = args[0] if args[0].endswith(".zip") else args[0] + ".zip"
    files = args[1:]
    node = fs.lookup(name) if fs.exists(name) else None
    if "T" in opts:
        if node is None or not isinstance(node.data, Archive) or node.data.kind != "zip":
            ctx.e("zip error: Zip file structure invalid (%s)\n" % name)
            return 3
        ctx.w("test of %s OK\n" % name)
        return 0
    if "F" in opts:
        ctx.w("Fix archive (-F) - assume mostly intact archive\nZip entry offsets do not need adjusting\n")
        return 0
    if "d" in opts:
        if node is None:
            ctx.e("zip error: Zip file structure invalid (%s)\n" % name)
            return 3
        arc = node.data
        for f in files:
            before = len(arc.members)
            arc.members = [m for m in arc.members if m["path"] != f]
            ctx.w("deleting: %s\n" % f if len(arc.members) < before else "")
        fs.write(name, arc, ctx.user)
        return 0
    if not files:
        ctx.e("zip error: Nothing to do! (%s)\n" % name)
        return 12
    arc = node.data if node is not None and isinstance(node.data, Archive) and node.data.kind == "zip" else Archive("zip")
    for f in files:
        try:
            nd = fs.lookup(f, follow=False)
            if nd is None:
                ctx.e("\tzip warning: name not matched: %s\n" % f)
                continue
            if nd.kind == "d" and "r" not in opts:
                ctx.w("  adding: %s/ (stored 0%%)\n" % f.rstrip("/"))
                arc.members.append({"path": f.rstrip("/") + "/", "kind": "d", "data": "", "mode": 0o755})
                continue
            for m in _collect(fs, f, ctx.user):
                arc.members = [x for x in arc.members if x["path"] != m["path"]]
                arc.members.append(m)
                pct = 0 if m["kind"] == "d" else 45 if inner_size(m["data"]) else 0
                ctx.w("  adding: %s (%s)\n" % (m["path"], "stored 0%" if m["kind"] == "d" else "deflated %d%%" % pct))
        except FSError as ex:
            ctx.e("\tzip warning: %s: %s\n" % (f, ex.msg))
    if "e" in opts:
        ctx.w("(the real zip -e asks for a password here)\n")
    fs.write(name, arc, ctx.user)
    return 0


@cmd("unzip", help=("list, test and extract compressed files in a ZIP archive", "unzip [-l] [-d dir] archive.zip", [("-l", "list files"), ("-d dir", "extract into dir")]))
def c_unzip(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="lqotv", valued="d")
    if opts is None:
        return 1
    if not args:
        ctx.e("UnZip usage: unzip [-l] [-d exdir] file[.zip]\n")
        return 1
    name = args[0] if args[0].endswith(".zip") or ctx.fs.exists(args[0]) else args[0] + ".zip"
    try:
        node = ctx.fs.lookup(name)
        data = ctx.fs.read(name, ctx.user) if node else None
    except FSError as ex:
        ctx.e("unzip: cannot find or open %s, %s.zip or %s.ZIP.\n" % (name, name, name))
        return 9
    if node is None or not isinstance(data, Archive) or data.kind != "zip":
        ctx.e("unzip:  cannot find or open %s, %s.zip or %s.ZIP.\n" % (name, name, name) if node is None else "End-of-central-directory signature not found.  Either this file is not\na zipfile, or it constitutes one disk of a multi-part archive.\n")
        return 9
    if "l" in opts:
        ctx.w("Archive:  %s\n  Length      Date    Time    Name\n---------  ---------- -----   ----\n" % name)
        tot = 0
        for m in data.members:
            ctx.w("%9d  2026-11-15 10:00   %s\n" % (inner_size(m["data"]), m["path"]))
            tot += inner_size(m["data"])
        ctx.w("---------                     -------\n%9d                     %d files\n" % (tot, len(data.members)))
        return 0
    ctx.w("Archive:  %s\n" % name)
    dest = opts.get("d", ".")
    for m in data.members:
        ctx.w("%s: %s\n" % ("   creating" if m["kind"] == "d" else "  inflating", (dest.rstrip("/") + "/" if dest != "." else "") + m["path"]))
    return _extract(ctx, data.members, dest, False)


@cmd("7z", "7za", "7zr", help=("7-Zip file archiver (high compression, cross-platform)", "7z {options} {filenames}", [
    ("a / -a", "add"), ("x / -x", "extract"), ("-o", "output directory"), ("-p", "password"), ("-mx", "compression level")]))
def c_7z(ctx):
    argv = ctx.argv[1:]
    if not argv:
        ctx.w("7-Zip [64] 16.02 : Copyright (c) 1999-2016 Igor Pavlov\n\nUsage: 7z <command> [<switches>...] <archive_name> [<file_names>...]\n")
        return 0
    sub = argv[0].lstrip("-")
    rest = [a for a in argv[1:] if not (a.startswith("-o") or a.startswith("-p") or a.startswith("-mx"))]
    outdir = next((a[2:] for a in argv[1:] if a.startswith("-o")), ".") or "."
    fs = ctx.fs
    if sub == "a":
        if len(rest) < 2:
            ctx.e("Command Line Error: Cannot find archive name\n")
            return 7
        name = rest[0] if "." in posixpath.basename(rest[0]) else rest[0] + ".7z"
        arc = Archive("7z")
        for f in rest[1:]:
            try:
                arc.members.extend(m for m in _collect(fs, f, ctx.user))
            except FSError:
                ctx.e("WARNING: No more files\n%s : No such file or directory\n" % f)
                return 2
        fs.write(name, arc, ctx.user)
        ctx.w("\n7-Zip [64] 16.02 : Copyright (c) 1999-2016 Igor Pavlov : 2016-05-21\n\nScanning the drive:\n%d files\n\nCreating archive: %s\n\nEverything is Ok\n" % (len(arc.members), name))
        return 0
    if sub in ("x", "e"):
        if not rest:
            ctx.e("Command Line Error: Cannot find archive name\n")
            return 7
        try:
            node = fs.lookup(rest[0])
            data = fs.read(rest[0], ctx.user) if node else None
        except FSError as ex:
            ctx.e("ERROR: %s : %s\n" % (rest[0], ex.msg))
            return 2
        if not isinstance(data, Archive) or data.kind != "7z":
            ctx.e("ERROR: %s\n%s : Can not open file as archive\n" % (rest[0], rest[0]))
            return 2
        ctx.w("\n7-Zip [64] 16.02\n\nExtracting archive: %s\n\nEverything is Ok\n" % rest[0])
        return _extract(ctx, data.members, outdir, False)
    if sub == "l":
        node = fs.lookup(rest[0]) if rest and fs.exists(rest[0]) else None
        if node is None:
            ctx.e("ERROR: no such archive\n")
            return 2
        for m in node.data.members:
            ctx.w("2026-11-15 10:00:00 ....A %12d %s\n" % (inner_size(m["data"]), m["path"]))
        return 0
    ctx.e("Command Line Error: Unsupported command:\n%s\n" % argv[0])
    return 7


# ----------------------------------------------------------------------------- cpio
@cmd("cpio", help=("copy files to and from archives", "cpio -o > archive  |  cpio -i < archive", [
    ("-o", "copy-out: create an archive from the file names on stdin"), ("-i", "copy-in: extract files from an archive"), ("-v", "verbose")]))
def c_cpio(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="oivtdm", valued="HF")
    if opts is None:
        return 1
    fs = ctx.fs
    kind = "tar" if opts.get("H") == "tar" else "cpio"
    if "o" in opts:
        names = (ctx.stdin if isinstance(ctx.stdin, str) else "").split("\n")
        arc = Archive(kind)
        n = 0
        for nm in names:
            nm = nm.strip()
            if not nm:
                continue
            try:
                for m in _collect(fs, nm, ctx.user, strip=True):
                    arc.members.append(m)
                    n += 1
                    if "v" in opts:
                        ctx.e(m["path"] + "\n")
            except FSError as ex:
                ctx.e("cpio: %s: %s\n" % (nm, ex.msg))
        ctx.e("%d block%s\n" % (max(1, int(math.ceil(arc.size() / 512.0))), "s"))
        if "F" in opts:
            fs.write(opts["F"], arc, ctx.user)
        else:
            ctx.w(arc)
        return 0
    if "i" in opts:
        data = ctx.stdin
        if "F" in opts:
            try:
                data = fs.read(opts["F"], ctx.user)
            except FSError as ex:
                ctx.e("cpio: %s: %s\n" % (opts["F"], ex.msg))
                return 1
        data = _unwrap(data)
        if not isinstance(data, Archive) or data.kind not in ("cpio", "tar"):
            ctx.e("cpio: standard input is closed\n" if data is None else "cpio: Malformed number or bad archive\n")
            return 1
        if "t" in opts:
            for m in data.members:
                ctx.w(m["path"] + "\n")
            return 0
        for m in data.members:
            if "v" in opts:
                ctx.e(m["path"] + "\n") if False else ctx.w(m["path"] + "\n")
        rc = _extract(ctx, data.members, ".", False)
        ctx.e("%d block%s\n" % (max(1, int(math.ceil(data.size() / 512.0))), "s"))
        return rc
    ctx.e("cpio: You must specify one of -oipt options.\nTry 'cpio --help' or 'cpio --usage' for more information.\n")
    return 2


# ----------------------------------------------------------------------------- dd / ddrescue
def _bytes_of(data):
    if isinstance(data, str):
        return data
    return data


def _nice(n):
    if n >= 1048576:
        return "%.1f MB, %.1f MiB" % (n / 1e6, n / 1048576.0)
    if n >= 1024:
        return "%.1f kB, %.1f KiB" % (n / 1e3, n / 1024.0)
    return "%d bytes" % n


def _size_arg(s):
    mult = 1
    s = s.strip()
    if s and s[-1] in "kKMG":
        mult = {"k": 1024, "K": 1024, "M": 1048576, "G": 1073741824}[s[-1]]
        s = s[:-1]
    return int(s) * mult


@cmd("dd", help=("convert and copy a file", "dd [OPERAND]...", [
    ("if=FILE", "read from FILE instead of stdin"), ("of=FILE", "write to FILE instead of stdout"), ("bs=BYTES", "read and write up to BYTES bytes at a time"),
    ("count=N", "copy only N input blocks"), ("status=LEVEL", "none | noxfer | progress")]))
def c_dd(ctx):
    ops = {}
    for a in ctx.argv[1:]:
        if "=" not in a:
            ctx.e("dd: unrecognized operand '%s'\nTry 'dd --help' for more information.\n" % a)
            return 1
        k, v = a.split("=", 1)
        if k not in ("if", "of", "bs", "count", "status", "conv", "skip", "seek", "ibs", "obs"):
            ctx.e("dd: unrecognized operand '%s'\nTry 'dd --help' for more information.\n" % a)
            return 1
        ops[k] = v
    fs = ctx.fs
    try:
        bs = _size_arg(ops.get("bs", "512"))
        count = int(ops["count"]) if "count" in ops else None
    except ValueError:
        ctx.e("dd: invalid number\n")
        return 1
    if "if" in ops:
        try:
            node = fs.lookup(ops["if"])
            if node is None:
                ctx.e("dd: failed to open '%s': No such file or directory\n" % ops["if"])
                return 1
            if node.kind == "d":
                ctx.e("dd: error reading '%s': Is a directory\n" % ops["if"])
                return 1
            data = fs.read(ops["if"], ctx.user)
        except FSError as ex:
            ctx.e("dd: failed to open '%s': %s\n" % (ops["if"], ex.msg))
            return 1
    else:
        node = None
        data = ctx.stdin or ""
    flaky = getattr(node, "flaky", None) if node is not None else None
    err_msg = None
    if isinstance(data, str):
        raw = data
        limit = len(raw) if count is None else min(len(raw), bs * count)
        if flaky is not None and flaky < limit:
            limit = flaky
            err_msg = "dd: error reading '%s': Input/output error\n" % ops["if"]
        raw = raw[:limit]
        full, part = divmod(len(raw), bs)
        total = len(raw)
    else:
        raw = data
        total = inner_size(data)
        full, part = max(1, total // bs), 0
    status = ops.get("status", "")
    if "of" in ops:
        try:
            node_o = fs.lookup(ops["of"])
            if node_o is not None and node_o.kind == "d":
                ctx.e("dd: failed to open '%s': Is a directory\n" % ops["of"])
                return 1
            fs.write(ops["of"], raw, ctx.user)
        except FSError as ex:
            ctx.e("dd: failed to open '%s': %s\n" % (ops["of"], ex.msg))
            return 1
    else:
        ctx.w(raw if isinstance(raw, str) else "<binary data>\n")
    if err_msg:
        ctx.e(err_msg)
    if status != "none":
        if status == "progress":
            ctx.e("%d bytes (%s) copied, 1 s, %.1f MB/s\n" % (total, _nice(total), total / 1e6))
        ctx.e("%d+%d records in\n%d+%d records out\n" % (full, 1 if part else 0, full, 1 if part else 0))
        if status != "noxfer":
            ctx.e("%d bytes (%s) copied, 0.0012 s, %.1f MB/s\n" % (total, _nice(total), max(1.0, total / 1e6 / 0.0012)))
    return 1 if err_msg else 0


@cmd("ddrescue", help=("data recovery tool for failing disks", "ddrescue [options] infile outfile [mapfile]", [
    ("-f", "force overwriting of outfile"), ("-r N", "exit after N retry passes over bad sectors"), ("-v", "be verbose")]))
def c_ddrescue(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="fvnd", valued="rbs")
    if opts is None:
        return 1
    if len(args) < 2:
        ctx.e("ddrescue: Too few files.\nTry 'ddrescue --help' for more information.\n")
        return 1
    fs = ctx.fs
    src, dst = args[0], args[1]
    try:
        node = fs.lookup(src)
        if node is None:
            ctx.e("ddrescue: Can't open input file '%s': No such file or directory\n" % src)
            return 1
        data = fs.read(src, ctx.user)
    except FSError as ex:
        ctx.e("ddrescue: Can't open input file '%s': %s\n" % (src, ex.msg))
        return 1
    if fs.exists(dst) and "f" not in opts:
        ctx.e("ddrescue: Output file exists and is not a regular file? Use '-f' to overwrite.\n" if False else "ddrescue: Output file exists. Use '-f' if you really want to overwrite it.\n")
        return 1
    flaky = getattr(node, "flaky", None)
    text = data if isinstance(data, str) else ""
    bad = 0
    if flaky is not None and flaky < len(text):
        bad = len(text) - flaky
        text = text[:flaky] + "\0" * bad
    try:
        fs.write(dst, text, ctx.user)
    except FSError as ex:
        ctx.e("ddrescue: Can't open output file '%s': %s\n" % (dst, ex.msg))
        return 1
    retries = int(opts.get("r", 0))
    ctx.e("GNU ddrescue 1.27\nPress Ctrl-C to interrupt\n")
    ctx.e("     ipos: %9d B, non-trimmed:        0 B,  current rate:   1024 kB/s\n" % len(text))
    ctx.e("     opos: %9d B, non-scraped:        0 B,  average rate:   1024 kB/s\n" % len(text))
    ctx.e("non-tried:        0 B,  bad-sector:%9d B,    error rate:       0 B/s\n" % bad)
    ctx.e("  rescued: %9d B,   bad areas:        %d,        run time:          1s\n" % (len(text) - bad, 1 if bad else 0))
    if retries and bad:
        ctx.e("Retried %d pass%s over the bad area\n" % (retries, "" if retries == 1 else "es"))
    ctx.e("Finished\n")
    return 0
