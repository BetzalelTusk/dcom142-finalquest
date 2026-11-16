"""Package-manager and download simulators: rpm, yum, dnf, createrepo, dpkg, apt, apt-get, wget, curl."""
import posixpath
import re

from .shell import cmd, getopts, lines_of, join_lines
from .vfs import FSError, Archive, Comp

# name: version, rpm deps, summary, files, deb name, deb deps
CATALOG = {
    "zip":        ("3.0-35.el9", [], "Utility for creating ZIP archives", ["/usr/bin/zip"], "zip", []),
    "unzip":      ("6.0-57.el9", [], "A utility for unpacking zip files", ["/usr/bin/unzip"], "unzip", []),
    "tree":       ("1.8.0-10.el9", [], "File system tree viewer", ["/usr/bin/tree"], "tree", []),
    "wget":       ("1.21.1-8.el9", [], "A utility for retrieving files using HTTP or FTP", ["/usr/bin/wget"], "wget", []),
    "htop":       ("3.2.2-4.el9", [], "Interactive process viewer", ["/usr/bin/htop"], "htop", []),
    "nmap":       ("7.92-3.el9", ["libpcap"], "Network exploration tool and security scanner", ["/usr/bin/nmap"], "nmap", ["libpcap0.8"]),
    "libpcap":    ("1.10.0-4.el9", [], "A system-independent interface for packet capture", ["/usr/lib64/libpcap.so.1"], "libpcap0.8", []),
    "vim-enhanced": ("9.0.1592-1.el9", ["vim-common"], "A version of the VIM editor which includes recent enhancements", ["/usr/bin/vim"], "vim", ["vim-common"]),
    "vim-common": ("9.0.1592-1.el9", [], "The common files needed by any version of the VIM editor", ["/usr/share/vim/vimrc"], "vim-common", []),
    "httpd":      ("2.4.57-5.el9", ["apr", "apr-util", "httpd-tools", "httpd-filesystem"], "Apache HTTP Server", ["/usr/sbin/httpd"], "apache2", ["apache2-bin", "apache2-data", "apache2-utils"]),
    "apr":        ("1.7.0-12.el9", [], "Apache Portable Runtime library", ["/usr/lib64/libapr-1.so.0"], "libapr1", []),
    "apr-util":   ("1.6.1-23.el9", ["apr"], "Apache Portable Runtime Utility library", ["/usr/lib64/libaprutil-1.so.0"], "libaprutil1", []),
    "httpd-tools": ("2.4.57-5.el9", ["apr", "apr-util"], "Tools for use with the Apache HTTP Server", ["/usr/bin/htpasswd"], "apache2-utils", []),
    "httpd-filesystem": ("2.4.57-5.el9", [], "The basic directory layout for the Apache HTTP server", ["/etc/httpd/conf/.keep"], "apache2-data", []),
    "p7zip":      ("16.02-20.el9", [], "Very high compression ratio file archiver", ["/usr/bin/7za"], "p7zip-full", []),
    "git":        ("2.39.3-1.el9", ["git-core"], "Fast Version Control System", ["/usr/bin/git"], "git", ["git-man"]),
    "git-core":   ("2.39.3-1.el9", [], "Core package of git with minimal functionality", ["/usr/libexec/git-core/git"], "git-man", []),
    "lvm2":       ("2.03.21-2.el9", [], "Userland logical volume management tools", ["/usr/sbin/lvm"], "lvm2", []),
    "localtool":  ("1.0-1", [], "In-house admin helper (from the local repo)", ["/usr/local/bin/localtool"], "localtool", []),
}
BASE_RPMS = ["bash", "coreutils", "curl", "cpio", "tar", "gzip", "bzip2", "xz", "vim-minimal", "grep", "sed", "rpm", "dnf"]
BASE_VER = "el9"


def pk(name):
    return CATALOG.get(name)


def deb_to_rpm(name):
    for k, v in CATALOG.items():
        if v[4] == name:
            return k
    return None


def pkg_header(name):
    v = CATALOG[name]
    return "RPMPKG name=%s version=%s deps=%s\n" % (name, v[0], ",".join(v[1]))


def deb_header(name):
    v = CATALOG[name]
    return "DEBPKG name=%s version=%s deps=%s\n" % (v[4], v[0].split("-")[0] + "-1", ",".join(v[5]))


def parse_pkgfile(text):
    m = re.match(r"^(RPMPKG|DEBPKG) name=(\S+) version=(\S+) deps=(\S*)", text if isinstance(text, str) else "")
    if not m:
        return None
    return {"kind": m.group(1), "name": m.group(2), "version": m.group(3), "deps": [d for d in m.group(4).split(",") if d]}


def state(fs):
    s = fs.sys
    s.setdefault("rpmdb", {})
    s.setdefault("dpkg", {})
    s.setdefault("localrepo", {})
    s.setdefault("net", {})
    return s


def full(name, ver):
    return "%s-%s.x86_64" % (name, ver)


def install_files(fs, name):
    for f in CATALOG[name][3]:
        fs.put(f, "#!/bin/sh\n# %s (simulated binary)\n" % name, owner="root", mode=0o755)


def remove_files(fs, name):
    for f in CATALOG[name][3]:
        try:
            if fs.exists(f, follow=False):
                fs.unlink(f, "root")
        except FSError:
            pass


# ----------------------------------------------------------------------------- repositories (rpm side)
def parse_repo_files(fs):
    repos = []
    try:
        names = fs.listdir("/etc/yum.repos.d")
    except FSError:
        return repos
    for nm in names:
        if not nm.endswith(".repo"):
            continue
        try:
            text = fs.read("/etc/yum.repos.d/" + nm, "root")
        except FSError:
            continue
        cur = None
        for l in lines_of(text if isinstance(text, str) else ""):
            l = l.strip()
            m = re.match(r"^\[(.+)\]$", l)
            if m:
                cur = {"id": m.group(1), "name": m.group(1), "baseurl": "", "enabled": "1", "gpgcheck": "1", "file": nm}
                repos.append(cur)
            elif cur is not None and "=" in l:
                k, v = l.split("=", 1)
                cur[k.strip()] = v.strip()
    return repos


def repo_packages(fs, repo):
    """dict name -> {'signed': bool} provided by the repo."""
    url = repo.get("baseurl", "")
    st = state(fs)
    if url.startswith("file://"):
        return {k: {"signed": False} for k in st["localrepo"].get(url[7:].rstrip("/") or "/", {})}
    if url.startswith("http"):
        return {k: {"signed": True} for k, v in CATALOG.items() if k != "localtool"}
    return {}


def find_package(fs, name):
    """-> (repo, signed) from the first enabled repo that carries the package, or None. Notes disabled repos."""
    for r in parse_repo_files(fs):
        if r.get("enabled", "1") != "1":
            continue
        pk_ = repo_packages(fs, r)
        if name in pk_:
            return r, pk_[name]["signed"]
    return None


def is_installed(fs, name):
    return name in state(fs)["rpmdb"]


def resolve(fs, name, seen=None):
    seen = seen if seen is not None else []
    for d in CATALOG[name][1]:
        if not is_installed(fs, d) and d not in seen:
            resolve(fs, d, seen)
    if name not in seen and not is_installed(fs, name):
        seen.append(name)
    return seen


def dependents(fs, name):
    out_ = []
    for p in state(fs)["rpmdb"]:
        if p in CATALOG and name in CATALOG[p][1] and p != name:
            out_.append(p)
    return out_


def rpm_install_local(fs, path, user):
    data = fs.read(path, user)
    info = parse_pkgfile(data)
    return info


def kb(n):
    return "%d k" % n


@cmd("dnf", "yum", help=("software package manager (Red Hat family, resolves dependencies)", "dnf [options] [subcommand] {package-name}", [
    ("install", "install a package and its dependencies"), ("remove", "uninstall a package"), ("upgrade/update", "update packages"),
    ("info", "show package details"), ("provides FILE", "which package provides a file"), ("list installed", "list installed packages"), ("-y", "answer yes to prompts")]))
def c_dnf(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="yqCd", valued="e", longs=("assumeyes", "enablerepo=", "disablerepo=", "nogpgcheck", "allowerasing"))
    if opts is None:
        return 1
    fs = ctx.fs
    st = state(fs)
    yes = "y" in opts or "assumeyes" in opts
    if not args:
        ctx.w("usage: %s [options] COMMAND\n\nList of Main Commands:\n\ninstall  remove  upgrade  info  provides  list  search  repolist  clean  makecache\n" % ctx.name)
        return 0
    sub, pkgs = args[0], args[1:]
    if sub == "localinstall":
        sub = "install"
    if sub == "update":
        sub = "upgrade"
    if sub in ("install", "remove", "upgrade", "erase") and not ctx.root:
        ctx.e("Error: This command has to be run with superuser privileges (under the root user on most systems).\n")
        return 1
    stamp = "Last metadata expiration check: 0:04:12 ago on Sun 15 Nov 2026 10:00:00 AM UTC.\n"
    if sub == "repolist":
        ctx.w("repo id                      repo name\n")
        for r in parse_repo_files(fs):
            if r.get("enabled", "1") == "1" or "all" in pkgs:
                ctx.w("%-28s %s%s\n" % (r["id"], r.get("name", r["id"]), "" if r.get("enabled", "1") == "1" else "   disabled"))
        return 0
    if sub in ("clean", "makecache"):
        ctx.w("%s\n" % ("Metadata cache created." if sub == "makecache" else "0 files removed" if False else "27 files removed"))
        return 0
    if sub in ("list", "info", "search", "provides", "whatprovides"):
        ctx.w(stamp)
    if sub == "list":
        which = pkgs[0] if pkgs else "all"
        if which in ("installed", "all"):
            ctx.w("Installed Packages\n")
            for n, v in sorted(st["rpmdb"].items()):
                ctx.w("%-40s %-24s @baseos\n" % (n + ".x86_64", v))
        if which in ("available", "all"):
            ctx.w("Available Packages\n")
            for n, v in sorted(CATALOG.items()):
                if n not in st["rpmdb"] and find_package(fs, n):
                    ctx.w("%-40s %-24s %s\n" % (n + ".x86_64", v[0], find_package(fs, n)[0]["id"]))
        return 0
    if sub == "search":
        hit = False
        for n, v in sorted(CATALOG.items()):
            if any(p.lower() in n.lower() or p.lower() in v[2].lower() for p in pkgs) and find_package(fs, n):
                ctx.w("%-30s : %s\n" % (n + ".x86_64", v[2]))
                hit = True
        if not hit:
            ctx.w("No matches found.\n")
        return 0 if hit else 1
    if sub == "info":
        if not pkgs:
            ctx.e("Error: Command line error: argument info missing package\n")
            return 1
        for p in pkgs:
            if p not in CATALOG and p not in st["rpmdb"]:
                ctx.e("Error: No matching Packages to list\n")
                return 1
            inst = p in st["rpmdb"]
            if not inst and not find_package(fs, p):
                ctx.e("Error: No matching Packages to list\n")
                return 1
            v = CATALOG.get(p, ("?", [], "", [], p, []))
            ctx.w("%s Packages\nName         : %s\nVersion      : %s\nRelease      : %s\nArchitecture : x86_64\nSize         : 266 k\nSource       : %s.src.rpm\nRepository   : %s\nSummary      : %s\nURL          : https://rockylinux.org\nLicense      : GPLv2+\nDescription  : %s\n"
                  % ("Installed" if inst else "Available", p, v[0].split("-")[0], v[0].split("-")[-1], p, "@System" if inst else find_package(fs, p)[0]["id"], v[2], v[2]))
        return 0
    if sub in ("provides", "whatprovides"):
        if not pkgs:
            ctx.e("Error: Command line error: argument provides missing file\n")
            return 1
        hit = False
        for n, v in CATALOG.items():
            for f in v[3]:
                if pkgs[0] == f or f.endswith("/" + pkgs[0].lstrip("*/")) or pkgs[0].endswith("/" + posixpath.basename(f)):
                    ctx.w("%s-%s.x86_64 : %s\nRepo        : %s\nMatched from:\nFilename    : %s\n\n" % (n, v[0], v[2], "@System" if n in st["rpmdb"] else (find_package(fs, n) or [{"id": "baseos"}])[0]["id"], f))
                    hit = True
        if not hit:
            ctx.e("Error: No Matches found\n")
        return 0 if hit else 1
    # transactions
    if sub in ("install",):
        if not pkgs:
            ctx.e("Error: Command line error: no package given\n")
            return 1
        to_install = []
        signed_ok = True
        for p in pkgs:
            if p.endswith(".rpm"):
                if not fs.exists(p):
                    ctx.w(stamp + "No match for argument: %s\nError: Unable to find a match: %s\n" % (p, p))
                    return 1
                info = parse_pkgfile(fs.read(p, ctx.user))
                if not info:
                    ctx.e("Error: Failed to open: %s\n" % p)
                    return 1
                name = info["name"]
                if name not in CATALOG:
                    ctx.e("Error: unknown package %s\n" % name)
                    return 1
                if is_installed(fs, name):
                    ctx.w(stamp + "Package %s is already installed.\nDependencies resolved.\nNothing to do.\nComplete!\n" % full(name, CATALOG[name][0]))
                    continue
                for n in resolve(fs, name):
                    if n not in [x[0] for x in to_install]:
                        to_install.append((n, "@commandline"))
                continue
            if p not in CATALOG:
                ctx.w(stamp + "No match for argument: %s\nError: Unable to find a match: %s\n" % (p, p))
                return 1
            if is_installed(fs, p):
                ctx.w(stamp + "Package %s is already installed.\nDependencies resolved.\nNothing to do.\nComplete!\n" % full(p, CATALOG[p][0]))
                continue
            found = find_package(fs, p)
            if not found:
                ctx.w(stamp + "No match for argument: %s\nError: Unable to find a match: %s\n" % (p, p))
                disabled = [r["id"] for r in parse_repo_files(fs) if r.get("enabled", "1") != "1" and p in repo_packages(fs, r)]
                if disabled:
                    ctx.w(ui_note("The package exists in the repository '%s', but that repo is disabled (enabled=0)." % disabled[0]))
                return 1
            repo, signed = found
            if repo.get("gpgcheck", "1") == "1" and not signed and "nogpgcheck" not in opts:
                needs = resolve(fs, p)
                ctx.w(stamp + "Dependencies resolved.\nTransaction Summary\nInstall  %d Package\n\n" % len(needs))
                if not yes:
                    ans = ctx.ask("Is this ok [y/N]: ")
                    if ans.strip().lower()[:1] != "y":
                        ctx.w("Operation aborted.\n")
                        return 1
                ctx.w("Downloading Packages:\n\nPublic key for %s.rpm is not installed\nThe downloaded packages were saved in cache until the next successful transaction.\nError: GPG check FAILED\n" % full(p, CATALOG[p][0]))
                ctx.w(ui_note("Repo '%s' has gpgcheck=1 but its packages are unsigned. Set gpgcheck=0 (not recommended) or sign the packages." % repo["id"]))
                return 1
            for n in resolve(fs, p):
                if n not in [x[0] for x in to_install]:
                    fr = find_package(fs, n)
                    to_install.append((n, fr[0]["id"] if fr else repo["id"]))
        if not to_install:
            return 0
        ctx.w(stamp + "Dependencies resolved.\n" + "=" * 78 + "\n Package            Arch     Version                 Repository      Size\n" + "=" * 78 + "\n")
        main = [x for x in to_install if x[0] in pkgs or any(x[0] == parse_name(p, fs) for p in pkgs)]
        deps = [x for x in to_install if x not in main]
        ctx.w("Installing:\n")
        for n, r in main:
            ctx.w(" %-18s x86_64   %-22s %-14s 266 k\n" % (n, CATALOG[n][0], r))
        if deps:
            ctx.w("Installing dependencies:\n")
            for n, r in deps:
                ctx.w(" %-18s x86_64   %-22s %-14s 120 k\n" % (n, CATALOG[n][0], r))
        ctx.w("\nTransaction Summary\n" + "=" * 78 + "\nInstall  %d Package%s\n\n" % (len(to_install), "" if len(to_install) == 1 else "s"))
        if not yes:
            ans = ctx.ask("Is this ok [y/N]: ")
            if ans.strip().lower()[:1] != "y":
                ctx.w("Operation aborted.\n")
                return 1
        ctx.w("Downloading Packages:\nRunning transaction check\nTransaction check succeeded.\nRunning transaction test\nTransaction test succeeded.\nRunning transaction\n")
        for i, (n, r) in enumerate(to_install, 1):
            st["rpmdb"][n] = CATALOG[n][0]
            install_files(fs, n)
            ctx.w("  Installing       : %-30s %d/%d\n" % (n + "-" + CATALOG[n][0], i, len(to_install)))
        ctx.w("\nInstalled:\n" + "".join("  %s\n" % full(n, CATALOG[n][0]) for n, _ in to_install) + "\nComplete!\n")
        return 0
    if sub in ("remove", "erase"):
        if not pkgs:
            ctx.e("Error: Command line error: no package given\n")
            return 1
        gone = []
        for p in pkgs:
            if p not in st["rpmdb"]:
                ctx.w(stamp + "No match for argument: %s\nNo packages marked for removal.\n" % p if False else "No match for argument: %s\nError: No packages marked for removal.\n" % p)
                return 1
            stack = [p]
            while stack:
                x = stack.pop()
                if x not in gone:
                    gone.append(x)
                    stack.extend(d for d in dependents(fs, x))
        ctx.w(stamp + "Dependencies resolved.\nRemoving:\n" + "".join(" %-18s x86_64   %s\n" % (n, CATALOG[n][0]) for n in gone))
        if len(gone) > len(pkgs):
            ctx.w("Removing dependent packages (dnf/yum resolve dependencies automatically):\n")
        ctx.w("\nTransaction Summary\nRemove  %d Package%s\n\n" % (len(gone), "" if len(gone) == 1 else "s"))
        if not yes:
            ans = ctx.ask("Is this ok [y/N]: ")
            if ans.strip().lower()[:1] != "y":
                ctx.w("Operation aborted.\n")
                return 1
        for n in gone:
            st["rpmdb"].pop(n, None)
            remove_files(fs, n)
            ctx.w("  Erasing          : %s\n" % n)
        ctx.w("\nRemoved:\n" + "".join("  %s\n" % full(n, CATALOG[n][0]) for n in gone) + "\nComplete!\n")
        return 0
    if sub == "upgrade":
        ctx.w(stamp + "Dependencies resolved.\nNothing to do.\nComplete!\n")
        return 0
    ctx.e("No such command: %s. Please use /usr/bin/%s --help\n" % (sub, ctx.name))
    return 1


def parse_name(p, fs):
    if p.endswith(".rpm") and fs.exists(p):
        info = parse_pkgfile(fs.read(p, "root"))
        return info["name"] if info else p
    return p


def ui_note(msg):
    """Teaching notes never print in the shell; they're queued and only shown as tips (when tips are on)."""
    from .shell import note
    return note(msg)


@cmd("rpm", help=("RPM Package Manager (low-level, does NOT resolve dependencies)", "rpm [options] {package-name}", [
    ("-i", "install"), ("-e", "erase (uninstall)"), ("-h", "print hash marks (progress bar)"), ("-v", "verbose"), ("-qa", "query all installed packages"), ("-qi PKG", "show package information")]))
def c_rpm(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="iehvqaUFlpfV", longs=("nodeps", "force", "test"))
    if opts is None:
        return 1
    fs = ctx.fs
    st = state(fs)
    if "q" in opts:
        if "a" in opts:
            for n, v in sorted(st["rpmdb"].items()):
                ctx.w("%s\n" % full(n, v))
            return 0
        if not args:
            ctx.e("rpm: no arguments given for query\n")
            return 1
        rc = 0
        for p in args:
            if p not in st["rpmdb"]:
                ctx.w("package %s is not installed\n" % p)
                rc = 1
                continue
            v = CATALOG.get(p, (st["rpmdb"][p], [], "", [], p, []))
            if "i" in opts:
                ctx.w("Name        : %s\nVersion     : %s\nRelease     : %s\nArchitecture: x86_64\nInstall Date: Sun 15 Nov 2026 10:00:00 AM UTC\nSize        : 272461\nLicense     : BSD\nSignature   : RSA/SHA256, Key ID 15af5dac6d745a60\nSource RPM  : %s.src.rpm\nSummary     : %s\n" % (p, v[0].split("-")[0], v[0].split("-")[-1], p, v[2]))
            elif "l" in opts:
                for f in v[3]:
                    ctx.w(f + "\n")
            else:
                ctx.w("%s\n" % full(p, st["rpmdb"][p]))
        return rc
    if "e" in opts:
        if not ctx.root:
            ctx.e("error: can't create transaction lock on /var/lib/rpm/.rpm.lock (Permission denied)\n")
            return 1
        rc = 0
        for p in args:
            if p not in st["rpmdb"]:
                ctx.e("error: package %s is not installed\n" % p)
                rc = 1
                continue
            deps = dependents(fs, p)
            if deps and "nodeps" not in opts:
                ctx.e("error: Failed dependencies:\n" + "".join("\t%s is needed by (installed) %s\n" % (p, full(d, CATALOG[d][0])) for d in deps))
                rc = 1
                continue
            st["rpmdb"].pop(p)
            remove_files(fs, p)
        return rc
    if "i" in opts or "U" in opts or "F" in opts:
        if not ctx.root:
            ctx.e("error: can't create transaction lock on /var/lib/rpm/.rpm.lock (Permission denied)\n")
            return 1
        if not args:
            ctx.e("rpm: no packages given for install\n")
            return 1
        for f in args:
            if not fs.exists(f):
                ctx.e("error: open of %s failed: No such file or directory\n" % f)
                return 1
            info = parse_pkgfile(fs.read(f, ctx.user))
            if not info or info["kind"] != "RPMPKG":
                ctx.e("error: %s: not an rpm package (or package manifest)\n" % f)
                return 1
            name = info["name"]
            missing = [d for d in info["deps"] if d not in st["rpmdb"]]
            if missing and "nodeps" not in opts:
                ctx.e("error: Failed dependencies:\n" + "".join("\t%s is needed by %s\n" % (d, full(name, info["version"])) for d in missing))
                ctx.e(ui_note("rpm is a low-level tool: it will not fetch %s for you. Use dnf/yum, which resolves dependencies." % ", ".join(missing)))
                return 1
            if name in st["rpmdb"] and "U" not in opts and "force" not in opts:
                ctx.w("\tpackage %s is already installed\n" % full(name, info["version"]))
                return 1
            st["rpmdb"][name] = info["version"]
            if name in CATALOG:
                install_files(fs, name)
            if "v" in opts or "h" in opts:
                ctx.w("Verifying...                          ################################# [100%%]\nPreparing...                          ################################# [100%%]\nUpdating / installing...\n   1:%-34s################################# [100%%]\n" % (name + "-" + info["version"]))
        return 0
    ctx.e("rpm: no operation specified (try -i, -e or -q)\n")
    return 1


@cmd("createrepo", "createrepo_c", help=("create a repository from a directory of .rpm files", "createrepo DIRECTORY", []))
def c_createrepo(ctx):
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    if not args:
        ctx.e("Usage: createrepo [options] <directory>\n")
        return 1
    fs = ctx.fs
    d = fs.abspath(args[0]).rstrip("/") or "/"
    if not fs.isdir(d):
        ctx.e("Cannot access/read input dir: %s\n" % args[0])
        return 1
    found = {}
    for nm in fs.listdir(d):
        if nm.endswith(".rpm"):
            try:
                info = parse_pkgfile(fs.read(d + "/" + nm, ctx.user))
            except FSError:
                info = None
            if info:
                found[info["name"]] = info
    try:
        if not fs.exists(d + "/repodata"):
            fs.mkdir(d + "/repodata", ctx.user)
        fs.write(d + "/repodata/repomd.xml", "<repomd><!-- %d packages --></repomd>\n" % len(found), ctx.user)
    except FSError as ex:
        ctx.e("Cannot create/verify %s/repodata: %s\n" % (d, ex.msg))
        return 1
    state(fs)["localrepo"][d] = found
    ctx.w("Directory walk started\nDirectory walk done - %d packages\nTemporary output repo path: %s/.repodata/\nPreparing sqlite DBs\nPool started (with 5 workers)\nPool finished\n" % (len(found), d))
    return 0


# ----------------------------------------------------------------------------- Debian family
def deb_installed(fs):
    return state(fs)["dpkg"]


@cmd("apt", "apt-get", help=("package manager (Debian family, resolves dependencies)", "apt [options] command", [
    ("update", "refresh the package lists (run after adding repos)"), ("install", "install packages"), ("remove", "remove packages"),
    ("show PKG", "show package details"), ("list --installed", "list installed packages"), ("-y", "assume yes")]))
def c_apt(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="yqf", longs=("installed", "upgradable", "assume-yes", "no-install-recommends"))
    if opts is None:
        return 100
    fs = ctx.fs
    st = state(fs)
    yes = "y" in opts or "assume-yes" in opts
    if not args:
        ctx.w("apt 2.6.1 (amd64)\nUsage: apt [options] command\n\nMost used commands:\n  list  search  show  install  remove  update  upgrade\n")
        return 0
    sub, pkgs = args[0], args[1:]
    if sub in ("install", "remove", "purge", "update", "upgrade", "autoremove") and not ctx.root:
        ctx.e("E: Could not open lock file /var/lib/apt/lists/lock - open (13: Permission denied)\nE: Unable to lock directory /var/lib/apt/lists/\n" if sub == "update" else "E: Could not open lock file /var/lib/dpkg/lock-frontend - open (13: Permission denied)\nE: Unable to acquire the dpkg frontend lock (/var/lib/dpkg/lock-frontend), are you root?\n")
        return 100
    if sub == "update":
        st["apt_updated"] = True
        ctx.w("Get:1 http://deb.debian.org/debian bookworm InRelease [151 kB]\nGet:2 http://deb.debian.org/debian-security bookworm-security InRelease [48.0 kB]\nFetched 199 kB in 1s (211 kB/s)\nReading package lists... Done\nBuilding dependency tree... Done\nAll packages are up to date.\n")
        return 0
    if sub == "upgrade":
        ctx.w("Reading package lists... Done\nBuilding dependency tree... Done\n0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n")
        return 0
    if sub == "list":
        ctx.w("Listing... Done\n")
        if "installed" in opts:
            for n, v in sorted(st["dpkg"].items()):
                ctx.w("%s/stable,now %s amd64 [installed]\n" % (n, v))
        else:
            for k, v in sorted(CATALOG.items(), key=lambda kv: kv[1][4]):
                if k != "localtool" and st.get("apt_updated"):
                    ctx.w("%s/stable %s amd64%s\n" % (v[4], v[0].split("-")[0] + "-1", " [installed]" if v[4] in st["dpkg"] else ""))
        return 0
    if sub == "search":
        for k, v in sorted(CATALOG.items(), key=lambda kv: kv[1][4]):
            if k != "localtool" and st.get("apt_updated") and any(p in v[4] or p in v[2].lower() for p in pkgs):
                ctx.w("%s/stable %s amd64\n  %s\n\n" % (v[4], v[0].split("-")[0] + "-1", v[2]))
        return 0
    if sub == "show":
        if not pkgs:
            ctx.e("E: No packages found\n")
            return 100
        for p in pkgs:
            k = deb_to_rpm(p)
            if k is None or (not st.get("apt_updated") and p not in st["dpkg"]):
                ctx.e("E: No packages found\n" if False else "N: Unable to locate package %s\nE: No packages found\n" % p)
                return 100
            v = CATALOG[k]
            ctx.w("Package: %s\nVersion: %s\nPriority: optional\nSection: utils\nMaintainer: Debian Maintainers <maint@debian.org>\nDepends: %s\nDownload-Size: 266 kB\nAPT-Manual-Installed: no\nAPT-Sources: http://deb.debian.org/debian bookworm/main amd64 Packages\nDescription: %s\n"
                  % (p, v[0].split("-")[0] + "-1", ", ".join(v[5]) or "libc6", v[2]))
        return 0
    if sub in ("install", "reinstall"):
        if not pkgs:
            ctx.e("E: No packages specified\n" if False else "")
            return 100
        need = []
        for p in pkgs:
            if p.endswith(".deb"):
                continue
            k = deb_to_rpm(p)
            if k is None or not st.get("apt_updated"):
                if p in st["dpkg"]:
                    continue
                ctx.e("Reading package lists... Done\nBuilding dependency tree... Done\nE: Unable to locate package %s\n" % p)
                if not st.get("apt_updated") and k is not None:
                    ctx.w(ui_note("The package lists are empty. Run 'apt update' first so APT learns what the repositories offer."))
                return 100
            if p in st["dpkg"]:
                ctx.w("Reading package lists... Done\nBuilding dependency tree... Done\n%s is already the newest version (%s).\n0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n" % (p, st["dpkg"][p]))
                continue
            for d in CATALOG[k][5] + [p]:
                if d not in st["dpkg"] and d not in need:
                    need.append(d)
        if not need:
            return 0
        extra = [n for n in need if n not in pkgs]
        ctx.w("Reading package lists... Done\nBuilding dependency tree... Done\n")
        if extra:
            ctx.w("The following additional packages will be installed:\n  %s\n" % " ".join(extra))
        ctx.w("The following NEW packages will be installed:\n  %s\n0 upgraded, %d newly installed, 0 to remove and 0 not upgraded.\nNeed to get 1,204 kB of archives.\n" % (" ".join(need), len(need)))
        if not yes:
            ans = ctx.ask("Do you want to continue? [Y/n] ")
            if ans.strip().lower()[:1] == "n":
                ctx.w("Abort.\n")
                return 1
        for n in need:
            k = deb_to_rpm(n)
            st["dpkg"][n] = (CATALOG[k][0].split("-")[0] + "-1") if k else "1.0-1"
            if k:
                install_files(fs, k)
            ctx.w("Setting up %s (%s) ...\n" % (n, st["dpkg"][n]))
        return 0
    if sub in ("remove", "purge", "autoremove"):
        for p in pkgs:
            if p not in st["dpkg"]:
                ctx.e("Reading package lists... Done\nBuilding dependency tree... Done\nPackage '%s' is not installed, so not removed\n" % p)
                continue
            if not yes:
                ans = ctx.ask("Do you want to continue? [Y/n] ")
                if ans.strip().lower()[:1] == "n":
                    ctx.w("Abort.\n")
                    return 1
            k = deb_to_rpm(p)
            st["dpkg"].pop(p)
            if k:
                remove_files(fs, k)
            ctx.w("Removing %s (%s) ...\n" % (p, "1.0-1"))
        return 0
    ctx.e("E: Invalid operation %s\n" % sub)
    return 100


@cmd("dpkg", help=("package manager for Debian (low-level, does NOT resolve dependencies)", "dpkg [options] {package-name}", [
    ("-i FILE.deb", "install a package file"), ("-r PKG", "remove a package"), ("-l", "list installed packages"), ("-s PKG", "show package status/details")]))
def c_dpkg(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="ilrsLP", longs=("list", "status", "install", "remove"))
    if opts is None:
        return 2
    fs = ctx.fs
    st = state(fs)
    if "l" in opts or "list" in opts:
        ctx.w("Desired=Unknown/Install/Remove/Purge/Hold\n| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend\n|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)\n||/ Name           Version        Architecture Description\n+++-==============-==============-============-=================================\n")
        for n, v in sorted(st["dpkg"].items()):
            if args and not any(a.strip("*") in n for a in args):
                continue
            ctx.w("ii  %-14s %-14s amd64        %s\n" % (n, v, (CATALOG.get(deb_to_rpm(n) or "", (0, 0, "installed package"))[2])))
        return 0
    if "s" in opts or "status" in opts:
        if not args:
            ctx.e("dpkg: error: --status needs a valid package name\n")
            return 2
        p = args[0]
        if p not in st["dpkg"]:
            ctx.e("dpkg-query: package '%s' is not installed and no information is available\n" % p)
            return 1
        k = deb_to_rpm(p)
        ctx.w("Package: %s\nStatus: install ok installed\nPriority: optional\nSection: utils\nArchitecture: amd64\nVersion: %s\nDepends: %s\nDescription: %s\n" % (p, st["dpkg"][p], ", ".join(CATALOG[k][5]) if k else "libc6", CATALOG[k][2] if k else "package"))
        return 0
    if "i" in opts or "install" in opts:
        if not ctx.root:
            ctx.e("dpkg: error: requested operation requires superuser privilege\n")
            return 2
        for f in args:
            if not fs.exists(f):
                ctx.e("dpkg: error: cannot access archive '%s': No such file or directory\n" % f)
                return 2
            info = parse_pkgfile(fs.read(f, ctx.user))
            if not info or info["kind"] != "DEBPKG":
                ctx.e("dpkg-deb: error: '%s' is not a Debian format archive\ndpkg: error processing archive %s (--install):\n parsing file '%s' near line 0\n" % (f, f, f))
                return 2
            missing = [d for d in info["deps"] if d not in st["dpkg"]]
            if missing:
                ctx.e("Selecting previously unselected package %s.\n(Reading database ... 41230 files and directories currently installed.)\nPreparing to unpack %s ...\nUnpacking %s (%s) ...\ndpkg: dependency problems prevent configuration of %s:\n" % (info["name"], f, info["name"], info["version"], info["name"]))
                for d in missing:
                    ctx.e(" %s depends on %s; however:\n  Package %s is not installed.\n" % (info["name"], d, d))
                ctx.e("\ndpkg: error processing package %s (--install):\n dependency problems - leaving unconfigured\nErrors were encountered while processing:\n %s\n" % (info["name"], info["name"]))
                ctx.e(ui_note("dpkg is low-level and does not install dependencies. apt install %s would." % info["name"]))
                return 1
            st["dpkg"][info["name"]] = info["version"]
            k = deb_to_rpm(info["name"])
            if k:
                install_files(fs, k)
            ctx.w("Selecting previously unselected package %s.\nUnpacking %s (%s) ...\nSetting up %s (%s) ...\n" % (info["name"], info["name"], info["version"], info["name"], info["version"]))
        return 0
    if "r" in opts or "remove" in opts:
        if not ctx.root:
            ctx.e("dpkg: error: requested operation requires superuser privilege\n")
            return 2
        for p in args:
            if p not in st["dpkg"]:
                ctx.e("dpkg: warning: ignoring request to remove %s which isn't installed\n" % p)
                continue
            deps = [n for n in st["dpkg"] if deb_to_rpm(n) and p in CATALOG[deb_to_rpm(n)][5] and n != p]
            if deps:
                ctx.e("dpkg: dependency problems prevent removal of %s:\n %s depends on %s.\n\ndpkg: error processing package %s (--remove):\n dependency problems - not removing\n" % (p, deps[0], p, p))
                return 1
            st["dpkg"].pop(p)
            k = deb_to_rpm(p)
            if k:
                remove_files(fs, k)
            ctx.w("Removing %s ...\n" % p)
        return 0
    ctx.e("dpkg: error: need an action option\n")
    return 2


# ----------------------------------------------------------------------------- downloads
def netget(fs, url):
    return state(fs)["net"].get(url)


def _basename_of(url):
    base = posixpath.basename(url.split("?")[0].rstrip("/"))
    return base or "index.html"


@cmd("wget", help=("download files from the web without a graphical browser", "wget [OPTION]... [URL]...", [
    ("-O FILE", "write documents to FILE"), ("-P DIR", "save files to DIR"), ("-q", "quiet"), ("-c", "continue a partial download"), ("-r", "recursive download")]))
def c_wget(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="qcrbvN", valued="OP", longs=("no-check-certificate",))
    if opts is None:
        return 1
    if not args:
        ctx.e("wget: missing URL\nUsage: wget [OPTION]... [URL]...\n\nTry `wget --help' for more options.\n")
        return 1
    fs = ctx.fs
    rc = 0
    for url in args:
        full_url = url if "://" in url else "http://" + url
        host = full_url.split("//", 1)[1].split("/")[0]
        data = netget(fs, full_url)
        if "q" not in opts:
            ctx.e("--2026-11-15 22:01:01--  %s\nResolving %s (%s)... 10.0.2.15\nConnecting to %s (%s)|10.0.2.15|:80... connected.\nHTTP request sent, awaiting response... " % (full_url, host, host, host, host))
        if data is None:
            if "q" not in opts:
                ctx.e("404 Not Found\n2026-11-15 22:01:01 ERROR 404: Not Found.\n")
            return 8
        name = opts.get("O") or _basename_of(full_url)
        if "P" in opts:
            name = opts["P"].rstrip("/") + "/" + name
        size = data.size() if hasattr(data, "size") else len(data.encode())
        try:
            fs.write(name, data, ctx.user)
        except FSError as ex:
            ctx.e("%s: Permission denied\n" % name if ex.msg == "Permission denied" else "%s: %s\n" % (name, ex.msg))
            return 1
        if "q" not in opts:
            ctx.e("200 OK\nLength: %d (%.0fK) [application/octet-stream]\nSaving to: '%s'\n\n%s       100%%[===================>] %6.2fK  --.-KB/s    in 0.001s\n\n2026-11-15 22:01:01 (21.0 MB/s) - '%s' saved [%d/%d]\n\n"
                  % (size, size / 1024.0, name, posixpath.basename(name), size / 1024.0, name, size, size))
    return rc


@cmd("curl", help=("transfer a URL (supports many protocols)", "curl [options] URL", [
    ("-o FILE", "write output to FILE"), ("-O", "write output to a local file named like the remote file"), ("-L", "follow redirects"), ("-s", "silent"), ("-I", "show headers only")]))
def c_curl(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="OLsSIfkv", valued="o")
    if opts is None:
        return 2
    if not args:
        ctx.e("curl: try 'curl --help' for more information\n")
        return 2
    fs = ctx.fs
    url = args[0]
    full_url = url if "://" in url else "http://" + url
    data = netget(fs, full_url)
    if data is None:
        host = full_url.split("//", 1)[1].split("/")[0]
        if host not in {u.split("//", 1)[1].split("/")[0] for u in state(fs)["net"]}:
            ctx.e("curl: (6) Could not resolve host: %s\n" % host)
            return 6
        if "f" in opts:
            ctx.e("curl: (22) The requested URL returned error: 404\n")
            return 22
        ctx.w("<html><body><h1>404 Not Found</h1></body></html>\n")
        return 0
    size = data.size() if hasattr(data, "size") else len(data.encode())
    if "I" in opts:
        ctx.w("HTTP/1.1 200 OK\nContent-Type: application/octet-stream\nContent-Length: %d\n\n" % size)
        return 0
    target = opts.get("o")
    if "O" in opts:
        target = _basename_of(full_url)
    if target:
        try:
            fs.write(target, data, ctx.user)
        except FSError as ex:
            ctx.e("curl: (23) Failure writing output to destination: %s\n" % ex.msg)
            return 23
        if "s" not in opts:
            ctx.e("  %% Total    %% Received %% Xferd  Average Speed   Time    Time     Time  Current\n                                 Dload  Upload   Total   Spent    Left  Speed\n100 %5d  100 %5d    0     0   612k      0 --:--:-- --:--:-- --:--:--  612k\n" % (size, size))
        return 0
    if isinstance(data, str):
        ctx.w(data if data.endswith("\n") else data + "\n")
        return 0
    ctx.e("Warning: Binary output can mess up your terminal. Use \"--output -\" to tell curl to output it to your\nWarning: terminal anyway, or consider \"--output <FILE>\" to save to a file.\n")
    return 23


def default_net():
    members = [{"path": "samba-4.19/README", "kind": "f", "data": "Samba is the standard Windows interoperability suite.\n" * 3, "mode": 0o644},
               {"path": "samba-4.19/configure", "kind": "f", "data": "#!/bin/sh\necho configuring samba\n", "mode": 0o755}]
    nm_members = [{"path": "nmap-7.70/README", "kind": "f", "data": "Nmap: network exploration tool.\n" * 3, "mode": 0o644},
                  {"path": "nmap-7.70/nmap.c", "kind": "f", "data": "int main(){return 0;}\n", "mode": 0o644}]
    return {
        "http://download.samba.org/pub/samba/samba-latest.tar.gz": Comp("gz", Archive("tar", members), "samba-latest.tar"),
        "https://nmap.org/dist/nmap-7.70.tar.bz2": Comp("bz2", Archive("tar", nm_members), "nmap-7.70.tar"),
        "http://mirror.example.com/hello.txt": "Hello from the mirror!\nThis file was fetched with wget or curl.\n",
        "https://example.com/index.html": "<html><body><h1>Example Domain</h1></body></html>\n",
    }
