"""A small in-memory Linux filesystem with real inodes, so hard links, soft links, stat and ls -i behave like the real thing."""
import hashlib
import math
import posixpath


class Archive:
    """tar / cpio / zip / 7z container. members = [{'path','kind','data','mode'}]"""

    def __init__(self, kind, members=None):
        self.kind = kind
        self.members = members or []

    def size(self):
        if self.kind == "tar":
            return 1024 + sum(512 + int(math.ceil(inner_size(m["data"]) / 512.0)) * 512 for m in self.members)
        if self.kind == "cpio":
            return 512 + sum(110 + len(m["path"]) + inner_size(m["data"]) for m in self.members)
        return 200 + sum(inner_size(m["data"]) // 2 + 60 for m in self.members)

    def digest(self):
        return repr((self.kind, [(m["path"], digest_of(m["data"])) for m in self.members]))


class Comp:
    """Compressed wrapper (gz, bz2, xz). xz squeezes the most, gzip the least."""
    RATIO = {"gz": 0.45, "bz2": 0.36, "xz": 0.28}

    def __init__(self, algo, inner, name=""):
        self.algo = algo
        self.inner = inner
        self.name = name

    def size(self):
        return max(24, int(inner_size(self.inner) * self.RATIO[self.algo]) + 20)

    def digest(self):
        return "%s:%s" % (self.algo, digest_of(self.inner))


class Blob:
    """Big binary content stored by size only (dd from /dev/zero, swap files, video files)."""

    def __init__(self, nbytes, what="zero"):
        self.nbytes = int(nbytes)
        self.what = what

    def size(self):
        return self.nbytes

    def digest(self):
        return "blob:%s:%d" % (self.what, self.nbytes)


def inner_size(d):
    return d.size() if hasattr(d, "size") else len(d.encode())


def digest_of(d):
    return d.digest() if hasattr(d, "digest") else d


def hexhash(algo, data):
    raw = digest_of(data)
    return hashlib.new(algo, raw.encode()).hexdigest()


class Inode:
    def __init__(self, ino, kind, mode, owner, group, now):
        self.ino = ino
        self.kind = kind            # 'f' file, 'd' dir, 'l' symlink, 'b' device
        self.mode = mode
        self.owner = owner
        self.group = group
        self.data = "" if kind == "f" else None
        self.entries = {} if kind == "d" else None
        self.target = None
        self.nlink = 1 if kind != "d" else 2
        self.mtime = now
        self.ctime = now
        self.atime = now

    def size(self):
        if self.kind == "d":
            return 4096
        if self.kind == "l":
            return len(self.target)
        return inner_size(self.data)


class FSError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.msg = msg


ENOENT, EEXIST, ENOTDIR, EISDIR, EACCES, ENOTEMPTY, EXDEV, EINVAL = (
    "No such file or directory", "File exists", "Not a directory", "Is a directory",
    "Permission denied", "Directory not empty", "Invalid cross-device link", "Invalid argument")


class FS:
    def __init__(self, user="rocky", group="rocky", host="rocky01"):
        self.clock = 1_795_000_000
        self.next_ino = 100
        self.user = user
        self.group = group
        self.host = host
        self.inodes = {}
        self.root = self._new("d", 0o755, "root", "root")
        self.cwd = "/home/%s" % user
        self.env = {"HOME": "/home/%s" % user, "USER": user, "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin"}
        self.mounts = {}            # extra data used by the storage simulator
        self.sys = {}               # misc simulator state (packages, storage, network)

    # ------------------------------------------------------------------ plumbing
    def tick(self):
        self.clock += 7
        return self.clock

    def _new(self, kind, mode, owner, group):
        ino = self.next_ino
        self.next_ino += 1
        n = Inode(ino, kind, mode, owner, group, self.tick())
        self.inodes[ino] = n
        return n

    def abspath(self, path, cwd=None):
        cwd = cwd or self.cwd
        if path.startswith("~"):
            path = self.env["HOME"] + path[1:]
        if not path.startswith("/"):
            path = cwd.rstrip("/") + "/" + path
        return posixpath.normpath(path) if path else cwd

    def _split(self, path):
        p = self.abspath(path)
        return [x for x in p.split("/") if x]

    def lookup(self, path, follow=True, _depth=0):
        """Return Inode or None. Follows symlinks in every component except (optionally) the last."""
        if _depth > 20:
            raise FSError("Too many levels of symbolic links")
        comps = self._split(path)
        node = self.root
        walked = ""
        for i, name in enumerate(comps):
            if node.kind != "d":
                raise FSError(ENOTDIR)
            child = node.entries.get(name)
            if child is None:
                return None
            node = self.inodes[child]
            walked += "/" + name
            last = i == len(comps) - 1
            if node.kind == "l" and (follow or not last):
                tgt = node.target
                if not tgt.startswith("/"):
                    tgt = posixpath.dirname(walked) + "/" + tgt
                rest = "/".join(comps[i + 1:])
                node = self.lookup(tgt + ("/" + rest if rest else ""), True, _depth + 1) if rest else self.lookup(tgt, True, _depth + 1)
                return node
        return node

    def parent_of(self, path):
        p = self.abspath(path)
        parent = posixpath.dirname(p) or "/"
        node = self.lookup(parent)
        if node is None:
            raise FSError(ENOENT)
        if node.kind != "d":
            raise FSError(ENOTDIR)
        return node, posixpath.basename(p)

    # ------------------------------------------------------------------ permissions
    def can(self, node, bit, user):
        if user == "root":
            return True
        m = node.mode
        if node.owner == user:
            sh = 6
        elif node.group == self.group and user == self.user:
            sh = 3
        else:
            sh = 0
        want = {"r": 4, "w": 2, "x": 1}[bit]
        return bool((m >> sh) & want)

    # ------------------------------------------------------------------ operations
    def mkdir(self, path, user=None, parents=False, mode=0o755):
        user = user or self.user
        if parents:
            cur = ""
            for name in self._split(path):
                cur += "/" + name
                if self.lookup(cur) is None:
                    self.mkdir(cur, user)
            return
        parent, name = self.parent_of(path)
        if name in parent.entries:
            raise FSError(EEXIST)
        if not self.can(parent, "w", user):
            raise FSError(EACCES)
        n = self._new("d", mode, user, self.group if user != "root" else "root")
        parent.entries[name] = n.ino
        parent.nlink += 1
        parent.mtime = self.tick()
        return n

    def write(self, path, data, user=None, append=False, mode=0o644, follow=True):
        """Create or overwrite a regular file (data may be str, Archive or Comp)."""
        user = user or self.user
        node = self.lookup(path, follow)
        if node is not None:
            if node.kind == "d":
                raise FSError(EISDIR)
            if not self.can(node, "w", user):
                raise FSError(EACCES)
            if append and isinstance(node.data, str) and isinstance(data, str):
                node.data += data
            else:
                node.data = data
            node.mtime = self.tick()
            return node
        parent, name = self.parent_of(path)
        if not self.can(parent, "w", user):
            raise FSError(EACCES)
        n = self._new("f", mode, user, self.group if user != "root" else "root")
        n.data = data
        parent.entries[name] = n.ino
        parent.mtime = self.tick()
        return n

    def read(self, path, user=None):
        user = user or self.user
        node = self.lookup(path)
        if node is None:
            raise FSError(ENOENT)
        if node.kind == "d":
            raise FSError(EISDIR)
        if not self.can(node, "r", user):
            raise FSError(EACCES)
        node.atime = self.tick()
        return node.data

    def touch(self, path, user=None):
        user = user or self.user
        node = self.lookup(path)
        if node is not None:
            if not self.can(node, "w", user):
                raise FSError(EACCES)
            node.mtime = self.tick()
            return node
        return self.write(path, "", user)

    def unlink(self, path, user=None):
        user = user or self.user
        node = self.lookup(path, follow=False)
        if node is None:
            raise FSError(ENOENT)
        if node.kind == "d":
            raise FSError(EISDIR)
        parent, name = self.parent_of(path)
        if not self.can(parent, "w", user):
            raise FSError(EACCES)
        del parent.entries[name]
        node.nlink -= 1
        node.ctime = parent.mtime = self.tick()
        if node.nlink <= 0:
            self.inodes.pop(node.ino, None)

    def rmdir(self, path, user=None):
        user = user or self.user
        node = self.lookup(path, follow=False)
        if node is None:
            raise FSError(ENOENT)
        if node.kind != "d":
            raise FSError(ENOTDIR)
        if node.entries:
            raise FSError(ENOTEMPTY)
        parent, name = self.parent_of(path)
        if not self.can(parent, "w", user):
            raise FSError(EACCES)
        del parent.entries[name]
        parent.nlink -= 1
        parent.mtime = self.tick()
        self.inodes.pop(node.ino, None)

    def rm_tree(self, path, user=None):
        node = self.lookup(path, follow=False)
        if node is None:
            raise FSError(ENOENT)
        if node.kind == "d":
            for name in sorted(node.entries):
                self.rm_tree(path.rstrip("/") + "/" + name, user)
            self.rmdir(path, user)
        else:
            self.unlink(path, user)

    def link(self, src, dst, user=None):
        user = user or self.user
        node = self.lookup(src)
        if node is None:
            raise FSError(ENOENT)
        if node.kind == "d":
            raise FSError("hard link not allowed for directory")
        parent, name = self.parent_of(dst)
        existing = parent.entries.get(name)
        if existing is not None:
            raise FSError(EEXIST)
        if not self.can(parent, "w", user):
            raise FSError(EACCES)
        parent.entries[name] = node.ino
        node.nlink += 1
        node.ctime = parent.mtime = self.tick()

    def symlink(self, target, dst, user=None):
        user = user or self.user
        parent, name = self.parent_of(dst)
        if name in parent.entries:
            raise FSError(EEXIST)
        if not self.can(parent, "w", user):
            raise FSError(EACCES)
        n = self._new("l", 0o777, user, self.group if user != "root" else "root")
        n.target = target
        parent.entries[name] = n.ino
        parent.mtime = self.tick()

    def rename(self, src, dst, user=None):
        user = user or self.user
        node = self.lookup(src, follow=False)
        if node is None:
            raise FSError(ENOENT)
        sp, sn = self.parent_of(src)
        dnode = self.lookup(dst)
        if dnode is not None and dnode.kind == "d":
            dp, dn = dnode, sn
        else:
            dp, dn = self.parent_of(dst)
        if not (self.can(sp, "w", user) and self.can(dp, "w", user)):
            raise FSError(EACCES)
        if dp.entries.get(dn) is not None and self.inodes[dp.entries[dn]].kind == "d" and node.kind != "d":
            raise FSError("cannot overwrite directory")
        old = dp.entries.get(dn)
        del sp.entries[sn]
        if old is not None and old != node.ino:
            o = self.inodes[old]
            o.nlink -= 1
            if o.nlink <= 0:
                self.inodes.pop(old, None)
        dp.entries[dn] = node.ino
        if node.kind == "d" and sp is not dp:
            sp.nlink -= 1
            dp.nlink += 1
        node.ctime = sp.mtime = dp.mtime = self.tick()

    def copy(self, src, dst, user=None, recursive=False):
        user = user or self.user
        node = self.lookup(src)
        if node is None:
            raise FSError(ENOENT)
        dnode = self.lookup(dst)
        if dnode is not None and dnode.kind == "d":
            dst = dst.rstrip("/") + "/" + posixpath.basename(self.abspath(src))
        if node.kind == "d":
            if not recursive:
                raise FSError("-r not specified; omitting directory")
            if self.lookup(dst) is None:
                self.mkdir(dst, user)
            for name in sorted(node.entries):
                self.copy(src.rstrip("/") + "/" + name, dst.rstrip("/") + "/" + name, user, True)
            return
        if not self.can(node, "r", user):
            raise FSError(EACCES)
        data = node.data
        if isinstance(data, Archive):
            data = Archive(data.kind, [dict(m) for m in data.members])
        n = self.write(dst, data, user, mode=node.mode & 0o777)
        return n

    def listdir(self, path):
        node = self.lookup(path)
        if node is None:
            raise FSError(ENOENT)
        if node.kind != "d":
            raise FSError(ENOTDIR)
        return sorted(node.entries)

    def isdir(self, path):
        try:
            n = self.lookup(path)
        except FSError:
            return False
        return n is not None and n.kind == "d"

    def exists(self, path, follow=True):
        try:
            return self.lookup(path, follow) is not None
        except FSError:
            return False

    def walk(self, path):
        """Yield absolute paths below path (depth first, sorted), not including path itself."""
        node = self.lookup(path, follow=False)
        if node is None or node.kind != "d":
            return
        for name in sorted(node.entries):
            p = path.rstrip("/") + "/" + name
            yield p
            child = self.inodes[node.entries[name]]
            if child.kind == "d":
                for x in self.walk(p):
                    yield x

    def glob(self, pattern):
        """Expand a pattern against the filesystem. Returns sorted matches or [] ."""
        import fnmatch
        absolute = pattern.startswith("/")
        parts = [p for p in pattern.split("/") if p != ""]
        results = [("/" if absolute else "")]
        for part in parts:
            nxt = []
            for base in results:
                if any(ch in part for ch in "*?["):
                    try:
                        names = self.listdir(base or ".") if base or not absolute else self.listdir("/")
                    except FSError:
                        continue
                    for nme in names:
                        if nme.startswith(".") and not part.startswith("."):
                            continue
                        if fnmatch.fnmatchcase(nme, part):
                            nxt.append(base + ("/" if base and not base.endswith("/") else "") + nme)
                else:
                    cand = base + ("/" if base and not base.endswith("/") else "") + part
                    if self.exists(cand or "/", follow=False):
                        nxt.append(cand)
            results = nxt
        return sorted(results)

    # ------------------------------------------------------------------ convenience for building scenarios
    def put(self, path, data="", owner=None, mode=0o644):
        parent = posixpath.dirname(self.abspath(path))
        if self.lookup(parent) is None:
            self.mkdir(parent, "root", parents=True)
        n = self.write(path, data, "root", mode=mode)
        n.owner = owner or n.owner
        n.group = n.owner if n.owner != "root" else "root"
        n.mode = mode
        return n

    def put_dir(self, path, owner="root", mode=0o755):
        if self.lookup(path) is None:
            self.mkdir(path, "root", parents=True)
        n = self.lookup(path)
        n.owner = owner
        n.group = owner if owner != "root" else "root"
        n.mode = mode
        return n


def mode_str(node):
    t = {"d": "d", "l": "l", "b": "b", "f": "-"}[node.kind]
    m = node.mode
    s = ""
    for sh in (6, 3, 0):
        s += "r" if m >> (sh + 2) & 1 else "-"
        s += "w" if m >> (sh + 1) & 1 else "-"
        s += "x" if m >> sh & 1 else "-"
    return t + s
