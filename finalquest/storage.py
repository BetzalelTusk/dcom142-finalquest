"""Storage simulator (PREVIEW for course Modules 11-12): lsblk, parted, mkfs, mount/umount, fstab, LVM, swap."""
import hashlib
import re

from .shell import cmd, getopts, lines_of
from .vfs import FSError


def S(fs):
    s = fs.sys
    s.setdefault("blk", {})
    s.setdefault("pv", {})
    s.setdefault("vg", {})
    s.setdefault("lv", {})
    s.setdefault("mounts", {})
    s.setdefault("swaps", [])
    return s


def size_mib(txt):
    m = re.match(r"^\+?(\d+(?:\.\d+)?)\s*([KMGT]?)(?:i?B)?$", txt.strip(), re.I)
    if not m:
        return None
    mult = {"": 1, "K": 1 / 1024.0, "M": 1, "G": 1024, "T": 1024 * 1024}[m.group(2).upper()]
    return int(float(m.group(1)) * mult)


def fmt(m):
    if m >= 1024 * 1024:
        return "%.1fT" % (m / 1024.0 / 1024)
    if m >= 1024:
        v = m / 1024.0
        return ("%dG" % v) if abs(v - round(v)) < 0.05 else "%.1fG" % v
    return "%dM" % m


def add_disk(fs, name, size_mib_, fstype=None):
    s = S(fs)
    s["blk"]["/dev/" + name] = {"type": "disk", "size": size_mib_, "fstype": fstype, "parent": None, "ptable": None, "dm": False}
    _node(fs, "/dev/" + name)


def _node(fs, path):
    if not fs.exists(path, follow=False):
        n = fs.put(path, "", owner="root", mode=0o660)
        n.kind = "b"
        n.data = ""


def uuid_for(path):
    h = hashlib.md5(path.encode()).hexdigest()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:32])


def need_root(ctx, what):
    if not ctx.root:
        ctx.e("%s: Permission denied (you need sudo)\n" % what)
        return True
    return False


def free_mib(fs, disk):
    s = S(fs)
    used = sum(v["size"] for k, v in s["blk"].items() if v["parent"] == disk) + 1
    return s["blk"][disk]["size"] - used


@cmd("lsblk", help=("list block devices", "lsblk", []))
def c_lsblk(ctx):
    s = S(ctx.fs)
    ctx.w("NAME          MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS\n")
    mounts = {v: k for k, v in s["mounts"].items()}
    n = 0

    def row(path, info, prefix):
        nonlocal n
        n += 1
        name = path.split("/")[-1] if not info.get("dm") else path.split("/")[-1].replace("/", "-")
        mp = mounts.get(path, "")
        if path in s["swaps"]:
            mp = "[SWAP]"
        ctx.w("%-13s %3d:%-3d 0 %5s  0 %-4s %s\n" % (prefix + name, 8, n, fmt(info["size"]), "lvm" if info.get("dm") else info["type"], mp))

    for path, info in sorted(s["blk"].items()):
        if info["parent"] is None and not info.get("dm"):
            row(path, info, "")
            kids = sorted(k for k, v in s["blk"].items() if v["parent"] == path)
            for i, k in enumerate(kids):
                row(k, s["blk"][k], "└─" if i == len(kids) - 1 else "├─")
            for pv in s["pv"]:
                if pv == path or pv.startswith(path):
                    for (vg, lv), li in sorted(s["lv"].items()):
                        if pv in s["vg"].get(vg, {}).get("pvs", []):
                            pass
    for (vg, lv), li in sorted(s["lv"].items()):
        p = "/dev/%s/%s" % (vg, lv)
        if p in s["blk"]:
            row(p, dict(s["blk"][p], dm=True), "  └─")
    return 0


@cmd("blkid", help=("print block device attributes (UUID, filesystem type)", "blkid [device]", []))
def c_blkid(ctx):
    if not ctx.root:
        return 2
    s = S(ctx.fs)
    for p, info in sorted(s["blk"].items()):
        if info.get("fstype"):
            ctx.w('%s: UUID="%s" TYPE="%s"\n' % (p, uuid_for(p), info["fstype"]))
    return 0


@cmd("fdisk", help=("manipulate disk partition table", "fdisk -l", [("-l", "list partition tables")]))
def c_fdisk(ctx):
    if "-l" not in ctx.argv:
        ctx.w("(the real fdisk is interactive: n = new, d = delete, p = print, w = write. This simulator supports 'fdisk -l' and 'parted -s'.)\n")
        return 0
    if need_root(ctx, "fdisk"):
        return 1
    s = S(ctx.fs)
    for p, info in sorted(s["blk"].items()):
        if info["type"] == "disk" and not info.get("dm"):
            ctx.w("Disk %s: %s, %d bytes, %d sectors\nUnits: sectors of 1 * 512 = 512 bytes\nDisklabel type: %s\n" % (p, fmt(info["size"]), info["size"] * 1048576, info["size"] * 2048, info.get("ptable") or "none"))
            kids = sorted(k for k, v in s["blk"].items() if v["parent"] == p)
            if kids:
                ctx.w("\nDevice       Start      End  Sectors  Size Type\n")
                for k in kids:
                    ctx.w("%-12s 2048  1048575  1046528 %5s Linux filesystem\n" % (k, fmt(s["blk"][k]["size"])))
            ctx.w("\n")
    return 0


@cmd("parted", help=("partition manipulation program", "parted -s DEVICE mklabel gpt | mkpart primary ext4 1MiB 5GiB", []))
def c_parted(ctx):
    if need_root(ctx, "parted"):
        return 1
    args = [a for a in ctx.argv[1:] if a not in ("-s", "--script")]
    s = S(ctx.fs)
    if len(args) < 2:
        ctx.w("(usage: parted -s /dev/sdb mklabel gpt  |  parted -s /dev/sdb mkpart primary 1MiB 5GiB)\n")
        return 0
    dev, sub = args[0], args[1]
    if dev not in s["blk"] or s["blk"][dev]["type"] != "disk":
        ctx.e("Error: Could not stat device %s - No such file or directory.\n" % dev)
        return 1
    if sub == "mklabel":
        s["blk"][dev]["ptable"] = args[2] if len(args) > 2 else "gpt"
        return 0
    if sub == "mkpart":
        if not s["blk"][dev].get("ptable"):
            ctx.e("Error: /dev/sdb: unrecognised disk label\n")
            return 1
        rest = args[2:]
        nums = [r for r in rest if re.match(r"^[\d.]+\s*[KMGT%]?i?B?$", r, re.I) or r.endswith("%")]
        free = free_mib(ctx.fs, dev)
        if len(nums) >= 2:
            a, b = nums[-2], nums[-1]
            start = 1 if a in ("0%", "1MiB") else (size_mib(a) or 1)
            end = s["blk"][dev]["size"] if b == "100%" else (size_mib(b) or free)
            size = max(1, min(free, end - start))
        else:
            size = free
        idx = 1 + len([k for k, v in s["blk"].items() if v["parent"] == dev])
        part = "%s%d" % (dev, idx)
        s["blk"][part] = {"type": "part", "size": size, "fstype": None, "parent": dev, "ptable": None, "dm": False}
        _node(ctx.fs, part)
        return 0
    ctx.e("parted: unsupported subcommand '%s' in the simulator\n" % sub)
    return 1


@cmd("partprobe", help=("inform the kernel of partition table changes", "partprobe", []))
def c_partprobe(ctx):
    return 0


def _mkfs(ctx, fstype, args):
    if need_root(ctx, ctx.name):
        return 1
    s = S(ctx.fs)
    devs = [a for a in args if a.startswith("/dev/")]
    if not devs:
        ctx.e("%s: no device given\n" % ctx.name)
        return 1
    d = devs[0]
    if d not in s["blk"]:
        ctx.e("%s: No such file or directory while trying to open %s\nCannot open the device.\n" % (ctx.name, d))
        return 1
    if s["blk"][d]["type"] == "disk" and any(v["parent"] == d for v in s["blk"].values()):
        ctx.e("%s: %s is apparently in use by the system\n" % (ctx.name, d))
        return 1
    if d in s["mounts"].values():
        ctx.e("%s: %s is mounted; will not make a filesystem here!\n" % (ctx.name, d))
        return 1
    s["blk"][d]["fstype"] = fstype
    ctx.w("Creating filesystem with %s on %s\nUUID: %s\nWriting superblocks and filesystem accounting information: done\n" % (fstype, d, uuid_for(d)))
    return 0


for _fs in ("ext4", "ext3", "xfs", "btrfs", "vfat"):
    def _make(fst):
        def fn(ctx):
            return _mkfs(ctx, fst, ctx.argv[1:])
        return fn
    cmd("mkfs." + _fs, help=("build a %s filesystem" % _fs, "mkfs.%s DEVICE" % _fs, []))(_make(_fs))


@cmd("mkfs", help=("build a Linux filesystem", "mkfs -t TYPE DEVICE", [("-t TYPE", "filesystem type (ext4, xfs, ...)")]))
def c_mkfs(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="", valued="t")
    if opts is None:
        return 1
    return _mkfs(ctx, opts.get("t", "ext2"), args)


@cmd("mkswap", help=("set up a Linux swap area", "mkswap DEVICE", []))
def c_mkswap(ctx):
    if need_root(ctx, "mkswap"):
        return 1
    s = S(ctx.fs)
    d = ctx.argv[-1]
    if d not in s["blk"]:
        ctx.e("mkswap: cannot open %s: No such file or directory\n" % d)
        return 1
    s["blk"][d]["fstype"] = "swap"
    ctx.w("Setting up swapspace version 1, size = %s\nUUID=%s\n" % (fmt(s["blk"][d]["size"]), uuid_for(d)))
    return 0


@cmd("swapon", help=("enable devices for swapping", "swapon DEVICE | swapon --show", []))
def c_swapon(ctx):
    s = S(ctx.fs)
    if "--show" in ctx.argv or len(ctx.argv) == 1:
        ctx.w("NAME      TYPE      SIZE USED PRIO\n")
        for d in s["swaps"]:
            ctx.w("%-9s partition %5s   0B   -2\n" % (d, fmt(s["blk"][d]["size"])))
        return 0
    if need_root(ctx, "swapon"):
        return 1
    d = ctx.argv[-1]
    if d not in s["blk"] or s["blk"][d].get("fstype") != "swap":
        ctx.e("swapon: %s: read swap header failed\n" % d)
        return 1
    if d not in s["swaps"]:
        s["swaps"].append(d)
    return 0


@cmd("swapoff")
def c_swapoff(ctx):
    s = S(ctx.fs)
    if need_root(ctx, "swapoff"):
        return 1
    d = ctx.argv[-1]
    if d in s["swaps"]:
        s["swaps"].remove(d)
    return 0


def _do_mount(ctx, dev, mp, user_cmd=True):
    s = S(ctx.fs)
    fs = ctx.fs
    if dev.startswith("UUID="):
        want = dev[5:].strip('"')
        match = [p for p in s["blk"] if uuid_for(p) == want]
        if not match:
            ctx.e("mount: %s: can't find in /etc/fstab or UUID.\n" % dev if False else "mount: %s: special device %s does not exist.\n" % (mp, dev))
            return 32
        dev = match[0]
    if dev not in s["blk"]:
        ctx.e("mount: %s: special device %s does not exist.\n" % (mp, dev))
        return 32
    if not s["blk"][dev].get("fstype") or s["blk"][dev]["fstype"] == "swap":
        ctx.e("mount: %s: wrong fs type, bad option, bad superblock on %s, missing codepage or helper program, or other error.\n" % (mp, dev))
        return 32
    if not fs.isdir(mp):
        ctx.e("mount: %s: mount point does not exist.\n" % mp)
        return 32
    if dev in s["mounts"].values():
        ctx.e("mount: %s: %s already mounted on %s.\n" % (mp, dev, [k for k, v in s["mounts"].items() if v == dev][0]))
        return 32
    s["mounts"][fs.abspath(mp)] = dev
    return 0


@cmd("mount", help=("mount a filesystem", "mount DEVICE DIRECTORY", [("-a", "mount all filesystems listed in /etc/fstab")]))
def c_mount(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="avr", valued="to")
    if opts is None:
        return 1
    s = S(ctx.fs)
    if not args and "a" not in opts:
        ctx.w("/dev/mapper/rl-root on / type xfs (rw,relatime,seclabel)\n/dev/sda1 on /boot type xfs (rw,relatime)\n")
        for mp, dev in sorted(s["mounts"].items()):
            ctx.w("%s on %s type %s (rw,relatime)\n" % (dev, mp, s["blk"].get(dev, {}).get("fstype", "?")))
        return 0
    if need_root(ctx, "mount"):
        return 32
    if "a" in opts:
        try:
            text = ctx.fs.read("/etc/fstab", "root")
        except FSError:
            return 0
        rc = 0
        for l in lines_of(text):
            l = l.strip()
            if not l or l.startswith("#"):
                continue
            f = l.split()
            if len(f) < 4 or f[2] in ("swap",) or f[1] in ("/", "/boot", "none"):
                continue
            if ctx.fs.abspath(f[1]) in s["mounts"]:
                continue
            rc = _do_mount(ctx, f[0], f[1]) or rc
        return rc
    if len(args) == 1:
        # look in fstab
        try:
            text = ctx.fs.read("/etc/fstab", "root")
        except FSError:
            text = ""
        for l in lines_of(text):
            f = l.split()
            if len(f) >= 2 and (f[1] == args[0] or f[0] == args[0]):
                return _do_mount(ctx, f[0], f[1])
        ctx.e("mount: %s: can't find in /etc/fstab.\n" % args[0])
        return 32
    return _do_mount(ctx, args[0], args[1])


@cmd("umount", help=("unmount filesystems", "umount DIRECTORY|DEVICE", []))
def c_umount(ctx):
    if need_root(ctx, "umount"):
        return 32
    s = S(ctx.fs)
    t = ctx.argv[-1]
    ap = ctx.fs.abspath(t)
    if ap in s["mounts"]:
        if ctx.fs.cwd == ap or ctx.fs.cwd.startswith(ap + "/"):
            ctx.e("umount: %s: target is busy.\n" % t)
            return 32
        del s["mounts"][ap]
        return 0
    for mp, dev in list(s["mounts"].items()):
        if dev == t:
            del s["mounts"][mp]
            return 0
    ctx.e("umount: %s: not mounted.\n" % t)
    return 32


@cmd("df", help=("report file system space usage", "df [-h]", [("-h", "human-readable sizes")]))
def c_df(ctx):
    s = S(ctx.fs)
    ctx.w("Filesystem           Size  Used Avail Use%% Mounted on\n/dev/mapper/rl-root   17G  3.9G   14G  23%% /\n/dev/sda1           1014M  280M  735M  28%% /boot\n")
    for mp, dev in sorted(s["mounts"].items()):
        sz = s["blk"].get(dev, {}).get("size", 0)
        ctx.w("%-20s %5s   45M  %5s   1%% %s\n" % (dev, fmt(sz), fmt(max(0, sz - 45)), mp))
    return 0


@cmd("du", help=("estimate file space usage", "du [-sh] FILE...", []))
def c_du(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="shac")
    if opts is None:
        return 1
    for a in args or ["."]:
        total = 0
        try:
            node = ctx.fs.lookup(a)
            if node is None:
                ctx.err("cannot access '%s': No such file or directory" % a)
                continue
            if node.kind == "d":
                total = sum(ctx.fs.lookup(p, follow=False).size() for p in ctx.fs.walk(a)) + 4096
            else:
                total = node.size()
        except FSError:
            continue
        from .shell import human
        ctx.w("%s\t%s\n" % (human(total) if "h" in opts else str(max(4, total // 1024)), a))
    return 0


# ----------------------------------------------------------------------------- LVM
@cmd("pvcreate", help=("initialize a disk or partition for use by LVM", "pvcreate DEVICE...", []))
def c_pvcreate(ctx):
    if need_root(ctx, "pvcreate"):
        return 5
    s = S(ctx.fs)
    for d in [a for a in ctx.argv[1:] if not a.startswith("-")]:
        if d not in s["blk"]:
            ctx.e("  Device %s not found.\n" % d)
            return 5
        s["pv"][d] = {"vg": None, "size": s["blk"][d]["size"]}
        ctx.w("  Physical volume \"%s\" successfully created.\n" % d)
    return 0


@cmd("vgcreate", help=("create a volume group", "vgcreate VG PV...", []))
def c_vgcreate(ctx):
    if need_root(ctx, "vgcreate"):
        return 5
    s = S(ctx.fs)
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    if len(args) < 2:
        ctx.e("  Please provide a volume group name and physical volume(s)\n")
        return 3
    vg, pvs = args[0], args[1:]
    for p in pvs:
        if p not in s["pv"]:
            ctx.e("  Device %s not found (or ignored by filtering).\n" % p if p not in s["blk"] else "  Physical volume '%s' not found (run pvcreate first).\n" % p)
            return 5
    s["vg"][vg] = {"pvs": pvs, "size": sum(s["pv"][p]["size"] for p in pvs) - len(pvs) * 4}
    for p in pvs:
        s["pv"][p]["vg"] = vg
    ctx.w("  Volume group \"%s\" successfully created\n" % vg)
    return 0


def vg_free(s, vg):
    return s["vg"][vg]["size"] - sum(v for (g, _), v in s["lv"].items() if g == vg)


@cmd("lvcreate", help=("create a logical volume", "lvcreate -L SIZE -n NAME VG", [("-L SIZE", "size of the LV"), ("-n NAME", "name of the LV")]))
def c_lvcreate(ctx):
    if need_root(ctx, "lvcreate"):
        return 5
    opts, args = getopts(ctx, ctx.argv[1:], flags="", valued="Ln", longs=("size=", "name=", "extents="))
    if opts is None:
        return 3
    s = S(ctx.fs)
    size = opts.get("L") or opts.get("size")
    name = opts.get("n") or opts.get("name")
    if not args or not size or not name:
        ctx.e("  Please specify a size (-L), a name (-n) and a volume group.\n")
        return 3
    vg = args[0]
    if vg not in s["vg"]:
        ctx.e("  Volume group \"%s\" not found\n  Cannot process volume group %s\n" % (vg, vg))
        return 5
    mib = size_mib(size)
    if mib is None:
        ctx.e("  Invalid argument for --size: %s\n" % size)
        return 3
    if mib > vg_free(s, vg):
        ctx.e("  Volume group \"%s\" has insufficient free space (%d extents): %d required.\n" % (vg, vg_free(s, vg) // 4, mib // 4))
        return 5
    s["lv"][(vg, name)] = mib
    p = "/dev/%s/%s" % (vg, name)
    s["blk"][p] = {"type": "lvm", "size": mib, "fstype": None, "parent": None, "ptable": None, "dm": True}
    _node(ctx.fs, p)
    _node(ctx.fs, "/dev/mapper/%s-%s" % (vg, name))
    ctx.w("  Logical volume \"%s\" created.\n" % name)
    return 0


@cmd("lvextend", help=("add space to a logical volume", "lvextend -L +SIZE /dev/VG/LV", []))
def c_lvextend(ctx):
    if need_root(ctx, "lvextend"):
        return 5
    opts, args = getopts(ctx, ctx.argv[1:], flags="r", valued="L", longs=("size=", "resizefs"))
    if opts is None:
        return 3
    s = S(ctx.fs)
    size = opts.get("L") or opts.get("size")
    if not args or not size:
        ctx.e("  Please specify either size or extents.\n")
        return 3
    m = re.match(r"^/dev/(?:mapper/)?([^/-]+)[/-]([^/]+)$", args[0])
    if not m or (m.group(1), m.group(2)) not in s["lv"]:
        ctx.e("  Failed to find logical volume \"%s\"\n" % args[0])
        return 5
    vg, lv = m.group(1), m.group(2)
    add = size_mib(size)
    cur = s["lv"][(vg, lv)]
    new = cur + add if size.startswith("+") else add
    if new - cur > vg_free(s, vg):
        ctx.e("  Insufficient free space: %d extents needed, but only %d available\n" % ((new - cur) // 4, vg_free(s, vg) // 4))
        return 5
    s["lv"][(vg, lv)] = new
    s["blk"]["/dev/%s/%s" % (vg, lv)]["size"] = new
    s["blk"]["/dev/%s/%s" % (vg, lv)]["fs_size"] = s["blk"]["/dev/%s/%s" % (vg, lv)].get("fs_size", cur)
    ctx.w("  Size of logical volume %s/%s changed from %s to %s.\n  Logical volume %s/%s successfully resized.\n" % (vg, lv, fmt(cur), fmt(new), vg, lv))
    if "r" in opts or "resizefs" in opts:
        s["blk"]["/dev/%s/%s" % (vg, lv)]["fs_size"] = new
        ctx.w("  (filesystem resized too, because of -r)\n")
    return 0


def _grow(ctx, target, what):
    s = S(ctx.fs)
    dev = target if target in s["blk"] else s["mounts"].get(ctx.fs.abspath(target))
    if not dev or dev not in s["blk"]:
        ctx.e("%s: %s: No such file or directory\n" % (what, target))
        return 1
    info = s["blk"][dev]
    if what == "xfs_growfs" and info.get("fstype") != "xfs":
        ctx.e("xfs_growfs: %s is not a valid XFS filesystem (it is %s)\n" % (target, info.get("fstype")))
        return 1
    if what == "resize2fs" and info.get("fstype") not in ("ext2", "ext3", "ext4"):
        ctx.e("resize2fs: Bad magic number in super-block while trying to open %s\n" % target)
        return 1
    info["fs_size"] = info["size"]
    ctx.w("The filesystem on %s is now %s in size.\n" % (dev, fmt(info["size"])))
    return 0


@cmd("resize2fs", help=("resize an ext2/3/4 filesystem", "resize2fs DEVICE", []))
def c_resize2fs(ctx):
    if need_root(ctx, "resize2fs"):
        return 1
    return _grow(ctx, ctx.argv[-1], "resize2fs")


@cmd("xfs_growfs", help=("expand an XFS filesystem (give the MOUNT POINT)", "xfs_growfs MOUNTPOINT", []))
def c_xfs_growfs(ctx):
    if need_root(ctx, "xfs_growfs"):
        return 1
    return _grow(ctx, ctx.argv[-1], "xfs_growfs")


@cmd("pvs", help=("display physical volumes", "pvs", []))
def c_pvs(ctx):
    s = S(ctx.fs)
    ctx.w("  PV         VG   Fmt  Attr PSize  PFree\n")
    for p, v in sorted(s["pv"].items()):
        vg = v["vg"]
        free = vg_free(s, vg) if vg else v["size"]
        ctx.w("  %-10s %-4s lvm2 a--  %5s %5s\n" % (p, vg or "", fmt(v["size"]), fmt(free)))
    return 0


@cmd("vgs", help=("display volume groups", "vgs", []))
def c_vgs(ctx):
    s = S(ctx.fs)
    ctx.w("  VG   #PV #LV #SN Attr   VSize  VFree\n")
    for vg, v in sorted(s["vg"].items()):
        nl = len([1 for (g, _) in s["lv"] if g == vg])
        ctx.w("  %-4s %3d %3d   0 wz--n- %5s %5s\n" % (vg, len(v["pvs"]), nl, fmt(v["size"]), fmt(vg_free(s, vg))))
    return 0


@cmd("lvs", help=("display logical volumes", "lvs", []))
def c_lvs(ctx):
    s = S(ctx.fs)
    ctx.w("  LV     VG   Attr       LSize\n")
    for (vg, lv), sz in sorted(s["lv"].items()):
        ctx.w("  %-6s %-4s -wi-a----- %5s\n" % (lv, vg, fmt(sz)))
    return 0
