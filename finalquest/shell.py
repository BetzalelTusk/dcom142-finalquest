"""A bash-like shell over the virtual filesystem. Implements the commands the DCOM 142 final covers."""
import fnmatch
import math
import posixpath
import re
import time

from . import ui
from .vfs import FS, FSError, Archive, Comp, mode_str, hexhash, inner_size

REGISTRY = {}
HELP = {}
PENDING_NOTES = []   # teaching notes raised by the simulator; the game shows them only as tips, on request


def note(msg):
    """Queue a teaching note instead of printing it. Returns '' so callers can do ctx.e(note(...))."""
    if msg not in PENDING_NOTES:
        PENDING_NOTES.append(msg)
    return ""


def cmd(*names, help=None):
    def deco(fn):
        for n in names:
            REGISTRY[n] = fn
        if help:
            for n in names:
                HELP[n] = help
        return fn
    return deco


# ----------------------------------------------------------------------------- tokenizer
class Word:
    __slots__ = ("text", "quoted")

    def __init__(self, text, quoted):
        self.text = text
        self.quoted = quoted


class ParseError(Exception):
    pass


def tokenize(line, env):
    toks = []
    i, n = 0, len(line)
    cur, quoted, has = "", False, False

    def flush():
        nonlocal cur, quoted, has
        if has:
            toks.append(Word(cur, quoted))
        cur, quoted, has = "", False, False

    def expand_var(s, j):
        m = re.match(r"\$(\w+|\{\w+\}|\?)", s[j:])
        if not m:
            return None, j
        name = m.group(1).strip("{}")
        return env.get(name, "0" if name == "?" else ""), j + m.end()

    while i < n:
        ch = line[i]
        if ch in " \t":
            flush()
            i += 1
        elif ch == "'":
            j = line.find("'", i + 1)
            if j < 0:
                raise ParseError("unexpected EOF while looking for matching `''")
            cur += line[i + 1:j]
            quoted = has = True
            i = j + 1
        elif ch == '"':
            j = i + 1
            buf = ""
            while j < n and line[j] != '"':
                if line[j] == "\\" and j + 1 < n and line[j + 1] in '"\\$`':
                    buf += line[j + 1]
                    j += 2
                elif line[j] == "$":
                    v, k = expand_var(line, j)
                    if v is None:
                        buf += "$"
                        j += 1
                    else:
                        buf += v
                        j = k
                else:
                    buf += line[j]
                    j += 1
            if j >= n:
                raise ParseError("unexpected EOF while looking for matching `\"'")
            cur += buf
            quoted = has = True
            i = j + 1
        elif ch == "\\" and i + 1 < n:
            cur += line[i + 1]
            has = quoted = True
            i += 2
        elif ch == "$":
            v, k = expand_var(line, i)
            if v is None:
                cur += "$"
                has = True
                i += 1
            else:
                cur += v
                has = True
                i = k
        elif ch == "#" and not has:
            break
        elif ch in "|&;<>":
            # fd redirects such as 2> or 2>>
            if ch == ">" and cur in ("2", "1") and has and not quoted:
                fd = cur
                cur, has = "", False
                if line[i:i + 2] == ">>":
                    toks.append(("op", fd + ">>"))
                    i += 2
                else:
                    toks.append(("op", fd + ">"))
                    i += 1
                continue
            flush()
            two = line[i:i + 2]
            if two in ("||", "&&", ">>", "&>", "<<"):
                toks.append(("op", two))
                i += 2
            else:
                toks.append(("op", ch))
                i += 1
        else:
            cur += ch
            has = True
            i += 1
    flush()
    return toks


class Cmd:
    def __init__(self):
        self.words = []
        self.redirs = []     # (op, target)


def parse(toks):
    """-> list of (connector, [Cmd, ...]) ; connector in ';', '&&', '||' relating to the previous pipeline."""
    seq = []
    pipeline = [Cmd()]
    conn = ";"
    i = 0
    while i < len(toks):
        t = toks[i]
        if isinstance(t, Word):
            pipeline[-1].words.append(t)
        else:
            op = t[1]
            if op in ("|",):
                if not pipeline[-1].words:
                    raise ParseError("syntax error near unexpected token `|'")
                pipeline.append(Cmd())
            elif op in (";", "&&", "||"):
                if pipeline[-1].words or len(pipeline) > 1:
                    if not pipeline[-1].words:
                        raise ParseError("syntax error near unexpected token `%s'" % op)
                    seq.append((conn, pipeline))
                elif op != ";":
                    raise ParseError("syntax error near unexpected token `%s'" % op)
                pipeline = [Cmd()]
                conn = op
            elif op == "&":
                raise ParseError("background jobs (&) are not supported in this simulator")
            elif op == "<<":
                raise ParseError("here documents (<<) are not supported in this simulator")
            else:
                i += 1
                if i >= len(toks) or not isinstance(toks[i], Word):
                    raise ParseError("syntax error near unexpected token `newline'")
                pipeline[-1].redirs.append((op, toks[i]))
        i += 1
    if pipeline[-1].words or len(pipeline) > 1:
        if not pipeline[-1].words:
            raise ParseError("syntax error: unexpected end of line")
        seq.append((conn, pipeline))
    elif conn in ("&&", "||"):
        raise ParseError("syntax error: unexpected end of line")
    return seq


# ----------------------------------------------------------------------------- context
class Ctx:
    def __init__(self, shell, argv, stdin, user, tty_out):
        self.sh = shell
        self.fs = shell.fs
        self.argv = argv
        self.stdin = stdin
        self.user = user
        self.tty_out = tty_out
        self.chunks = []     # (stream, text)
        self.name = argv[0]

    def w(self, s):
        self.chunks.append(("o", s))

    def e(self, s):
        self.chunks.append(("e", s))

    def err(self, msg):
        self.e("%s: %s\n" % (self.name, msg))

    def ask(self, prompt):
        # show what the command printed so far before prompting, like a real terminal
        if self.tty_out:
            for _, text in self.chunks:
                self.sh.emit(text if isinstance(text, str) else "")
            self.chunks = []
        return self.sh.ask(prompt)

    @property
    def root(self):
        return self.user == "root"


def getopts(ctx, args, flags="", valued="", longs=(), numeric=None):
    """Tiny getopt. Returns (opts, positional) or (None, None) after printing an error.
    flags/valued are strings of single letters. Long options may be passed as 'name' or 'name='."""
    opts = {}
    pos = []
    i = 0
    only_pos = False
    longmap = {}
    for lo in longs:
        longmap[lo.rstrip("=")] = lo.endswith("=")
    while i < len(args):
        a = args[i]
        if only_pos or a == "-" or not a.startswith("-"):
            pos.append(a)
        elif a == "--":
            only_pos = True
        elif a.startswith("--"):
            name, eq, val = a[2:].partition("=")
            if name not in longmap:
                ctx.err("unrecognized option '--%s'" % name)
                return None, None
            if longmap[name]:
                if not eq:
                    i += 1
                    val = args[i] if i < len(args) else ""
                opts[name] = val
            else:
                opts[name] = True
        else:
            j = 1
            while j < len(a):
                ch = a[j]
                if numeric and ch.isdigit():
                    opts[numeric] = a[j:]
                    break
                if ch in flags:
                    opts[ch] = True
                elif ch in valued:
                    rest = a[j + 1:]
                    if rest:
                        opts[ch] = rest
                    else:
                        i += 1
                        if i >= len(args):
                            ctx.err("option requires an argument -- '%s'" % ch)
                            return None, None
                        opts[ch] = args[i]
                    break
                else:
                    ctx.err("invalid option -- '%s'" % ch)
                    return None, None
                j += 1
        i += 1
    return opts, pos


# ----------------------------------------------------------------------------- shell
class Shell:
    def __init__(self, fs, distro="rocky", emit=None, ask=None):
        self.fs = fs
        self.distro = distro
        self.history = []
        self.emit = emit or (lambda s: None)
        self._ask = ask
        self.last_status = 0
        self.cmdlog = []        # every executed simple command (argv list, effective user) for mission checks
        self.errlog = []
        self.check_ok = {}      # algo -> True once a "<hash>sum -c" run passed

    # -- prompt / user interaction
    def ask(self, prompt):
        if self._ask:
            return self._ask(prompt)
        return "n"

    def prompt(self):
        fs = self.fs
        home = fs.env["HOME"]
        cwd = fs.cwd
        shown = "~" + cwd[len(home):] if cwd == home or cwd.startswith(home + "/") else cwd
        base = posixpath.basename(shown) if shown != "~" and shown != "/" else shown
        return "[%s@%s %s]$ " % (fs.user, fs.host, base)

    def colored_prompt(self):
        fs = self.fs
        home = fs.env["HOME"]
        cwd = fs.cwd
        shown = "~" + cwd[len(home):] if cwd == home or cwd.startswith(home + "/") else cwd
        base = posixpath.basename(shown) if shown not in ("~", "/") else shown
        return (ui.c("[", "gray") + ui.c(fs.user, "bgreen", "bold") + ui.c("@", "gray") + ui.c(fs.host, "bgreen", "bold")
                + " " + ui.c(base, "bblue", "bold") + ui.c("]", "gray") + ui.c("$ ", "byellow", "bold"))

    # -- running
    def run(self, line):
        """Execute a command line. Output goes through self.emit. Returns the exit status."""
        line = line.strip()
        if not line:
            return self.last_status
        if "!!" in line:
            # bash history expansion: !! = the previous command (bash echoes the expanded line)
            if not self.history:
                self.emit("bash: !!: event not found\n")
                return 1
            line = line.replace("!!", self.history[-1])
            self.emit(line + "\n")
        self.history.append(line)
        try:
            toks = tokenize(line, dict(self.fs.env, **{"?": str(self.last_status)}))
            seq = parse(toks)
        except ParseError as ex:
            self.emit("bash: %s\n" % ex)
            self.last_status = 2
            return 2
        status = self.last_status
        for conn, pipeline in seq:
            if conn == "&&" and status != 0:
                continue
            if conn == "||" and status == 0:
                continue
            status = self._pipeline(pipeline)
        self.last_status = status
        return status

    def _expand(self, words):
        argv = []
        for w in words:
            t = w.text
            if not w.quoted and t.startswith("~"):
                t = self.fs.env["HOME"] + t[1:]
            if not w.quoted and any(ch in t for ch in "*?["):
                m = self.fs.glob(t)
                if m:
                    argv.extend(m)
                    continue
            argv.append(t)
        return argv

    def _pipeline(self, pipeline):
        data = None
        status = 0
        n = len(pipeline)
        for idx, c in enumerate(pipeline):
            last = idx == n - 1
            argv = self._expand(c.words)
            user = self.fs.user
            # redirections are performed by the user's shell, even under sudo
            stdin = data
            targets = {}
            failed = False
            for op, tgt in c.redirs:
                path = self._expand([tgt])
                path = path[0] if path else tgt.text
                if op == "<":
                    try:
                        stdin = self.fs.read(path, self.fs.user)
                    except FSError as ex:
                        self.emit("bash: %s: %s\n" % (path, ex.msg))
                        failed = True
                else:
                    key = {">": "1", ">>": "1", "1>": "1", "1>>": "1", "2>": "2", "2>>": "2", "&>": "b"}[op]
                    app = op.endswith(">>")
                    try:
                        node = self.fs.lookup(path)
                        if node is not None and node.kind == "d":
                            raise FSError("Is a directory")
                        if node is None or not app:
                            # truncate/create now, like a real shell
                            self.fs.write(path, "", self.fs.user)
                        elif not self.fs.can(node, "w", self.fs.user):
                            raise FSError("Permission denied")
                        targets[key] = (path, True)
                    except FSError as ex:
                        self.emit("bash: %s: %s\n" % (path, ex.msg))
                        if ex.msg == "Permission denied":
                            note("The redirect (> or >>) is done by YOUR shell, before sudo runs, so it has no root rights. "
                                 "To write a root-owned file use tee: echo ... | sudo tee -a FILE")
                        failed = True
            if failed or not argv:
                data = ""
                status = 1
                continue
            tty_out = last and not any(k in targets for k in ("1", "b"))
            ctx_chunks = self._run_simple(argv, stdin, tty_out)
            status = self.last_status_simple
            out_text = ""
            for stream, text in ctx_chunks:
                dest = None
                if stream == "o":
                    dest = targets.get("1") or targets.get("b")
                    if dest is None and not last:
                        out_text = (out_text + text) if isinstance(text, str) and isinstance(out_text, str) else text
                        continue
                else:
                    dest = targets.get("2") or targets.get("b")
                if dest:
                    try:
                        if isinstance(text, str):
                            self.fs.write(dest[0], text, self.fs.user, append=True)
                        else:
                            self.fs.write(dest[0], text, self.fs.user)
                    except FSError:
                        pass
                else:
                    self.emit(text if isinstance(text, str) else "(binary data not shown)\n")
            data = out_text
        return status

    def _run_simple(self, argv, stdin, tty_out):
        user = self.fs.user
        # sudo prefix
        if argv[0] == "sudo":
            args = argv[1:]
            while args and args[0].startswith("-") and args[0] in ("-E", "-n", "-H"):
                args = args[1:]
            if not args:
                self.last_status_simple = 1
                return [("e", "usage: sudo command\n")]
            if args[0] in ("-i", "-s", "su"):
                self.last_status_simple = 1
                return [("e", "sudo: interactive root shells are not available in the simulator. Prefix each command with sudo.\n")]
            argv = args
            user = "root"
        name = argv[0]
        self.cmdlog.append((list(argv), user))
        fn = REGISTRY.get(name)
        if fn is None or not self._available(name):
            self.last_status_simple = 127
            self.errlog.append(argv)
            return [("e", "bash: %s: command not found\n" % name)]
        ctx = Ctx(self, argv, stdin, user, tty_out)
        try:
            st = fn(ctx)
        except FSError as ex:
            ctx.e("%s: %s\n" % (name, ex.msg))
            st = 1
        except KeyboardInterrupt:
            ctx.e("^C\n")
            st = 130
        except Exception as ex:  # a simulator bug must never crash the game
            ctx.e("bash: %s: simulator error (%s: %s)\n" % (name, type(ex).__name__, ex))
            st = 70
        self.last_status_simple = 0 if st is None else st
        return ctx.chunks

    def _available(self, name):
        rpm_only = {"rpm", "yum", "dnf", "createrepo", "createrepo_c"}
        deb_only = {"dpkg", "apt", "apt-get"}
        if name in rpm_only:
            return self.distro == "rocky"
        if name in deb_only:
            return self.distro == "debian"
        return True

    def exec_args(self, argv, stdin=None, user=None):
        """Run a command programmatically (used by xargs). Returns (status, chunks)."""
        user = user or self.fs.user
        fn = REGISTRY.get(argv[0])
        if fn is None or not self._available(argv[0]):
            return 127, [("e", "xargs: %s: No such file or directory\n" % argv[0])]
        ctx = Ctx(self, argv, stdin, user, False)
        try:
            st = fn(ctx)
        except FSError as ex:
            ctx.e("%s: %s\n" % (argv[0], ex.msg))
            st = 1
        return (0 if st is None else st), ctx.chunks

    # -- tab completion
    def complete(self, buf, pos):
        before = buf[:pos]
        words = before.split(" ")
        word = words[-1]
        first = len([w for w in words[:-1] if w and w != "sudo"]) == 0 and not any(x in before for x in "|;&")
        if first and "/" not in word:
            names = sorted(n for n in REGISTRY if n.startswith(word) and self._available(n) and not n.startswith("mkfs."))
            return names
        head, _, tail = word.rpartition("/")
        base = (head + "/") if _ else ""
        d = head if head else ("/" if word.startswith("/") else ".")
        try:
            names = self.fs.listdir(d)
        except FSError:
            return []
        res = []
        for nme in names:
            if nme.startswith(tail) and (not nme.startswith(".") or tail.startswith(".")):
                full = base + nme
                if self.fs.isdir((head or ".") + "/" + nme if head else nme):
                    full += "/"
                res.append(full)
        return res


# ----------------------------------------------------------------------------- helpers
def fmt_time(ts):
    return time.strftime("%b %e %H:%M", time.gmtime(ts))


def fmt_full_time(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S.000000000 +0000", time.gmtime(ts))


def human(n):
    if n < 1024:
        return str(n)
    v = n / 1024.0
    for unit in "KMG":
        if v < 1024 or unit == "G":
            return "%.1f%s" % (math.ceil(v * 10) / 10.0, unit) if v < 10 else "%d%s" % (math.ceil(v), unit)
        v /= 1024.0


def text_of(ctx, node_data):
    return node_data if isinstance(node_data, str) else "<binary data>\n"


def read_inputs(ctx, files, name=None):
    """Yield (display_name, text) for files, or stdin when no files. Prints errors and records failure."""
    results = []
    bad = False
    sin = ctx.stdin if isinstance(ctx.stdin, str) else ("<binary data>\n" if ctx.stdin is not None else "")
    if not files:
        results.append((None, sin))
        return results, bad
    for f in files:
        if f == "-":
            results.append((f, sin))
            continue
        try:
            node = ctx.fs.lookup(f)
            if node is None:
                ctx.err("%s: No such file or directory" % f)
                bad = True
                continue
            data = ctx.fs.read(f, ctx.user)
            results.append((f, data if isinstance(data, str) else "<binary data>\n"))
        except FSError as ex:
            ctx.err("%s: %s" % (f, ex.msg))
            bad = True
    return results, bad


def lines_of(text):
    if text == "":
        return []
    parts = text.split("\n")
    if parts[-1] == "":
        parts.pop()
    return parts


def join_lines(lines):
    return "".join(l + "\n" for l in lines)


# ----------------------------------------------------------------------------- navigation
@cmd("pwd", help=("print working directory", "pwd", []))
def c_pwd(ctx):
    ctx.w(ctx.fs.cwd + "\n")


@cmd("cd", help=("change directory", "cd [dir]", [("~ or no argument", "home directory"), ("..", "parent directory")]))
def c_cd(ctx):
    args = [a for a in ctx.argv[1:] if not a.startswith("-") or a == "-"]
    target = args[0] if args else "~"
    fs = ctx.fs
    if target == "-":
        target = fs.env.get("OLDPWD", fs.cwd)
    try:
        node = fs.lookup(target)
    except FSError as ex:
        ctx.err("%s: %s" % (target, ex.msg))
        return 1
    if node is None:
        ctx.err("%s: No such file or directory" % target)
        return 1
    if node.kind != "d":
        ctx.err("%s: Not a directory" % target)
        return 1
    if not fs.can(node, "x", ctx.fs.user):
        ctx.err("%s: Permission denied" % target)
        return 1
    fs.env["OLDPWD"] = fs.cwd
    p = fs.abspath(target)
    # resolve symlinks for the physical path, like bash -P does not; keep logical path
    fs.cwd = p
    return 0


def ls_color(node, name, tty):
    if not tty:
        return name
    if node.kind == "d":
        return ui.c(name, "bblue", "bold")
    if node.kind == "l":
        return ui.c(name, "bcyan", "bold")
    if node.kind == "b":
        return ui.c(name, "byellow")
    if isinstance(node.data, (Archive, Comp)):
        return ui.c(name, "bred")
    if node.mode & 0o111:
        return ui.c(name, "bgreen", "bold")
    return name


@cmd("ls", help=("list directory contents", "ls [OPTION]... [FILE]...", [
    ("-a", "do not ignore entries starting with ."), ("-l", "use a long listing format"),
    ("-h", "with -l, print human readable sizes"), ("-R", "list subdirectories recursively"),
    ("-S", "sort by file size, largest first"), ("-t", "sort by modification time, newest first"),
    ("-d", "list directories themselves, not their contents"), ("-i", "print the inode number of each file"),
    ("-r", "reverse order while sorting")]))
def c_ls(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="alhRSdirt1FA")
    if opts is None:
        return 2
    fs = ctx.fs
    args = args or ["."]
    status = 0
    long_ = "l" in opts
    entries_for = []
    files = []
    for a in args:
        try:
            lnode = fs.lookup(a, follow=False)
            node = lnode
            if lnode is not None and lnode.kind == "l" and "l" not in opts and "d" not in opts:
                tgt = fs.lookup(a)
                if tgt is not None and tgt.kind == "d":
                    node = tgt
        except FSError as ex:
            ctx.err("cannot access '%s': %s" % (a, ex.msg))
            status = 2
            continue
        if node is None:
            ctx.err("cannot access '%s': No such file or directory" % a)
            status = 2
            continue
        if node.kind == "d" and "d" not in opts:
            entries_for.append((a, node))
        else:
            files.append((a, lnode or node))

    def order(items):
        # items: list of (name, node)
        items = sorted(items, key=lambda x: x[0].lower() if False else x[0])
        if "S" in opts:
            items = sorted(items, key=lambda x: -x[1].size())
        elif "t" in opts:
            items = sorted(items, key=lambda x: -x[1].mtime)
        if "r" in opts:
            items = list(reversed(items))
        return items

    def fmt_block(items, show_total):
        if not items:
            return
        if long_:
            rows = []
            total = 0
            for nm, nd in items:
                total += max(1, int(math.ceil(nd.size() / 4096.0))) * 4 if nd.kind != "l" else 0
                size = human(nd.size()) if "h" in opts else str(nd.size())
                name = ls_color(nd, nm, ctx.tty_out)
                if nd.kind == "l":
                    name += " -> " + nd.target
                row = [mode_str(nd) + ".", str(nd.nlink), nd.owner, nd.group, size, fmt_time(nd.mtime), name]
                if "i" in opts:
                    row.insert(0, str(nd.ino))
                rows.append(row)
            if show_total:
                ctx.w("total %d\n" % total)
            ncol = len(rows[0])
            widths = [max(len(r[k]) for r in rows) for k in range(ncol - 1)]
            for r in rows:
                cells = []
                for k in range(ncol - 1):
                    if k == (1 if "i" not in opts else 2) or (k == (4 if "i" not in opts else 5)) or (k == 0 and "i" in opts):
                        cells.append(r[k].rjust(widths[k]))
                    else:
                        cells.append(r[k].ljust(widths[k]))
                ctx.w(" ".join(cells) + " " + r[-1] + "\n")
        else:
            names = []
            for nm, nd in items:
                shown = ls_color(nd, nm, ctx.tty_out)
                if "F" in opts:
                    shown += {"d": "/", "l": "@"}.get(nd.kind, "*" if nd.mode & 0o111 else "")
                if "i" in opts:
                    shown = "%d %s" % (nd.ino, shown)
                names.append((shown, ui.vlen(shown)))
            if not ctx.tty_out or "1" in opts:
                for s, _ in names:
                    ctx.w(s + "\n")
            else:
                width = 80
                colw = max(l for _, l in names) + 2
                per = max(1, width // colw)
                rows_n = int(math.ceil(len(names) / float(per)))
                for r in range(rows_n):
                    line = ""
                    for k in range(per):
                        idx = r + k * rows_n
                        if idx < len(names):
                            s, l = names[idx]
                            line += s + " " * (colw - l)
                    ctx.w(line.rstrip() + "\n")

    if files:
        fmt_block(order(files), False)
    multi = len(args) > 1 or "R" in opts
    first = not files
    for path, node in sorted(entries_for, key=lambda x: x[0]):
        def do_dir(p, nd, header):
            if header:
                if not first_flag[0]:
                    ctx.w("\n")
                ctx.w(p + ":\n")
            first_flag[0] = False
            if not fs.can(nd, "r", ctx.user):
                ctx.err("cannot open directory '%s': Permission denied" % p)
                return
            items = []
            if "a" in opts:
                items.append((".", nd))
                parent = fs.lookup(posixpath.dirname(fs.abspath(p)) or "/") or nd
                items.append(("..", parent))
            for nm in sorted(nd.entries):
                if nm.startswith(".") and "a" not in opts and "A" not in opts:
                    continue
                items.append((nm, fs.inodes[nd.entries[nm]]))
            fmt_block(order(items), long_)
            if "R" in opts:
                for nm, ch in order([(n, i) for n, i in items if n not in (".", "..")]):
                    if ch.kind == "d":
                        do_dir(p.rstrip("/") + "/" + nm, ch, True)
        first_flag = [first]
        do_dir(path, node, multi)
        first = False
    return status


@cmd("tree", help=("list contents of directories in a tree-like format", "tree [dir]", []))
def c_tree(ctx):
    args = ctx.argv[1:] or ["."]
    fs = ctx.fs
    nd = nf = 0

    def rec(path, prefix):
        nonlocal nd, nf
        names = [n for n in fs.listdir(path) if not n.startswith(".")]
        for i, nm in enumerate(names):
            last = i == len(names) - 1
            p = path.rstrip("/") + "/" + nm
            node = fs.lookup(p, follow=False)
            label = nm + (" -> " + node.target if node.kind == "l" else "")
            ctx.w(prefix + ("└── " if last else "├── ") + (ui.c(label, "bblue") if node.kind == "d" and ctx.tty_out else label) + "\n")
            if node.kind == "d":
                nd += 1
                rec(p, prefix + ("    " if last else "│   "))
            else:
                nf += 1

    for a in args:
        if not fs.isdir(a):
            ctx.w("%s [error opening dir]\n" % a)
            continue
        ctx.w(a + "\n")
        rec(a, "")
    ctx.w("\n%d director%s, %d file%s\n" % (nd, "y" if nd == 1 else "ies", nf, "" if nf == 1 else "s"))


@cmd("stat", help=("display file status", "stat FILE...", []))
def c_stat(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="L")
    if opts is None:
        return 1
    if not args:
        ctx.err("missing operand")
        return 1
    st = 0
    for a in args:
        try:
            n = ctx.fs.lookup(a, follow=False)
        except FSError as ex:
            ctx.err("cannot statx '%s': %s" % (a, ex.msg))
            st = 1
            continue
        if n is None:
            ctx.err("cannot statx '%s': No such file or directory" % a)
            st = 1
            continue
        kind = {"f": "regular file" if n.size() else "regular empty file", "d": "directory", "l": "symbolic link", "b": "block special file"}[n.kind]
        uid = 0 if n.owner == "root" else 1000
        ctx.w("  File: %s%s\n" % (a, " -> " + n.target if n.kind == "l" else ""))
        ctx.w("  Size: %-10d\tBlocks: %-10d IO Block: 4096   %s\n" % (n.size(), 0 if n.kind == "l" else max(0, math.ceil(n.size() / 512.0)), kind))
        ctx.w("Device: fd00h/64768d\tInode: %-11d Links: %d\n" % (n.ino, n.nlink))
        ctx.w("Access: (%04o/%s)  Uid: ( %4d/ %7s)   Gid: ( %4d/ %7s)\n" % (n.mode & 0o7777, mode_str(n), uid, n.owner, uid, n.group))
        ctx.w("Access: %s\nModify: %s\nChange: %s\n Birth: -\n" % (fmt_full_time(n.atime), fmt_full_time(n.mtime), fmt_full_time(n.ctime)))
    return st


@cmd("whoami", help=("print the effective user name", "whoami", []))
def c_whoami(ctx):
    ctx.w(ctx.user + "\n")


@cmd("id")
def c_id(ctx):
    if ctx.user == "root":
        ctx.w("uid=0(root) gid=0(root) groups=0(root)\n")
    else:
        ctx.w("uid=1000(%s) gid=1000(%s) groups=1000(%s),10(wheel)\n" % (ctx.user, ctx.user, ctx.user))


@cmd("hostname", help=("show the system's host name", "hostname", []))
def c_hostname(ctx):
    ctx.w(ctx.fs.host + "\n")


@cmd("date")
def c_date(ctx):
    ctx.w(time.strftime("%a %b %e %H:%M:%S UTC %Y", time.gmtime(ctx.fs.clock)) + "\n")


@cmd("clear")
def c_clear(ctx):
    if ctx.tty_out and ui.COLOR:
        ctx.w("\x1b[2J\x1b[H")


@cmd("history")
def c_history(ctx):
    for i, h in enumerate(ctx.sh.history, 1):
        ctx.w("%5d  %s\n" % (i, h))


@cmd("man", help=("display the manual page", "man COMMAND", []))
def c_man(ctx):
    if len(ctx.argv) < 2:
        ctx.w("What manual page do you want?\n")
        return 1
    name = ctx.argv[1]
    h = HELP.get(name)
    if not h:
        ctx.e("No manual entry for %s\n" % name)
        return 16
    one, syn, options = h
    ctx.w("%s(1)                      User Commands\n\nNAME\n       %s - %s\n\nSYNOPSIS\n       %s\n" % (name.upper(), name, one, syn))
    if options:
        ctx.w("\nOPTIONS\n")
        for o, d in options:
            ctx.w("       %-12s %s\n" % (o, d))
    ctx.w("\n(simulated page: the real one has more. Press q in a real terminal to quit.)\n")


# ----------------------------------------------------------------------------- creating / removing
@cmd("touch", help=("change file timestamps, or create an empty file", "touch FILE...", []))
def c_touch(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="ac")
    if opts is None:
        return 1
    if not args:
        ctx.err("missing file operand")
        return 1
    st = 0
    for a in args:
        try:
            ctx.fs.touch(a, ctx.user)
        except FSError as ex:
            ctx.err("cannot touch '%s': %s" % (a, ex.msg))
            st = 1
    return st


@cmd("mkdir", help=("make directories", "mkdir [-p] DIRECTORY...", [("-p", "make parent directories as needed")]))
def c_mkdir(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="pv")
    if opts is None:
        return 1
    if not args:
        ctx.err("missing operand")
        return 1
    st = 0
    for a in args:
        try:
            ctx.fs.mkdir(a, ctx.user, parents="p" in opts)
        except FSError as ex:
            ctx.err("cannot create directory '%s': %s" % (a, ex.msg))
            st = 1
    return st


@cmd("rmdir", help=("remove empty directories", "rmdir DIRECTORY...", []))
def c_rmdir(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="p")
    if opts is None:
        return 1
    if not args:
        ctx.err("missing operand")
        return 1
    st = 0
    for a in args:
        try:
            ctx.fs.rmdir(a, ctx.user)
        except FSError as ex:
            ctx.err("failed to remove '%s': %s" % (a, ex.msg))
            st = 1
    return st


@cmd("rm", help=("remove files or directories", "rm [OPTION]... FILE...", [
    ("-f", "ignore nonexistent files, never prompt"), ("-i", "prompt before every removal"),
    ("-r, -R", "remove directories and their contents recursively")]))
def c_rm(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="firRv")
    if opts is None:
        return 1
    force = "f" in opts
    rec = "r" in opts or "R" in opts
    if not args:
        if not force:
            ctx.err("missing operand")
            return 1
        return 0
    st = 0
    fs = ctx.fs
    for a in args:
        try:
            node = fs.lookup(a, follow=False)
        except FSError as ex:
            node = None
        if node is None:
            if not force:
                ctx.err("cannot remove '%s': No such file or directory" % a)
                st = 1
            continue
        if node.kind == "d" and not rec:
            ctx.err("cannot remove '%s': Is a directory" % a)
            st = 1
            continue
        if "i" in opts and not force:
            what = "directory" if node.kind == "d" else ("symbolic link" if node.kind == "l" else ("regular empty file" if node.size() == 0 else "regular file"))
            ans = ctx.ask("rm: remove %s '%s'? " % (what, a))
            if not ans or ans.strip().lower()[:1] != "y":
                continue
        try:
            if node.kind == "d":
                fs.rm_tree(a, ctx.user)
            else:
                fs.unlink(a, ctx.user)
            if "v" in opts:
                ctx.w("removed '%s'\n" % a)
        except FSError as ex:
            ctx.err("cannot remove '%s': %s" % (a, ex.msg))
            st = 1
    return st


@cmd("cp", help=("copy files and directories", "cp [OPTION]... SOURCE... DEST", [("-R, -r", "copy directories recursively (required for directories)")]))
def c_cp(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="rRivpa")
    if opts is None:
        return 1
    if len(args) < 2:
        ctx.err("missing destination file operand after '%s'" % (args[0] if args else ""))
        return 1
    *srcs, dst = args
    fs = ctx.fs
    rec = "r" in opts or "R" in opts or "a" in opts
    dnode = fs.lookup(dst) if fs.exists(dst) else None
    if len(srcs) > 1 and not (dnode and dnode.kind == "d"):
        ctx.err("target '%s' is not a directory" % dst)
        return 1
    st = 0
    for s in srcs:
        try:
            node = fs.lookup(s)
            if node is None:
                ctx.err("cannot stat '%s': No such file or directory" % s)
                st = 1
                continue
            if node.kind == "d" and not rec:
                ctx.err("-r not specified; omitting directory '%s'" % s)
                st = 1
                continue
            fs.copy(s, dst, ctx.user, recursive=rec)
            if "v" in opts:
                ctx.w("'%s' -> '%s'\n" % (s, dst))
        except FSError as ex:
            ctx.err("cannot create regular file '%s': %s" % (dst, ex.msg))
            st = 1
    return st


@cmd("mv", help=("move (rename) files", "mv [OPTION]... SOURCE... DEST", []))
def c_mv(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="ivf")
    if opts is None:
        return 1
    if len(args) < 2:
        ctx.err("missing destination file operand after '%s'" % (args[0] if args else ""))
        return 1
    *srcs, dst = args
    fs = ctx.fs
    dnode = fs.lookup(dst) if fs.exists(dst) else None
    if len(srcs) > 1 and not (dnode and dnode.kind == "d"):
        ctx.err("target '%s' is not a directory" % dst)
        return 1
    st = 0
    for s in srcs:
        try:
            fs.rename(s, dst, ctx.user)
            if "v" in opts:
                ctx.w("renamed '%s' -> '%s'\n" % (s, dst))
        except FSError as ex:
            ctx.err("cannot move '%s' to '%s': %s" % (s, dst, ex.msg))
            st = 1
    return st


@cmd("ln", help=("make links between files", "ln [-s] TARGET LINK_NAME", [("-s", "make symbolic links instead of hard links")]))
def c_ln(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="sfv")
    if opts is None:
        return 1
    if len(args) < 2:
        ctx.err("missing file operand" if not args else "missing destination file operand after '%s'" % args[0])
        return 1
    target, link = args[0], args[1]
    fs = ctx.fs
    if fs.isdir(link):
        link = link.rstrip("/") + "/" + posixpath.basename(target.rstrip("/"))
    try:
        if "f" in opts and fs.exists(link, follow=False):
            fs.unlink(link, ctx.user)
        if "s" in opts:
            fs.symlink(target, link, ctx.user)
        else:
            if fs.lookup(target) is None:
                ctx.err("failed to access '%s': No such file or directory" % target)
                return 1
            fs.link(target, link, ctx.user)
    except FSError as ex:
        if "hard link" in ex.msg:
            ctx.err("%s: %s" % (target, ex.msg))
        else:
            ctx.err("failed to create %s link '%s': %s" % ("symbolic" if "s" in opts else "hard", link, ex.msg))
        return 1
    return 0


# ----------------------------------------------------------------------------- viewing
def _cat_like(ctx, files, number=False):
    res, bad = read_inputs(ctx, files)
    n = 0
    for _, text in res:
        if number:
            for l in lines_of(text):
                n += 1
                ctx.w("%6d\t%s\n" % (n, l))
        else:
            ctx.w(text)
    return 1 if bad else 0


@cmd("cat", help=("concatenate files and print on the standard output", "cat [FILE]...", [("-n", "number all output lines")]))
def c_cat(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="nAEv")
    if opts is None:
        return 1
    return _cat_like(ctx, args, "n" in opts)


@cmd("less", "more", help=("page through a file", "less FILE", []))
def c_less(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="NSXiMFER")
    if opts is None:
        return 1
    st = _cat_like(ctx, args)
    ctx.w(ui.c("(END) in a real terminal you would scroll with the arrow keys / space and press q to quit\n", "gray") if ctx.tty_out else "")
    return st


@cmd("head", help=("output the first part of files", "head [-n N] [FILE]...", [("-n N", "print the first N lines instead of 10")]))
def c_head(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="q", valued="nc", numeric="n")
    if opts is None:
        return 1
    n = int(opts.get("n", 10))
    res, bad = read_inputs(ctx, args)
    for k, (name, text) in enumerate(res):
        if len(res) > 1:
            ctx.w(("\n" if k else "") + "==> %s <==\n" % name)
        ctx.w(join_lines(lines_of(text)[:n]))
    return 1 if bad else 0


@cmd("tail", help=("output the last part of files", "tail [-n N] [FILE]...", [("-n N", "output the last N lines instead of 10")]))
def c_tail(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="qf", valued="nc", numeric="n")
    if opts is None:
        return 1
    spec = str(opts.get("n", 10))
    res, bad = read_inputs(ctx, args)
    for k, (name, text) in enumerate(res):
        if len(res) > 1:
            ctx.w(("\n" if k else "") + "==> %s <==\n" % name)
        ls = lines_of(text)
        if spec.startswith("+"):
            ctx.w(join_lines(ls[int(spec[1:]) - 1:]))
        else:
            n = int(spec)
            ctx.w(join_lines(ls[-n:] if n else []))
    return 1 if bad else 0


@cmd("echo", help=("display a line of text", "echo [-n] [STRING]...", []))
def c_echo(ctx):
    args = ctx.argv[1:]
    nl = True
    esc = False
    while args and args[0] in ("-n", "-e", "-ne", "-en", "-E"):
        if "n" in args[0]:
            nl = False
        if "e" in args[0]:
            esc = True
        args = args[1:]
    s = " ".join(args)
    if esc:
        s = s.replace("\\n", "\n").replace("\\t", "\t")
    ctx.w(s + ("\n" if nl else ""))


@cmd("printf", help=("format and print data", "printf FORMAT [ARGUMENT]...", []))
def c_printf(ctx):
    if len(ctx.argv) < 2:
        ctx.err("usage: printf format [arguments]")
        return 1
    fmt = ctx.argv[1].replace("\\n", "\n").replace("\\t", "\t")
    args = ctx.argv[2:]
    out_ = ""
    ai = 0

    def sub(m):
        nonlocal ai
        v = args[ai] if ai < len(args) else ""
        ai += 1
        return str(int(v) if m.group(1) == "d" and v.lstrip("-").isdigit() else v)
    out_ = re.sub(r"%([sd])", sub, fmt)
    ctx.w(out_)


@cmd("tee", help=("read from standard input and write to standard output and files", "tee [-a] FILE...", [("-a", "append to the files, do not overwrite")]))
def c_tee(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="ai")
    if opts is None:
        return 1
    text = ctx.stdin or ""
    ctx.w(text)
    st = 0
    for a in args:
        try:
            ctx.fs.write(a, text, ctx.user, append="a" in opts)
        except FSError as ex:
            ctx.err("%s: %s" % (a, ex.msg))
            st = 1
    return st


@cmd("xargs", help=("build and execute command lines from standard input", "xargs [command [initial-arguments]]", []))
def c_xargs(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="0tr", valued="nI")
    if opts is None:
        return 1
    base = args or ["echo"]
    toks = (ctx.stdin or "").split()
    if not toks:
        return 0
    batches = [toks]
    if "n" in opts:
        k = int(opts["n"])
        batches = [toks[i:i + k] for i in range(0, len(toks), k)]
    st = 0
    for b in batches:
        if "I" in opts:
            for t in b:
                argv = [a.replace(opts["I"], t) for a in base]
                s, ch = ctx.sh.exec_args(argv, None, ctx.user)
                ctx.chunks.extend(ch)
                st = st or s
        else:
            s, ch = ctx.sh.exec_args(base + b, None, ctx.user)
            ctx.chunks.extend(ch)
            st = st or s
    return st


# ----------------------------------------------------------------------------- text processing
@cmd("wc", help=("print newline, word, and byte counts for each file", "wc [OPTION]... [FILE]...", [
    ("-l", "print the newline counts"), ("-w", "print the word counts"), ("-c", "print the byte counts")]))
def c_wc(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="lwcm")
    if opts is None:
        return 1
    res, bad = read_inputs(ctx, args)
    show = [k for k in ("l", "w", "c") if k in opts or (k == "c" and "m" in opts)]
    if not show:
        show = ["l", "w", "c"]
    rows = []
    for name, text in res:
        vals = {"l": text.count("\n"), "w": len(text.split()), "c": len(text.encode())}
        rows.append((name, [vals[k] for k in show]))
    if len(rows) > 1:
        rows.append(("total", [sum(r[1][i] for r in rows) for i in range(len(show))]))
    width = max([len(str(v)) for r in rows for v in r[1]] + [1]) if (len(show) > 1 or len(rows) > 1 or args) else 0
    for name, vals in rows:
        cells = " ".join(str(v).rjust(width) for v in vals)
        ctx.w(cells + ((" " + name) if name else "") + "\n")
    return 1 if bad else 0


def _sortkey(opts):
    k = None
    if "k" in opts:
        m = re.match(r"(\d+)", opts["k"])
        k = int(m.group(1)) if m else None
    sep = opts.get("t")
    num = "n" in opts

    def key(line):
        field = line
        if k:
            parts = line.split(sep) if sep else line.split()
            field = parts[k - 1] if len(parts) >= k else ""
        if num:
            m = re.match(r"\s*(-?\d+(\.\d+)?)", field)
            return (0, float(m.group(1))) if m else (0, 0.0)
        return (0, field)
    return key


@cmd("sort", help=("sort lines of text files", "sort [OPTION]... [FILE]...", [
    ("-n", "compare according to string numerical value"), ("-r", "reverse the result"),
    ("-k N", "sort via a key (field number)"), ("-t SEP", "use SEP as the field separator"), ("-u", "output only unique lines")]))
def c_sort(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="nruf", valued="kt")
    if opts is None:
        return 1
    res, bad = read_inputs(ctx, args)
    lines = []
    for _, t in res:
        lines.extend(lines_of(t))
    lines.sort(key=_sortkey(opts), reverse="r" in opts)
    if "u" in opts:
        seen, uniq = set(), []
        for l in lines:
            if l not in seen:
                seen.add(l)
                uniq.append(l)
        lines = uniq
    ctx.w(join_lines(lines))
    return 1 if bad else 0


@cmd("uniq", help=("report or omit repeated lines", "uniq [-c] [FILE]", []))
def c_uniq(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="cdu")
    if opts is None:
        return 1
    res, bad = read_inputs(ctx, args[:1])
    prev, cnt = None, 0
    outl = []
    for l in lines_of(res[0][1]) if res else []:
        if l == prev:
            cnt += 1
        else:
            if prev is not None:
                outl.append((cnt, prev))
            prev, cnt = l, 1
    if prev is not None:
        outl.append((cnt, prev))
    for c_, l in outl:
        ctx.w(("%7d %s\n" % (c_, l)) if "c" in opts else l + "\n")
    return 1 if bad else 0


def _ranges(spec):
    out_ = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out_.append((int(a) if a else 1, int(b) if b else 10 ** 9))
        elif part:
            out_.append((int(part), int(part)))
    return out_


@cmd("cut", help=("remove sections from each line of files", "cut OPTION... [FILE]...", [
    ("-c LIST", "select only these characters"), ("-d DELIM", "use DELIM instead of TAB for field delimiter"),
    ("-f LIST", "select only these fields"), ("-s", "do not print lines not containing delimiters")]))
def c_cut(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="s", valued="cdf")
    if opts is None:
        return 1
    if "c" not in opts and "f" not in opts:
        ctx.e("cut: you must specify a list of bytes, characters, or fields\n")
        return 1
    res, bad = read_inputs(ctx, args)
    delim = opts.get("d", "\t")
    for _, text in res:
        for l in lines_of(text):
            if "c" in opts:
                rng = _ranges(opts["c"])
                ctx.w("".join(ch for i, ch in enumerate(l, 1) if any(a <= i <= b for a, b in rng)) + "\n")
            else:
                if delim not in l:
                    if "s" not in opts:
                        ctx.w(l + "\n")
                    continue
                parts = l.split(delim)
                rng = _ranges(opts["f"])
                ctx.w(delim.join(p for i, p in enumerate(parts, 1) if any(a <= i <= b for a, b in rng)) + "\n")
    return 1 if bad else 0


def _tr_set(s):
    out_ = []
    i = 0
    s = s.replace("[:upper:]", "A-Z").replace("[:lower:]", "a-z").replace("[:digit:]", "0-9").replace("\\n", "\n")
    while i < len(s):
        if i + 2 < len(s) and s[i + 1] == "-":
            out_.extend(chr(x) for x in range(ord(s[i]), ord(s[i + 2]) + 1))
            i += 3
        else:
            out_.append(s[i])
            i += 1
    return out_


@cmd("tr", help=("translate or delete characters", "tr SET1 SET2", [("-d", "delete characters in SET1")]))
def c_tr(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="ds")
    if opts is None:
        return 1
    text = ctx.stdin if ctx.stdin is not None else ""
    if "d" in opts:
        if not args:
            ctx.err("missing operand")
            return 1
        rm = set(_tr_set(args[0]))
        ctx.w("".join(ch for ch in text if ch not in rm))
        return 0
    if len(args) < 2:
        ctx.err("missing operand after '%s'" % (args[0] if args else ""))
        ctx.e("Two strings must be given when translating.\n")
        return 1
    a, b = _tr_set(args[0]), _tr_set(args[1])
    if len(b) < len(a):
        b = b + [b[-1]] * (len(a) - len(b))
    m = dict(zip(a, b))
    ctx.w("".join(m.get(ch, ch) for ch in text))


def _regex(pat, flags=0):
    try:
        return re.compile(pat, flags)
    except re.error:
        return re.compile(re.escape(pat), flags)


@cmd("grep", help=("print lines that match patterns", "grep [OPTION]... PATTERN [FILE]...", [
    ("-i", "ignore case distinctions"), ("-c", "print only a count of matching lines"), ("-v", "select non-matching lines"),
    ("-n", "print line number with output lines"), ("-r", "read all files under each directory, recursively")]))
def c_grep(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="icvnrEwlFH", valued="e")
    if opts is None:
        return 2
    if "e" in opts:
        args = [opts["e"]] + args
    if not args:
        ctx.e("Usage: grep [OPTION]... PATTERNS [FILE]...\n")
        return 2
    pat, files = args[0], args[1:]
    rx = _regex(re.escape(pat) if "F" in opts else pat, re.I if "i" in opts else 0)
    if "w" in opts:
        rx = _regex(r"\b(?:%s)\b" % pat, re.I if "i" in opts else 0)
    fs = ctx.fs
    targets = []
    if "r" in opts:
        for f in files or ["."]:
            if fs.isdir(f):
                for p in fs.walk(f):
                    n = fs.lookup(p, follow=False)
                    if n.kind == "f":
                        targets.append(p)
            else:
                targets.append(f)
        files = targets
    res, bad = read_inputs(ctx, files)
    multi = len(res) > 1 or "r" in opts
    found = False
    for name, text in res:
        cnt = 0
        for i, l in enumerate(lines_of(text), 1):
            hit = bool(rx.search(l))
            if hit != ("v" in opts):
                cnt += 1
                found = True
                if "c" not in opts and "l" not in opts:
                    pre = ""
                    if multi and name is not None:
                        pre += name + ":"
                    if "n" in opts:
                        pre += "%d:" % i
                    shown = l
                    if ctx.tty_out and ui.COLOR and "v" not in opts:
                        shown = rx.sub(lambda m: ui.c(m.group(0), "bred", "bold"), l)
                    ctx.w(pre + shown + "\n")
        if "c" in opts:
            ctx.w(("%s:" % name if multi and name else "") + "%d\n" % cnt)
        elif "l" in opts and cnt:
            ctx.w(name + "\n")
    if bad:
        return 2
    return 0 if found else 1


def _sed_script(script):
    cmds = []
    for part in re.split(r";(?![^/]*/[^/]*$)", script) if False else _split_sed(script):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+|/.*?/)?\s*([dp])$", part)
        if m:
            cmds.append(("dp", m.group(1), m.group(2)))
            continue
        m = re.match(r"^(\d+|/.*?/)?\s*s(.)(.*?)(?<!\\)\2(.*?)(?<!\\)\2([gI]*)$", part)
        if m:
            cmds.append(("s", m.group(1), m.group(3), m.group(4), m.group(5)))
            continue
        raise ValueError(part)
    return cmds


def _split_sed(s):
    parts, cur, delim, count = [], "", None, 0
    for ch in s:
        if ch == ";" and count % 3 == 0 and delim is None:
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    parts.append(cur)
    return parts


@cmd("sed", help=("stream editor for filtering and transforming text", "sed [OPTION]... {script} [FILE]...", [
    ("s/old/new/", "substitute the first match on each line"), ("s/old/new/g", "substitute every match"),
    ("d", "delete lines"), ("-n ... p", "print only the lines that match"), ("-i", "edit the file in place")]))
def c_sed(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="niE", valued="e", longs=("in-place",))
    if opts is None:
        return 1
    script = opts.get("e")
    if script is None:
        if not args:
            ctx.e("Usage: sed [OPTION]... {script-only-if-no-other-script} [input-file]...\n")
            return 1
        script, args = args[0], args[1:]
    try:
        prog = _sed_script(script)
    except ValueError as ex:
        ctx.e("sed: -e expression #1, char 1: unknown command: `%s'\n" % ex)
        return 1
    inplace = "i" in opts or "in-place" in opts
    quiet = "n" in opts
    res, bad = read_inputs(ctx, args)
    for name, text in res:
        outl = []
        ls = lines_of(text)
        for ln, l in enumerate(ls, 1):
            printed = False
            deleted = False
            cur = l
            for c_ in prog:
                addr = c_[1]
                ok = True
                if addr:
                    if addr.isdigit():
                        ok = ln == int(addr)
                    else:
                        ok = bool(_regex(addr[1:-1]).search(cur))
                if not ok:
                    continue
                if c_[0] == "dp":
                    if c_[2] == "d":
                        deleted = True
                        break
                    outl.append(cur)
                    printed = True
                else:
                    flags = c_[4]
                    rx = _regex(c_[2], re.I if "I" in flags else 0)
                    repl = c_[3].replace("&", r"\g<0>")
                    cur = rx.sub(repl, cur, count=0 if "g" in flags else 1)
            if deleted:
                continue
            if not quiet:
                outl.append(cur)
        text_out = join_lines(outl)
        if inplace and name:
            try:
                ctx.fs.write(name, text_out, ctx.user)
            except FSError as ex:
                ctx.err("couldn't open temporary file %s: %s" % (name, ex.msg))
                return 4
        else:
            ctx.w(text_out)
    return 1 if bad else 0


def _awk_items(body, sep):
    items = []
    for part in re.findall(r'"[^"]*"|[^,\s][^,]*', body):
        part = part.strip()
        if part:
            items.append(part)
    return items


@cmd("awk", help=("pattern scanning and processing language", "awk [-F sep] 'pattern {action}' [FILE]...", []))
def c_awk(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="", valued="F")
    if opts is None:
        return 1
    if not args:
        ctx.e("usage: awk [-F sep] 'program' [file ...]\n")
        return 2
    prog, files = args[0], args[1:]
    m = re.match(r"^\s*(/.*/)?\s*(\{(.*)\})?\s*$", prog)
    if not m or not (m.group(1) or m.group(2)):
        ctx.e("awk: syntax error in program\n")
        return 2
    rx = _regex(m.group(1)[1:-1]) if m.group(1) else None
    body = m.group(3)
    sep = opts.get("F")
    res, bad = read_inputs(ctx, files)
    nr = 0
    for _, text in res:
        for l in lines_of(text):
            nr += 1
            if rx and not rx.search(l):
                continue
            fields = l.split(sep) if sep and len(sep) == 1 else (re.split(sep, l) if sep else l.split())
            if body is None or body.strip() == "":
                ctx.w(l + "\n")
                continue
            body_s = body.strip()
            if not body_s.startswith("print"):
                ctx.e("awk: only print actions are supported in the simulator\n")
                return 2
            body_s = body_s[5:].strip()
            if not body_s:
                ctx.w(l + "\n")
                continue
            vals = []
            for it in _awk_items(body_s, sep):
                if it == "$0":
                    vals.append(l)
                elif it == "$NF":
                    vals.append(fields[-1] if fields else "")
                elif it == "NF":
                    vals.append(str(len(fields)))
                elif it == "NR":
                    vals.append(str(nr))
                elif re.match(r"^\$\d+$", it):
                    k = int(it[1:])
                    vals.append(fields[k - 1] if 0 < k <= len(fields) else "")
                elif it.startswith('"'):
                    vals.append(it.strip('"'))
                else:
                    vals.append(it)
            ctx.w(" ".join(vals) + "\n")
    return 1 if bad else 0


@cmd("diff", "sdiff", help=("compare files line by line (sdiff: side by side)", "sdiff FILE1 FILE2", [("|", "lines differ"), ("<", "line only in the left file"), (">", "line only in the right file")]))
def c_diff(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="uy")
    if opts is None or len(args) != 2:
        ctx.e("%s: missing operand\n" % ctx.name)
        return 2
    res, bad = read_inputs(ctx, args)
    if bad or len(res) != 2:
        return 2
    a, b = lines_of(res[0][1]), lines_of(res[1][1])
    differ = False
    side = ctx.name == "sdiff"
    n = max(len(a), len(b))
    for i in range(n):
        l = a[i] if i < len(a) else None
        r = b[i] if i < len(b) else None
        if side:
            if l == r:
                ctx.w("%-40s   %s\n" % (l, r))
            elif l is not None and r is not None:
                ctx.w("%-40s | %s\n" % (l, r))
                differ = True
            elif l is not None:
                ctx.w("%-40s <\n" % l)
                differ = True
            else:
                ctx.w("%-40s > %s\n" % ("", r))
                differ = True
        elif l != r:
            differ = True
            ctx.w("%dc%d\n< %s\n---\n> %s\n" % (i + 1, i + 1, l, r))
    return 1 if differ else 0


@cmd("find", help=("search for files in a directory hierarchy", "find [starting-point...] [expression]", [
    ("-name PATTERN", "base name matches shell pattern"), ("-type f|d|l", "file type"),
    ("-perm MODE", "permission bits are exactly MODE"), ("-user NAME", "file is owned by user NAME")]))
def c_find(ctx):
    argv = ctx.argv[1:]
    paths = []
    while argv and not argv[0].startswith("-"):
        paths.append(argv.pop(0))
    paths = paths or ["."]
    conds = []
    maxdepth = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-name", "-iname", "-type", "-perm", "-user", "-maxdepth", "-size", "-mindepth") and i + 1 < len(argv):
            v = argv[i + 1]
            if a == "-maxdepth":
                maxdepth = int(v)
            else:
                conds.append((a, v))
            i += 2
        elif a in ("-print", "-ls"):
            i += 1
        else:
            ctx.e("find: unknown predicate `%s'\n" % a)
            return 1
    fs = ctx.fs
    st = 0

    def ok(path, node):
        for k, v in conds:
            base = posixpath.basename(path.rstrip("/")) or path
            if k == "-name" and not fnmatch.fnmatchcase(base, v):
                return False
            if k == "-iname" and not fnmatch.fnmatchcase(base.lower(), v.lower()):
                return False
            if k == "-type" and node.kind != {"f": "f", "d": "d", "l": "l"}.get(v, "?"):
                return False
            if k == "-perm":
                want = int(v.lstrip("-/"), 8)
                if v.startswith("-"):
                    if node.mode & want != want:
                        return False
                elif node.mode & 0o7777 != want:
                    return False
            if k == "-user" and node.owner != v:
                return False
            if k == "-size":
                m = re.match(r"([+-]?)(\d+)([kMGc]?)", v)
                if m:
                    mult = {"": 512, "c": 1, "k": 1024, "M": 1048576, "G": 1073741824}[m.group(3)]
                    nb = int(math.ceil(node.size() / float(mult)))
                    t = int(m.group(2))
                    if (m.group(1) == "+" and not nb > t) or (m.group(1) == "-" and not nb < t) or (m.group(1) == "" and nb != t):
                        return False
        return True

    for start in paths:
        try:
            node = fs.lookup(start, follow=False)
        except FSError:
            node = None
        if node is None:
            ctx.err("'%s': No such file or directory" % start)
            st = 1
            continue
        if ok(start, node):
            ctx.w(start + "\n")

        def rec(p, depth):
            nd = fs.lookup(p, follow=False)
            if nd is None or nd.kind != "d":
                return
            if maxdepth is not None and depth >= maxdepth:
                return
            if not fs.can(nd, "r", ctx.user):
                ctx.err("'%s': Permission denied" % p)
                return
            for nm in sorted(nd.entries):
                cp = p.rstrip("/") + "/" + nm
                ch = fs.inodes[nd.entries[nm]]
                if ok(cp, ch):
                    ctx.w(cp + "\n")
                if ch.kind == "d":
                    rec(cp, depth + 1)
        rec(start, 0)
    return st


@cmd("md5sum", "sha1sum", "sha256sum", "sha384sum", "sha512sum", help=("compute and check message digests", "md5sum [-c] FILE...", [("-c", "read sums from the FILEs and check them")]))
def c_hash(ctx):
    algo = {"md5sum": "md5", "sha1sum": "sha1", "sha256sum": "sha256", "sha384sum": "sha384", "sha512sum": "sha512"}[ctx.name]
    opts, args = getopts(ctx, ctx.argv[1:], flags="cb")
    if opts is None:
        return 1
    fs = ctx.fs
    if "c" in opts:
        res, bad = read_inputs(ctx, args or [])
        failed = 0
        missing = 0
        for _, text in res:
            for l in lines_of(text):
                m = re.match(r"^([0-9a-f]+)\s+\*?(.+)$", l)
                if not m:
                    continue
                want, f = m.groups()
                try:
                    node = fs.lookup(f)
                    if node is None:
                        ctx.w("%s: FAILED open or read\n" % f)
                        ctx.e("%s: %s: No such file or directory\n" % (ctx.name, f))
                        missing += 1
                        continue
                    got = hexhash(algo, fs.read(f, ctx.user))
                except FSError as ex:
                    ctx.w("%s: FAILED open or read\n" % f)
                    missing += 1
                    continue
                if got == want:
                    ctx.w("%s: OK\n" % f)
                else:
                    ctx.w("%s: FAILED\n" % f)
                    failed += 1
        if failed:
            ctx.e("%s: WARNING: %d computed checksum did NOT match\n" % (ctx.name, failed))
        if not (failed or missing or bad):
            ctx.sh.check_ok[algo] = True
            return 0
        return 1
    st = 0
    if not args:
        ctx.w("%s  -\n" % hexhash(algo, ctx.stdin or ""))
        return 0
    for a in args:
        try:
            if fs.lookup(a) is None:
                ctx.err("%s: No such file or directory" % a)
                st = 1
                continue
            ctx.w("%s  %s\n" % (hexhash(algo, fs.read(a, ctx.user)), a))
        except FSError as ex:
            ctx.err("%s: %s" % (a, ex.msg))
            st = 1
    return st


@cmd("file")
def c_file(ctx):
    for a in ctx.argv[1:]:
        n = ctx.fs.lookup(a, follow=False)
        if n is None:
            ctx.w("%s: cannot open (No such file or directory)\n" % a)
            continue
        if n.kind == "d":
            kind = "directory"
        elif n.kind == "l":
            kind = "symbolic link to " + n.target
        elif isinstance(n.data, Comp):
            kind = {"gz": "gzip compressed data", "bz2": "bzip2 compressed data, block size = 900k", "xz": "XZ compressed data"}[n.data.algo]
        elif isinstance(n.data, Archive):
            kind = {"tar": "POSIX tar archive (GNU)", "cpio": "ASCII cpio archive (SVR4 with no CRC)", "zip": "Zip archive data", "7z": "7-zip archive data"}[n.data.kind]
        else:
            kind = "empty" if n.size() == 0 else "ASCII text"
        ctx.w("%s: %s\n" % (a, kind))


@cmd("exit", "logout")
def c_exit(ctx):
    ctx.w("(this simulator keeps the shell open. Type !quit to leave the mission.)\n")


from . import archive, pkg, storage  # noqa: E402,F401  (register more commands)
