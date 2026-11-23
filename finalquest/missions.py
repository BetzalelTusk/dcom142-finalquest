"""Hands-on missions played in the simulated shell. Each mission is checked against the machine's
real state (files, inodes, packages, mounts), not against the exact commands you typed."""
import re

from .vfs import Comp, Archive, FSError, hexhash
from .world import make_world, mkfile
from . import pkg, storage

MISSIONS = []


def mission(**kw):
    kw.setdefault("distro", "rocky")
    kw.setdefault("hints", [])
    MISSIONS.append(kw)


# ----------------------------------------------------------------------------- helpers for checks
def text(fs, path):
    try:
        n = fs.lookup(path)
        if n is None or n.kind == "d":
            return None
        return n.data if isinstance(n.data, str) else None
    except FSError:
        return None


def lines(fs, path):
    t = text(fs, path)
    return None if t is None else [l for l in t.split("\n") if l.strip() != ""]


def node(fs, path, follow=True):
    try:
        return fs.lookup(path, follow)
    except FSError:
        return None


def ran(sh, *words):
    """True if a command was run whose argv contains all the given words (in any position)."""
    for argv, _ in sh.cmdlog:
        if all(any(w == a or (w.startswith("-") and a.startswith("-") and not a.startswith("--") and set(w[1:]) <= set(a[1:])) for a in argv) for w in words):
            return True
    return False


def history_has(sh, *parts):
    return any(all(p in h for p in parts) for h in sh.history)


def tar_members(fs, path, algo=None):
    n = node(fs, path)
    if n is None:
        return None
    d = n.data
    if algo:
        if not isinstance(d, Comp) or d.algo != algo:
            return None
        d = d.inner
    if not isinstance(d, Archive) or d.kind != "tar":
        return None
    return [m["path"] for m in d.members]


H = "/home/rocky"

# ============================================================================= Level 1: Module 6
def s_first(fs, sh):
    mkfile(fs, H + "/README", "Welcome to rocky01. Type !goal to see your objectives.\n")


mission(id="first-boot", level=1, title="First Boot",
        brief="New hire, first login. Your manager wants a workspace before lunch. Build it, then park yourself inside it.",
        goals=["In your home directory (~ means /home/rocky), create ~/projects/logs (both levels)",
               "Create the empty files a.txt and b.txt inside ~/projects (next to logs, not inside it)",
               "Finish with ~/projects as your working directory (check with pwd)"],
        setup=s_first,
        near=lambda fs, sh: ("Close! You built a projects folder at %s, but the goal is ~/projects = /home/rocky/projects. "
                             "~ is your home directory. Type cd (or cd ~) to go home and build it there." %
                             next(p for p in ("/projects", "/home/projects") if fs.exists(p))) if any(fs.exists(p) for p in ("/projects", "/home/projects")) else
                            ("a.txt and b.txt should be in ~/projects itself, not inside logs." if fs.exists(H + "/projects/logs/a.txt") and not fs.exists(H + "/projects/a.txt") else None),
        check=lambda fs, sh: [fs.isdir(H + "/projects/logs"),
                              node(fs, H + "/projects/a.txt") is not None and node(fs, H + "/projects/b.txt") is not None,
                              fs.cwd == H + "/projects"],
        hints=["mkdir -p makes parent directories as needed.", "touch can create several files at once.", "cd into the directory, then pwd."],
        solution=["mkdir -p projects/logs", "touch projects/a.txt projects/b.txt", "cd projects"], par=3)


def s_links(fs, sh):
    mkfile(fs, H + "/dir1/file2", "payroll: alice 52000, bob 48000\n")
    mkfile(fs, H + "/dir1/file3", "config version 1\n")
    fs.sys["m_ino"] = fs.lookup(H + "/dir1/file2").ino


mission(id="link-lab", level=1, title="Link Lab",
        brief="Inside ~/dir1 there are two files. Prove to the class what happens to hard and soft links when the original disappears.",
        goals=["Make a HARD link ~/dir1/file2-hl pointing at file2", "Make a SYMBOLIC link ~/dir1/file3-sl pointing at file3",
               "Delete the originals file2 and file3", "(watch: the hard link still has the data, the soft link is now broken; try cat on both)"],
        setup=s_links,
        check=lambda fs, sh: [node(fs, H + "/dir1/file2-hl", False) is not None and node(fs, H + "/dir1/file2-hl", False).ino == fs.sys.get("m_ino"),
                              node(fs, H + "/dir1/file3-sl", False) is not None and node(fs, H + "/dir1/file3-sl", False).kind == "l" and node(fs, H + "/dir1/file3-sl", False).target.endswith("file3"),
                              node(fs, H + "/dir1/file2", False) is None and node(fs, H + "/dir1/file3", False) is None,
                              True],
        warn=lambda fs, sh: _links_warn(fs),
        dead=lambda fs, sh: _links_dead(fs),
        hints=["ln with no flag makes a hard link: ln SOURCE LINKNAME", "ln -s makes a symbolic link.", "ls -li shows inode numbers: a hard link shares the inode."],
        solution=["cd dir1", "ln file2 file2-hl", "ln -s file3 file3-sl", "ls -li", "rm file2 file3", "cat file2-hl"], par=4)


def _links_dead(fs):
    """The original file2 is gone and nothing links to it: goal 1 can never be met."""
    if fs.sys.get("m_ino") in fs.inodes:
        return None
    return ("The ORIGINAL file2 (with the payroll data) has been deleted while nothing was hard-linked to it, so its data is gone "
            "and goal 1 (a hard link to that file) can't be completed any more.")


def _links_warn(fs):
    hl = node(fs, H + "/dir1/file2-hl", False)
    orig = fs.sys.get("m_ino")
    if hl is not None and orig in fs.inodes and hl.ino != orig and hl.kind == "f":
        return ("~/dir1/file2-hl is a separate file, not a hard link to file2: ls -li shows two different inode numbers. "
                "rm file2-hl, then make the link with  ln file2 file2-hl  (existing file first, new name second).")
    sl = node(fs, H + "/dir1/file3-sl", False)
    if sl is not None and sl.kind == "f":
        return ("~/dir1/file3-sl is an ordinary file (ls -l starts with -), not a symbolic link (a symlink starts with l and shows -> file3). "
                "touch makes plain files. rm file3-sl, then  ln -s file3 file3-sl")
    if sl is not None and sl.kind == "l" and not sl.target.endswith("file3"):
        return "~/dir1/file3-sl is a symlink, but it points at %s instead of file3. rm file3-sl, then  ln -s file3 file3-sl" % sl.target
    return None


def s_needle(fs, sh):
    for p in ["/srv/data/2023/q1/notes.txt", "/srv/data/2023/q4/secret.key.bak", "/srv/data/2024/q2/report.pdf",
              "/srv/data/2024/q3/backup/secret.key", "/srv/data/keys/README", "/srv/www/index.html"]:
        fs.put(p, "content of %s\n" % p.split("/")[-1])


mission(id="needle", level=1, title="Needle in a Haystack",
        brief="Somebody hid the TLS key 'secret.key' somewhere under /srv. Security needs its exact path, today.",
        goals=["Save the absolute path of the file named exactly secret.key (under /srv) into ~/found.txt",
               "found.txt must contain only that path (not the .bak decoy)"],
        setup=s_needle,
        check=lambda fs, sh: [lines(fs, H + "/found.txt") is not None and "/srv/data/2024/q3/backup/secret.key" in lines(fs, H + "/found.txt"),
                              lines(fs, H + "/found.txt") == ["/srv/data/2024/q3/backup/secret.key"]],
        hints=["find {where} -name {pattern}", "Start the search at /srv so the output is an absolute path.", "Redirect the output with > ~/found.txt"],
        solution=["find /srv -name secret.key > ~/found.txt", "cat found.txt"], par=1)


def s_columns(fs, sh):
    mkfile(fs, H + "/motd.txt", "maintenance window tonight at 10 pm\n")


def _users_sorted(fs):
    return sorted(l.split(":")[0] for l in fs.read("/etc/passwd", "root").split("\n") if l)


mission(id="columns", level=1, title="Column Surgeon",
        brief="The auditor wants three quick reports from /etc/passwd and the message of the day. No editors allowed: text tools only.",
        goals=["~/users.txt: every username from /etc/passwd (field 1), sorted A-Z",
               "~/count.txt: the number of lines in /etc/passwd (wc)",
               "~/LOUD.txt: the text of ~/motd.txt converted to UPPERCASE"],
        setup=s_columns,
        check=lambda fs, sh: [lines(fs, H + "/users.txt") == _users_sorted(fs),
                              bool(lines(fs, H + "/count.txt")) and lines(fs, H + "/count.txt")[0].split()[0] == "12",
                              text(fs, H + "/LOUD.txt") == "MAINTENANCE WINDOW TONIGHT AT 10 PM\n"],
        hints=["cut -d: -f1 picks the first colon-separated field. Pipe it into sort.", "wc -l counts lines.", "tr a-z A-Z translates; feed it the file with < or cat |"],
        solution=["cut -d: -f1 /etc/passwd | sort > users.txt", "wc -l /etc/passwd > count.txt", "tr a-z A-Z < motd.txt > LOUD.txt"], par=3)

# ============================================================================= Level 2: Module 7
mission(id="log-hunter", level=2, title="Log Hunter",
        brief="Linux01 is being brute-forced. As the security analyst, pull the evidence out of /var/log/secure (it is root-only).",
        goals=["~/fails.txt: the COUNT of 'failed password' lines, ignoring case",
               "~/attacker.txt: every line in /var/log/secure that mentions 192.168.1.103"],
        setup=lambda fs, sh: None,
        check=lambda fs, sh: [bool(lines(fs, H + "/fails.txt")) and lines(fs, H + "/fails.txt")[0].strip().split()[0] == "6",
                              lines(fs, H + "/attacker.txt") == [l for l in fs.read("/var/log/secure", "root").split("\n") if "192.168.1.103" in l]],
        hints=["The log is root-only: you'll need sudo in front of grep.", "grep -i ignores case and -c counts. They combine: -ic",
               "Quote patterns that contain spaces: \"Failed password\""],
        solution=["sudo grep -ic \"failed password\" /var/log/secure > fails.txt", "sudo grep 192.168.1.103 /var/log/secure > attacker.txt"], par=2)


def s_clean(fs, sh):
    for i in range(1, 6):
        mkfile(fs, H + "/work/cache%d.tmp" % i, "temp\n")
    mkfile(fs, H + "/work/old/2023/report.txt", "old\n")
    mkfile(fs, H + "/work/old/notes.txt", "old notes\n")
    fs.mkdir(H + "/work/empty", fs.user)
    mkfile(fs, H + "/work/keep.txt", "KEEP ME\n")
    mkfile(fs, H + "/work/notes.txt", "meeting notes\n")


mission(id="spring-cleaning", level=2, title="Spring Cleaning",
        brief="~/work is a mess. Clean it without losing anything important. There is no recycle bin on Linux.",
        goals=["Remove every *.tmp file in ~/work", "Remove the directory ~/work/old and everything in it",
               "Remove the EMPTY directory ~/work/empty", "Create ~/work/archive and MOVE (not copy) notes.txt into it",
               "keep.txt must survive"],
        setup=s_clean,
        check=lambda fs, sh: [not any(n.endswith(".tmp") for n in fs.listdir(H + "/work")) if fs.isdir(H + "/work") else False,
                              not fs.exists(H + "/work/old"), not fs.exists(H + "/work/empty"),
                              text(fs, H + "/work/archive/notes.txt") == "meeting notes\n" and not fs.exists(H + "/work/notes.txt"),
                              text(fs, H + "/work/keep.txt") == "KEEP ME\n"],
        hints=["A wildcard: rm *.tmp", "rmdir only removes empty directories; rm -R removes a tree.", "mv moves; cp leaves the original behind."],
        solution=["cd work", "rm *.tmp", "rm -R old", "rmdir empty", "mkdir archive", "mv notes.txt archive"], par=6)

mission(id="redirect-rodeo", level=2, title="Redirect Rodeo",
        brief="Build a status report and capture errors separately. One wrong > and you wipe the file.",
        goals=["~/report.txt contains exactly 3 lines: Report / disk ok / net ok",
               "~/errors.txt holds ONLY the error from: ls /nope",
               "~/both.log holds BOTH the output and the error of: ls /etc/hosts /nope"],
        setup=lambda fs, sh: None,
        check=lambda fs, sh: [lines(fs, H + "/report.txt") == ["Report", "disk ok", "net ok"],
                              text(fs, H + "/errors.txt") is not None and "No such file" in text(fs, H + "/errors.txt") and "/etc/hosts" not in text(fs, H + "/errors.txt"),
                              text(fs, H + "/both.log") is not None and "/etc/hosts" in text(fs, H + "/both.log") and "No such file" in text(fs, H + "/both.log")],
        hints=["> overwrites, >> appends.", "2> sends only stderr (errors) to a file.", "&> sends stdout AND stderr to the same file."],
        solution=["echo Report > report.txt", "echo \"disk ok\" >> report.txt", "echo \"net ok\" >> report.txt", "ls /nope 2> errors.txt", "ls /etc/hosts /nope &> both.log"], par=5)


def s_pipe(fs, sh):
    for i in range(1, 5):
        mkfile(fs, H + "/cache/app%d.log" % i, "log %d\n" % i)
    mkfile(fs, H + "/cache/keep.conf", "setting=1\n")


mission(id="plumber", level=2, title="Pipeline Plumber",
        brief="Chain commands like a pro: show-and-save, run-only-if-it-worked, and feed a list into another command.",
        goals=["Show the hostname on screen AND save it in ~/host.txt with ONE command line (tee)",
               "On ONE line, create ~/deploy and, only if that worked, create ~/deploy/ok.txt (&&)",
               "Delete all *.log files in ~/cache by piping a listing into xargs (keep.conf stays)"],
        setup=s_pipe,
        check=lambda fs, sh: [text(fs, H + "/host.txt") == "rocky01\n" and ran(sh, "tee"),
                              fs.exists(H + "/deploy/ok.txt") and history_has(sh, "&&", "deploy"),
                              fs.isdir(H + "/cache") and fs.listdir(H + "/cache") == ["keep.conf"] and ran(sh, "xargs")],
        hints=["hostname | tee FILE", "mkdir DIR && touch DIR/ok.txt", "ls cache/*.log | xargs rm"],
        solution=["hostname | tee host.txt", "mkdir deploy && touch deploy/ok.txt", "ls cache/*.log | xargs rm"], par=3)

# ============================================================================= Level 4: Module 9
mission(id="backup-bunker", level=4, title="Backup Bunker",
        brief="The instructor's Review exercise, for real: create two files, archive them, compress them two ways, and fingerprint one.",
        goals=["Create the files file10 and file20 in your home directory",
               "Make backup.tar from file10 and file20, then compress backup.tar with bzip2 (-> backup.tar.bz2)",
               "Make a gzip-compressed tarball backup.tar.gz of the same two files in one tar command",
               "~/hashes.txt: the MD5 hash of file10, then its SHA1 hash appended"],
        setup=lambda fs, sh: None,
        check=lambda fs, sh: [fs.exists(H + "/file10") and fs.exists(H + "/file20"),
                              sorted(tar_members(fs, H + "/backup.tar.bz2", "bz2") or []) == ["file10", "file20"],
                              sorted(tar_members(fs, H + "/backup.tar.gz", "gz") or []) == ["file10", "file20"],
                              _hashes_ok(fs)],
        hints=["tar -cvf NAME.tar files... creates; add z for gzip.", "bzip2 FILE replaces FILE with FILE.bz2", "md5sum f > out ; sha1sum f >> out"],
        solution=["touch file10 file20", "tar -cvf backup.tar file10 file20", "tar -czvf backup.tar.gz file10 file20", "bzip2 backup.tar",
                  "md5sum file10 > hashes.txt", "sha1sum file10 >> hashes.txt"], par=6)


def _hashes_ok(fs):
    t = text(fs, H + "/hashes.txt")
    d = text(fs, H + "/file10")
    if t is None or d is None:
        return False
    return hexhash("md5", d) in t and hexhash("sha1", d) in t


def s_restore(fs, sh):
    files = {"site/index.html": "<h1>Rocky Web</h1>\n", "site/style.css": "body { color: green }\n", "site/app.js": "console.log('hi')\n"}
    arc = Archive("tar", [{"path": "site/", "kind": "d", "data": "", "mode": 0o755}] + [{"path": k, "kind": "f", "data": v, "mode": 0o644} for k, v in files.items()])
    mkfile(fs, H + "/site.tar.gz", "")
    fs.lookup(H + "/site.tar.gz").data = Comp("gz", arc, "site.tar")
    mkfile(fs, H + "/site.md5", "".join("%s  %s\n" % (hexhash("md5", v), k) for k, v in files.items()))


mission(id="restore-point", level=4, title="Restore Point",
        brief="The web server died. You have site.tar.gz and a checksum list (site.md5). Restore into ~/restore and prove nothing is corrupted.",
        goals=["Extract site.tar.gz so that ~/restore/site/index.html exists", "Verify the restored files with md5sum -c using ~/site.md5 (all OK)"],
        setup=s_restore,
        check=lambda fs, sh: [text(fs, H + "/restore/site/index.html") == "<h1>Rocky Web</h1>\n",
                              sh.check_ok.get("md5", False)],
        hints=["tar -x extracts; add z because it is gzip; -v shows names; -f names the file.", "Extract from inside ~/restore (cd there, then point tar at ../site.tar.gz).",
               "md5sum -c ../site.md5 must be run from the folder where the paths in the list make sense."],
        solution=["mkdir restore", "cd restore", "tar -xzvf ../site.tar.gz", "md5sum -c ../site.md5"], par=4)


def _verified(sh):
    return getattr(sh, "_md5_ok", False)


def s_tamper(fs, sh):
    docs = {"report%d.txt" % i: "Quarterly report %d. Revenue steady.\n" % i for i in range(1, 6)}
    for k, v in docs.items():
        mkfile(fs, H + "/evidence/" + k, v)
    mkfile(fs, H + "/evidence/evidence.sha256", "".join("%s  %s\n" % (hexhash("sha256", v), k) for k, v in docs.items()))
    fs.lookup(H + "/evidence/report3.txt").data = "Quarterly report 3. Revenue steady. (and wire $9,000 to account 4471)\n"


mission(id="tamper-alert", level=4, title="Tamper Alert",
        brief="One of the five reports in ~/evidence was altered after it was hashed. Find it using the saved SHA-256 list.",
        goals=["Check every file against ~/evidence/evidence.sha256", "Write the tampered file's name into ~/culprit.txt"],
        setup=s_tamper,
        check=lambda fs, sh: [ran(sh, "sha256sum", "-c"), lines(fs, H + "/culprit.txt") is not None and any("report3.txt" in l for l in lines(fs, H + "/culprit.txt")) and not any(("report%d" % i) in (text(fs, H + "/culprit.txt") or "") for i in (1, 2, 4, 5))],
        hints=["sha256sum -c LISTFILE checks each file and prints OK or FAILED.", "Run it inside ~/evidence so the names resolve.", "echo report?.txt > ~/culprit.txt"],
        solution=["cd evidence", "sha256sum -c evidence.sha256", "echo report3.txt > ~/culprit.txt"], par=3)


def s_contest(fs, sh):
    row = "2026-11-15,rocky01,cpu=12,mem=41,disk=77,net=3\n"
    mkfile(fs, H + "/bigdata.csv", "timestamp,host,cpu,mem,disk,net\n" + row * 600)


mission(id="compression-contest", level=4, title="Compression Contest",
        brief="Storage is full. Compress bigdata.csv with three tools, KEEP the original each time, then compare sizes.",
        goals=["Create bigdata.csv.gz, bigdata.csv.bz2 and bigdata.csv.xz (and keep bigdata.csv)",
               "Write the file name of the SMALLEST compressed file into ~/best.txt"],
        setup=s_contest,
        check=lambda fs, sh: [all(fs.exists(H + "/bigdata.csv" + s) for s in (".gz", ".bz2", ".xz")) and text(fs, H + "/bigdata.csv") is not None,
                              lines(fs, H + "/best.txt") is not None and "bigdata.csv.xz" in (text(fs, H + "/best.txt") or "") and ".gz" not in text(fs, H + "/best.txt") and ".bz2" not in text(fs, H + "/best.txt")],
        hints=["-k keeps the input file for gzip, bzip2 and xz.", "ls -lS sorts by size, largest first.", "Slides: gzip fastest/lower ratio, xz best ratio/slowest, bzip2 balanced."],
        solution=["gzip -k bigdata.csv", "bzip2 -k bigdata.csv", "xz -k bigdata.csv", "ls -lS", "echo bigdata.csv.xz > best.txt"], par=5)


def s_disk(fs, sh):
    storage.add_disk(fs, "sdb", 4096)
    storage.add_disk(fs, "sdc", 4096)
    fs.lookup("/dev/sdb").data = ("BOOTSECTOR" + "healthy-disk-data;" * 200)
    fs.lookup("/dev/sdc").data = ("BOOTSECTOR" + "dying-disk-photos;" * 200)
    fs.lookup("/dev/sdc").flaky = 2000


mission(id="disk-doctor", level=4, title="Disk Doctor",
        brief="Two drives need imaging before they go to the lab. /dev/sdb is healthy. /dev/sdc is failing (see /var/log/messages).",
        goals=["Image the whole of /dev/sdb into ~/sdb.img with dd", "Recover as much of failing /dev/sdc as possible into ~/sdc.img with ddrescue"],
        setup=s_disk,
        check=lambda fs, sh: [text(fs, H + "/sdb.img") == fs.lookup("/dev/sdb").data,
                              ran(sh, "ddrescue") and text(fs, H + "/sdc.img") is not None and len(text(fs, H + "/sdc.img")) == len(fs.lookup("/dev/sdc").data)],
        hints=["Raw disks are root-only: sudo.", "dd if=INPUT of=OUTPUT", "dd stops at the bad sector. ddrescue SOURCE DEST keeps going; if DEST already exists it needs -f."],
        solution=["sudo dd if=/dev/sdb of=sdb.img", "sudo ddrescue /dev/sdc sdc.img"], par=2)

# ============================================================================= Level 5: Module 10 (A)
def s_dep(fs, sh):
    mkfile(fs, H + "/Downloads/httpd-2.4.57-5.el9.x86_64.rpm", pkg.pkg_header("httpd"))


mission(id="dependency-hell", level=5, title="Dependency Hell",
        brief="Your boss downloaded the Apache web server package to ~/Downloads and says 'just rpm -i it'. Try it. Then do it properly.",
        goals=["Get httpd installed", "All of httpd's dependencies must be installed too (apr, apr-util, httpd-tools, httpd-filesystem)"],
        setup=s_dep,
        check=lambda fs, sh: [pkg.is_installed(fs, "httpd"), all(pkg.is_installed(fs, d) for d in ("apr", "apr-util", "httpd-tools", "httpd-filesystem"))],
        hints=["rpm -ivh FILE.rpm is the low-level way: it stops at 'Failed dependencies'.", "dnf (or yum) resolves dependencies automatically.",
               "Package managers need root. -y answers yes for you."],
        solution=["sudo rpm -ivh Downloads/httpd-2.4.57-5.el9.x86_64.rpm", "sudo dnf install -y httpd"], par=1)

mission(id="inventory", level=5, title="Inventory Day",
        brief="The instructor's review exercise: record what's installed, then remove and reinstall zip with two different tools.",
        goals=["~/softwarelist.txt: every installed package, from the rpm database (must still list zip)",
               "Remove zip using yum", "Install zip again using dnf"],
        setup=lambda fs, sh: None,
        check=lambda fs, sh: [text(fs, H + "/softwarelist.txt") is not None and "zip-3.0" in text(fs, H + "/softwarelist.txt") and len(lines(fs, H + "/softwarelist.txt")) >= 10,
                              ran(sh, "yum", "remove", "zip") or ran(sh, "yum", "erase", "zip"),
                              pkg.is_installed(fs, "zip") and ran(sh, "dnf", "install", "zip") and _after(sh, ("yum",), ("dnf", "install"))],
        hints=["rpm -qa lists every installed package. Redirect it.", "yum remove zip (needs sudo; -y skips the question)", "dnf install zip"],
        solution=["rpm -qa > softwarelist.txt", "rpm -qi zip", "sudo yum remove -y zip", "sudo dnf install -y zip"], par=3)


def _after(sh, first, second):
    i1 = i2 = -1
    for i, (argv, _) in enumerate(sh.cmdlog):
        if all(w in argv for w in first) and ("remove" in argv or "erase" in argv):
            i1 = i
        if all(w in argv for w in second):
            i2 = i
    return i1 != -1 and i2 > i1


DH = "/home/student"
mission(id="debian-duty", level=5, title="Debian Duty", distro="debian",
        brief="Different distro, different tools. On deb01 (Debian 12) install tree and nmap, then record the package list.",
        goals=["Install tree with apt", "Install nmap (APT must pull in its dependency libpcap0.8)", "~/softwarelist.txt: the installed-package list from dpkg -l (or apt list --installed)"],
        setup=lambda fs, sh: None,
        check=lambda fs, sh: ["tree" in pkg.state(fs)["dpkg"], "nmap" in pkg.state(fs)["dpkg"] and "libpcap0.8" in pkg.state(fs)["dpkg"],
                              text(fs, DH + "/softwarelist.txt") is not None and "tree" in text(fs, DH + "/softwarelist.txt")],
        hints=["'Unable to locate package'? The package lists are empty: sudo apt update", "sudo apt install -y tree nmap", "dpkg -l > softwarelist.txt"],
        solution=["sudo apt update", "sudo apt install -y tree nmap", "dpkg -l > softwarelist.txt"], par=3)

# ============================================================================= Level 6: Module 10 (B)
mission(id="download-day", level=6, title="Download Day",
        brief="No browser on a server. Fetch two source tarballs from the command line (the exact URLs from the slides) and unpack them.",
        goals=["Download http://download.samba.org/pub/samba/samba-latest.tar.gz with wget",
               "Download https://nmap.org/dist/nmap-7.70.tar.bz2 with curl, saving it as nmap-7.70.tar.bz2",
               "Extract both (samba-4.19/ and nmap-7.70/ appear in your home)"],
        setup=lambda fs, sh: None,
        check=lambda fs, sh: [fs.exists(H + "/samba-latest.tar.gz") and ran(sh, "wget"),
                              fs.exists(H + "/nmap-7.70.tar.bz2") and ran(sh, "curl"),
                              fs.isdir(H + "/samba-4.19") and fs.isdir(H + "/nmap-7.70")],
        hints=["wget URL saves using the remote file name.", "curl -o NAME URL saves to NAME (without -o it prints to the screen).", "gzip tarball: tar -xzvf ; bzip2 tarball: tar -xjvf"],
        solution=["wget http://download.samba.org/pub/samba/samba-latest.tar.gz", "curl -o nmap-7.70.tar.bz2 https://nmap.org/dist/nmap-7.70.tar.bz2",
                  "tar -xzvf samba-latest.tar.gz", "tar -xjvf nmap-7.70.tar.bz2"], par=4)


def s_repo(fs, sh):
    fs.put_dir("/repo", owner="rocky")
    fs.put("/repo/localtool-1.0-1.x86_64.rpm", pkg.pkg_header("localtool"), owner="rocky")
    fs.put("/etc/yum.repos.d/local.repo", "[local]\nname=Local Admin Tools\nbaseurl=file:///repo\nenabled=0\ngpgcheck=1\n")


def _repo_ok(fs):
    for r in pkg.parse_repo_files(fs):
        if r["id"] == "local":
            return r.get("enabled") == "1" and r.get("gpgcheck") == "0" and r.get("baseurl", "").rstrip("/") == "file:///repo"
    return False


mission(id="repo-rebellion", level=6, title="Repo Rebellion",
        brief="IT keeps in-house tools in a local repository at /repo. The repo was never indexed and its .repo file is misconfigured. Fix it and install localtool.",
        goals=["Turn /repo into a repository (index it with createrepo)", "Fix /etc/yum.repos.d/local.repo: enabled=1 and gpgcheck=0 (packages are unsigned)", "Install localtool with dnf"],
        setup=s_repo,
        check=lambda fs, sh: ["/repo" in pkg.state(fs)["localrepo"], _repo_ok(fs), pkg.is_installed(fs, "localtool")],
        hints=["createrepo /repo builds the repodata/ index.", "cat the .repo file. sudo sed -i 's/old/new/' FILE edits in place (redirects won't work on root files).",
               "dnf repolist all shows disabled repos. Then: sudo dnf install -y localtool"],
        solution=["createrepo /repo", "cat /etc/yum.repos.d/local.repo", "sudo sed -i 's/enabled=0/enabled=1/' /etc/yum.repos.d/local.repo",
                  "sudo sed -i 's/gpgcheck=1/gpgcheck=0/' /etc/yum.repos.d/local.repo", "sudo dnf install -y localtool"], par=4)

# ============================================================================= Level 7: Module 11 (Lessons 7.1-7.2)
def st(fs):
    return storage.S(fs)


def blk(fs, p):
    return st(fs)["blk"].get(p, {})


def fstab_for(fs, mp):
    for e in storage.fstab_entries(fs):
        if e["mp"] == mp:
            return e
    return None


def fstab_dev_is(fs, mp, dev, uuid_only=False):
    e = fstab_for(fs, mp)
    if not e:
        return False
    if e["dev"].startswith("UUID="):
        return e["dev"][5:].strip('"').lower() == storage.uuid_for(dev)
    return (not uuid_only) and e["dev"] == dev


def booted_ok(fs):
    return st(fs)["boots"] >= 1 and st(fs)["boot_ok"]


def ftext(fs, path):
    return (text(fs, path) or "").strip()


# -- Disk Detective (7.1: detect the hardware, read UUIDs and labels)
def s_detective(fs, sh):
    storage.add_disk(fs, "sdb", 8192, model="VMware Virtual disk")
    storage.add_part(fs, "/dev/sdb", 1, 1, 3072, fstype="ext4", label="payroll", ptable="gpt")
    storage.add_part(fs, "/dev/sdb", 2, 3073, 5118, fstype="xfs", label="archive")
    storage.add_disk(fs, "sdc", 4096)
    storage.add_disk(fs, "sdd", 2048)
    storage.add_part(fs, "/dev/sdd", 1, 1, 2047, fstype="ext4", label="scratch", ptable="dos")


def _uuid_file_ok(fs):
    t = ftext(fs, H + "/payroll-uuid.txt").replace('"', "")
    if t.upper().startswith("UUID="):
        t = t[5:]
    return t.lower() == storage.uuid_for("/dev/sdb1")


mission(id="disk-detective", level=7, title="Disk Detective",
        brief="Three disks were plugged into rocky01 over the weekend and nobody wrote anything down. Before anyone partitions anything, find out what's there.",
        goals=["Save a filesystem inventory (lsblk -f) to ~/inventory.txt",
               "Put the UUID of the partition labelled payroll (just the UUID) in ~/payroll-uuid.txt",
               "Write the device name of the disk that has NO partitions to ~/blank-disk.txt",
               "Write the partition table type of /dev/sdd (gpt or dos) to ~/sdd-table.txt"],
        setup=s_detective,
        check=lambda fs, sh: [all(x in ftext(fs, H + "/inventory.txt") for x in ("payroll", "sdd1", storage.uuid_for("/dev/sdb1"))),
                              _uuid_file_ok(fs),
                              ftext(fs, H + "/blank-disk.txt") in ("/dev/sdc", "sdc"),
                              ftext(fs, H + "/sdd-table.txt").lower() in ("dos", "msdos", "mbr")],
        hints=["lsblk -f > ~/inventory.txt  (redirect the output into the file)",
               "sudo blkid lists LABEL and UUID. blkid -s UUID -o value /dev/sdb1 prints just the UUID: redirect it into the file.",
               "lsblk shows which disk has no part rows under it. Then: echo /dev/sdX > ~/blank-disk.txt",
               "sudo fdisk -l /dev/sdd shows 'Disklabel type:' (or sudo parted /dev/sdd print -> 'Partition Table:')."],
        solution=["lsblk -f > ~/inventory.txt", "sudo blkid", "sudo blkid -s UUID -o value /dev/sdb1 > ~/payroll-uuid.txt", "lsblk",
                  "echo /dev/sdc > ~/blank-disk.txt", "sudo fdisk -l /dev/sdd", "echo dos > ~/sdd-table.txt"], par=6)


# -- fdisk Drill (7.1: the slide demo, MBR primary / extended / logical, partprobe)
def s_fdisk(fs, sh):
    storage.add_disk(fs, "sdb", 10240)
    storage.add_part(fs, "/dev/sdb", 1, 1, 4096, fstype="xfs", ptable="dos")
    fs.put_dir("/data")
    storage.attach(fs, "/dev/sdb1", "/data")
    fs.write("/etc/fstab", "/dev/sdb1 /data xfs defaults 0 0\n", "root", append=True)


def _logical(fs, num, lo=None, hi=None):
    v = blk(fs, "/dev/sdb%d" % num)
    if v.get("pkind") != "logical":
        return False
    return (lo is None or v["size"] >= lo) and (hi is None or v["size"] <= hi)


mission(id="fdisk-drill", level=7, title="fdisk Drill",
        brief="/dev/sdb (10 GB, MBR) has one 4 GB partition, mounted on /data and in use. Use the rest of the disk exactly the way the Module 11 demo does: fdisk, then tell the kernel.",
        goals=["Add an EXTENDED partition /dev/sdb2 that fills the rest of the disk",
               "Inside it create logical partitions /dev/sdb5 (2G) and /dev/sdb6 (the rest)",
               "Make the kernel see the new partitions without rebooting (the disk is busy)",
               "Format /dev/sdb5 as ext4 and turn /dev/sdb6 into active swap"],
        setup=s_fdisk,
        check=lambda fs, sh: [blk(fs, "/dev/sdb2").get("pkind") == "extended" and blk(fs, "/dev/sdb2").get("size", 0) >= 6000,
                              _logical(fs, 5, 1990, 2110) and _logical(fs, 6, 3000),
                              _logical(fs, 5) and not blk(fs, "/dev/sdb5").get("pending") and not blk(fs, "/dev/sdb6").get("pending"),
                              blk(fs, "/dev/sdb5").get("fstype") == "ext4" and "/dev/sdb6" in st(fs)["swaps"]],
        hints=["sudo fdisk /dev/sdb, then n, e (extended), Enter, Enter, Enter. Press p to look before w.",
               "Still in fdisk: n, l (logical), Enter, +2G. Then n, l, Enter, Enter. Then w.",
               "fdisk says 'Device or resource busy' because /data is mounted. sudo partprobe fixes that (cat /proc/partitions to check).",
               "sudo mkfs.ext4 /dev/sdb5 ; sudo mkswap /dev/sdb6 ; sudo swapon /dev/sdb6"],
        solution=["sudo fdisk -l /dev/sdb", "printf 'n\\ne\\n\\n\\n\\nn\\nl\\n\\n+2G\\nn\\nl\\n\\n\\np\\nw\\n' | sudo fdisk /dev/sdb",
                  "sudo partprobe", "cat /proc/partitions", "sudo mkfs.ext4 /dev/sdb5", "sudo mkswap /dev/sdb6", "sudo swapon /dev/sdb6"], par=7)


# -- New Disk Day (7.1: the 7-step storage deployment summary)
def s_newdisk(fs, sh):
    storage.add_disk(fs, "sdb", 10240)


def _rocky_wrote(fs, dev, name):
    r = st(fs)["fsroot"].get(dev)
    if not r or name not in r["entries"]:
        return False
    n = fs.inodes.get(r["entries"][name])
    return n is not None and n.owner == "rocky"


mission(id="new-disk", level=7, title="New Disk Day",
        brief="A new 10 GB disk /dev/sdb was added for downloads. Follow the slides' storage deployment summary from 'Linux sees it' to 'it comes back after a reboot'.",
        goals=["Give /dev/sdb a GPT table with one partition /dev/sdb1 using the whole disk (parted)",
               "Format /dev/sdb1 with XFS and mount it on /opt/downloads",
               "Let rocky write there: create /opt/downloads/test.txt AS rocky (no sudo)",
               "Add /dev/sdb1 (or its UUID) on /opt/downloads, type xfs, to /etc/fstab",
               "Reboot cleanly with the disk back on /opt/downloads"],
        setup=s_newdisk,
        check=lambda fs, sh: [blk(fs, "/dev/sdb").get("ptable") == "gpt" and blk(fs, "/dev/sdb1").get("size", 0) >= 10000,
                              blk(fs, "/dev/sdb1").get("fstype") == "xfs" and st(fs)["mounts"].get("/opt/downloads") == "/dev/sdb1",
                              _rocky_wrote(fs, "/dev/sdb1", "test.txt"),
                              fstab_dev_is(fs, "/opt/downloads", "/dev/sdb1") and (fstab_for(fs, "/opt/downloads") or {}).get("type") == "xfs",
                              booted_ok(fs) and st(fs)["mounts"].get("/opt/downloads") == "/dev/sdb1"],
        hints=["lsblk or hwinfo --block to confirm Linux sees sdb. Then sudo parted /dev/sdb: mklabel gpt, mkpart primary xfs 1MiB 100%, print, quit.",
               "sudo mkfs.xfs /dev/sdb1 ; sudo mkdir /opt/downloads ; sudo mount /dev/sdb1 /opt/downloads",
               "The mount point now shows the new filesystem, owned by root: sudo chown rocky:rocky /opt/downloads, then touch /opt/downloads/test.txt",
               "echo '/dev/sdb1 /opt/downloads xfs defaults 0 0' | sudo tee -a /etc/fstab  (a > redirect would fail: it runs as rocky)",
               "Test with sudo mount -a, then sudo reboot, then lsblk -f / mount | grep sdb1."],
        solution=["lsblk", "sudo parted -s /dev/sdb mklabel gpt mkpart primary xfs 1MiB 100%", "sudo parted /dev/sdb print", "sudo mkfs.xfs /dev/sdb1",
                  "sudo mkdir /opt/downloads", "sudo mount /dev/sdb1 /opt/downloads", "sudo chown rocky:rocky /opt/downloads", "touch /opt/downloads/test.txt",
                  "echo '/dev/sdb1 /opt/downloads xfs defaults 0 0' | sudo tee -a /etc/fstab", "sudo mount -a", "sudo reboot", "mount | grep sdb1"], par=11)


# -- Filesystem Fixer (7.1: ext and XFS tools)
def s_fixer(fs, sh):
    storage.add_disk(fs, "sdb", 5120)
    storage.add_part(fs, "/dev/sdb", 1, 1, 5118, fstype="ext4", ptable="gpt")
    storage.S(fs)["blk"]["/dev/sdb1"]["errors"] = True
    fs.put_dir("/archive")
    storage.attach(fs, "/dev/sdb1", "/archive")
    fs.write("/archive/2025-q4.tar.gz", "archive data\n", "root")
    fs.write("/etc/fstab", "/dev/sdb1 /archive ext4 defaults 0 0\n", "root", append=True)
    storage.add_disk(fs, "sdc", 2048)
    storage.add_part(fs, "/dev/sdc", 1, 1, 2046, fstype="xfs", ptable="gpt")
    old = fs.read("/var/log/messages", "root")
    fs.put("/var/log/messages", old + "Nov 15 12:01:44 rocky01 kernel: EXT4-fs error (device sdb1): ext4_lookup:1855: inode #12: comm ls: deleted inode referenced: 1234\n", mode=0o600)


mission(id="fs-fixer", level=7, title="Filesystem Fixer",
        brief="The kernel log is complaining about the ext4 filesystem on /dev/sdb1 (mounted on /archive). Repair it, tidy up its settings, and label the spare XFS partition while you're there.",
        goals=["Repair the ext4 filesystem on /dev/sdb1 with fsck (it must be UNMOUNTED first)",
               "Label /dev/sdb1 archive (e2label or tune2fs -L)",
               "Cut its reserved blocks to 1% (tune2fs -m)",
               "Put /dev/sdb1 back on /archive",
               "Label the XFS partition /dev/sdc1 scratch (xfs_admin -L)"],
        setup=s_fixer,
        check=lambda fs, sh: [not blk(fs, "/dev/sdb1").get("errors"), blk(fs, "/dev/sdb1").get("label") == "archive",
                              blk(fs, "/dev/sdb1").get("reserved") == 1, st(fs)["mounts"].get("/archive") == "/dev/sdb1",
                              blk(fs, "/dev/sdc1").get("label") == "scratch"],
        hints=["sudo grep -i error /var/log/messages ; sudo tune2fs -l /dev/sdb1 shows 'Filesystem state'.",
               "fsck refuses a mounted filesystem: sudo umount /archive, then sudo fsck -y /dev/sdb1",
               "sudo e2label /dev/sdb1 archive ; sudo tune2fs -m 1 /dev/sdb1",
               "sudo mount /archive  (one argument: mount looks it up in /etc/fstab)",
               "sudo xfs_admin -L scratch /dev/sdc1 ; check with sudo blkid or lsblk -f"],
        solution=["sudo grep -i error /var/log/messages", "sudo umount /archive", "sudo fsck -y /dev/sdb1", "sudo e2label /dev/sdb1 archive",
                  "sudo tune2fs -m 1 /dev/sdb1", "sudo mount /archive", "sudo xfs_admin -L scratch /dev/sdc1", "lsblk -f"], par=7)


# -- Swap Shop (7.1: swap partition + swap file, persistent)
def s_swap(fs, sh):
    storage.add_disk(fs, "sdb", 4096)
    t = fs.read("/etc/fstab", "root").replace("/dev/mapper/rl-swap     none                    swap    defaults        0 0\n", "")
    fs.put("/etc/fstab", t)


def _swapfile_ok(fs):
    n = node(fs, "/swapfile")
    return n is not None and n.size() >= 1024 * 1048576 and (n.mode & 0o777) == 0o600 and "/swapfile" in st(fs)["swaps"]


def _fstab_swap(fs, dev):
    for e in storage.fstab_entries(fs):
        if e["type"] == "swap" and (e["dev"] == dev or (e["dev"].startswith("UUID=") and e["dev"][5:].strip('"').lower() == storage.uuid_for(dev))):
            return True
    return False


mission(id="swap-shop", level=7, title="Swap Shop",
        brief="rocky01 was built with 1.9 GB of RAM and NO swap, and the database keeps getting killed. Add swap two ways (the slides list device swap and file swap) and make both permanent.",
        goals=["Make a 2G partition /dev/sdb1 on the new disk, turn it into swap and switch it on",
               "Create a 1 GiB swap file /swapfile with dd, permissions 600, and switch it on",
               "Add both to /etc/fstab (type swap)",
               "Reboot and check that both swap areas come back"],
        setup=s_swap,
        check=lambda fs, sh: [blk(fs, "/dev/sdb1").get("fstype") == "swap" and 1990 <= blk(fs, "/dev/sdb1").get("size", 0) <= 2110 and "/dev/sdb1" in st(fs)["swaps"],
                              _swapfile_ok(fs), _fstab_swap(fs, "/dev/sdb1") and _fstab_swap(fs, "/swapfile"),
                              booted_ok(fs) and "/dev/sdb1" in st(fs)["swaps"] and "/swapfile" in st(fs)["swaps"]],
        hints=["free -h and swapon --show first. sudo fdisk /dev/sdb: n, p, Enter, Enter, +2G, then t and 82 (Linux swap), then w.",
               "sudo mkswap /dev/sdb1 ; sudo swapon /dev/sdb1",
               "sudo dd if=/dev/zero of=/swapfile bs=1M count=1024 ; sudo chmod 600 /swapfile ; sudo mkswap /swapfile ; sudo swapon /swapfile",
               "echo '/dev/sdb1 none swap defaults 0 0' | sudo tee -a /etc/fstab  (and the same for /swapfile). Then sudo reboot ; swapon --show"],
        solution=["free -h", "printf 'n\\np\\n\\n\\n+2G\\nt\\n82\\nw\\n' | sudo fdisk /dev/sdb", "sudo mkswap /dev/sdb1", "sudo swapon /dev/sdb1",
                  "sudo dd if=/dev/zero of=/swapfile bs=1M count=1024", "sudo chmod 600 /swapfile", "sudo mkswap /swapfile", "sudo swapon /swapfile",
                  "echo '/dev/sdb1 none swap defaults 0 0' | sudo tee -a /etc/fstab", "echo '/swapfile none swap defaults 0 0' | sudo tee -a /etc/fstab",
                  "sudo reboot", "swapon --show"], par=11)


# -- LVM Builder (7.2)
def s_lvm(fs, sh):
    storage.add_disk(fs, "sdc", 2048)
    storage.add_disk(fs, "sdd", 2048)


def _lv(fs):
    return st(fs)["lv"].get(("vg0", "lvdata"))


mission(id="lvm-builder", level=7, title="LVM Builder",
        brief="Pool two 2 GB disks with LVM (physical volumes -> volume group -> logical volumes), carve out a volume for the app, then grow it without a reboot when the app gets popular.",
        goals=["Make /dev/sdc and /dev/sdd physical volumes", "Create volume group vg0 from both", "Create a 2G logical volume lvdata in vg0, format it ext4, mount it on /srv/app",
               "Extend lvdata by 1G AND grow the filesystem to match"],
        setup=s_lvm,
        check=lambda fs, sh: [all(d in st(fs)["pv"] for d in ("/dev/sdc", "/dev/sdd")),
                              sorted(st(fs)["vg"].get("vg0", {}).get("pvs", [])) == ["/dev/sdc", "/dev/sdd"],
                              _lv(fs) is not None and blk(fs, "/dev/vg0/lvdata").get("fstype") == "ext4" and st(fs)["mounts"].get("/srv/app") == "/dev/vg0/lvdata",
                              (_lv(fs) or 0) >= 3072 and blk(fs, "/dev/vg0/lvdata").get("fs_size", 0) >= 3072],
        hints=["Order: pvcreate -> vgcreate -> lvcreate -> mkfs -> mount. Check each step with pvs, vgs, lvs.", "sudo lvcreate -L 2G -n lvdata vg0",
               "sudo lvextend -L +1G /dev/vg0/lvdata, then sudo resize2fs /dev/vg0/lvdata (ext4). Or lvextend -r does both."],
        solution=["sudo pvcreate /dev/sdc /dev/sdd", "sudo vgcreate vg0 /dev/sdc /dev/sdd", "sudo lvcreate -L 2G -n lvdata vg0", "sudo mkfs.ext4 /dev/vg0/lvdata",
                  "sudo mkdir -p /srv/app", "sudo mount /dev/vg0/lvdata /srv/app", "sudo lvextend -L +1G /dev/vg0/lvdata", "sudo resize2fs /dev/vg0/lvdata"], par=8)


# ============================================================================= Level 8: Module 12 (Lessons 7.3-7.4, preview)
# -- Mount Point Mystery (files hidden under a mount point)
MEDIA = ("lecture01.mp4", "lecture02.mp4", "notes.txt")


def s_mystery(fs, sh):
    storage.add_disk(fs, "sdb", 8192)
    storage.add_part(fs, "/dev/sdb", 1, 1, 8190, fstype="xfs", ptable="gpt")
    fs.put_dir("/srv/media", owner="rocky", mode=0o755)
    from .vfs import Blob
    for name in MEDIA:
        n = fs.put("/srv/media/" + name, "", owner="rocky")
        n.data = Blob(700 * 1048576) if name.endswith(".mp4") else "Week 12 notes: mount, fstab, UUIDs\n"


def _media_dead(fs):
    """A lecture file no longer exists anywhere (visible tree, hidden under a mount, or on an unmounted disk)."""
    alive = set()
    s = storage.S(fs)
    stacks = [fs.root.entries] + [u["entries"] for u in s["under"].values()] + [r["entries"] for r in s["fsroot"].values()]
    seen = set()
    while stacks:
        ents = stacks.pop()
        for name, ino in ents.items():
            if ino in seen:
                continue
            seen.add(ino)
            alive.add(name)
            n = fs.inodes.get(ino)
            if n is not None and n.kind == "d":
                stacks.append(n.entries)
    lost = [x for x in MEDIA if x not in alive]
    if not lost:
        return None
    return "%s was deleted, so it can never end up on the new disk." % ", ".join(lost)


def _media_on_disk(fs):
    return all(x in storage.mounted_entries(fs, "/dev/sdb1") for x in MEDIA)


mission(id="mount-mystery", level=8, title="Mount Point Mystery",
        brief="The media team copied 1.4 GB of lectures into /srv/media, but nobody had mounted the new disk /dev/sdb1 there, so the files landed on the root filesystem. Move them onto the disk where they belong.",
        goals=["Get all three files onto the new disk /dev/sdb1",
               "Leave nothing behind underneath /srv/media on the root filesystem",
               "Mount /dev/sdb1 on /srv/media, owned by rocky so the team can keep writing",
               "Make it permanent in /etc/fstab using the UUID (not /dev/sdb1)",
               "Reboot cleanly with the disk back on /srv/media"],
        setup=s_mystery,
        dead=lambda fs, sh: _media_dead(fs),
        check=lambda fs, sh: [_media_on_disk(fs), _media_on_disk(fs) and not storage.under_entries(fs, "/srv/media"),
                              st(fs)["mounts"].get("/srv/media") == "/dev/sdb1" and node(fs, "/srv/media").owner == "rocky",
                              fstab_dev_is(fs, "/srv/media", "/dev/sdb1", uuid_only=True),
                              booted_ok(fs) and st(fs)["mounts"].get("/srv/media") == "/dev/sdb1"],
        hints=["If you mount the disk on /srv/media now, the files don't vanish: they're hidden UNDER the mount. Mount the disk somewhere else first, e.g. /mnt.",
               "sudo mount /dev/sdb1 /mnt ; sudo mv /srv/media/* /mnt/ ; sudo umount /mnt",
               "sudo mount /dev/sdb1 /srv/media ; sudo chown rocky:rocky /srv/media",
               "sudo blkid -s UUID -o value /dev/sdb1 gives the UUID. echo 'UUID=... /srv/media xfs defaults 0 0' | sudo tee -a /etc/fstab ; sudo mount -a ; sudo reboot"],
        solution=["df -h", "sudo mount /dev/sdb1 /mnt", "sudo mv /srv/media/lecture01.mp4 /srv/media/lecture02.mp4 /srv/media/notes.txt /mnt/", "sudo umount /mnt",
                  "sudo mount /dev/sdb1 /srv/media", "sudo chown rocky:rocky /srv/media", "sudo blkid /dev/sdb1",
                  "echo 'UUID=%s /srv/media xfs defaults 0 0' | sudo tee -a /etc/fstab" % storage.uuid_for("/dev/sdb1"), "sudo mount -a", "sudo reboot"], par=10)


# -- Boot Breaker (fstab troubleshooting)
def s_breaker(fs, sh):
    storage.add_disk(fs, "sdb", 6144)
    storage.add_part(fs, "/dev/sdb", 1, 1, 3072, fstype="xfs", label="web", ptable="gpt")
    storage.add_part(fs, "/dev/sdb", 2, 3073, 3070, fstype="ext4", label="backup")
    storage.add_disk(fs, "sdc", 2048)
    storage.add_part(fs, "/dev/sdc", 1, 1, 2046, fstype="xfs", label="reports", ptable="gpt")
    fs.put_dir("/var/www")
    fs.put_dir("/backup")
    real = storage.uuid_for("/dev/sdb1")
    typo = real[:-1] + ("0" if real[-1] != "0" else "1")
    fs.write("/etc/fstab", "UUID=%s /var/www xfs defaults 0 0\n/dev/sdb2 /backup xfs defaults 0 0\n/dev/sdc1 /reports xfs defaults 0 0\n" % typo, "root", append=True)
    storage.S(fs)["boot_ok"] = False


def _all_three(fs):
    m = st(fs)["mounts"]
    return m.get("/var/www") == "/dev/sdb1" and m.get("/backup") == "/dev/sdb2" and m.get("/reports") == "/dev/sdc1"


mission(id="boot-breaker", level=8, title="Boot Breaker",
        brief="After last night's maintenance rocky01 boots into EMERGENCY MODE. Someone added three lines to /etc/fstab and every one of them is wrong in a different way.",
        goals=["Fix the /var/www line (its UUID is wrong: blkid shows the real one)",
               "Fix the /backup line (wrong filesystem type)",
               "Fix /reports (its mount point doesn't exist)",
               "Reboot cleanly with all three filesystems mounted"],
        setup=s_breaker,
        check=lambda fs, sh: [fstab_dev_is(fs, "/var/www", "/dev/sdb1"), (fstab_for(fs, "/backup") or {}).get("type") == "ext4",
                              node(fs, "/reports") is not None and node(fs, "/reports").kind == "d",
                              booted_ok(fs) and _all_three(fs)],
        hints=["cat /etc/fstab, then sudo mount -a: each error message names the broken line.",
               "sudo blkid /dev/sdb1 shows the real UUID. Fix it with sudo sed -i 's/OLD/NEW/' /etc/fstab (copy the last few characters).",
               "lsblk -f shows /dev/sdb2 is ext4: sudo sed -i 's/backup xfs/backup ext4/' /etc/fstab",
               "sudo mkdir /reports. Then sudo mount -a must print nothing. Then sudo reboot."],
        solution=["cat /etc/fstab", "sudo mount -a", "sudo blkid",
                  "sudo sed -i 's/UUID=[0-9a-f-]* \\/var\\/www/UUID=%s \\/var\\/www/' /etc/fstab" % storage.uuid_for("/dev/sdb1"),
                  "sudo sed -i 's/backup xfs/backup ext4/' /etc/fstab", "sudo mkdir /reports", "sudo mount -a", "sudo reboot"], par=8)


# -- Quota Cop (disk quotas)
def s_quota(fs, sh):
    storage.add_disk(fs, "sdb", 4096)
    storage.add_part(fs, "/dev/sdb", 1, 1, 4094, fstype="ext4", ptable="gpt")
    fs.put_dir("/home2")
    storage.attach(fs, "/dev/sdb1", "/home2")
    fs.write("/etc/fstab", "/dev/sdb1 /home2 ext4 defaults 0 0\n", "root", append=True)
    from .vfs import Blob
    fs.mkdir("/home2/bob", "root")
    n = fs.lookup("/home2/bob")
    n.owner = n.group = "bob"
    n.mode = 0o700
    f = fs.put("/home2/bob/videos.tar", "", owner="bob")
    f.data = Blob(450 * 1048576)


def _qopts(fs):
    e = fstab_for(fs, "/home2") or {}
    o = e.get("opts", "").split(",")
    return "usrquota" in o and "grpquota" in o


def _bob(fs):
    q = st(fs)["quota"].get("/home2", {})
    lim = q.get("users", {}).get("bob")
    return bool(lim) and 500000 <= lim[0] <= 512000 and 600000 <= lim[1] <= 614400


mission(id="quota-cop", level=8, title="Quota Cop",
        brief="bob keeps filling /home2 with videos. Turn on disk quotas for /home2 and give bob a soft limit of 500 MB and a hard limit of 600 MB.",
        goals=["Enable user AND group quotas for /home2 in /etc/fstab (usrquota,grpquota)",
               "Apply them without rebooting and build the quota files (quotacheck)",
               "Turn quotas on for /home2",
               "Limit bob: soft 500 MB, hard 600 MB (in 1K blocks: 512000 / 614400)"],
        setup=s_quota,
        check=lambda fs, sh: [_qopts(fs),
                              all(storage._quota_opts(st(fs), "/home2")) and st(fs)["quota"].get("/home2", {}).get("checked", False) and "aquota.user" in storage.mounted_entries(fs, "/dev/sdb1"),
                              st(fs)["quota"].get("/home2", {}).get("on", False), _bob(fs)],
        hints=["sudo sed -i 's/home2 ext4 defaults/home2 ext4 defaults,usrquota,grpquota/' /etc/fstab",
               "sudo mount -o remount /home2 (re-reads fstab options; check with mount), then sudo quotacheck -cug /home2",
               "sudo quotaon /home2",
               "sudo setquota -u bob 512000 614400 0 0 /home2 ; sudo repquota /home2"],
        solution=["sudo sed -i 's/home2 ext4 defaults/home2 ext4 defaults,usrquota,grpquota/' /etc/fstab", "sudo mount -o remount /home2", "mount | grep home2",
                  "sudo quotacheck -cug /home2", "sudo quotaon /home2", "sudo setquota -u bob 512000 614400 0 0 /home2", "sudo repquota /home2"], par=6)


# -- RAID Rescue (software RAID 1)
def s_raid(fs, sh):
    for d in ("sdb", "sdc", "sdd"):
        storage.add_disk(fs, d, 2048)
    storage.make_md(fs, "/dev/md0", 1, ["/dev/sdb", "/dev/sdc"], fstype="xfs")
    fs.put_dir("/srv/vault")
    storage.attach(fs, "/dev/md0", "/srv/vault")
    fs.write("/srv/vault/grades-fall2026.csv", "id,grade\n1001,A\n1002,B\n", "root")
    fs.write("/etc/fstab", "/dev/md0 /srv/vault xfs defaults 0 0\n", "root", append=True)


def _md(fs):
    return st(fs)["md"].get("/dev/md0", {"members": [], "failed": [], "spares": []})


mission(id="raid-rescue", level=8, title="RAID Rescue",
        brief="/dev/md0 is a software RAID 1 mirror of /dev/sdb and /dev/sdc, mounted on /srv/vault. The kernel log says sdc is throwing I/O errors. Swap in the spare disk /dev/sdd without losing the data or unmounting.",
        goals=["Mark the failing disk /dev/sdc as faulty and remove it from /dev/md0",
               "Add the spare /dev/sdd so the mirror is healthy again ([UU] in /proc/mdstat)",
               "Save the array's details (mdadm --detail) to ~/md0-status.txt",
               "Record the array in /etc/mdadm.conf (mdadm --detail --scan)"],
        setup=s_raid,
        check=lambda fs, sh: ["/dev/sdc" not in _md(fs)["members"] and "/dev/sdc" not in _md(fs)["failed"],
                              _md(fs)["members"] == ["/dev/sdb", "/dev/sdd"] and st(fs)["mounts"].get("/srv/vault") == "/dev/md0",
                              all(x in ftext(fs, H + "/md0-status.txt") for x in ("/dev/sdd", "clean")) and "degraded" not in ftext(fs, H + "/md0-status.txt"),
                              "ARRAY /dev/md0" in ftext(fs, "/etc/mdadm.conf")],
        hints=["sudo grep sdc /var/log/messages ; cat /proc/mdstat",
               "sudo mdadm /dev/md0 --fail /dev/sdc, then sudo mdadm /dev/md0 --remove /dev/sdc (remove only works once it's failed)",
               "sudo mdadm /dev/md0 --add /dev/sdd ; cat /proc/mdstat should show [2/2] [UU]",
               "sudo mdadm --detail /dev/md0 > ~/md0-status.txt ; sudo mdadm --detail --scan | sudo tee /etc/mdadm.conf"],
        solution=["cat /proc/mdstat", "sudo mdadm /dev/md0 --fail /dev/sdc", "sudo mdadm /dev/md0 --remove /dev/sdc", "sudo mdadm /dev/md0 --add /dev/sdd",
                  "cat /proc/mdstat", "sudo mdadm --detail /dev/md0 > ~/md0-status.txt", "sudo mdadm --detail --scan | sudo tee /etc/mdadm.conf"], par=6)


def build(m):
    """Fresh world + shell for a mission."""
    from .shell import Shell
    fs = make_world(m["distro"])
    sh = Shell(fs, distro=m["distro"])
    m["setup"](fs, sh)
    sh.cmdlog.clear()
    return fs, sh


def check(m, fs, sh):
    try:
        res = m["check"](fs, sh)
    except Exception:
        res = [False] * len(m["goals"])
    return [bool(x) for x in res]
