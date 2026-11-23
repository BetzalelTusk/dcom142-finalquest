"""Storage questions. Module 11 (CertMaster 7.1-7.2) comes from the instructor's Module 11 deck
("Module 11_Section 1.pptx", 77 slides). Module 12 (7.3-7.4) has no deck yet: items about mounting,
fstab, RAID and quotas that ARE on the Module 11 slides cite them; the rest are marked PREVIEW."""
from .content_base import R, M, PV

M11 = "Module 11 slides"

# ============================================================================= storage: MC (Module 11)
M("storage", "Which storage type uses spinning magnetic disks and is usually inexpensive, large and relatively slow?",
  "HDD", ["SSD", "Thumb drive", "tmpfs"],
  "HDD = spinning magnetic disks (cheap, big, slow). SSD = flash memory (expensive, fast, small, shorter-lived).",
  M11 + " (Types of Storage)")
M("storage", "Which storage design gives each piece of data its own ID and metadata, and is cheap, scalable and best for static data?",
  "Object storage", ["File storage", "Block storage", "Swap space"],
  "File storage = a filing cabinet of folders (doesn't scale well). Block storage = raw fixed-size blocks, used with SANs, VMs and databases. Object storage = a warehouse with barcodes.",
  M11 + " (Storage Designs)")
M("storage", "Which storage design splits data into fixed-size addressed blocks and is common with SANs, virtual machines and databases?",
  "Block storage", ["Object storage", "File storage", "Cloud folders"],
  "Block storage: each block has its own address; the OS builds a filesystem on top. 'Raw storage boxes where you decide the organization.'",
  M11 + " (Storage Designs: Block Storage)")
M("storage", "What are the limits of an MBR partition table?",
  "2 TB drive size and 4 primary partitions", ["16 TB and 128 partitions", "No size limit, 4 partitions", "2 TB and unlimited partitions"],
  "MBR: max drive 2 TB, max 4 partitions, boot data in one sector. GPT: virtually unlimited size and partitions, boot data in several places.",
  M11 + " (Types of Partitions: MBR vs GPT)")
M("storage", "Which statements about GPT are true? (choose the best answer)",
  "It is the UEFI-era successor to MBR and stores boot data in multiple locations for redundancy", ["It is limited to 2 TB", "It allows only four partitions", "It stores boot data in a single sector"],
  "GPT (GUID Partition Table) is the modern, preferred solution: virtually unlimited drive size and partitions, redundant boot data.",
  M11 + " (Types of Partitions)")
M("storage", "In /dev/sdb2, what do 'sd', 'b' and '2' mean?",
  "SCSI/SATA disk, second drive, second partition", ["SSD, bus 2, slot 2", "Standard disk, partition b, drive 2", "Swap device, backup, version 2"],
  "sd = controller type (SCSI/SATA), the letter = which whole drive (a = first), the number = which partition on it.",
  M11 + " (The /dev/ Directory)")
M("storage", "On an MBR disk, how many EXTENDED partitions can you have?",
  "One", ["Four", "Twelve", "Unlimited"],
  "Only one extended partition. It holds logical partitions (no fixed limit, 12 max is advisable) and has its own partition table.",
  M11 + " (Types of Partitions: primary / extended / logical)")
M("storage", "Where are logical partitions created?",
  "Inside the extended partition", ["Inside a volume group", "In /etc/fstab", "Inside the swap partition"],
  "Logical partitions act as separate drives but live inside the (single) extended partition. On MBR they are numbered from 5.",
  M11 + " (Types of Partitions)")
M("storage", "Which partition types are usually PRIMARY partitions?",
  "Swap and boot", ["Logical and extended", "Only /home", "LVM snapshots"],
  "The slide: 'Swap and boot are usually primary partitions.'",
  M11 + " (Types of Partitions)")
M("storage", "In fdisk, which key writes your changes to the disk and exits?",
  "w", ["q", "p", "n"],
  "n = new partition, d = delete, p = print the table, w = write and exit, q = quit WITHOUT saving, m = menu. Nothing is saved until w.",
  M11 + " (fdisk Menu Options)")
M("storage", "You made a mistake in fdisk and want to leave without changing the disk. Which key?",
  "q", ["w", "d", "x"],
  "q cancels the changes made and exits. fdisk keeps every change in memory until you press w.",
  M11 + " (fdisk Menu Options)")
M("storage", "After writing a new partition table, which command tells the kernel about the changes without rebooting?",
  "partprobe", ["mkfs", "blkid", "mount -a"],
  "'Enter sudo partprobe to update the Linux kernel with the partition table changes.' The kernel's list is in /proc/partitions.",
  M11 + " (Demo in CertMaster; Partition Management)")
M("storage", "Which parted command creates a GPT partition table on the disk you opened?",
  "mklabel gpt", ["mkpart gpt", "label new gpt", "fdisk -g"],
  "Slide steps: sudo parted /dev/sdb, mklabel gpt, mkpart primary ext4 1MB 3GB, print, quit, then partprobe.",
  M11 + " (Parted Utility)")
M("storage", "In parted you typed 'mkpart primary ext4 1MB 3GB'. Is the new partition formatted with ext4?",
  "No: you still need to run mkfs.ext4 on it", ["Yes, parted formats it", "Only if you reboot", "Only on MBR disks"],
  "The filesystem type in mkpart only labels the partition. The storage setup process is partition, THEN format (mkfs), THEN mount.",
  M11 + " (Parted Utility; The Storage Device Setup Process)")
M("storage", "Which tool can create, destroy AND resize partitions, and also recognizes and resizes NTFS partitions?",
  "parted", ["fdisk", "mkswap", "e2label"],
  "parted (GNU Parted) creates, destroys and resizes partitions. growpart can also extend partitions, often on cloud VMs.",
  M11 + " (Partition Management)")
M("storage", "What is the correct order to set up a new storage device?",
  "Partition it, format it with a filesystem, then mount it (and add it to /etc/fstab)", ["Mount it, partition it, format it", "Format it, partition it, mount it", "Add it to fstab, partition it, format it"],
  "Slide: partition (sdb), format with ext4 or xfs, mount manually or add to the fstab file so it is configured on boot.",
  M11 + " (The Storage Device Setup Process)")
M("storage", "What are the advantages of XFS over ext4 listed on the slides?",
  "Larger partition sizes, larger file sizes, and it avoids inode exhaustion", ["It stores data in RAM", "It is older and more compatible", "It can shrink but not grow"],
  "ext4: older, journaling, recognized by most distros. XFS: larger partitions and files, avoids inode exhaustion (default on RHEL/Rocky).",
  M11 + " (Filesystems on a Partition)")
M("storage", "Which filesystem keeps its data in memory, so it is fast but lost at shutdown?",
  "tmpfs", ["Btrfs", "XFS", "ext4"],
  "tmpfs stores data in memory instead of on a storage disk. Btrfs is scalable and easy to manage. FUSE lets apps create virtual filesystems.",
  M11 + " (Filesystems on a Partition)")
M("storage", "Which XFS tool expands the filesystem to fill the drive?",
  "xfs_growfs", ["xfs_repair", "xfs_admin", "xfs_metadump"],
  "xfs_info = details, xfs_admin = change parameters (label), xfs_metadump = copy superblock metadata, xfs_growfs = expand, xfs_copy = copy, xfs_repair = repair, xfs_db = debug.",
  M11 + " (Filesystem Management Tasks for xfs tools)")
M("storage", "Which XFS tool repairs and recovers a corrupt XFS filesystem?",
  "xfs_repair", ["fsck.xfs", "xfs_growfs", "xfs_info"],
  "xfs_repair (on an unmounted filesystem). fsck.xfs does nothing and just points you to xfs_repair.",
  M11 + " (Filesystem Management Tasks for xfs tools)")
M("storage", "Which tool can both ENLARGE and SHRINK an ext4 filesystem?",
  "resize2fs", ["xfs_growfs", "tune2fs", "e2label"],
  "resize2fs resizes ext2/3/4 either way. XFS can only grow (xfs_growfs).",
  M11 + " (Filesystem Management)")
M("storage", "The system won't boot because of filesystem damage. Which tool does diagnostics and repair for ext filesystems?",
  "fsck", ["dumpe2fs", "tune2fs", "lsblk"],
  "fsck = diagnostics and repair, 'use if the system won't boot'. Run it on an UNMOUNTED filesystem. e2label = labels, resize2fs = resize, tune2fs = tunables, dumpe2fs = dump info.",
  M11 + " (Filesystem Management)")
M("storage", "Which command changes 'tunable' ext4 parameters such as the reserved-blocks percentage?",
  "tune2fs", ["dumpe2fs", "e2label", "fsck"],
  "tune2fs configures ext4 options, e.g. tune2fs -m 1 /dev/sdb1 sets reserved blocks to 1%. dumpe2fs prints superblock and block-group information.",
  M11 + " (Filesystem Management Tasks for ext2/ext3/ext4)")
M("storage", "Which command prints ext4 superblock and block group information?",
  "dumpe2fs", ["tune2fs -m", "e2label", "xfs_info"],
  "dumpe2fs prints or displays ext4 filesystem information: superblock and block-group details.",
  M11 + " (Filesystem Management Tasks for ext2/ext3/ext4)")
M("storage", "What is swap space?",
  "Disk space Linux uses when the system runs out of physical memory", ["A backup copy of /home", "The partition that holds /boot", "A RAID mirror"],
  "Linux pushes unused pages from RAM to swap. It prevents crashes but is slower than RAM, so it is not a replacement for RAM.",
  M11 + " (Swap Space)")
M("storage", "What is the Windows equivalent of Linux swap space?",
  "pagefile.sys", ["hiberfil.sys", "C:\\Windows\\Temp", "The registry"],
  "Slide: 'In Windows OS it is called pagefile.sys.'",
  M11 + " (Swap Space)")
M("storage", "Which set of commands creates and manages swap?",
  "mkswap, swapon, swapoff", ["mkfs.swap, mount, umount", "swapctl add, swapctl del", "fdisk, partprobe, blkid"],
  "mkswap creates the swap area, swapon activates it, swapoff deactivates it. Swap can be a device, a file or pseudo-swap.",
  M11 + " (Swap Space and Virtual Memory)")
M("storage", "Which symptom suggests the system needs more RAM rather than more swap?",
  "Constant, excessive swapping and performance lag", ["A full /boot partition", "An unmounted USB drive", "A missing UUID in blkid"],
  "Swap issues on the slide: too much swapping (needs more memory), out-of-memory errors (swap misconfigured), performance lag (swap is slower than RAM).",
  M11 + " (Swap Space and Virtual Memory)")
M("storage", "Which command shows SCSI/NVMe devices, and with -s their sizes?",
  "lsscsi", ["lsblk -f", "hwinfo --block", "blkid"],
  "lsscsi lists SCSI/NVMe devices (-s = size). hwinfo --storage shows controllers and --block shows disks and partitions.",
  M11 + " (Hard Disk Drive Deployments)")
M("storage", "Which command shows each partition's UUID (Universally Unique ID)?",
  "blkid", ["partprobe", "fdisk -l", "df -h"],
  "blkid displays known information about partitions, including the UUID identifier.",
  M11 + " (Partition Management)")
M("storage", "Which statement about SCSI and SAS is correct?",
  "SAS is faster with more capacity than SCSI, but costs even more", ["SCSI is cheaper and bigger than SAS", "SAS is slower but cheaper", "They are only used in laptops"],
  "SCSI: very fast, scalable, expensive with less capacity. SAS (Serial Attached SCSI): faster, higher capacity, more flexible, even higher cost.",
  M11 + " (Hard Disk Drive Deployments)")
M("storage", "What is a benefit of LVM over traditional partitioning?",
  "Volumes can be created, resized and deleted without rebooting, and can span several disks", ["It needs no filesystem", "It only works with MBR", "It makes disks immune to failure"],
  "LVM: flexible, scalable; dynamically create, delete and resize volumes without rebooting; map logical volumes across multiple physical devices; snapshots.",
  M11 + " (Logical Volume Manager Storage)")
M("storage", "In LVM, what is the correct order of the layers?",
  "Physical volumes, volume group, logical volumes", ["Logical volumes, volume group, physical volumes", "Volume group, physical volumes, logical volumes", "Physical volumes, logical volumes, volume group"],
  "Physical volumes combine to form the volume group, which is then divided into logical volumes (which get filesystems such as ext4 or XFS).",
  M11 + " (Logical Volume Manager Storage; speaker note)")
M("storage", "Which LVM feature lets you easily revert a volume to a specific earlier state?",
  "Snapshots", ["Swap", "Striping", "Quotas"],
  "'Create virtual snapshots of logical volumes to easily revert to a specific state.'",
  M11 + " (Logical Volume Manager Storage)")
M("storage", "Which command creates a 5 GB logical volume called data in the volume group vg0?",
  "lvcreate -L 5G -n data vg0", ["vgcreate -L 5G -n data vg0", "pvcreate -L 5G data vg0", "lvextend -L 5G data vg0"],
  "lvcreate -L sets the size and -n the name, followed by the volume group. (The deck names the LVM layers; the commands are standard Linux+ material.)",
  "Linux+ XK0-006 (background to " + M11 + ": Logical Volume Deployments)")

# ============================================================================= mounts: MC (Module 12; mount slides are in the Module 11 deck)
M("mounts", "What does mounting do?",
  "Attaches a filesystem to a directory in the FHS so users can reach it", ["Formats a partition", "Creates a partition table", "Copies a disk image"],
  "'The term for attaching storage to the FHS is mounting, and the command is mount.' The reverse is umount.",
  M11 + " (What is Mounting?)")
M("mounts", "You mount /dev/sdb1 on a directory that already contains files. What happens to those files?",
  "They are hidden (not deleted) until the filesystem is unmounted", ["They are deleted", "They are copied onto /dev/sdb1", "The mount fails"],
  "Mount on an empty directory. If it has content, the content is invisible until the filesystem is unmounted.",
  M11 + " (What is Mounting?)")
M("mounts", "Which three things does the slide say you need to mount a filesystem?",
  "A device, a directory, and root privilege", ["A UUID, a label and a password", "An fstab line, a reboot and sudo", "A partition table, swap and a VG"],
  "Three requirements: a device (e.g. /dev/sdb1), a directory (the mount point) and root privilege.",
  M11 + " (The mount Command)")
M("mounts", "Which command unmounts a filesystem?",
  "umount", ["unmount", "mount -u", "eject -f"],
  "It's umount, with no 'n'. You can't unmount a filesystem that's busy (for example your shell is cd'd into it).",
  M11 + " (What is Mounting?)")
M("mounts", "Which file makes a mount happen automatically at every boot?",
  "/etc/fstab", ["/etc/mtab", "/proc/partitions", "/etc/mount.conf"],
  "Slide: edit /etc/fstab and add /dev/sdb1 /opt/downloads xfs defaults 0 0, save, reboot, then verify with lsblk -f and mount | grep sdb1.",
  M11 + " (Make a Mount Permanent)")
M("mounts", "You just mounted a new XFS filesystem on /opt/downloads but rocky gets 'Permission denied' writing there. Why?",
  "The mount point now shows the new filesystem's root, which is owned by root; chown/chmod it", ["XFS is read-only", "rocky must reboot", "The disk needs a UUID"],
  "The slides change ownership and permissions of the mount point after mounting so the rocky user group can write, then test with touch.",
  M11 + " (Manually Test Mount)")
M("mounts", "How many fields are on each line of /etc/fstab?",
  "Six", ["Four", "Five", "Seven"],
  "device, mount point, filesystem type, options, dump, fsck pass order. The slide's line: /dev/sdb1 /opt/downloads xfs defaults 0 0.",
  M11 + " (Make a Mount Permanent)")
M("mounts", "Why is UUID=... often better than /dev/sdb1 in /etc/fstab?",
  "Device names can change when disks are added; the UUID does not", ["A UUID makes the disk faster", "A UUID encrypts the partition", "/dev names are not allowed in fstab"],
  "Disk order can change, so /dev/sdX names aren't stable. blkid shows each partition's UUID.",
  PV + "Linux+ XK0-006 7.3 Mount Storage (blkid/UUID is on the " + M11 + ")")
M("mounts", "You edited /etc/fstab. How can you test it BEFORE rebooting?",
  "sudo mount -a", ["sudo partprobe", "sudo fsck -a", "cat /etc/fstab"],
  "mount -a mounts everything listed in fstab and reports errors now. A bad fstab line can drop the server into emergency mode at boot.",
  PV + "Linux+ XK0-006 7.3 Mount Storage")
M("mounts", "What is the difference between df and du?",
  "df reports free space per mounted filesystem; du reports space used by files and directories", ["df lists devices; du lists users", "df repairs filesystems; du unmounts them", "They are identical"],
  "df -h shows filesystem capacity and free space. du -sh DIR shows how much a directory uses.",
  PV + "Linux+ XK0-006 7.3 Mount Storage")
M("mounts", "What problems of standalone disks does RAID address?",
  "Single point of failure, transfer speed and capacity", ["File permissions and ownership", "Package dependencies", "Boot loader errors"],
  "RAID (Redundant Array of Inexpensive Disks) answers the limits of standalone disks: single point of failure, transfer speed, capacity.",
  M11 + " (RAID Storage)")
M("mounts", "Which kind of RAID is faster and more flexible, and is preferred?",
  "Hardware RAID (a RAID controller)", ["Software RAID (part of the OS)", "Swap RAID", "tmpfs RAID"],
  "Hardware RAID controllers: faster, more flexible, preferred. Software RAID: part of the OS, slower, less preferred.",
  M11 + " (RAID Storage)")
M("mounts", "Which RAID level mirrors data across two disks so one can fail without data loss?",
  "RAID 1", ["RAID 0", "RAID 5 with one disk", "RAID 6 with no parity"],
  "RAID 0 stripes (speed, no redundancy), RAID 1 mirrors, RAID 5 = striping with parity (3+ disks), RAID 6 = double parity (4+), RAID 10 = mirrored stripes.",
  PV + "Linux+ XK0-006 7.4 Manage Other Storage Options")
M("mounts", "/proc/mdstat shows [2/1] [U_] for md0. What does it mean?",
  "The mirror is degraded: one of its two disks is missing or failed", ["Both disks are healthy", "The array is being created for the first time", "md0 is a swap device"],
  "[n/m] = n devices expected, m working. U = up, _ = missing. Fix: mdadm --fail and --remove the bad disk, then --add a replacement.",
  PV + "Linux+ XK0-006 7.4 Manage Other Storage Options (RAID)")
M("mounts", "In disk quotas, what is the soft limit?",
  "A warning level a user may exceed for a grace period", ["An absolute maximum that can never be crossed", "The size of the swap file", "The reserved-blocks percentage"],
  "Quota = space allotted to a user. Soft limit (may exceed during the grace period), hard limit (cannot exceed).",
  M11 + " (Setting Disk Quotas)")
M("mounts", "Which /etc/fstab options turn on user and group quotas for a filesystem?",
  "usrquota and grpquota", ["quota=on", "userlimit,grouplimit", "defaults,quota"],
  "Slide: '/etc/fstab file with options usrquota and grpquota.' Then remount, quotacheck, quotaon, and set limits.",
  M11 + " (Setting Disk Quotas)")
M("mounts", "After adding usrquota to an existing mount in /etc/fstab, what applies it without rebooting?",
  "mount -o remount /home2", ["partprobe /home2", "umount -f /home2", "quotaon -a only"],
  "remount re-reads the options. Then quotacheck -cug builds aquota.user/aquota.group and quotaon enables enforcement.",
  PV + "Linux+ XK0-006 7.4 (disk quotas)")
M("mounts", "Which is block storage over the network, and which is file-level storage over the network?",
  "SAN is block-level; NAS is file-level", ["NAS is block-level; SAN is file-level", "Both are file-level", "Both are block-level"],
  "A SAN presents raw blocks (the Module 11 slides link block storage with SANs). A NAS shares files, e.g. over NFS or SMB.",
  PV + "Linux+ XK0-006 7.4 (network storage); block storage + SAN is on the " + M11)

# ============================================================================= storage: typed commands (Module 11)
R("storage", "Show all block devices (disks and partitions) in a tree",
  "lsblk",
  "lsblk displays all block storage devices in a tree: physical devices at the top, partitions/logical volumes branching off, with names, major:minor numbers, type and mount point.",
  M11 + " (The lsblk Command)", "ls + blk")
R("storage", "Show block devices with their filesystem type, label and UUID",
  "lsblk -f",
  "lsblk -f adds FSTYPE, LABEL, UUID and the mount point. The slides use it after a reboot to confirm the fstab mount.",
  M11 + " (Make a Mount Permanent)", "lsblk + a filesystem flag")
R("storage", "Show the UUID and filesystem type of every block device",
  "blkid",
  "blkid displays known information on partitions, including the UUID. Use the UUID in /etc/fstab.",
  M11 + " (Partition Management)", "blk + id")
R("storage", "Print ONLY the UUID of /dev/sdb1 (no labels, just the value)",
  "blkid -s UUID -o value /dev/sdb1;;blkid -o value -s UUID /dev/sdb1",
  "-s picks the tag and -o value prints just its value: handy for building an fstab line.",
  "Linux+ XK0-006 (background to " + M11 + ": blkid)", "-s TAG -o value")
R("storage", "Show details of the storage controllers with hwinfo",
  "hwinfo --storage",
  "hwinfo displays details about system components: --storage shows storage controllers, --block shows disks and partitions.",
  M11 + " (Hard Disk Drive Deployments)", "hwinfo + --storage")
R("storage", "Show disks and partitions with hwinfo",
  "hwinfo --block",
  "After installing a disk, confirm Linux sees it with hwinfo or lsblk.",
  M11 + " (Hard Disk Drive Deployments)", "hwinfo + --block")
R("storage", "List SCSI/NVMe devices with their sizes",
  "lsscsi -s",
  "lsscsi displays SCSI/NVMe devices; -s shows device size info.",
  M11 + " (Hard Disk Drive Deployments)", "ls + scsi, size flag")
R("storage", "List the partition table of /dev/sdb with fdisk (without changing anything)",
  "fdisk -l /dev/sdb",
  "fdisk -l lists partitions; give a disk to see only that one. Needs sudo.",
  M11 + " (Demo: Partitioning the drive using fdisk)", "fdisk + list + disk")
R("storage", "Open /dev/sdb in fdisk to edit its partition table",
  "fdisk /dev/sdb",
  "Then m = menu, n = new, p = print, w = write and exit, q = quit without saving. Run sudo partprobe afterwards.",
  M11 + " (Demo in CertMaster)", "fdisk + the whole disk (not sdb1)")
R("storage", "Update the kernel with partition table changes without rebooting",
  "partprobe",
  "partprobe scans for disk and partition changes; the kernel's view is in /proc/partitions. Needed when fdisk says 'Device or resource busy'.",
  M11 + " (Demo in CertMaster; Partition Management)", "part + probe")
R("storage", "Show the kernel's current list of partitions (a file in /proc)",
  "cat /proc/partitions",
  "Partition information is stored in /proc/partitions. If a new partition isn't there, run partprobe.",
  M11 + " (Partition Management)", "/proc/...")
R("storage", "Open /dev/sdb in parted to edit its partitions",
  "parted /dev/sdb",
  "Inside parted: mklabel gpt, mkpart primary ext4 1MB 3GB, print, quit. parted writes each change immediately.",
  M11 + " (Parted Utility)", "parted + disk")
R("storage", "In one non-interactive command, give /dev/sdb a GPT partition table with parted",
  "parted -s /dev/sdb mklabel gpt;;parted --script /dev/sdb mklabel gpt;;parted /dev/sdb mklabel gpt",
  "-s (script mode) runs the commands without prompting. mklabel gpt creates a new GPT table (msdos for MBR).",
  M11 + " (Parted Utility)", "-s + mklabel")
R("storage", "Grow partition 1 of /dev/sdb into the free space after it",
  "growpart /dev/sdb 1",
  "growpart resizes/extends existing partitions, often on cloud VMs. Then grow the filesystem (xfs_growfs or resize2fs).",
  M11 + " (Partition Management)", "growpart DISK NUMBER")
R("storage", "Format the partition /dev/sdb1 as ext4",
  "mkfs.ext4 /dev/sdb1;;mkfs -t ext4 /dev/sdb1",
  "Slide: 'Command to create filesystem: sudo mkfs.ext4 /dev/sdb1'. Formatting destroys existing data.",
  M11 + " (Filesystem Management Tasks for ext2/ext3/ext4)", "mkfs + type")
R("storage", "Format the partition /dev/sdb1 as XFS",
  "mkfs.xfs /dev/sdb1;;mkfs -t xfs /dev/sdb1",
  "Slide: 'Create an XFS file system on the new partition: sudo mkfs.xfs /dev/sdb1'.",
  M11 + " (XFS Filesystems)", "mkfs + type")
R("storage", "Format /dev/sdb1 as Btrfs",
  "mkfs.btrfs /dev/sdb1;;mkfs -t btrfs /dev/sdb1",
  "Btrfs: very scalable, easy to manage, reliable. View it with btrfs filesystem show.",
  M11 + " (Btrfs Filesystems)", "mkfs + type")
R("storage", "Show information about Btrfs filesystems",
  "btrfs filesystem show;;btrfs fi show",
  "The slide's command to view information about Btrfs.",
  M11 + " (Btrfs Filesystems)", "btrfs + filesystem + show")
R("storage", "Display the details of the XFS filesystem on /dev/sdb1",
  "xfs_info /dev/sdb1",
  "xfs_info displays details about the filesystem (block size, block count, log).",
  M11 + " (Filesystem Management Tasks for xfs tools)", "xfs_ + info")
R("storage", "Set the label of the (unmounted) XFS filesystem /dev/sdc1 to scratch",
  "xfs_admin -L scratch /dev/sdc1",
  "xfs_admin changes filesystem parameters; -L sets the label. XFS must be unmounted for this.",
  M11 + " (Filesystem Management Tasks for xfs tools)", "xfs_admin -L LABEL DEV")
R("storage", "Repair the corrupt (unmounted) XFS filesystem on /dev/sdc1",
  "xfs_repair /dev/sdc1",
  "xfs_repair repairs and recovers a corrupt XFS filesystem. fsck.xfs does nothing for XFS.",
  M11 + " (Filesystem Management Tasks for xfs tools)", "xfs_ + repair")
R("storage", "Grow the XFS filesystem mounted on /data to fill its (bigger) device",
  "xfs_growfs /data",
  "xfs_growfs expands the filesystem to fill the drive. Give it the MOUNT POINT. XFS can only grow, never shrink.",
  M11 + " (Filesystem Management Tasks for xfs tools)", "xfs_ + growfs + mount point")
R("storage", "Check and repair the unmounted ext4 filesystem /dev/sdb1, answering yes to every fix",
  "fsck -y /dev/sdb1;;e2fsck -y /dev/sdb1;;fsck.ext4 -y /dev/sdb1",
  "fsck = diagnostics and repair (use if the system won't boot). Never run it on a mounted filesystem: umount first.",
  M11 + " (Filesystem Management)", "fsck + yes + device")
R("storage", "Set the label of the ext4 filesystem /dev/sdb1 to archive with e2label",
  "e2label /dev/sdb1 archive;;tune2fs -L archive /dev/sdb1",
  "e2label sets filesystem labels for easy identification; tune2fs -L does the same.",
  M11 + " (Filesystem Management Tasks for ext2/ext3/ext4)", "e2label DEV LABEL")
R("storage", "Set the reserved blocks on the ext4 filesystem /dev/sdb1 to 1 percent",
  "tune2fs -m 1 /dev/sdb1",
  "tune2fs configures ext4 options such as reserved blocks (-m, default 5%).",
  M11 + " (Filesystem Management Tasks for ext2/ext3/ext4)", "tune2fs + -m")
R("storage", "Print only the superblock information of /dev/sdb1 with dumpe2fs",
  "dumpe2fs -h /dev/sdb1",
  "dumpe2fs prints superblock and block-group information; -h stops after the superblock.",
  M11 + " (Filesystem Management Tasks for ext2/ext3/ext4)", "dumpe2fs + header flag")
R("storage", "After extending the LV, grow the ext4 filesystem on /dev/vg0/lvdata to fill it",
  "resize2fs /dev/vg0/lvdata",
  "resize2fs can enlarge or shrink an ext filesystem. For XFS use xfs_growfs on the mount point.",
  M11 + " (Filesystem Management)", "resize + 2 + fs")
R("storage", "Prepare /dev/sdc1 as swap space",
  "mkswap /dev/sdc1",
  "mkswap creates swap space; swapon activates it. An /etc/fstab line with type swap makes it permanent.",
  M11 + " (Swap Space and Virtual Memory)", "mk + swap")
R("storage", "Enable the swap partition /dev/sdc1",
  "swapon /dev/sdc1",
  "swapon and swapoff activate and deactivate swap. swapon --show lists what's active.",
  M11 + " (Swap Space and Virtual Memory)", "swap + on")
R("storage", "List the active swap areas",
  "swapon --show;;swapon -s;;cat /proc/swaps",
  "swapon --show lists active swap devices and files with their sizes.",
  M11 + " (Swap Space and Virtual Memory)", "swapon + show")
R("storage", "Show RAM and swap usage in human-readable units",
  "free -h",
  "free shows total/used/free memory and the Swap line. Swap prevents crashes but is slower than RAM.",
  "Linux+ XK0-006 (background to " + M11 + ": Swap Space and Virtual Memory)", "free + human")
R("storage", "Create a 1 GiB file /swapfile full of zeros with dd (block size 1M)",
  "dd if=/dev/zero of=/swapfile bs=1M count=1024",
  "File swap is one of the swap configurations on the slide. dd if= input, of= output, bs= block size, count= number of blocks. Then chmod 600, mkswap, swapon.",
  M11 + " (Swap Space and Virtual Memory: file swap); dd is Module 9", "if=/dev/zero of=... bs=... count=...")
R("storage", "LVM step 1: initialize /dev/sdb1 as a physical volume",
  "pvcreate /dev/sdb1",
  "LVM setup: partition disks, designate drives as physical volumes, aggregate into volume groups, allocate logical volumes. Check with pvs, vgs, lvs.",
  "Linux+ XK0-006 (background to " + M11 + ": Logical Volume Deployments)", "pv + create")
R("storage", "LVM step 2: create a volume group named vg0 from /dev/sdb1",
  "vgcreate vg0 /dev/sdb1",
  "vgcreate {vg name} {physical volumes}. The group pools the space of its PVs.",
  "Linux+ XK0-006 (background to " + M11 + ": Logical Volume Deployments)", "vg + create; name first.")
R("storage", "LVM step 3: create a 2 GB logical volume named lvdata in vg0",
  "lvcreate -L 2G -n lvdata vg0;;lvcreate -n lvdata -L 2G vg0;;lvcreate --size 2G --name lvdata vg0",
  "-L sets the size and -n the name; the volume group comes last. It appears as /dev/vg0/lvdata (and /dev/mapper/vg0-lvdata).",
  "Linux+ XK0-006 (background to " + M11 + ": Logical Volume Deployments)", "-L size, -n name, then VG.")
R("storage", "Grow the logical volume /dev/vg0/lvdata by 1 GB",
  "lvextend -L +1G /dev/vg0/lvdata;;lvextend -r -L +1G /dev/vg0/lvdata",
  "lvextend -L +1G adds 1 GB ('resize storage' is an LVM management task). Then grow the filesystem too, or add -r to do both.",
  "Linux+ XK0-006 (background to " + M11 + ": Logical Volume Deployments)", "A plus sign means add.")

# ============================================================================= mounts: typed commands
R("mounts", "Create the mount point /opt/downloads",
  "mkdir /opt/downloads;;mkdir -p /opt/downloads",
  "Slide: 'Create a mount point (directory) /opt/downloads for the new partition.' Mount on an empty directory.",
  M11 + " (Manually Test Mount)", "make a directory")
R("mounts", "Mount /dev/sdb1 on the directory /opt/downloads",
  "mount /dev/sdb1 /opt/downloads",
  "mount {device} {mount point}. You need the device, the directory and root privilege. It doesn't survive a reboot unless it's in /etc/fstab.",
  M11 + " (Manually Test Mount)", "device first, then directory.")
R("mounts", "Confirm that /dev/sdb1 is mounted (filter the mount list)",
  "mount | grep sdb1;;mount|grep sdb1;;mount | grep /dev/sdb1",
  "Slide: 'Type mount | grep sdb1. Verify that the /dev/sdb1 partition mounted on /opt/downloads.'",
  M11 + " (Make a Mount Permanent)", "mount piped to grep")
R("mounts", "Give the rocky user and group ownership of the mount point /opt/downloads",
  "chown rocky:rocky /opt/downloads;;chown rocky.rocky /opt/downloads",
  "After mounting, the directory shows the new filesystem's root (owned by root). The slides change ownership so rocky can write, then test with touch.",
  M11 + " (Manually Test Mount)", "chown user:group dir")
R("mounts", "Unmount /opt/downloads",
  "umount /opt/downloads;;umount /dev/sdb1",
  "umount, no 'n'. 'target is busy' means something (maybe your own shell) is inside it.",
  M11 + " (What is Mounting?)", "umount, no n.")
R("mounts", "Type the /etc/fstab line that mounts /dev/sdb1 at /opt/downloads as xfs with default options, no dump and no fsck",
  "/dev/sdb1 /opt/downloads xfs defaults 0 0",
  "The exact line from the slide. Six fields: device, mount point, filesystem type, options, dump, fsck pass order.",
  M11 + " (Make a Mount Permanent)", "Six fields.", loose=True)
R("mounts", "Mount everything listed in /etc/fstab (the safe way to test an fstab edit)",
  "mount -a",
  "mount -a reports fstab mistakes now instead of at boot, where a bad line drops the server into emergency mode.",
  PV + "Linux+ XK0-006 7.3 Mount Storage", "mount + all")
R("mounts", "Reboot the server now",
  "reboot;;shutdown -r now;;systemctl reboot",
  "The slides reboot to prove the /etc/fstab mount comes back. Needs sudo.",
  M11 + " (Make a Mount Permanent)", "re + boot")
R("mounts", "Mount a 100 MB RAM-backed tmpfs on /mnt/ram",
  "mount -t tmpfs -o size=100M tmpfs /mnt/ram;;mount -t tmpfs tmpfs /mnt/ram -o size=100M",
  "tmpfs stores data in memory: fast, but gone at unmount or shutdown.",
  "Linux+ XK0-006 (background to " + M11 + ": tmpfs)", "-t tmpfs -o size=... tmpfs DIR")
R("mounts", "Show disk space usage of mounted filesystems in human-readable units",
  "df -h",
  "df reports filesystem usage; -h uses K/M/G. du reports usage of files and directories.",
  PV + "Linux+ XK0-006 7.3 Mount Storage", "disk free + human")
R("mounts", "Show the total size of /var/log in human-readable form (summary only)",
  "du -sh /var/log",
  "du -s summarizes and -h is human-readable. df is per filesystem, du is per directory.",
  PV + "Linux+ XK0-006 7.3 Mount Storage", "disk usage + summary + human")
R("mounts", "Re-apply the /etc/fstab options for /home2 without unmounting it",
  "mount -o remount /home2",
  "remount re-reads the mount options, e.g. after adding usrquota,grpquota to fstab.",
  PV + "Linux+ XK0-006 7.4 (disk quotas)", "-o remount")
R("mounts", "Build the user and group quota files for /home2",
  "quotacheck -cug /home2;;quotacheck -ugc /home2",
  "quotacheck -c creates aquota.user/aquota.group, -u users, -g groups. The filesystem must be mounted with usrquota/grpquota.",
  PV + "Linux+ XK0-006 7.4 (disk quotas; usrquota/grpquota are on the " + M11 + ")", "-c create, -u, -g")
R("mounts", "Turn quotas on for /home2",
  "quotaon /home2;;quotaon -v /home2",
  "quotaon starts enforcing the limits. quotaoff stops it.",
  PV + "Linux+ XK0-006 7.4 (disk quotas)", "quota + on")
R("mounts", "Give bob a 500 MB soft and 600 MB hard block limit on /home2 (no inode limits), in 1K blocks",
  "setquota -u bob 512000 614400 0 0 /home2;;setquota -u bob 500000 600000 0 0 /home2",
  "setquota -u USER block-soft block-hard inode-soft inode-hard MOUNTPOINT. Soft can be exceeded during the grace period; hard can't.",
  PV + "Linux+ XK0-006 7.4 (soft/hard limits are on the " + M11 + ")", "setquota -u USER SOFT HARD 0 0 MP", loose=True)
R("mounts", "Show a quota report for /home2",
  "repquota /home2;;repquota -s /home2",
  "'Quota reports display storage space usage by user.'",
  M11 + " (Setting Disk Quotas)", "rep + quota")
R("mounts", "Create RAID 1 array /dev/md0 from /dev/sdb and /dev/sdc with mdadm",
  "mdadm --create /dev/md0 --level=1 --raid-devices=2 /dev/sdb /dev/sdc;;mdadm -C /dev/md0 -l 1 -n 2 /dev/sdb /dev/sdc;;mdadm --create /dev/md0 --level 1 --raid-devices 2 /dev/sdb /dev/sdc",
  "Software RAID is part of the OS. mdadm --create names the array, --level picks the RAID level and --raid-devices the count. Check with cat /proc/mdstat.",
  PV + "Linux+ XK0-006 7.4 (RAID; hardware vs software RAID is on the " + M11 + ")", "--create, --level, --raid-devices")
R("mounts", "Show the status of all software RAID arrays (a file in /proc)",
  "cat /proc/mdstat",
  "[2/2] [UU] = healthy mirror; [2/1] [U_] = degraded.",
  PV + "Linux+ XK0-006 7.4 (RAID)", "/proc/md...")
R("mounts", "Mark /dev/sdc as failed in the array /dev/md0",
  "mdadm /dev/md0 --fail /dev/sdc;;mdadm --manage /dev/md0 --fail /dev/sdc;;mdadm /dev/md0 -f /dev/sdc",
  "Fail it, then --remove it, then --add a replacement; the array rebuilds.",
  PV + "Linux+ XK0-006 7.4 (RAID)", "MD --fail DEV")
