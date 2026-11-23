"""Storage simulator for course Modules 11-12 (CertMaster 7.1-7.4).

Disks, MBR/GPT partition tables (interactive fdisk and parted, as the Module 11 slides demo them),
partprobe, filesystems (ext4/XFS/Btrfs/tmpfs) and their tools, mounting (a mount really hides what
was in the directory), /etc/fstab and reboot, swap partitions and swap files, LVM, software RAID
(mdadm) and disk quotas. Sizes are kept in MiB.
"""
import hashlib
import posixpath
import re

from .shell import cmd, getopts, lines_of, human
from .vfs import FSError, Blob, inner_size

SECT = 2048          # 512-byte sectors per MiB
DEFAULT_RAM = 1900   # MiB of "physical" RAM shown by free


# ============================================================================= state
def S(fs):
    s = fs.sys
    for k, v in (("blk", {}), ("pv", {}), ("vg", {}), ("lv", {}), ("mounts", {}), ("swaps", []), ("fsroot", {}),
                 ("under", {}), ("mopts", {}), ("quota", {}), ("md", {}), ("boots", 0), ("boot_ok", True),
                 ("boot_errors", []), ("ram", DEFAULT_RAM)):
        if k not in s:
            s[k] = v
    return s


def size_mib(txt):
    m = re.match(r"^\+?(\d+(?:\.\d+)?)\s*([KMGT]?)(?:i?B)?$", txt.strip(), re.I)
    if not m:
        return None
    mult = {"": 1, "K": 1 / 1024.0, "M": 1, "G": 1024, "T": 1024 * 1024}[m.group(2).upper()]
    return int(round(float(m.group(1)) * mult))


def fmt(m):
    if m >= 1024 * 1024:
        return "%.1fT" % (m / 1024.0 / 1024)
    if m >= 1024:
        v = m / 1024.0
        return ("%dG" % round(v)) if abs(v - round(v)) < 0.05 else "%.1fG" % v
    return "%dM" % m


def fmt_gib(m):
    """fdisk style: '4 GiB', '1.5 GiB', '500 MiB'"""
    if m >= 1024:
        v = m / 1024.0
        return ("%d GiB" % round(v)) if abs(v - round(v)) < 0.05 else "%.1f GiB" % v
    return "%d MiB" % m


def uuid_for(path):
    h = hashlib.md5(path.encode()).hexdigest()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:32])


def ident(path):
    return hashlib.md5(("id" + path).encode()).hexdigest()[:8]


def need_root(ctx, what):
    if not ctx.root:
        ctx.e("%s: Permission denied (you need sudo)\n" % what)
        return True
    return False


def _node(fs, path):
    if not fs.exists(path, follow=False):
        parent = posixpath.dirname(path)
        if not fs.exists(parent):
            fs.mkdir(parent, "root", parents=True)
        n = fs.put(path, "", owner="root", mode=0o660)
        n.kind = "b"
        n.data = ""


def _unnode(fs, path):
    try:
        fs.unlink(path, "root")
    except FSError:
        pass


def add_disk(fs, name, size, fstype=None, model="VMware Virtual disk"):
    s = S(fs)
    s["blk"]["/dev/" + name] = {"type": "disk", "size": size, "fstype": fstype, "parent": None, "ptable": None, "dm": False, "model": model}
    _node(fs, "/dev/" + name)
    if fstype:
        _new_root(fs, "/dev/" + name, fstype)
    sync(fs)


def default_ptype(label, pkind="primary"):
    if pkind == "extended":
        return "Extended"
    return "Linux filesystem" if label == "gpt" else "Linux"


def add_part(fs, disk, num, start, size, fstype=None, pkind="primary", ptype=None, label=None, ptable=None, pending=False, name=None):
    """Create a partition directly (used to build mission machines)."""
    s = S(fs)
    d = s["blk"][disk]
    if ptable:
        d["ptable"] = ptable
    d["ptable"] = d.get("ptable") or "gpt"
    p = "%s%d" % (disk, num)
    s["blk"][p] = {"type": "part", "size": size, "start": start, "num": num, "pkind": pkind, "ptype": ptype or default_ptype(d["ptable"], pkind),
                   "fstype": None, "parent": disk, "ptable": None, "dm": False, "pending": pending, "label": None, "pname": name or ""}
    if not pending:
        _node(fs, p)
    if fstype:
        s["blk"][p]["fstype"] = fstype
        s["blk"][p]["label"] = label
        _new_root(fs, p, fstype)
    sync(fs)
    return p


def visible(s, p):
    return p in s["blk"] and not s["blk"][p].get("pending")


def parts(s, disk, pending=True):
    ps = [k for k, v in s["blk"].items() if v.get("parent") == disk and v["type"] == "part" and (pending or not v.get("pending"))]
    return sorted(ps, key=lambda k: s["blk"][k]["num"])


def free_mib(fs, disk):
    s = S(fs)
    d = s["blk"][disk]
    top = [(v["start"], v["size"]) for p in parts(s, disk) for v in [s["blk"][p]] if v.get("pkind") != "logical"]
    return sum(b - a for a, b in _gaps(top, 1, d["size"] - (1 if d.get("ptable") == "gpt" else 0)))


def _gaps(entries, lo, hi):
    gaps, cur = [], lo
    for st, sz in sorted(entries):
        if st > cur:
            gaps.append((cur, st))
        cur = max(cur, st + sz)
    if hi > cur:
        gaps.append((cur, hi))
    return [g for g in gaps if g[1] - g[0] >= 1]


def in_use(s, p):
    if p in s["mounts"].values() or p in s["swaps"]:
        return True
    if p in s["pv"] and s["pv"][p].get("vg"):
        return True
    for md in s["md"].values():
        if p in md["members"] or p in md["failed"] or p in md.get("spares", []):
            return True
    return False


def disk_busy(s, disk):
    return in_use(s, disk) or any(in_use(s, p) for p in parts(s, disk))


# ----------------------------------------------------------------------------- filesystem contents
def _new_root(fs, dev, fstype):
    s = S(fs)
    root = {"entries": {}, "owner": "root", "group": "root", "mode": 0o755}
    if fstype in ("ext2", "ext3", "ext4"):
        lf = fs._new("d", 0o700, "root", "root")
        root["entries"]["lost+found"] = lf.ino
    s["fsroot"][dev] = root
    info = s["blk"].get(dev)
    if info is not None:
        info["errors"] = False
        info["reserved"] = 5 if fstype.startswith("ext") else None
    return root


def _tree_bytes(fs, entries):
    total = 0
    for ino in entries.values():
        n = fs.inodes.get(ino)
        if n is None:
            continue
        if n.kind == "d":
            total += 4096 + _tree_bytes(fs, n.entries)
        else:
            total += n.size()
    return total


def _tree_owners(fs, entries, acc):
    for ino in entries.values():
        n = fs.inodes.get(ino)
        if n is None:
            continue
        acc[n.owner] = acc.get(n.owner, 0) + (4096 if n.kind == "d" else n.size())
        if n.kind == "d":
            _tree_owners(fs, n.entries, acc)
    return acc


def mounted_entries(fs, dev):
    """Names at the top of a device's filesystem (whether or not it is mounted)."""
    s = S(fs)
    r = s["fsroot"].get(dev)
    return sorted(r["entries"]) if r else []


def under_entries(fs, mp):
    """Names that are in the directory itself, underneath any mount."""
    s = S(fs)
    ap = fs.abspath(mp)
    if ap in s["under"]:
        return sorted(s["under"][ap]["entries"])
    try:
        n = fs.lookup(ap)
    except FSError:
        return []
    return sorted(n.entries) if n is not None and n.kind == "d" else []


def attach(fs, dev, mp, opts="defaults"):
    """Mount dev on mp: the directory now shows the device's files (and owner/mode); its own files are hidden."""
    s = S(fs)
    ap = fs.abspath(mp)
    node = fs.lookup(ap)
    if dev == "tmpfs":
        root = {"entries": {}, "owner": "root", "group": "root", "mode": 0o1777}
        s["fsroot"]["tmpfs:" + ap] = root
        dev = "tmpfs:" + ap
    root = s["fsroot"][dev]
    s["under"][ap] = {"entries": node.entries, "owner": node.owner, "group": node.group, "mode": node.mode}
    node.entries = root["entries"]
    node.owner, node.group, node.mode = root["owner"], root["group"], root["mode"]
    s["mounts"][ap] = dev
    s["mopts"][ap] = opts or "defaults"
    sync(fs)


def detach(fs, ap):
    s = S(fs)
    node = fs.lookup(ap)
    dev = s["mounts"].pop(ap)
    root = s["fsroot"].get(dev)
    if root is not None:
        root.update(owner=node.owner, group=node.group, mode=node.mode)
    u = s["under"].pop(ap)
    node.entries = u["entries"]
    node.owner, node.group, node.mode = u["owner"], u["group"], u["mode"]
    s["mopts"].pop(ap, None)
    if dev.startswith("tmpfs:"):
        s["fsroot"].pop(dev, None)       # tmpfs lives in RAM: gone when unmounted
    sync(fs)
    return dev


# ----------------------------------------------------------------------------- /proc
def sync(fs):
    s = S(fs)
    rows = ["major minor  #blocks  name", ""]
    minor = 0
    for p, v in sorted(s["blk"].items()):
        if v.get("pending") or v.get("dm") or v["type"] == "raid":
            continue
        rows.append("%4d %7d %10d %s" % (8, minor, v["size"] * 1024 if v.get("pkind") != "extended" else 1, p.split("/")[-1]))
        minor += 1
    for md, v in sorted(s["md"].items()):
        rows.append("%4d %7d %10d %s" % (9, int(md[-1]) if md[-1].isdigit() else 0, s["blk"][md]["size"] * 1024, md.split("/")[-1]))
    try:
        fs.put("/proc/partitions", "\n".join(rows) + "\n", mode=0o444)
        fs.put("/proc/mdstat", mdstat_text(s), mode=0o444)
        sw = ["Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority"]
        for d in s["swaps"]:
            sw.append("%-40s%-16s%-16d0\t\t-2" % (d, "file" if not d.startswith("/dev/") else "partition", swap_size(fs, d) * 1024))
        fs.put("/proc/swaps", "\n".join(sw) + "\n", mode=0o444)
        mt = ["/dev/mapper/rl-root / xfs rw,seclabel,relatime 0 0", "/dev/sda1 /boot xfs rw,seclabel,relatime 0 0"]
        for mp, dev in sorted(s["mounts"].items()):
            typ = "tmpfs" if dev.startswith("tmpfs:") else s["blk"].get(dev, {}).get("fstype", "?")
            mt.append("%s %s %s rw,relatime%s 0 0" % ("tmpfs" if dev.startswith("tmpfs:") else dev, mp, typ, _extra_opts(s, mp)))
        fs.put("/proc/mounts", "\n".join(mt) + "\n", mode=0o444)
    except FSError:
        pass


def _extra_opts(s, mp):
    o = [x for x in s["mopts"].get(mp, "defaults").split(",") if x not in ("defaults", "rw", "auto", "nofail")]
    return ("," + ",".join(o)) if o else ""


# ============================================================================= detection
def _tree_rows(s):
    """[(path, depth, last_flags)] in lsblk order."""
    out = []

    def kids(p):
        k = [x for x in parts(s, p, pending=False)] if s["blk"][p]["type"] == "disk" else []
        extra = []
        for (vg, lv), _ in sorted(s["lv"].items()):
            if p in s["vg"].get(vg, {}).get("pvs", []):
                extra.append("/dev/%s/%s" % (vg, lv))
        for md, v in sorted(s["md"].items()):
            if p in v["members"] or p in v.get("spares", []):
                extra.append(md)
        return k + extra

    def walk(p, depth, flags):
        out.append((p, depth, flags))
        ks = kids(p)
        for i, k in enumerate(ks):
            walk(k, depth + 1, flags + [i == len(ks) - 1])

    for p, v in sorted(s["blk"].items()):
        if v["type"] == "disk":
            walk(p, 0, [])
    return out


def _prefix(flags):
    if not flags:
        return ""
    return "".join("  " if f else "\u2502 " for f in flags[:-1]) + ("\u2514\u2500" if flags[-1] else "\u251c\u2500")


def _display_name(p, info):
    if info.get("dm"):
        vg, lv = p.split("/")[-2:]
        return "%s-%s" % (vg, lv)
    return p.split("/")[-1]


def _fstype_shown(s, p):
    info = s["blk"].get(p, {})
    if p in s["pv"]:
        return "LVM2_member"
    for md in s["md"].values():
        if p in md["members"] or p in md["failed"] or p in md.get("spares", []):
            return "linux_raid_member"
    return info.get("fstype") or ""


def _mp_shown(s, p):
    if p in s["swaps"]:
        return "[SWAP]"
    for mp, dev in s["mounts"].items():
        if dev == p:
            return mp
    return ""


@cmd("lsblk", help=("list block devices", "lsblk [-f] [DEVICE]", [("-f", "show filesystems: type, label, UUID"), ("-o LIST", "choose columns (NAME,SIZE,FSTYPE,MOUNTPOINT...)")]))
def c_lsblk(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="fapl", valued="o")
    if opts is None:
        return 1
    s = S(ctx.fs)
    rows = _tree_rows(s)
    if args:
        for a in args:
            if a not in s["blk"]:
                ctx.e("lsblk: %s: not a block device\n" % a)
                return 32
        # keep each requested device plus everything below it
        out = []
        for i, (p, d, fl) in enumerate(rows):
            if p in args:
                out.append((p, 0, []))
                for q, d2, fl2 in rows[i + 1:]:
                    if d2 <= d:
                        break
                    out.append((q, d2 - d, fl2[d:]))
        rows = out
    if "f" in opts:
        ctx.w("NAME        FSTYPE            LABEL    UUID                                 MOUNTPOINTS\n")
        for p, depth, flags in rows:
            info = s["blk"][p]
            fst = _fstype_shown(s, p)
            uu = uuid_for(p) if fst else ""
            ctx.w("%-11s %-17s %-8s %-36s %s\n" % (_prefix(flags) + _display_name(p, info), fst, info.get("label") or "", uu, _mp_shown(s, p)))
        return 0
    ctx.w("NAME        MAJ:MIN RM  SIZE RO TYPE  MOUNTPOINTS\n")
    for i, (p, depth, flags) in enumerate(rows):
        info = s["blk"][p]
        typ = {"disk": "disk", "part": "part", "lvm": "lvm", "raid": info.get("raidtype", "raid1")}.get(info["type"], info["type"])
        size = "1K" if info.get("pkind") == "extended" else fmt(info["size"])
        major = 253 if info.get("dm") else (9 if info["type"] == "raid" else 8)
        ctx.w("%-11s %3d:%-3d  0 %5s  0 %-5s %s\n" % (_prefix(flags) + _display_name(p, info), major, i, size, typ, _mp_shown(s, p)))
    return 0


@cmd("blkid", help=("print block device attributes (LABEL, UUID, TYPE)", "blkid [DEVICE] | blkid -s UUID -o value DEVICE | blkid -L LABEL", [
    ("-s TAG", "show only this tag (UUID, LABEL, TYPE)"), ("-o value", "print only the value"), ("-L LABEL", "find the device with this label"), ("-U UUID", "find the device with this UUID")]))
def c_blkid(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="p", valued="soLU")
    if opts is None:
        return 2
    s = S(ctx.fs)
    devs = [p for p, info in sorted(s["blk"].items()) if visible(s, p) and _fstype_shown(s, p)]
    if "L" in opts or "U" in opts:
        for p in devs:
            if ("L" in opts and s["blk"][p].get("label") == opts["L"]) or ("U" in opts and uuid_for(p) == opts["U"]):
                ctx.w(p + "\n")
                return 0
        return 2
    if args:
        devs = [d for d in args if d in devs]
        if not devs:
            return 2
    for p in devs:
        info = s["blk"][p]
        tags = []
        if info.get("label"):
            tags.append(("LABEL", info["label"]))
        tags.append(("UUID", uuid_for(p)))
        tags.append(("TYPE", _fstype_shown(s, p)))
        if "s" in opts:
            tags = [t for t in tags if t[0] == opts["s"].upper()]
        if opts.get("o") == "value":
            for _, v in tags:
                ctx.w(v + "\n")
        else:
            ctx.w("%s: %s\n" % (p, " ".join('%s="%s"' % t for t in tags)))
    return 0


@cmd("hwinfo", help=("probe for hardware", "hwinfo --short | --storage | --block | --disk", [
    ("--storage", "storage controllers"), ("--block", "disks and partitions"), ("--disk", "disks only"), ("--short", "one line per device")]))
def c_hwinfo(ctx):
    s = S(ctx.fs)
    a = set(ctx.argv[1:])
    disks = [p for p, v in sorted(s["blk"].items()) if v["type"] == "disk"]
    if not a or a == {"--short"}:
        a = {"--storage", "--block"}
    if "--storage" in a:
        ctx.w("storage:\n                       VMware PVSCSI SCSI Controller\n                       Intel 82371AB/EB/MB PIIX4 IDE\n")
    if a & {"--block", "--disk"}:
        ctx.w("disk:\n")
        for p in disks:
            ctx.w("  %-20s %s\n" % (p, s["blk"][p].get("model", "VMware Virtual disk")))
        if "--block" in a:
            ctx.w("partition:\n")
            for p in disks:
                for q in parts(s, p, pending=False):
                    ctx.w("  %-20s Partition\n" % q)
    return 0


@cmd("lsscsi", help=("list SCSI devices (or hosts) and their attributes", "lsscsi [-s]", [("-s", "show device sizes")]))
def c_lsscsi(ctx):
    s = S(ctx.fs)
    for i, (p, v) in enumerate(sorted((p, v) for p, v in s["blk"].items() if v["type"] == "disk")):
        model = v.get("model", "VMware Virtual disk")
        vendor, _, rest = model.partition(" ")
        size = "  %6.1fGB" % (v["size"] * 1048576 / 1e9) if "-s" in ctx.argv else ""
        ctx.w("[2:0:%d:0]    disk    %-8s %-16s 2.0   %s%s\n" % (i, vendor[:8], rest[:16], p, size))
    return 0


# ============================================================================= fdisk
DOS_TYPES = {"83": "Linux", "82": "Linux swap / Solaris", "8e": "Linux LVM", "fd": "Linux raid autodetect", "5": "Extended",
             "7": "HPFS/NTFS/exFAT", "b": "W95 FAT32", "ef": "EFI (FAT-12/16/32)"}
GPT_TYPES = {"1": "EFI System", "19": "Linux swap", "20": "Linux filesystem", "29": "Linux RAID", "30": "Linux LVM"}
ALIASES = {"linux": ("83", "20"), "swap": ("82", "19"), "lvm": ("8e", "30"), "raid": ("fd", "29"), "uefi": ("ef", "1")}


def _ptype_code(label, name):
    table = DOS_TYPES if label == "dos" else GPT_TYPES
    for k, v in table.items():
        if v == name:
            return k
    return "83" if label == "dos" else "20"


def _print_table(ctx, disk, label, P, model):
    s = S(ctx.fs)
    size = s["blk"][disk]["size"]
    ctx.w("Disk %s: %s, %d bytes, %d sectors\nDisk model: %-16s\nUnits: sectors of 1 * 512 = 512 bytes\n"
          "Sector size (logical/physical): 512 bytes / 512 bytes\nI/O size (minimum/optimal): 512 bytes / 512 bytes\n" % (
              disk, fmt_gib(size), size * 1048576, size * SECT, model[7:] if model.startswith("VMware ") else model))
    if not label:
        return
    ctx.w("Disklabel type: %s\n" % label)
    ctx.w(("Disk identifier: 0x%s\n" % ident(disk)) if label == "dos" else ("Disk identifier: %s\n" % uuid_for("gpt" + disk).upper()))
    if not P:
        return
    if label == "dos":
        ctx.w("\nDevice     Boot   Start      End  Sectors  Size Id Type\n")
    else:
        ctx.w("\nDevice       Start      End  Sectors  Size Type\n")
    for num in sorted(P):
        v = P[num]
        st, en = v["start"] * SECT, (v["start"] + v["size"]) * SECT - 1
        if label == "dos":
            ctx.w("%-10s      %8d %8d %8d %5s %2s %s\n" % ("%s%d" % (disk, num), st, en, en - st + 1, fmt(v["size"]), _ptype_code("dos", v["ptype"]), v["ptype"]))
        else:
            ctx.w("%-10s %8d %8d %8d %5s %s\n" % ("%s%d" % (disk, num), st, en, en - st + 1, fmt(v["size"]), v["ptype"]))


def _fdisk_list(ctx, only=None):
    s = S(ctx.fs)
    for p, info in sorted(s["blk"].items()):
        if info["type"] != "disk" or (only and p not in only):
            continue
        P = {s["blk"][q]["num"]: s["blk"][q] for q in parts(s, p)}
        _print_table(ctx, p, info.get("ptable"), P, info.get("model", "VMware Virtual disk"))
        ctx.w("\n")
    return 0


FDISK_HELP = """
Help:

  DOS (MBR)
   a   toggle a bootable flag

  Generic
   d   delete a partition
   F   list free unpartitioned space
   l   list known partition types
   n   add a new partition
   p   print the partition table
   t   change a partition type
   v   verify the partition table

  Misc
   m   print this menu

  Save & Exit
   w   write table to disk and exit
   q   quit without saving changes

  Create a new label
   g   create a new empty GPT partition table
   o   create a new empty DOS partition table
"""


def _make_asker(ctx):
    feed = ctx.stdin.split("\n") if ctx.stdin is not None else None
    count = [0]

    def ask(prompt):
        count[0] += 1
        if count[0] > 300:
            return None
        if feed is not None:
            if not feed or (len(feed) == 1 and feed[0] == ""):
                ctx.w(prompt + "\n")
                return None
            a = feed.pop(0)
            ctx.w(prompt + a + "\n")
            return a.strip()
        a = ctx.ask(prompt)
        return None if a is None else a.strip()
    return ask


def _parse_sector(ans, default, lo, hi):
    """-> MiB position or None. lo/hi in MiB; ans in sectors."""
    if ans == "":
        return default
    if re.match(r"^\d+$", ans):
        v = int(ans) // SECT
        return v if lo <= v <= hi else None
    return None


def _parse_last(ans, start, default_end, hi):
    if ans == "":
        return default_end
    m = re.match(r"^\+(\d+(?:\.\d+)?)\s*([KMGTP])?(?:i?B)?$", ans, re.I)
    if m:
        mult = {None: 1.0 / SECT, "K": 1 / 1024.0, "M": 1, "G": 1024, "T": 1024 * 1024, "P": 1024 ** 3}[(m.group(2) or "").upper() or None]
        end = start + max(1, int(round(float(m.group(1)) * mult)))
        return end if end <= hi else None
    if re.match(r"^\d+$", ans):
        end = (int(ans) + 1) // SECT
        return end if start < end <= hi else None
    return None


def _fdisk_session(ctx, disk):
    s = S(ctx.fs)
    d = s["blk"][disk]
    ask = _make_asker(ctx)
    tbl = {"label": d.get("ptable"), "parts": {}}
    for p in parts(s, disk):
        v = s["blk"][p]
        tbl["parts"][v["num"]] = {"start": v["start"], "size": v["size"], "pkind": v.get("pkind", "primary"), "ptype": v.get("ptype"), "path": p}
    P = tbl["parts"]
    ctx.w("\nWelcome to fdisk (util-linux 2.37.4).\nChanges will remain in memory only, until you decide to write them.\nBe careful before using the write command.\n\n")
    if not tbl["label"]:
        ctx.w("Device does not contain a recognized partition table.\nCreated a new DOS disklabel with disk identifier 0x%s.\n" % ident(disk))
        tbl["label"] = "dos"

    def pick_existing(verb):
        nums = sorted(P)
        if not nums:
            ctx.w("No partition is defined yet!\n")
            return None
        if len(nums) == 1:
            ctx.w("Selected partition %d\n" % nums[0])
            return nums[0]
        for _ in range(3):
            a = ask("Partition number (%s, default %d): " % (",".join(str(n) for n in nums), nums[-1]))
            if a is None:
                return None
            if a == "":
                return nums[-1]
            if a.isdigit() and int(a) in P:
                return int(a)
            ctx.w("Value out of range.\n")
        return None

    def ask_range(prompt_fn, parse):
        for _ in range(3):
            a = ask(prompt_fn())
            if a is None:
                return None
            v = parse(a)
            if v is not None:
                return v
            ctx.w("Value out of range.\n")
        return None

    def new_part():
        label = tbl["label"]
        size = d["size"]
        top = [(v["start"], v["size"]) for n, v in P.items() if v["pkind"] != "logical"]
        if label == "gpt":
            gaps = _gaps(top, 1, size - 1)
            free_nums = [i for i in range(1, 129) if i not in P]
            if not gaps:
                ctx.w("No free sectors available.\n")
                return
            num = ask_range(lambda: "Partition number (%d-128, default %d): " % (free_nums[0], free_nums[0]),
                            lambda a: free_nums[0] if a == "" else (int(a) if a.isdigit() and int(a) in free_nums else None))
            if num is None:
                return
            kind = "primary"
        else:
            ext = [n for n, v in P.items() if v["pkind"] == "extended"]
            slots = [i for i in range(1, 5) if i not in P]
            gaps = _gaps(top, 1, size)
            lgaps = []
            if ext:
                e = P[ext[0]]
                logs = [(v["start"] - 1, v["size"] + 1) for v in P.values() if v["pkind"] == "logical"]
                lgaps = [(a + 1, b) for a, b in _gaps(logs, e["start"], e["start"] + e["size"]) if b - a >= 2]
            can_p = bool(slots and gaps)
            can_l = bool(lgaps)
            if not can_p and not can_l:
                ctx.w("No free sectors available.\n" if slots or ext else
                      "If you want to create more than four partitions, you must replace a primary partition with an extended partition first.\n")
                return
            if not slots:
                ctx.w("All primary partitions are in use.\n")
                kind = "l"
            else:
                nprim = len([n for n in P if n <= 4]) - len(ext)
                ctx.w("Partition type\n   p   primary (%d primary, %d extended, %d free)\n" % (nprim, len(ext), len(slots)))
                ctx.w("   l   logical (numbered from 5)\n" if ext else "   e   extended (container for logical partitions)\n")
                allowed = ["p"] + (["l"] if ext else ["e"])
                deflt = "p" if can_p else "l"
                kind = ask_range(lambda: "Select (default %s): " % deflt, lambda a: deflt if a == "" else (a.lower() if a.lower() in allowed else None))
                if kind is None:
                    return
            if kind in ("p", "e"):
                if not can_p:
                    ctx.w("No free sectors available.\n")
                    return
                rng = ("%d-4" % slots[0]) if slots == list(range(slots[0], 5)) else ",".join(str(x) for x in slots)
                num = ask_range(lambda: "Partition number (%s, default %d): " % (rng, slots[0]),
                                lambda a: slots[0] if a == "" else (int(a) if a.isdigit() and int(a) in slots else None))
                if num is None:
                    return
                kind = "primary" if kind == "p" else "extended"
            else:
                num = max([n for n in P if n >= 5] or [4]) + 1
                ctx.w("Adding logical partition %d\n" % num)
                gaps = lgaps
                kind = "logical"
        lo, hi = gaps[0][0], gaps[-1][1]
        start = ask_range(lambda: "First sector (%d-%d, default %d): " % (lo * SECT, hi * SECT - 1, lo * SECT),
                          lambda a: _parse_sector(a, lo, lo, hi - 1))
        if start is None:
            return
        gap = [g for g in gaps if g[0] <= start < g[1]]
        if not gap:
            ctx.w("Value out of range.\n")
            return
        gend = gap[0][1]
        end = ask_range(lambda: "Last sector, +/-sectors or +/-size{K,M,G,T,P} (%d-%d, default %d): " % (start * SECT, gend * SECT - 1, gend * SECT - 1),
                        lambda a: _parse_last(a, start, gend, gend))
        if end is None:
            return
        ptype = default_ptype(label, kind)
        P[num] = {"start": start, "size": end - start, "pkind": kind, "ptype": ptype, "path": None}
        ctx.w("\nCreated a new partition %d of type '%s' and of size %s.\n" % (num, ptype, fmt_gib(end - start)))

    while True:
        ctx.w("\n")
        a = ask("Command (m for help): ")
        if a is None:
            ctx.w("\n")
            return 0
        if a == "":
            continue
        c = a.split()[0]
        if c == "m":
            ctx.w(FDISK_HELP)
        elif c == "n":
            new_part()
        elif c == "p":
            _print_table(ctx, disk, tbl["label"], P, d.get("model", "VMware Virtual disk"))
        elif c == "d":
            n = pick_existing("delete")
            if n is None:
                continue
            path = P[n].get("path")
            if path and in_use(s, path):
                ctx.w("(simulator) %s is in use (mounted, active swap, LVM or RAID). Unmount / swapoff it first, then delete it.\n" % path)
                continue
            if P[n]["pkind"] == "extended":
                busy = [v["path"] for v in P.values() if v["pkind"] == "logical" and v.get("path") and in_use(s, v["path"])]
                if busy:
                    ctx.w("(simulator) %s is in use; unmount it before deleting the extended partition.\n" % busy[0])
                    continue
                for k in [k for k, v in P.items() if v["pkind"] == "logical"]:
                    del P[k]
            del P[n]
            ctx.w("\nPartition %d has been deleted.\n" % n)
        elif c == "t":
            n = pick_existing("change")
            if n is None:
                continue
            table = DOS_TYPES if tbl["label"] == "dos" else GPT_TYPES
            while True:
                code = ask("Hex code or alias (type L to list all): ")
                if code is None:
                    break
                if code.upper() == "L":
                    ctx.w("".join(" %2s  %s\n" % kv for kv in table.items()) + "\nAliases:\n   linux  swap  lvm  raid  uefi\n")
                    continue
                code = code.lower()
                if code in ALIASES:
                    code = ALIASES[code][0 if tbl["label"] == "dos" else 1]
                if code in table:
                    old = P[n]["ptype"]
                    P[n]["ptype"] = table[code]
                    ctx.w("\nChanged type of partition '%s' to '%s'.\n" % (old, table[code]))
                    break
                ctx.w("Type %s is not valid.\n" % code)
        elif c == "l":
            table = DOS_TYPES if tbl["label"] == "dos" else GPT_TYPES
            ctx.w("".join(" %2s  %s\n" % kv for kv in table.items()))
        elif c == "F":
            top = [(v["start"], v["size"]) for v in P.values() if v["pkind"] != "logical"]
            gaps = _gaps(top, 1, d["size"] - (1 if tbl["label"] == "gpt" else 0))
            ctx.w("Unpartitioned space %s: %s\n" % (disk, fmt_gib(sum(b - a for a, b in gaps))))
            for a_, b_ in gaps:
                ctx.w("  %10d %10d  %s\n" % (a_ * SECT, b_ * SECT - 1, fmt(b_ - a_)))
        elif c == "v":
            top = [(v["start"], v["size"]) for v in P.values() if v["pkind"] != "logical"]
            free = sum(b - a for a, b in _gaps(top, 1, d["size"]))
            ctx.w("Remaining %d unallocated 512-byte sectors.\n" % (free * SECT))
        elif c in ("g", "o"):
            busy = [v["path"] for v in P.values() if v.get("path") and in_use(s, v["path"])]
            if busy:
                ctx.w("(simulator) %s is in use; a new label would destroy it. Unmount it first.\n" % busy[0])
                continue
            P.clear()
            if c == "g":
                tbl["label"] = "gpt"
                ctx.w("Created a new GPT disklabel (GUID: %s).\n" % uuid_for("gpt" + disk).upper())
            else:
                tbl["label"] = "dos"
                ctx.w("Created a new DOS disklabel with disk identifier 0x%s.\n" % ident(disk))
        elif c == "a":
            ctx.w("(simulator) bootable flag noted. Nothing on the exam needs it.\n")
        elif c == "w":
            _fdisk_commit(ctx, disk, tbl)
            return 0
        elif c == "q":
            return 0
        else:
            ctx.w("%s: unknown command\n" % c)


def _remove_part(fs, p):
    s = S(fs)
    s["blk"].pop(p, None)
    s["fsroot"].pop(p, None)
    s["pv"].pop(p, None)
    _unnode(fs, p)


def _fdisk_commit(ctx, disk, tbl):
    fs = ctx.fs
    s = S(fs)
    d = s["blk"][disk]
    busy = disk_busy(s, disk)
    old = {s["blk"][p]["num"]: p for p in parts(s, disk)}
    d["ptable"] = tbl["label"]
    for num, p in old.items():
        nv = tbl["parts"].get(num)
        if nv is None or nv.get("path") != p:
            _remove_part(fs, p)
    for num, v in sorted(tbl["parts"].items()):
        p = "%s%d" % (disk, num)
        if v.get("path") == p and p in s["blk"]:
            s["blk"][p]["ptype"] = v["ptype"]
            continue
        s["blk"][p] = {"type": "part", "size": v["size"], "start": v["start"], "num": num, "pkind": v["pkind"], "ptype": v["ptype"],
                       "fstype": None, "parent": disk, "ptable": None, "dm": False, "pending": busy, "label": None, "pname": ""}
        if not busy:
            _node(fs, p)
    ctx.w("The partition table has been altered.\nCalling ioctl() to re-read partition table.\n")
    if busy:
        ctx.w("Re-reading the partition table failed.: Device or resource busy\n\n"
              "The kernel still uses the old table. The new table will be used at the next reboot or after you run partprobe(8) or partx(8).\n")
    ctx.w("Syncing disks.\n")
    sync(fs)


@cmd("fdisk", help=("manipulate disk partition table (interactive: m n p d t w q)", "fdisk /dev/sdb   |   fdisk -l [/dev/sdb]", [
    ("-l", "list partition tables"), ("m", "(inside fdisk) help"), ("n", "(inside) new partition"), ("p", "(inside) print the table"),
    ("d", "(inside) delete a partition"), ("t", "(inside) change type: 82 swap, 8e LVM, fd RAID"), ("w", "(inside) write and exit"), ("q", "(inside) quit without saving")]))
def c_fdisk(ctx):
    args = ctx.argv[1:]
    if need_root(ctx, "fdisk"):
        ctx.e("fdisk: cannot open %s: Permission denied\n" % (args[-1] if args else "/dev/sda"))
        return 1
    s = S(ctx.fs)
    if "-l" in args:
        devs = [a for a in args if a != "-l"]
        for a in devs:
            if a not in s["blk"]:
                ctx.e("fdisk: cannot open %s: No such file or directory\n" % a)
                return 1
        return _fdisk_list(ctx, devs or None)
    devs = [a for a in args if not a.startswith("-")]
    if not devs:
        ctx.e("Usage:\n fdisk [options] <disk>         change partition table\n fdisk [options] -l [<disk>...] list partition table(s)\n")
        return 1
    dev = devs[0]
    if dev not in s["blk"]:
        ctx.e("fdisk: cannot open %s: No such file or directory\n" % dev)
        return 1
    if s["blk"][dev]["type"] != "disk":
        ctx.e("(simulator) %s is a partition. Run fdisk on the whole disk, e.g. fdisk %s\n" % (dev, s["blk"][dev].get("parent") or dev))
        return 1
    return _fdisk_session(ctx, dev)


@cmd("partprobe", "partx", help=("inform the kernel (and /dev) of partition table changes", "partprobe [DEVICE]", []))
def c_partprobe(ctx):
    if need_root(ctx, ctx.name):
        return 1
    s = S(ctx.fs)
    devs = [a for a in ctx.argv[1:] if a.startswith("/dev/")]
    for p, v in list(s["blk"].items()):
        if v.get("pending") and (not devs or v.get("parent") in devs):
            v["pending"] = False
            _node(ctx.fs, p)
    sync(ctx.fs)
    return 0


# ============================================================================= parted
UNITS = {"s": 1.0 / SECT, "b": 1 / 1048576.0, "kb": 1000 / 1048576.0, "mb": 1e6 / 1048576, "gb": 1e9 / 1048576, "tb": 1e12 / 1048576,
         "kib": 1 / 1024.0, "mib": 1, "gib": 1024, "tib": 1024 * 1024}


def _parted_pos(txt, disk_size):
    t = txt.strip().lower()
    m = re.match(r"^(-?\d+(?:\.\d+)?)\s*(%|s|b|kb|mb|gb|tb|kib|mib|gib|tib|k|m|g|t)?$", t)
    if not m:
        return None
    v = float(m.group(1))
    u = m.group(2) or "mb"
    u = {"k": "kb", "m": "mb", "g": "gb", "t": "tb"}.get(u, u)
    if u == "%":
        mib = disk_size * v / 100.0
    else:
        mib = v * UNITS[u]
    if v < 0:
        mib = disk_size + mib
    return int(round(mib))


def _compact(mib):
    b = mib * 1048576.0
    if b < 1e6:
        return "%dkB" % round(b / 1000)
    if b < 1e10:
        return "%dMB" % round(b / 1e6)
    return "%.1fGB" % (b / 1e9)


def _parted_print(ctx, disk):
    s = S(ctx.fs)
    d = s["blk"][disk]
    label = {"dos": "msdos", "gpt": "gpt"}.get(d.get("ptable"))
    if not label:
        ctx.e("Error: %s: unrecognised disk label\n" % disk)
    ctx.w("Model: %s (scsi)\nDisk %s: %s\nSector size (logical/physical): 512B/512B\nPartition Table: %s\nDisk Flags: \n\n" % (
        d.get("model", "VMware Virtual disk"), disk, _compact(d["size"]), label or "unknown"))
    if not label:
        return
    if label == "gpt":
        ctx.w("Number  Start   End     Size    File system     Name     Flags\n")
    else:
        ctx.w("Number  Start   End     Size    Type      File system     Flags\n")
    for p in parts(s, disk):
        v = s["blk"][p]
        st = _compact(v["start"]) if v["start"] > 1 else "1049kB"
        fsn = "linux-swap(v1)" if v.get("fstype") == "swap" else (v.get("fstype") or "")
        if label == "gpt":
            ctx.w(" %-6d %-7s %-7s %-7s %-15s %-8s\n" % (v["num"], st, _compact(v["start"] + v["size"]), _compact(v["size"]), fsn, v.get("pname", "")))
        else:
            ctx.w(" %-6d %-7s %-7s %-7s %-9s %-15s\n" % (v["num"], st, _compact(v["start"] + v["size"]), _compact(v["size"]), v.get("pkind", "primary"), fsn))
    ctx.w("\n")


PARTED_FS = ("ext2", "ext3", "ext4", "xfs", "btrfs", "linux-swap", "fat16", "fat32", "ntfs", "hfs+")
PARTED_HELP = """  help [COMMAND]                           print general help, or help on COMMAND
  mklabel,mktable LABEL-TYPE               create a new disklabel (partition table): gpt or msdos
  mkpart PART-TYPE [FS-TYPE] START END     make a partition
  print [devices|free|list,all]            display the partition table
  quit                                     exit program
  rm NUMBER                                delete partition NUMBER
  unit UNIT                                set the default unit to UNIT
"""


def _parted_mkpart(ctx, disk, toks, ask):
    """toks: remaining tokens of this command (consumed). Returns True if ok."""
    s = S(ctx.fs)
    d = s["blk"][disk]
    label = d.get("ptable")
    if not label:
        ctx.e("Error: %s: unrecognised disk label\n" % disk)
        return False

    def need(prompt):
        if toks:
            return toks.pop(0)
        if ask is None:
            return None
        return ask(prompt)

    if label == "gpt":
        name = need("Partition name?  []? ")
        if name is None:
            ctx.e("Error: Expecting a partition name.\n")
            return False
        pkind = "primary"
    else:
        name = ""
        pk = need("Partition type?  primary/extended? ")
        if pk not in ("primary", "extended", "logical"):
            ctx.e("parted: invalid token: %s\nError: Expecting a partition type.\n" % pk)
            return False
        pkind = pk
    fst = None
    if toks and toks[0].lower() in PARTED_FS:
        fst = toks.pop(0).lower()
    elif ask is not None and not toks:
        a = ask("File system type?  [ext2]? ")
        if a is None:
            return False
        fst = (a or "ext2").lower()
    start = need("Start? ")
    end = need("End? ")
    if start is None or end is None:
        ctx.e("Error: Expecting a start and an end.\n")
        return False
    a = _parted_pos(start, d["size"])
    b = _parted_pos(end, d["size"])
    if a is None or b is None or b <= a:
        ctx.e("Error: Invalid start/end: %s %s\n" % (start, end))
        return False
    a = max(1, a)
    b = min(b, d["size"] - (1 if label == "gpt" else 0))
    existing = [s["blk"][p] for p in parts(s, disk)]
    if pkind == "logical":
        ext = [v for v in existing if v.get("pkind") == "extended"]
        if not ext:
            ctx.e("Error: Can't create a logical partition: there is no extended partition.\n")
            return False
        e = ext[0]
        if a < e["start"] or b > e["start"] + e["size"]:
            ctx.e("Error: Can't have a logical partition outside of the extended partition.\n")
            return False
        others = [v for v in existing if v.get("pkind") == "logical"]
        num = max([v["num"] for v in others] or [4]) + 1
    else:
        others = [v for v in existing if v.get("pkind") != "logical"]
        used = [v["num"] for v in existing]
        if label == "dos":
            free = [i for i in range(1, 5) if i not in used]
            if not free:
                ctx.e("Error: Too many primary partitions.\n")
                return False
            if pkind == "extended" and any(v.get("pkind") == "extended" for v in existing):
                ctx.e("Error: Too many extended partitions.\n")
                return False
            num = free[0]
        else:
            num = min(i for i in range(1, 129) if i not in used)
    for v in others:
        if a < v["start"] + v["size"] and v["start"] < b:
            ctx.e("Error: Can't have overlapping partitions.\n")
            return False
    p = "%s%d" % (disk, num)
    ptype = "Linux swap" if fst == "linux-swap" else default_ptype(label, pkind)
    s["blk"][p] = {"type": "part", "size": b - a, "start": a, "num": num, "pkind": pkind, "ptype": ptype, "fstype": None,
                   "parent": disk, "ptable": None, "dm": False, "pending": False, "label": None, "pname": name}
    _node(ctx.fs, p)
    sync(ctx.fs)
    return True


def _parted_one(ctx, disk, toks, ask, script):
    """Run one parted command from toks (consumed). Returns 'quit', True (ok) or False (error)."""
    s = S(ctx.fs)
    d = s["blk"][disk]
    c = toks.pop(0).lower()
    if c in ("quit", "q"):
        return "quit"
    if c == "help":
        ctx.w(PARTED_HELP)
        return True
    if c == "print":
        if toks and toks[0] in ("free", "all", "list", "devices"):
            toks.pop(0)
        _parted_print(ctx, disk)
        return True
    if c in ("mklabel", "mktable"):
        lab = toks.pop(0) if toks else (ask("New disk label type? ") if ask else None)
        if lab not in ("gpt", "msdos"):
            ctx.e("parted: invalid token: %s\nError: Expecting a disk label type (gpt or msdos).\n" % lab)
            return False
        if disk_busy(s, disk):
            ctx.e("Error: Partition(s) on %s are being used.\n" % disk)
            return False
        if d.get("ptable") and not script:
            a = ask("Warning: The existing disk label on %s will be destroyed and all data on this disk will be lost. Do you want to continue?\nYes/No? " % disk) if ask else "yes"
            if (a or "").lower() not in ("y", "yes"):
                return False
        for p in parts(s, disk):
            _remove_part(ctx.fs, p)
        d["ptable"] = "dos" if lab == "msdos" else "gpt"
        sync(ctx.fs)
        return True
    if c == "mkpart":
        return _parted_mkpart(ctx, disk, toks, None if script else ask)
    if c == "rm":
        n = toks.pop(0) if toks else (ask("Partition number? ") if ask else None)
        p = "%s%s" % (disk, n)
        if p not in s["blk"]:
            ctx.e("Error: Partition doesn't exist.\n")
            return False
        if in_use(s, p):
            ctx.e("Error: Partition %s is being used. You must unmount it before you modify it with Parted.\n" % p)
            return False
        if s["blk"][p].get("pkind") == "extended":
            for q in parts(s, disk):
                if s["blk"][q].get("pkind") == "logical":
                    _remove_part(ctx.fs, q)
        _remove_part(ctx.fs, p)
        sync(ctx.fs)
        return True
    if c == "unit":
        if toks:
            toks.pop(0)
        return True
    ctx.e('parted: invalid token: %s\nError: Unknown command "%s". Type help for the list.\n' % (c, c))
    return False


@cmd("parted", help=("partition manipulation program (writes each change immediately)", "parted /dev/sdb   |   parted -s /dev/sdb mklabel gpt mkpart primary xfs 1MiB 100%", [
    ("-s", "script mode: never prompt"), ("mklabel gpt|msdos", "(inside) new partition table"), ("mkpart NAME [FS] START END", "(inside) new partition; FS does NOT format it"),
    ("print", "(inside) show the table"), ("rm N", "(inside) delete partition N"), ("quit", "(inside) leave")]))
def c_parted(ctx):
    if need_root(ctx, "parted"):
        return 1
    script = any(a in ("-s", "--script") for a in ctx.argv[1:])
    args = [a for a in ctx.argv[1:] if a not in ("-s", "--script")]
    s = S(ctx.fs)
    if not args:
        ctx.e("(simulator) give the disk: parted /dev/sdb\n")
        return 1
    dev = args[0]
    if dev not in s["blk"] or s["blk"][dev]["type"] != "disk":
        ctx.e("Error: Could not stat device %s - No such file or directory.\n" % dev)
        return 1
    toks = args[1:]
    if toks:     # one-shot / script mode: run the commands and exit
        while toks:
            r = _parted_one(ctx, dev, toks, None if script else _make_asker(ctx), script)
            if r is False:
                return 1
            if r == "quit":
                break
        return 0
    ask = _make_asker(ctx)
    ctx.w("GNU Parted 3.4\nUsing %s\nWelcome to GNU Parted! Type 'help' to view a list of commands.\n" % dev)
    while True:
        line = ask("(parted) ")
        if line is None:
            ctx.w("Information: You may need to update /etc/fstab.\n\n")
            return 0
        toks = line.split()
        while toks:
            r = _parted_one(ctx, dev, toks, ask, False)
            if r == "quit":
                ctx.w("Information: You may need to update /etc/fstab.\n\n")
                return 0
            if r is False:
                break


@cmd("growpart", help=("extend a partition into the free space after it", "growpart DISK PARTNUM", []))
def c_growpart(ctx):
    if need_root(ctx, "growpart"):
        return 1
    s = S(ctx.fs)
    if len(ctx.argv) < 3:
        ctx.e("growpart disk partition\n   rewrite partition table so that partition takes up all the space it can\n")
        return 2
    p = "%s%s" % (ctx.argv[1], ctx.argv[2])
    if p not in s["blk"]:
        ctx.e("FAILED: %s: partition %s does not exist\n" % (ctx.argv[1], ctx.argv[2]))
        return 2
    v = s["blk"][p]
    d = s["blk"][ctx.argv[1]]
    after = [s["blk"][q]["start"] for q in parts(s, ctx.argv[1]) if s["blk"][q]["start"] > v["start"] and s["blk"][q].get("pkind") != "logical"]
    limit = min(after) if after else d["size"] - (1 if d.get("ptable") == "gpt" else 0)
    if limit <= v["start"] + v["size"]:
        ctx.w("NOCHANGE: partition %s is size %d. it cannot be grown\n" % (ctx.argv[2], v["size"] * SECT))
        return 1
    old = v["size"]
    v["size"] = limit - v["start"]
    ctx.w("CHANGED: partition=%s start=%d old: size=%d end=%d new: size=%d end=%d\n" % (
        ctx.argv[2], v["start"] * SECT, old * SECT, (v["start"] + old) * SECT, v["size"] * SECT, limit * SECT))
    sync(ctx.fs)
    return 0


# ============================================================================= mkfs
def _mkfs(ctx, fstype, args, label=None, force=False):
    if need_root(ctx, ctx.name):
        return 1
    s = S(ctx.fs)
    devs = [a for a in args if a.startswith("/dev/")]
    if not devs:
        ctx.e("%s: no device given\n" % ctx.name)
        return 1
    d = devs[0]
    if not visible(s, d):
        ctx.e("%s: The file %s does not exist and no size was specified.\n" % (ctx.name, d))
        return 1
    info = s["blk"][d]
    if info["type"] == "disk" and parts(s, d):
        ctx.e("%s: %s is apparently in use by the system; will not make a filesystem here!\n" % (ctx.name, d))
        return 1
    if info.get("pkind") == "extended":
        ctx.e("%s: %s is an extended partition: it only holds logical partitions. Format one of those (e.g. %s5).\n" % (ctx.name, d, info["parent"]))
        return 1
    if d in s["mounts"].values():
        ctx.e("%s: %s is mounted; will not make a filesystem here!\n" % (ctx.name, d))
        return 1
    if in_use(s, d):
        ctx.e("%s: %s is apparently in use by the system; will not make a filesystem here!\n" % (ctx.name, d))
        return 1
    if info.get("fstype") and not force:
        if fstype == "xfs":
            ctx.e("mkfs.xfs: %s appears to contain an existing filesystem (%s).\nmkfs.xfs: Use the -f option to force overwrite.\n" % (d, info["fstype"]))
            return 1
        if fstype.startswith("ext"):
            a = ctx.ask("%s contains a %s file system%s\nProceed anyway? (y,N) " % (d, info["fstype"], (" labelled '%s'" % info["label"]) if info.get("label") else ""))
            if (a or "").strip().lower()[:1] != "y":
                return 1
    info["fstype"] = fstype
    info["label"] = label
    _new_root(ctx.fs, d, fstype)
    blocks = info["size"] * 256
    if fstype == "xfs":
        ctx.w("meta-data=%-22s isize=512    agcount=4, agsize=%d blks\n         =                       sectsz=512   attr=2, projid32bit=1\n"
              "data     =                       bsize=4096   blocks=%d, imaxpct=25\nnaming   =version 2              bsize=4096   ascii-ci=0, ftype=1\n"
              "log      =internal log           bsize=4096   blocks=2560, version=2\nrealtime =none                   extsz=4096   blocks=0, rtextents=0\n" % (d, blocks // 4, blocks))
    elif fstype.startswith("ext"):
        ctx.w("mke2fs 1.46.5 (30-Dec-2021)\nCreating filesystem with %d 4k blocks and %d inodes\nFilesystem UUID: %s\n"
              "Superblock backups stored on blocks: \n\t32768, 98304, 163840, 229376\n\nAllocating group tables: done\nWriting inode tables: done\n"
              "%sWriting superblocks and filesystem accounting information: done\n\n" % (blocks, blocks // 4, uuid_for(d), "Creating journal (16384 blocks): done\n" if fstype != "ext2" else ""))
    elif fstype == "btrfs":
        ctx.w("btrfs-progs v6.2.1\nLabel:              %s\nUUID:               %s\nNode size:          16384\nFilesystem size:    %s\n" % (
            label or "(null)", uuid_for(d), fmt_gib(info["size"])))
    else:
        ctx.w("mkfs.%s: created a %s filesystem on %s\n" % (fstype, fstype, d))
    sync(ctx.fs)
    return 0


def _mkfs_cmd(fst):
    def fn(ctx):
        opts, args = getopts(ctx, ctx.argv[1:], flags="fFqv", valued="LnbmtI")
        if opts is None:
            return 1
        return _mkfs(ctx, fst, args, label=opts.get("L"), force=bool(opts.get("f") or opts.get("F")))
    return fn


for _fs in ("ext2", "ext3", "ext4", "xfs", "btrfs", "vfat"):
    cmd("mkfs." + _fs, help=("build a %s filesystem" % _fs, "mkfs.%s [-L LABEL] DEVICE" % _fs, [("-L LABEL", "set a filesystem label"), ("-f", "(xfs) overwrite an existing filesystem")]))(_mkfs_cmd(_fs))


@cmd("mkfs", help=("build a Linux filesystem", "mkfs -t TYPE DEVICE", [("-t TYPE", "filesystem type (ext4, xfs, ...)")]))
def c_mkfs(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="fFqv", valued="tL")
    if opts is None:
        return 1
    return _mkfs(ctx, opts.get("t", "ext2"), args, label=opts.get("L"), force=bool(opts.get("f") or opts.get("F")))


# ============================================================================= swap
def swap_size(fs, d):
    s = S(fs)
    if d in s["blk"]:
        return s["blk"][d]["size"]
    try:
        n = fs.lookup(d)
        return (n.size() // 1048576) if n is not None else 0
    except FSError:
        return 0


def _swap_ok(fs, d):
    """Does d carry a swap signature? Works for devices and swap files."""
    s = S(fs)
    if d in s["blk"]:
        return visible(s, d) and s["blk"][d].get("fstype") == "swap"
    try:
        n = fs.lookup(d)
    except FSError:
        return False
    return n is not None and n.kind == "f" and getattr(n, "swapsig", False)


@cmd("mkswap", help=("set up a Linux swap area on a partition or file", "mkswap DEVICE|FILE", []))
def c_mkswap(ctx):
    if need_root(ctx, "mkswap"):
        return 1
    s = S(ctx.fs)
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    if not args:
        ctx.e("mkswap: no device specified\n")
        return 1
    d = args[0]
    if d.startswith("/dev/"):
        if not visible(s, d):
            ctx.e("mkswap: cannot open %s: No such file or directory\n" % d)
            return 1
        if d in s["mounts"].values():
            ctx.e("mkswap: error: %s is mounted; will not make swapspace\n" % d)
            return 1
        s["blk"][d]["fstype"] = "swap"
        s["fsroot"].pop(d, None)
        size = s["blk"][d]["size"]
    else:
        ap = ctx.fs.abspath(d)
        n = ctx.fs.lookup(ap)
        if n is None or n.kind != "f":
            ctx.e("mkswap: cannot open %s: No such file or directory\n" % d)
            return 1
        size = n.size() // 1048576
        if size < 1:
            ctx.e("mkswap: error: swap area needs to be at least 40 KiB\n(make the file first: dd if=/dev/zero of=%s bs=1M count=1024)\n" % d)
            return 1
        if n.mode & 0o077:
            ctx.e("mkswap: %s: insecure permissions %04o, fix with: chmod 0600 %s\n" % (d, n.mode & 0o777, d))
        n.swapsig = True
        d = ap
    ctx.w("Setting up swapspace version 1, size = %s (%d bytes)\nno label, UUID=%s\n" % (fmt_gib(size), size * 1048576, uuid_for(d)))
    return 0


def _swapon_one(ctx, d, quiet=False):
    s = S(ctx.fs)
    spec = d
    if d.startswith("UUID="):
        d = _resolve(s, d) or d
    ap = d if d.startswith("/dev/") else ctx.fs.abspath(d)
    if not _swap_ok(ctx.fs, ap):
        ctx.e("swapon: %s: read swap header failed (run mkswap on it first)\n" % spec)
        return 255
    if ap not in s["blk"]:
        n = ctx.fs.lookup(ap)
        if n.mode & 0o077 and not quiet:
            ctx.e("swapon: %s: insecure permissions %04o, 0600 suggested.\n" % (ap, n.mode & 0o777))
    if ap in s["swaps"]:
        ctx.e("swapon: %s: swapon failed: Device or resource busy\n" % spec)
        return 255
    s["swaps"].append(ap)
    sync(ctx.fs)
    return 0


@cmd("swapon", help=("enable swap on a device or file", "swapon DEVICE|FILE | swapon -a | swapon --show", [
    ("--show", "list active swap"), ("-a", "enable every swap entry in /etc/fstab"), ("-s", "summary (like cat /proc/swaps)")]))
def c_swapon(ctx):
    s = S(ctx.fs)
    args = ctx.argv[1:]
    if "--show" in args or not args:
        if s["swaps"]:
            ctx.w("NAME      TYPE       SIZE USED PRIO\n")
        for d in s["swaps"]:
            ctx.w("%-9s %-9s %5s   0B   -2\n" % (d, "partition" if d.startswith("/dev/") else "file", fmt(swap_size(ctx.fs, d))))
        return 0
    if "-s" in args:
        ctx.w(ctx.fs.read("/proc/swaps", "root"))
        return 0
    if need_root(ctx, "swapon"):
        return 1
    if "-a" in args:
        rc = 0
        for e in fstab_entries(ctx.fs):
            if e["type"] == "swap" and not e["system"]:
                spec = _resolve(s, e["dev"]) or e["dev"]
                if (spec if spec.startswith("/dev/") else ctx.fs.abspath(spec)) not in s["swaps"]:
                    rc = _swapon_one(ctx, e["dev"]) or rc
        return rc
    rc = 0
    for d in [a for a in args if not a.startswith("-")]:
        rc = _swapon_one(ctx, d) or rc
    return rc


@cmd("swapoff", help=("disable swap", "swapoff DEVICE|FILE | swapoff -a", [("-a", "disable all swap")]))
def c_swapoff(ctx):
    s = S(ctx.fs)
    if need_root(ctx, "swapoff"):
        return 1
    if "-a" in ctx.argv:
        s["swaps"] = []
        sync(ctx.fs)
        return 0
    rc = 0
    for d in [a for a in ctx.argv[1:] if not a.startswith("-")]:
        ap = d if d.startswith("/dev/") else ctx.fs.abspath(d)
        if ap in s["swaps"]:
            s["swaps"].remove(ap)
        else:
            ctx.e("swapoff: %s: swapoff failed: Invalid argument\n" % d)
            rc = 255
    sync(ctx.fs)
    return rc


@cmd("free", help=("display amount of free and used memory (RAM and swap)", "free [-h] [-m]", [("-h", "human-readable"), ("-m", "in MiB")]))
def c_free(ctx):
    s = S(ctx.fs)
    ram = s["ram"]
    sw = sum(swap_size(ctx.fs, d) for d in s["swaps"])
    used, cache = int(ram * 0.62), int(ram * 0.28)
    freem = ram - used - cache

    def f(m):
        if "-h" in ctx.argv:
            return "%.1fGi" % (m / 1024.0) if m >= 1024 else ("%dMi" % m if m else "0B")
        if "-m" in ctx.argv:
            return str(m)
        return str(m * 1024)
    ctx.w("               total        used        free      shared  buff/cache   available\n")
    ctx.w("Mem:      %10s  %10s  %10s  %10s  %10s  %10s\n" % (f(ram), f(used), f(freem), f(12), f(cache), f(freem + cache - 40)))
    ctx.w("Swap:     %10s  %10s  %10s\n" % (f(sw), f(0), f(sw)))
    return 0


# ============================================================================= mounting
def fstab_entries(fs):
    out = []
    try:
        text = fs.read("/etc/fstab", "root")
    except FSError:
        return out
    for i, l in enumerate(lines_of(text)):
        t = l.strip()
        if not t or t.startswith("#"):
            continue
        f = t.split()
        e = {"dev": f[0], "mp": f[1] if len(f) > 1 else "", "type": f[2] if len(f) > 2 else "", "opts": f[3] if len(f) > 3 else "defaults",
             "fields": len(f), "line": i + 1, "text": t}
        e["system"] = e["mp"] in ("/", "/boot") or e["dev"].startswith("/dev/mapper/rl-")
        out.append(e)
    return out


def _resolve(s, spec):
    """UUID=..., LABEL=... or /dev/... -> device path or None."""
    spec = spec.strip('"')
    if spec.startswith("UUID="):
        want = spec[5:].strip('"').lower()
        for p in s["blk"]:
            if visible(s, p) and uuid_for(p) == want and (s["blk"][p].get("fstype") or p in s["pv"]):
                return p
        return None
    if spec.startswith("LABEL="):
        want = spec[6:].strip('"')
        for p, v in s["blk"].items():
            if visible(s, p) and v.get("label") == want:
                return p
        return None
    return spec if visible(s, spec) else None


def _do_mount(ctx, spec, mp, fstype=None, opts="defaults"):
    s = S(ctx.fs)
    fs = ctx.fs
    if spec == "tmpfs" or fstype == "tmpfs":
        if not fs.isdir(mp):
            ctx.e("mount: %s: mount point does not exist.\n" % mp)
            return 32
        if fs.abspath(mp) in s["mounts"]:
            ctx.e("mount: %s: tmpfs already mounted or mount point busy.\n" % mp)
            return 32
        attach(fs, "tmpfs", mp, opts)
        return 0
    dev = _resolve(s, spec)
    if dev is None:
        if spec.startswith(("UUID=", "LABEL=")):
            ctx.e("mount: %s: can't find %s.\n" % (mp, spec))
        else:
            ctx.e("mount: %s: special device %s does not exist.\n" % (mp, spec))
        return 32
    info = s["blk"][dev]
    actual = info.get("fstype")
    if not actual or actual == "swap" or dev in s["pv"] or info.get("pkind") == "extended":
        ctx.e("mount: %s: wrong fs type, bad option, bad superblock on %s, missing codepage or helper program, or other error.\n" % (mp, dev))
        return 32
    if fstype and fstype not in ("auto", actual):
        ctx.e("mount: %s: wrong fs type, bad option, bad superblock on %s, missing codepage or helper program, or other error.\n" % (mp, dev))
        return 32
    if not fs.isdir(mp):
        ctx.e("mount: %s: mount point does not exist.\n" % mp)
        return 32
    ap = fs.abspath(mp)
    if dev in s["mounts"].values():
        ctx.e("mount: %s: %s already mounted on %s.\n" % (mp, dev, [k for k, v in s["mounts"].items() if v == dev][0]))
        return 32
    if ap in s["mounts"]:
        ctx.e("mount: %s: %s already mounted or mount point busy.\n" % (mp, dev))
        return 32
    attach(fs, dev, ap, opts)
    return 0


def _mount_all(ctx, verbose=False):
    s = S(ctx.fs)
    rc = 0
    for e in fstab_entries(ctx.fs):
        if e["system"] or e["type"] == "swap" or "noauto" in e["opts"].split(","):
            continue
        if e["fields"] < 4:
            ctx.e("mount: /etc/fstab: parse error at line %d -- ignored\n" % e["line"])
            rc = 32
            continue
        if ctx.fs.abspath(e["mp"]) in s["mounts"]:
            continue
        r = _do_mount(ctx, e["dev"], e["mp"], e["type"], e["opts"])
        rc = r or rc
    return rc


@cmd("mount", help=("mount a filesystem", "mount DEVICE DIRECTORY | mount -a | mount -o remount DIR", [
    ("-a", "mount everything in /etc/fstab (test fstab before rebooting)"), ("-t TYPE", "filesystem type (xfs, ext4, tmpfs)"),
    ("-o OPTS", "options, e.g. remount,usrquota"), ("(no args)", "list mounted filesystems")]))
def c_mount(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="avrlf", valued="to")
    if opts is None:
        return 1
    s = S(ctx.fs)
    if not args and "a" not in opts:
        ctx.w("/dev/mapper/rl-root on / type xfs (rw,relatime,seclabel)\n/dev/sda1 on /boot type xfs (rw,relatime,seclabel)\n")
        for mp, dev in sorted(s["mounts"].items()):
            if dev.startswith("tmpfs:"):
                ctx.w("tmpfs on %s type tmpfs (rw,relatime%s)\n" % (mp, _extra_opts(s, mp)))
            else:
                ctx.w("%s on %s type %s (rw,relatime%s)\n" % (dev, mp, s["blk"].get(dev, {}).get("fstype", "?"), _extra_opts(s, mp)))
        return 0
    if need_root(ctx, "mount"):
        ctx.e("mount: only root can do that\n")
        return 32
    o = opts.get("o", "")
    if "remount" in o.split(","):
        if not args:
            ctx.e("mount: no mount point given for remount\n")
            return 1
        ap = ctx.fs.abspath(args[-1])
        if ap not in s["mounts"]:
            ctx.e("mount: %s: mount point not mounted or bad option.\n" % args[-1])
            return 32
        new = [x for x in o.split(",") if x and x != "remount"]
        for e in fstab_entries(ctx.fs):
            if ctx.fs.abspath(e["mp"] or "/x") == ap:
                new = e["opts"].split(",") + new
        cur = [x for x in s["mopts"].get(ap, "defaults").split(",")]
        merged = []
        for x in cur + new:
            if x not in merged:
                merged.append(x)
        s["mopts"][ap] = ",".join(merged)
        sync(ctx.fs)
        return 0
    if "a" in opts:
        return _mount_all(ctx)
    if len(args) == 1:
        for e in fstab_entries(ctx.fs):
            if e["mp"] == args[0] or e["dev"] == args[0] or ctx.fs.abspath(e["mp"] or "/x") == ctx.fs.abspath(args[0]):
                return _do_mount(ctx, e["dev"], e["mp"], e["type"], e["opts"])
        ctx.e("mount: %s: can't find in /etc/fstab.\n" % args[0])
        return 32
    return _do_mount(ctx, args[0], args[1], opts.get("t"), o or "defaults")


@cmd("umount", help=("unmount a filesystem (no 'n')", "umount DIRECTORY|DEVICE", []))
def c_umount(ctx):
    if need_root(ctx, "umount"):
        ctx.e("umount: only root can do that\n")
        return 32
    s = S(ctx.fs)
    rc = 0
    for t in [a for a in ctx.argv[1:] if not a.startswith("-")] or [""]:
        if not t:
            ctx.e("umount: bad usage\n")
            return 1
        ap = ctx.fs.abspath(t)
        if ap not in s["mounts"]:
            hits = [mp for mp, dev in s["mounts"].items() if dev == t]
            if not hits:
                ctx.e("umount: %s: not mounted.\n" % t)
                rc = 32
                continue
            ap = hits[0]
        if ctx.fs.cwd == ap or ctx.fs.cwd.startswith(ap + "/"):
            ctx.e("umount: %s: target is busy.\n" % t)
            rc = 32
            continue
        detach(ctx.fs, ap)
    return rc


def _fs_used(fs, dev):
    s = S(fs)
    r = s["fsroot"].get(dev)
    return (_tree_bytes(fs, r["entries"]) // 1048576) if r else 0


@cmd("df", help=("report filesystem space usage", "df [-h] [-T]", [("-h", "human-readable sizes"), ("-T", "show filesystem type")]))
def c_df(ctx):
    s = S(ctx.fs)
    T = "-T" in ctx.argv or "-hT" in ctx.argv or "-Th" in ctx.argv
    hflag = any(a.startswith("-") and "h" in a for a in ctx.argv[1:])
    rows = [("/dev/mapper/rl-root", "xfs", 17 * 1024, 3994, "/"), ("/dev/sda1", "xfs", 1014, 280, "/boot")]
    for mp, dev in sorted(s["mounts"].items()):
        if dev.startswith("tmpfs:"):
            rows.append(("tmpfs", "tmpfs", 950, _fs_used(ctx.fs, dev), mp))
        else:
            info = s["blk"].get(dev, {})
            rows.append((dev, info.get("fstype", "?"), info.get("fs_size", info.get("size", 0)), _fs_used(ctx.fs, dev) + 30, mp))
    ctx.w("Filesystem          %s %s  Used Avail Use%% Mounted on\n" % ("Type " if T else "", " Size" if hflag else "1K-blocks"))
    for dev, typ, size, used, mp in rows:
        used = min(used, size)
        pct = int(round(100.0 * used / size)) if size else 0
        val = (lambda m: fmt(m)) if hflag else (lambda m: str(m * 1024))
        ctx.w("%-19s %s %5s %5s %5s %3d%% %s\n" % (dev, ("%-5s" % typ) if T else "", val(size), val(used), val(size - used), pct, mp))
    return 0


@cmd("du", help=("estimate file space usage", "du [-sh] FILE...", [("-s", "summary only"), ("-h", "human-readable")]))
def c_du(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="shac")
    if opts is None:
        return 1
    for a in args or ["."]:
        try:
            node = ctx.fs.lookup(a)
            if node is None:
                ctx.err("cannot access '%s': No such file or directory" % a)
                continue
            total = (4096 + _tree_bytes(ctx.fs, node.entries)) if node.kind == "d" else node.size()
        except FSError:
            continue
        ctx.w("%s\t%s\n" % (human(total) if "h" in opts else str(max(4, total // 1024)), a))
    return 0


# ============================================================================= reboot
@cmd("reboot", "shutdown", help=("restart the machine (re-reads /etc/fstab at boot)", "reboot   |   shutdown -r now", []))
def c_reboot(ctx):
    if ctx.name == "shutdown" and "-r" not in ctx.argv:
        ctx.w("(simulator) only 'shutdown -r now' (reboot) is supported: powering off would end the mission.\n")
        return 1
    if not ctx.root:
        ctx.e("Call to Reboot failed: Interactive authentication required. (use sudo)\n")
        return 1
    fs = ctx.fs
    s = S(fs)
    fs.cwd = fs.env["HOME"]
    for ap in sorted(s["mounts"], key=len, reverse=True):
        detach(fs, ap)
    s["swaps"] = []
    for p, v in s["blk"].items():
        if v.get("pending"):
            v["pending"] = False
            _node(fs, p)
    s["boots"] += 1
    errors = []
    ctx.w("Broadcast message from root@%s: The system will reboot now!\n\n" % fs.host)
    ctx.w("[  OK  ] Reached target Local File Systems (Pre).\n[  OK  ] Mounted /boot.\n")
    for e in fstab_entries(fs):
        if e["system"]:
            continue
        if e["fields"] < 4:
            errors.append("/etc/fstab line %d is incomplete: %s" % (e["line"], e["text"]))
            ctx.w("[FAILED] Failed to parse /etc/fstab line %d.\n" % e["line"])
            continue
        o = e["opts"].split(",")
        if e["type"] == "swap":
            sub = Quiet(ctx)
            r = _swapon_one(sub, e["dev"], quiet=True)
            if r:
                errors.append("swap %s: %s" % (e["dev"], sub.msg.strip()))
                ctx.w("[FAILED] Failed to activate swap %s.\n" % e["dev"])
            else:
                ctx.w("[  OK  ] Activated swap %s.\n" % e["dev"])
            continue
        if "noauto" in o:
            continue
        sub = Quiet(ctx)
        r = _do_mount(sub, e["dev"], e["mp"], e["type"], e["opts"])
        if r:
            if "nofail" in o:
                ctx.w("[ WARN ] %s not mounted (nofail): %s\n" % (e["mp"], sub.msg.strip()))
            else:
                errors.append(sub.msg.strip())
                ctx.w("[FAILED] Failed to mount %s.\n[DEPEND] Dependency failed for Local File Systems.\n" % e["mp"])
        else:
            ctx.w("[  OK  ] Mounted %s.\n" % e["mp"])
    s["boot_ok"] = not errors
    s["boot_errors"] = errors
    if errors:
        ctx.w("\nYou are in emergency mode. After logging in, type \"journalctl -xb\" to view\nsystem logs, \"systemctl reboot\" to reboot, \"systemctl default\" or \"exit\"\nto boot into default mode.\n")
        ctx.w("\njournal: " + "\n         ".join(errors) + "\n")
        ctx.w("(fix /etc/fstab, test it with  sudo mount -a , then  sudo reboot  again)\n")
    else:
        ctx.w("[  OK  ] Reached target Multi-User System.\n\n%s login: %s (auto-login)\n" % (fs.host, fs.user))
    sync(fs)
    return 0


class Quiet:
    """A ctx stand-in that captures error text (used while booting)."""

    def __init__(self, ctx):
        self.fs = ctx.fs
        self.sh = ctx.sh
        self.root = True
        self.user = "root"
        self.name = "mount"
        self.msg = ""
        self.stdin = None

    def w(self, t):
        pass

    def e(self, t):
        self.msg += t

    def err(self, m):
        self.msg += m + "\n"

    def ask(self, p):
        return "n"


# ============================================================================= filesystem tools
def _fs_dev(ctx, target, what, kinds):
    """target may be a device or (for some tools) a mount point."""
    s = S(ctx.fs)
    dev = target if target in s["blk"] else s["mounts"].get(ctx.fs.abspath(target)) if target else None
    if not dev or not visible(s, dev):
        ctx.e("%s: No such file or directory while trying to open %s\n" % (what, target))
        return None
    if kinds and s["blk"][dev].get("fstype") not in kinds:
        ctx.e("%s: %s is not a %s filesystem (it is %s)\n" % (what, dev, "/".join(kinds), s["blk"][dev].get("fstype") or "unformatted"))
        return None
    return dev


def _mp_of(s, dev):
    for mp, d in s["mounts"].items():
        if d == dev:
            return mp
    return None


@cmd("e2label", help=("show or change the label on an ext2/ext3/ext4 filesystem", "e2label DEVICE [NEW-LABEL]", []))
def c_e2label(ctx):
    args = ctx.argv[1:]
    if not args:
        ctx.e("Usage: e2label device [newlabel]\n")
        return 1
    dev = _fs_dev(ctx, args[0], "e2label", ("ext2", "ext3", "ext4"))
    if dev is None:
        return 1
    s = S(ctx.fs)
    if len(args) == 1:
        ctx.w((s["blk"][dev].get("label") or "") + "\n")
        return 0
    if need_root(ctx, "e2label"):
        return 1
    s["blk"][dev]["label"] = args[1][:16]
    return 0


def _ext_info(s, dev, mp_hint=None):
    v = s["blk"][dev]
    blocks = v.get("fs_size", v["size"]) * 256
    return ("tune2fs 1.46.5 (30-Dec-2021)\nFilesystem volume name:   %s\nLast mounted on:          %s\nFilesystem UUID:          %s\n"
            "Filesystem features:      has_journal ext_attr resize_inode dir_index filetype extent 64bit flex_bg sparse_super large_file huge_file\n"
            "Filesystem state:         %s\nErrors behavior:          Continue\nFilesystem OS type:       Linux\nInode count:              %d\nBlock count:              %d\n"
            "Reserved block count:     %d\nFree blocks:              %d\nBlock size:               4096\nMount count:              7\nMaximum mount count:      -1\n" % (
                v.get("label") or "<none>", _mp_of(s, dev) or mp_hint or "<not available>", uuid_for(dev),
                "not clean with errors" if v.get("errors") else "clean", blocks // 4, blocks, blocks * (v.get("reserved") or 0) // 100, int(blocks * 0.93)))


@cmd("tune2fs", help=("adjust tunable ext2/3/4 filesystem parameters", "tune2fs -l DEV | -L LABEL DEV | -m PERCENT DEV", [
    ("-l", "list the superblock contents"), ("-L LABEL", "set the volume label"), ("-m PCT", "reserved-blocks percentage (default 5)")]))
def c_tune2fs(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="l", valued="Lmcir")
    if opts is None:
        return 1
    if not args:
        ctx.e("Usage: tune2fs [-l] [-L volume_label] [-m reserved_blocks_percent] device\n")
        return 1
    dev = _fs_dev(ctx, args[0], "tune2fs", ("ext2", "ext3", "ext4"))
    if dev is None:
        return 1
    if need_root(ctx, "tune2fs"):
        return 1
    s = S(ctx.fs)
    v = s["blk"][dev]
    if "l" in opts:
        ctx.w(_ext_info(s, dev))
    if "L" in opts:
        v["label"] = opts["L"][:16]
        ctx.w("tune2fs 1.46.5 (30-Dec-2021)\n")
    if "m" in opts:
        try:
            pct = float(opts["m"])
        except ValueError:
            ctx.e("tune2fs: bad reserved block ratio - %s\n" % opts["m"])
            return 1
        v["reserved"] = pct if pct != int(pct) else int(pct)
        blocks = v["size"] * 256
        ctx.w("tune2fs 1.46.5 (30-Dec-2021)\nSetting reserved blocks percentage to %s%% (%d blocks)\n" % (opts["m"], blocks * pct / 100))
    if "c" in opts or "i" in opts:
        ctx.w("tune2fs 1.46.5 (30-Dec-2021)\nSetting maximal mount count / check interval (noted).\n")
    return 0


@cmd("dumpe2fs", help=("dump ext2/3/4 superblock and block-group information", "dumpe2fs [-h] DEVICE", [("-h", "superblock only")]))
def c_dumpe2fs(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="hx")
    if opts is None or not args:
        ctx.e("Usage: dumpe2fs [-h] device\n")
        return 1
    dev = _fs_dev(ctx, args[0], "dumpe2fs", ("ext2", "ext3", "ext4"))
    if dev is None:
        return 1
    if need_root(ctx, "dumpe2fs"):
        return 1
    s = S(ctx.fs)
    ctx.w(_ext_info(s, dev).replace("tune2fs", "dumpe2fs"))
    if "h" not in opts:
        ctx.w("\nGroup 0: (Blocks 0-32767) csum 0x1d2c [ITABLE_ZEROED]\n  Primary superblock at 0, Group descriptors at 1-1\n"
              "Group 1: (Blocks 32768-65535) csum 0x8a11 [INODE_UNINIT, ITABLE_ZEROED]\n  Backup superblock at 32768, Group descriptors at 32769-32769\n")
    return 0


def _fsck_ext(ctx, dev, yes, dry):
    s = S(ctx.fs)
    v = s["blk"][dev]
    if dev in s["mounts"].values():
        ctx.e("e2fsck 1.46.5 (30-Dec-2021)\n%s is mounted.\ne2fsck: Cannot continue, aborting.\n\n" % dev)
        return 8
    ctx.w("e2fsck 1.46.5 (30-Dec-2021)\n")
    if not v.get("errors"):
        blocks = v["size"] * 256
        ctx.w("%s: clean, 11/%d files, %d/%d blocks\n" % (dev, blocks // 4, blocks // 30, blocks))
        return 0
    ctx.w("%s contains a file system with errors, check forced.\nPass 1: Checking inodes, blocks, and sizes\nPass 2: Checking directory structure\n"
          "Entry 'report.old' in /reports (12) has deleted/unused inode 1234.  " % dev)
    if dry:
        ctx.w("Clear? no\n\nPass 3: Checking directory connectivity\nPass 4: Checking reference counts\nPass 5: Checking group summary information\n\n"
              "%s: ********** WARNING: Filesystem still has errors **********\n" % dev)
        return 4
    if yes:
        ctx.w("Clear? yes\n")
        ans = "y"
    else:
        ans = (ctx.ask("Clear<y>? ") or "y").strip().lower()
    if ans[:1] not in ("y", ""):
        ctx.w("\n%s: ********** WARNING: Filesystem still has errors **********\n" % dev)
        return 4
    v["errors"] = False
    ctx.w("\nPass 3: Checking directory connectivity\nPass 4: Checking reference counts\nPass 5: Checking group summary information\n\n"
          "%s: ***** FILE SYSTEM WAS MODIFIED *****\n%s: 12/327680 files (0.0%% non-contiguous), 42078/1310720 blocks\n" % (dev, dev))
    return 1


@cmd("fsck", "e2fsck", "fsck.ext4", "fsck.ext3", "fsck.ext2", "fsck.xfs", help=("check and repair a filesystem (it must be UNMOUNTED)", "fsck [-y] DEVICE", [
    ("-y", "answer yes to every repair"), ("-n", "check only, change nothing"), ("-f", "force a check even if clean")]))
def c_fsck(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="ynfpavACNrt")
    if opts is None:
        return 16
    if not args:
        ctx.e("(simulator) give a device: fsck /dev/sdb1\n")
        return 16
    if need_root(ctx, ctx.name):
        return 8
    dev = _fs_dev(ctx, args[0], ctx.name, None)
    if dev is None:
        return 8
    s = S(ctx.fs)
    typ = s["blk"][dev].get("fstype")
    if typ == "xfs" or ctx.name == "fsck.xfs":
        ctx.w("If you wish to check the consistency of an XFS filesystem or\nrepair a damaged filesystem, see xfs_repair(8).\n")
        return 0
    if typ not in ("ext2", "ext3", "ext4"):
        ctx.e("fsck: fsck.%s: not found\nfsck: error 2 (No such file or directory) while executing fsck.%s for %s\n" % (typ, typ, dev))
        return 8
    if ctx.name == "fsck":
        ctx.w("fsck from util-linux 2.37.4\n")
    return _fsck_ext(ctx, dev, bool(opts.get("y") or opts.get("p") or opts.get("a")), bool(opts.get("n")))


@cmd("xfs_info", help=("display XFS filesystem geometry", "xfs_info DEVICE|MOUNTPOINT", []))
def c_xfs_info(ctx):
    if len(ctx.argv) < 2:
        ctx.e("Usage: xfs_info [-V] [-t mtab] [mountpoint|device|file]\n")
        return 1
    dev = _fs_dev(ctx, ctx.argv[-1], "xfs_info", ("xfs",))
    if dev is None:
        return 1
    v = S(ctx.fs)["blk"][dev]
    blocks = v.get("fs_size", v["size"]) * 256
    ctx.w("meta-data=%-22s isize=512    agcount=4, agsize=%d blks\n         =                       sectsz=512   attr=2, projid32bit=1\n"
          "data     =                       bsize=4096   blocks=%d, imaxpct=25\nnaming   =version 2              bsize=4096   ascii-ci=0, ftype=1\n"
          "log      =internal log           bsize=4096   blocks=2560, version=2\nrealtime =none                   extsz=4096   blocks=0, rtextents=0\n" % (dev, blocks // 4, blocks))
    return 0


@cmd("xfs_admin", help=("change parameters of an XFS filesystem (must be unmounted)", "xfs_admin -L LABEL DEVICE | -l DEVICE | -u DEVICE", [
    ("-L LABEL", "set the label"), ("-l", "print the label"), ("-u", "print the UUID")]))
def c_xfs_admin(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="lu", valued="LU")
    if opts is None or not args:
        ctx.e("Usage: xfs_admin [-lu] [-L label] [-U uuid] device\n")
        return 1
    if need_root(ctx, "xfs_admin"):
        return 1
    dev = _fs_dev(ctx, args[0], "xfs_admin", ("xfs",))
    if dev is None:
        return 1
    s = S(ctx.fs)
    v = s["blk"][dev]
    if "l" in opts:
        ctx.w('label = "%s"\n' % (v.get("label") or ""))
    if "u" in opts:
        ctx.w("UUID = %s\n" % uuid_for(dev))
    if "L" in opts:
        if dev in s["mounts"].values():
            ctx.e("xfs_admin: %s contains a mounted filesystem\n\nfatal error -- couldn't initialize XFS library\n" % dev)
            return 1
        v["label"] = opts["L"][:12]
        ctx.w('writing all SBs\nnew label = "%s"\n' % v["label"])
    return 0


@cmd("xfs_repair", help=("repair a corrupt XFS filesystem (must be unmounted)", "xfs_repair [-n] DEVICE", [("-n", "no-modify mode: report only")]))
def c_xfs_repair(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="nvL")
    if opts is None or not args:
        ctx.e("Usage: xfs_repair [-n] device\n")
        return 1
    if need_root(ctx, "xfs_repair"):
        return 1
    dev = _fs_dev(ctx, args[0], "xfs_repair", ("xfs",))
    if dev is None:
        return 1
    s = S(ctx.fs)
    if dev in s["mounts"].values():
        ctx.e("xfs_repair: %s contains a mounted filesystem\nxfs_repair: %s contains a mounted and writable filesystem\n\nfatal error -- couldn't initialize XFS library\n" % (dev, dev))
        return 1
    ctx.w("Phase 1 - find and verify superblock...\nPhase 2 - using internal log\nPhase 3 - for each AG...\nPhase 4 - check for duplicate blocks...\n"
          "Phase 5 - rebuild AG headers and trees...\nPhase 6 - check inode connectivity...\nPhase 7 - verify and correct link counts...\ndone\n")
    if not opts.get("n"):
        s["blk"][dev]["errors"] = False
    return 0


@cmd("xfs_growfs", help=("expand an XFS filesystem to fill its device (give the MOUNT POINT); XFS cannot shrink", "xfs_growfs MOUNTPOINT", []))
def c_xfs_growfs(ctx):
    if need_root(ctx, "xfs_growfs"):
        return 1
    return _grow(ctx, ctx.argv[-1], "xfs_growfs")


@cmd("resize2fs", help=("enlarge or shrink an ext2/3/4 filesystem", "resize2fs DEVICE [SIZE]", []))
def c_resize2fs(ctx):
    if need_root(ctx, "resize2fs"):
        return 1
    return _grow(ctx, ctx.argv[-1], "resize2fs")


def _grow(ctx, target, what):
    s = S(ctx.fs)
    dev = target if target in s["blk"] else s["mounts"].get(ctx.fs.abspath(target))
    if not dev or dev not in s["blk"]:
        ctx.e("%s: %s: No such file or directory\n" % (what, target))
        return 1
    info = s["blk"][dev]
    if what == "xfs_growfs" and info.get("fstype") != "xfs":
        ctx.e("xfs_growfs: %s is not a mounted XFS filesystem\n" % target)
        return 1
    if what == "xfs_growfs" and dev not in s["mounts"].values():
        ctx.e("xfs_growfs: %s is not a mounted XFS filesystem (mount it, then give the mount point)\n" % target)
        return 1
    if what == "resize2fs" and info.get("fstype") not in ("ext2", "ext3", "ext4"):
        ctx.e("resize2fs: Bad magic number in super-block while trying to open %s\n" % target)
        return 1
    info["fs_size"] = info["size"]
    ctx.w("The filesystem on %s is now %d (4k) blocks long.\n" % (dev, info["size"] * 256))
    return 0


@cmd("xfs_metadump", help=("copy XFS metadata (superblock etc.) to a file", "xfs_metadump DEVICE FILE", []))
def c_xfs_metadump(ctx):
    if need_root(ctx, "xfs_metadump") or len(ctx.argv) < 3:
        return 1
    dev = _fs_dev(ctx, ctx.argv[1], "xfs_metadump", ("xfs",))
    if dev is None:
        return 1
    ctx.fs.write(ctx.argv[2], "XFSM metadata dump of %s (UUID %s)\n" % (dev, uuid_for(dev)), "root")
    return 0


@cmd("xfs_copy", help=("copy the contents of an XFS filesystem to another device", "xfs_copy SOURCE TARGET", []))
def c_xfs_copy(ctx):
    if need_root(ctx, "xfs_copy") or len(ctx.argv) < 3:
        return 1
    s = S(ctx.fs)
    src = _fs_dev(ctx, ctx.argv[1], "xfs_copy", ("xfs",))
    dst = ctx.argv[2]
    if src is None:
        return 1
    if not visible(s, dst) or in_use(s, dst):
        ctx.e("xfs_copy: %s is missing or in use\n" % dst)
        return 1
    s["blk"][dst]["fstype"] = "xfs"
    s["blk"][dst]["label"] = s["blk"][src].get("label")
    _new_root(ctx.fs, dst, "xfs")
    ctx.w(" 0%  ... 20%  ... 40%  ... 60%  ... 80%  ... 100%\n\nAll copies completed.\n")
    return 0


@cmd("xfs_db", help=("debug an XFS filesystem (interactive, for experts)", "xfs_db -r DEVICE", []))
def c_xfs_db(ctx):
    ctx.w("(simulator) xfs_db is an interactive debugger for XFS internals (it opens an 'xfs_db>' prompt).\n"
          "For a summary use xfs_info; to repair use xfs_repair.\n")
    return 0


@cmd("btrfs", help=("manage Btrfs filesystems", "btrfs filesystem show", []))
def c_btrfs(ctx):
    a = ctx.argv[1:]
    s = S(ctx.fs)
    if len(a) >= 2 and a[0] in ("filesystem", "fi") and a[1] in ("show", "sh"):
        found = False
        for p, v in sorted(s["blk"].items()):
            if v.get("fstype") == "btrfs" and visible(s, p):
                found = True
                ctx.w("Label: %s  uuid: %s\n\tTotal devices 1 FS bytes used %s\n\tdevid    1 size %s used 536.00MiB path %s\n\n" % (
                    ("'%s'" % v["label"]) if v.get("label") else "none", uuid_for(p), "144.00KiB", fmt_gib(v["size"]).replace(" ", ""), p))
        if not found:
            ctx.w("(no Btrfs filesystems found. Make one with mkfs.btrfs /dev/sdX1)\n")
        return 0
    ctx.w("(simulator) supported: btrfs filesystem show\n")
    return 0


# ============================================================================= LVM
@cmd("pvcreate", help=("initialize a disk or partition for use by LVM", "pvcreate DEVICE...", []))
def c_pvcreate(ctx):
    if need_root(ctx, "pvcreate"):
        return 5
    s = S(ctx.fs)
    for d in [a for a in ctx.argv[1:] if not a.startswith("-")]:
        if not visible(s, d):
            ctx.e("  No device found for %s.\n" % d)
            return 5
        if d in s["mounts"].values() or d in s["swaps"]:
            ctx.e("  Can't open %s exclusively.  Mounted filesystem?\n" % d)
            return 5
        if s["blk"][d]["type"] == "disk" and parts(s, d):
            ctx.e("  Cannot use %s: device is partitioned\n" % d)
            return 5
        s["pv"][d] = {"vg": None, "size": s["blk"][d]["size"]}
        ctx.w("  Physical volume \"%s\" successfully created.\n" % d)
    return 0


@cmd("vgcreate", help=("create a volume group from physical volumes", "vgcreate VG PV...", []))
def c_vgcreate(ctx):
    if need_root(ctx, "vgcreate"):
        return 5
    s = S(ctx.fs)
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    if len(args) < 2:
        ctx.e("  Please provide a volume group name and physical volume(s)\n")
        return 3
    vg, pvs = args[0], args[1:]
    if vg in s["vg"]:
        ctx.e("  A volume group called %s already exists.\n" % vg)
        return 5
    for p in pvs:
        if p not in s["pv"]:
            ctx.e("  Physical volume '%s' not found (run pvcreate first).\n" % p if p in s["blk"] else "  Device %s not found.\n" % p)
            return 5
        if s["pv"][p]["vg"]:
            ctx.e("  Physical volume '%s' is already in volume group '%s'\n" % (p, s["pv"][p]["vg"]))
            return 5
    s["vg"][vg] = {"pvs": pvs, "size": sum(s["pv"][p]["size"] for p in pvs) - len(pvs) * 4}
    for p in pvs:
        s["pv"][p]["vg"] = vg
    ctx.w("  Volume group \"%s\" successfully created\n" % vg)
    return 0


@cmd("vgextend", help=("add physical volumes to a volume group", "vgextend VG PV...", []))
def c_vgextend(ctx):
    if need_root(ctx, "vgextend"):
        return 5
    s = S(ctx.fs)
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    if len(args) < 2 or args[0] not in s["vg"]:
        ctx.e("  Volume group \"%s\" not found\n" % (args[0] if args else ""))
        return 5
    vg = args[0]
    for p in args[1:]:
        if p not in s["pv"]:
            ctx.e("  Physical volume '%s' not found (run pvcreate first).\n" % p)
            return 5
        s["pv"][p]["vg"] = vg
        s["vg"][vg]["pvs"].append(p)
        s["vg"][vg]["size"] += s["pv"][p]["size"] - 4
    ctx.w("  Volume group \"%s\" successfully extended\n" % vg)
    return 0


def vg_free(s, vg):
    return s["vg"][vg]["size"] - sum(v for (g, _), v in s["lv"].items() if g == vg)


@cmd("lvcreate", help=("create a logical volume", "lvcreate -L SIZE -n NAME VG", [("-L SIZE", "size of the LV"), ("-n NAME", "name of the LV")]))
def c_lvcreate(ctx):
    if need_root(ctx, "lvcreate"):
        return 5
    opts, args = getopts(ctx, ctx.argv[1:], flags="s", valued="Lnl", longs=("size=", "name=", "extents="))
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


@cmd("lvextend", help=("add space to a logical volume", "lvextend -L +SIZE [-r] /dev/VG/LV", [("-L +SIZE", "grow by SIZE"), ("-r", "resize the filesystem too")]))
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
    p = "/dev/%s/%s" % (vg, lv)
    s["lv"][(vg, lv)] = new
    s["blk"][p]["fs_size"] = s["blk"][p].get("fs_size", cur)
    s["blk"][p]["size"] = new
    ctx.w("  Size of logical volume %s/%s changed from %s to %s.\n  Logical volume %s/%s successfully resized.\n" % (vg, lv, fmt(cur), fmt(new), vg, lv))
    if "r" in opts or "resizefs" in opts:
        s["blk"][p]["fs_size"] = new
        ctx.w("  (filesystem resized too, because of -r)\n")
    return 0


@cmd("pvs", "pvdisplay", help=("display physical volumes", "pvs", []))
def c_pvs(ctx):
    s = S(ctx.fs)
    ctx.w("  PV         VG   Fmt  Attr PSize  PFree\n")
    for p, v in sorted(s["pv"].items()):
        vg = v["vg"]
        free = vg_free(s, vg) if vg else v["size"]
        ctx.w("  %-10s %-4s lvm2 a--  %5s %5s\n" % (p, vg or "", fmt(v["size"]), fmt(free)))
    return 0


@cmd("vgs", "vgdisplay", help=("display volume groups", "vgs", []))
def c_vgs(ctx):
    s = S(ctx.fs)
    ctx.w("  VG   #PV #LV #SN Attr   VSize  VFree\n")
    for vg, v in sorted(s["vg"].items()):
        nl = len([1 for (g, _) in s["lv"] if g == vg])
        ctx.w("  %-4s %3d %3d   0 wz--n- %5s %5s\n" % (vg, len(v["pvs"]), nl, fmt(v["size"]), fmt(vg_free(s, vg))))
    return 0


@cmd("lvs", "lvdisplay", help=("display logical volumes", "lvs", []))
def c_lvs(ctx):
    s = S(ctx.fs)
    ctx.w("  LV     VG   Attr       LSize\n")
    for (vg, lv), sz in sorted(s["lv"].items()):
        ctx.w("  %-6s %-4s -wi-a----- %5s\n" % (lv, vg, fmt(sz)))
    return 0


# ============================================================================= RAID (mdadm)
def _md_size(level, members, s):
    sizes = [s["blk"][m]["size"] for m in members]
    n, mn = len(sizes), min(sizes)
    return {0: sum(sizes), 1: mn, 5: (n - 1) * mn, 6: (n - 2) * mn, 10: (n // 2) * mn}[level]


MIN_DEVS = {0: 2, 1: 2, 5: 3, 6: 4, 10: 4}


def mdstat_text(s):
    lv = sorted(set(v["level"] for v in s["md"].values()))
    out = ["Personalities : " + " ".join("[raid%d]" % l for l in lv)]
    for md, v in sorted(s["md"].items()):
        n = v["n"]
        parts_ = []
        for i, m in enumerate(v["members"]):
            parts_.append("%s[%d]" % (m.split("/")[-1], i))
        for m in v["failed"]:
            parts_.append("%s[%d](F)" % (m.split("/")[-1], n))
        for m in v.get("spares", []):
            parts_.append("%s[%d](S)" % (m.split("/")[-1], n + 1))
        up = "".join("U" if i < len(v["members"]) else "_" for i in range(n))
        out.append("%s : active raid%d %s" % (md.split("/")[-1], v["level"], " ".join(reversed(parts_))))
        out.append("      %d blocks super 1.2 [%d/%d] [%s]" % (s["blk"][md]["size"] * 1024, n, len(v["members"]), up))
        out.append("")
    out.append("unused devices: <none>")
    return "\n".join(out) + "\n"


def make_md(fs, md, level, members, fstype=None):
    """Build an array directly (mission setup)."""
    s = S(fs)
    s["md"][md] = {"level": level, "n": len(members), "members": list(members), "failed": [], "spares": []}
    s["blk"][md] = {"type": "raid", "raidtype": "raid%d" % level, "size": _md_size(level, members, s), "fstype": None, "parent": None, "ptable": None, "dm": False}
    _node(fs, md)
    if fstype:
        s["blk"][md]["fstype"] = fstype
        _new_root(fs, md, fstype)
    sync(fs)


@cmd("mdadm", help=("manage Linux software RAID arrays", "mdadm --create /dev/md0 --level=1 --raid-devices=2 /dev/sdb /dev/sdc", [
    ("--create (-C)", "build an array; --level (-l) 0/1/5/6/10, --raid-devices (-n) N"), ("--detail (-D)", "show an array's state"),
    ("--detail --scan", "one ARRAY line per array (for /etc/mdadm.conf)"), ("MD --fail (-f) DEV", "mark a member faulty"),
    ("MD --remove (-r) DEV", "remove a failed member"), ("MD --add (-a) DEV", "add a disk (it rebuilds)"), ("--stop (-S) MD", "stop an array")]))
def c_mdadm(ctx):
    a = ctx.argv[1:]
    s = S(ctx.fs)
    if need_root(ctx, "mdadm"):
        ctx.e("mdadm: must be super-user to perform this action\n")
        return 1
    flags = {}
    pos = []
    i = 0
    alias = {"-C": "--create", "-D": "--detail", "-f": "--fail", "-r": "--remove", "-a": "--add", "-S": "--stop", "-l": "--level", "-n": "--raid-devices"}
    while i < len(a):
        t = a[i]
        if t.startswith("--") and "=" in t:
            k, v = t.split("=", 1)
            flags[k] = v
        elif t in alias or t.startswith("--"):
            k = alias.get(t, t)
            if k in ("--level", "--raid-devices"):
                i += 1
                flags[k] = a[i] if i < len(a) else ""
            else:
                flags[k] = True
        elif re.match(r"^-l\d+$", t) or re.match(r"^-n\d+$", t):
            flags["--level" if t[1] == "l" else "--raid-devices"] = t[2:]
        else:
            pos.append(t)
        i += 1
    if "--create" in flags:
        if not pos:
            ctx.e("mdadm: an md device must be given in this mode\n")
            return 2
        md, devs = pos[0], pos[1:]
        lvl = str(flags.get("--level", "")).replace("raid", "").replace("mirror", "1").replace("stripe", "0")
        if not lvl.isdigit() or int(lvl) not in MIN_DEVS:
            ctx.e("mdadm: invalid raid level: %s\n" % flags.get("--level"))
            return 2
        lvl = int(lvl)
        try:
            n = int(flags.get("--raid-devices", len(devs)))
        except ValueError:
            ctx.e("mdadm: invalid number of raid devices\n")
            return 2
        if n != len(devs):
            ctx.e("mdadm: You have listed %d devices for %d raid devices.\n" % (len(devs), n))
            return 2
        if n < MIN_DEVS[lvl]:
            ctx.e("mdadm: at least %d raid-devices needed for level %d\n" % (MIN_DEVS[lvl], lvl))
            return 2
        if md in s["md"]:
            ctx.e("mdadm: %s is already in use.\n" % md)
            return 1
        for d in devs:
            if not visible(s, d) or in_use(s, d):
                ctx.e("mdadm: cannot open %s: %s\n" % (d, "Device or resource busy" if d in s["blk"] else "No such file or directory"))
                return 1
        make_md(ctx.fs, md, lvl, devs)
        ctx.w("mdadm: Defaulting to version 1.2 metadata\nmdadm: array %s started.\n" % md)
        return 0
    if "--detail" in flags and "--scan" in flags:
        for md in sorted(s["md"]):
            ctx.w("ARRAY %s metadata=1.2 name=%s:%s UUID=%s\n" % (md, ctx.fs.host, md[-1], uuid_for("md" + md)))
        return 0
    if "--detail" in flags:
        md = pos[0] if pos else ""
        if md not in s["md"]:
            ctx.e("mdadm: cannot open %s: No such file or directory\n" % md)
            return 1
        v = s["md"][md]
        deg = len(v["members"]) < v["n"]
        size = s["blk"][md]["size"]
        ctx.w("%s:\n           Version : 1.2\n     Creation Time : Sun Nov 15 08:00:00 2026\n        Raid Level : raid%d\n"
              "        Array Size : %d (%.2f GiB)\n      Raid Devices : %d\n     Total Devices : %d\n             State : clean%s\n"
              "    Active Devices : %d\n   Working Devices : %d\n    Failed Devices : %d\n     Spare Devices : %d\n\n"
              "    Number   Major   Minor   RaidDevice State\n" % (
                  md, v["level"], size * 1024, size / 1024.0, v["n"], len(v["members"]) + len(v["failed"]) + len(v.get("spares", [])),
                  ", degraded" if deg else "", len(v["members"]), len(v["members"]) + len(v.get("spares", [])), len(v["failed"]), len(v.get("spares", []))))
        for i, m in enumerate(v["members"]):
            ctx.w("       %d       8       %2d        %d      active sync   %s\n" % (i, 16 * (i + 1), i, m))
        for i in range(len(v["members"]), v["n"]):
            ctx.w("       -       0        0        %d      removed\n" % i)
        for m in v["failed"]:
            ctx.w("       -       8       48        -      faulty   %s\n" % m)
        for m in v.get("spares", []):
            ctx.w("       -       8       64        -      spare   %s\n" % m)
        return 0
    if "--stop" in flags:
        md = pos[0] if pos else ""
        if md not in s["md"]:
            ctx.e("mdadm: error opening %s: No such file or directory\n" % md)
            return 1
        if md in s["mounts"].values():
            ctx.e("mdadm: Cannot get exclusive access to %s:Perhaps a running process, mounted filesystem or active volume group?\n" % md)
            return 1
        del s["md"][md]
        s["blk"].pop(md, None)
        _unnode(ctx.fs, md)
        sync(ctx.fs)
        ctx.w("mdadm: stopped %s\n" % md)
        return 0
    # manage mode: mdadm /dev/md0 --fail /dev/sdc   (or --manage /dev/md0 --fail ...)
    if not pos or pos[0] not in s["md"]:
        ctx.e("mdadm: %s does not appear to be an md device\n" % (pos[0] if pos else "(none)"))
        return 1
    md, devs = pos[0], pos[1:]
    v = s["md"][md]
    if not devs:
        ctx.e("mdadm: no devices given\n")
        return 1
    rc = 0
    for d in devs:
        if "--fail" in flags:
            if d not in v["members"]:
                ctx.e("mdadm: set device faulty failed for %s:  No such device\n" % d)
                rc = 1
                continue
            v["members"].remove(d)
            v["failed"].append(d)
            ctx.w("mdadm: set %s faulty in %s\n" % (d, md))
        elif "--remove" in flags:
            if d in v["members"]:
                ctx.e("mdadm: hot remove failed for %s: Device or resource busy (mark it --fail first)\n" % d)
                rc = 1
                continue
            if d in v["failed"]:
                v["failed"].remove(d)
            elif d in v.get("spares", []):
                v["spares"].remove(d)
            else:
                ctx.e("mdadm: %s is not a member of %s\n" % (d, md))
                rc = 1
                continue
            ctx.w("mdadm: hot removed %s from %s\n" % (d, md))
        elif "--add" in flags:
            if not visible(s, d) or in_use(s, d):
                ctx.e("mdadm: cannot open %s: Device or resource busy\n" % d)
                rc = 1
                continue
            if s["blk"][d]["size"] < min(s["blk"][m]["size"] for m in v["members"] or [d]):
                ctx.e("mdadm: %s not large enough to join array\n" % d)
                rc = 1
                continue
            if len(v["members"]) < v["n"]:
                v["members"].append(d)
                ctx.w("mdadm: added %s\n" % d)
            else:
                v.setdefault("spares", []).append(d)
                ctx.w("mdadm: added %s (as a spare)\n" % d)
        else:
            ctx.e("mdadm: give --fail, --remove or --add\n")
            return 1
    sync(ctx.fs)
    return rc


# ============================================================================= quotas
def _quota_opts(s, mp):
    o = s["mopts"].get(mp, "").split(",")
    return ("usrquota" in o or "uquota" in o or "quota" in o), ("grpquota" in o or "gquota" in o)


def _quota_mp(ctx, target):
    s = S(ctx.fs)
    ap = ctx.fs.abspath(target) if target else ""
    if ap in s["mounts"]:
        return ap
    for mp, dev in s["mounts"].items():
        if dev == target:
            return mp
    return None


@cmd("quotacheck", help=("scan a filesystem and build its quota files", "quotacheck -cug MOUNTPOINT", [("-c", "create new quota files"), ("-u", "user quotas"), ("-g", "group quotas")]))
def c_quotacheck(ctx):
    if need_root(ctx, "quotacheck"):
        return 1
    s = S(ctx.fs)
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    flags = "".join(a[1:] for a in ctx.argv[1:] if a.startswith("-"))
    targets = args or ([mp for mp in s["mounts"] if any(_quota_opts(s, mp))] if "a" in flags else [])
    if not targets:
        ctx.e("quotacheck: Mountpoint (or device) not given\n")
        return 1
    for t in targets:
        mp = _quota_mp(ctx, t)
        uq, gq = _quota_opts(s, mp) if mp else (False, False)
        if not mp or not (uq or gq):
            ctx.e("quotacheck: Mountpoint (or device) %s not found or has no quota enabled.\nquotacheck: Cannot find filesystem to check or filesystem not mounted with quota option.\n" % t)
            return 1
        q = s["quota"].setdefault(mp, {"checked": False, "on": False, "users": {}, "groups": {}})
        q["checked"] = True
        for name, ok in (("aquota.user", uq), ("aquota.group", gq)):
            if ok:
                ctx.fs.write(mp.rstrip("/") + "/" + name, "", "root", mode=0o600)
    return 0


@cmd("quotaon", "quotaoff", help=("turn filesystem quotas on or off", "quotaon MOUNTPOINT | quotaon -a", [("-v", "verbose"), ("-a", "all filesystems")]))
def c_quotaon(ctx):
    if need_root(ctx, ctx.name):
        return 1
    s = S(ctx.fs)
    on = ctx.name == "quotaon"
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    targets = args or (list(s["quota"]) if any("a" in a for a in ctx.argv[1:] if a.startswith("-")) else [])
    if not targets:
        ctx.e("%s: no filesystem given\n" % ctx.name)
        return 1
    for t in targets:
        mp = _quota_mp(ctx, t)
        q = s["quota"].get(mp) if mp else None
        if q is None or not q["checked"]:
            ctx.e("quotaon: cannot find %s/aquota.user on %s [%s]\n(run quotacheck -cug %s first)\n" % (t, s["mounts"].get(mp, t) if mp else t, t, t))
            return 1
        q["on"] = on
        if "-v" in ctx.argv or "-uv" in ctx.argv or "-vug" in ctx.argv:
            ctx.w("%s [%s]: user quotas turned %s\n" % (s["mounts"][mp], mp, "on" if on else "off"))
    return 0


@cmd("setquota", help=("set disk quotas from the command line", "setquota -u USER BSOFT BHARD ISOFT IHARD MOUNTPOINT", [("-u", "user"), ("-g", "group"), ("(numbers)", "block limits are in 1K blocks; 0 = no limit")]))
def c_setquota(ctx):
    if need_root(ctx, "setquota"):
        return 1
    s = S(ctx.fs)
    a = ctx.argv[1:]
    kind = "groups" if "-g" in a else "users"
    a = [x for x in a if x not in ("-u", "-g")]
    if len(a) != 6:
        ctx.e("setquota: Bad number of arguments.\nUsage: setquota -u USER block-softlimit block-hardlimit inode-softlimit inode-hardlimit MOUNTPOINT\n")
        return 1
    name, nums, t = a[0], a[1:5], a[5]
    try:
        nums = [_quota_num(x) for x in nums]
    except ValueError:
        ctx.e("setquota: Bad block limit\n")
        return 1
    mp = _quota_mp(ctx, t)
    if not mp or mp not in s["quota"] or not s["quota"][mp]["checked"]:
        ctx.e("setquota: Mountpoint (or device) %s not found or has no quota enabled.\n" % t)
        return 1
    if kind == "users" and ("\n" + name + ":") not in ("\n" + ctx.fs.read("/etc/passwd", "root")):
        ctx.e("setquota: user %s does not exist.\n" % name)
        return 1
    s["quota"][mp][kind][name] = nums
    return 0


def _quota_num(x):
    m = re.match(r"^(\d+)([KMGT]?)$", x, re.I)
    if not m:
        raise ValueError(x)
    return int(m.group(1)) * {"": 1, "K": 1, "M": 1024, "G": 1024 * 1024, "T": 1024 ** 3}[m.group(2).upper()]


@cmd("edquota", help=("edit user quotas (opens an editor)", "edquota -u USER", []))
def c_edquota(ctx):
    ctx.w("(simulator) edquota opens vi on a temporary file of limits. Here, use the one-line equivalent:\n"
          "  sudo setquota -u USER SOFT HARD 0 0 MOUNTPOINT     (limits in 1K blocks, 0 = none)\n")
    return 0


@cmd("repquota", help=("report quota usage per user", "repquota MOUNTPOINT | repquota -a", [("-a", "all filesystems with quotas"), ("-s", "human-readable")]))
def c_repquota(ctx):
    if need_root(ctx, "repquota"):
        return 1
    s = S(ctx.fs)
    args = [a for a in ctx.argv[1:] if not a.startswith("-")]
    mps = [_quota_mp(ctx, a) for a in args] if args else [mp for mp in s["quota"]]
    if not mps or None in mps:
        ctx.e("repquota: Mountpoint (or device) %s not found or has no quota enabled.\n" % (args[0] if args else ""))
        return 1
    for mp in mps:
        q = s["quota"].get(mp)
        if not q or not q["checked"]:
            ctx.e("repquota: Cannot find quota file on %s [%s] to get quota information.\n" % (s["mounts"].get(mp), mp))
            continue
        usage = _tree_owners(ctx.fs, ctx.fs.lookup(mp).entries, {})
        users = sorted(set(list(usage) + list(q["users"])))
        ctx.w("*** Report for user quotas on device %s\nBlock grace time: 7days; Inode grace time: 7days\n" % s["mounts"][mp])
        ctx.w("                        Block limits                File limits\nUser            used    soft    hard  grace    used  soft  hard  grace\n")
        ctx.w("----------------------------------------------------------------------\n")
        for u in users:
            used = usage.get(u, 0) // 1024
            soft, hard = (q["users"].get(u) or [0, 0])[:2]
            flag = "+-" if soft and used > soft else "--"
            ctx.w("%-10s%s %8d %7d %7d %6s %6d %5d %5d\n" % (u, flag, used, soft, hard, "6days" if flag == "+-" else "", 3, 0, 0))
        ctx.w("\n")
        if not q["on"]:
            ctx.w("(quotas are NOT enforced yet: run quotaon %s)\n" % mp)
    return 0


@cmd("quota", help=("show a user's disk usage and limits", "quota [-u USER]", []))
def c_quota(ctx):
    s = S(ctx.fs)
    a = [x for x in ctx.argv[1:] if not x.startswith("-")]
    user = a[0] if a else ctx.fs.user
    shown = False
    for mp, q in s["quota"].items():
        lim = q["users"].get(user)
        if not lim:
            continue
        if not shown:
            ctx.w("Disk quotas for user %s:\n     Filesystem  blocks   quota   limit   grace   files   quota   limit   grace\n" % user)
            shown = True
        used = _tree_owners(ctx.fs, ctx.fs.lookup(mp).entries, {}).get(user, 0) // 1024
        ctx.w("%15s %7d %7d %7d %7s %7d %7d %7d\n" % (s["mounts"][mp], used, lim[0], lim[1], "", 3, lim[2], lim[3]))
    if not shown:
        ctx.w("Disk quotas for user %s: none\n" % user)
    return 0
