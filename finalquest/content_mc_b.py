"""Multiple-choice bank, part B: Modules 9-10 (plus a PREVIEW of Modules 11-12 storage)."""
from .content_base import M

PV = "PREVIEW (slides not posted yet): "

# ---------------------------------------------------------------- archive (8)
M("archive", "Which tar option creates a new tarball?",
  "-c", ["-x", "-t", "-r"],
  "-c creates, -x extracts, -t tests (lists) and -r appends to an existing archive.",
  "Module 9 slides (Archiving with tar)")
M("archive", "Which tar option is REQUIRED because it specifies the tarball filename?",
  "-f", ["-v", "-z", "-t"],
  "-f names the tarball and must be used with tar. -v is only verbose output.",
  "Module 9 slides (Archiving with tar)")
M("archive", "An administrator wants to see what is inside backup.tar without extracting it. Which command does this?",
  "tar -tf backup.tar", ["tar -xf backup.tar", "tar -cf backup.tar", "tar -rf backup.tar"],
  "-t tests/lists the contents of the tarball. -x would extract the files.",
  "Module 9 slides (Archiving with tar)")
M("archive", "Which command adds file4 to an archive that already exists named backup.tar?",
  "tar -rf backup.tar file4", ["tar -cf backup.tar file4", "tar -xf backup.tar file4", "tar -tf backup.tar file4"],
  "-r appends files to an existing archive. -c would create a new archive and overwrite the old one.",
  "Module 9 slides (Archiving with tar)")
M("archive", "Which command copies files OUT of the filesystem into a cpio archive?",
  "ls | cpio -ov > /tmp/archive.cpio", ["cpio -iv < /tmp/archive.cpio", "ls | cpio -iv > /tmp/archive.cpio", "cpio -tv /tmp/archive.cpio"],
  "-o is copy-out (create the archive) and reads the file list from stdin. -i is copy-in (extract) and reads the archive from stdin.",
  "Module 9 slides (Copy In/Copy Out)")
M("archive", "In cpio, what does the -i option do?",
  "Copies files into the filesystem to restore or extract them from an archive", ["Copies files out of the filesystem to create an archive", "Ignores errors while archiving", "Includes hidden files in the archive"],
  "-i = copy in (restore/extract). -o = copy out (back up/create). -v is verbose.",
  "Module 9 slides (Copy In/Copy Out)")
M("archive", "Which command creates a gzip-compressed tarball of all .txt files named myfiles.tar.gz?",
  "tar -czvf myfiles.tar.gz *.txt", ["tar -cjvf myfiles.tar.gz *.txt", "tar -xzvf myfiles.tar.gz *.txt", "tar -cvf myfiles.tar *.txt.gz"],
  "-c creates, -z filters through gzip, -v is verbose and -f supplies the filename. -j would use bzip2 instead.",
  "Module 9 slides (File Compression with tar)")
M("archive", "True or false: the cpio tool can also create tar-format archives.",
  "True", ["False"],
  "The Copy In/Copy Out slide notes that cpio can also create tar files.",
  "Module 9 slides (Copy In/Copy Out)")

# ---------------------------------------------------------------- compress (12)
M("compress", "Which type of compression removes only redundant data so the original can be rebuilt exactly?",
  "Lossless", ["Lossy", "Lossless-fast", "Differential"],
  "Lossless removes only redundant data. Lossy removes non-essential data and the original cannot be fully restored.",
  "Module 9 slides (File Compression Concepts)")
M("compress", "Which file extension does the gzip command create?",
  ".gz", [".gzip", ".bz2", ".xz"],
  "gzip creates .gz files. .bz2 is bzip2 and .xz is xz.",
  "Module 9 slides (File Compression Concepts)")
M("compress", "Which command decompresses archive.tar.gz? (Choose the best answer.)",
  "gunzip archive.tar.gz", ["gzip -c archive.tar.gz", "unzip archive.tar.gz", "bzip2 -d archive.tar.gz"],
  "gunzip (or gzip -d) decompresses .gz files. unzip is for .zip files.",
  "Module 9 slides (File Compression Concepts)")
M("compress", "Which gzip option checks the integrity of a compressed file?",
  "-t", ["-d", "-r", "-q"],
  "-t tests integrity. -d decompresses, -r is recursive and -q suppresses warnings.",
  "Module 9 slides (File Compression Concepts: gzip)")
M("compress", "You want to read a .gz file without decompressing it. Which command should you use?",
  "zcat", ["bzcat", "xzcat -d", "zip -v"],
  "zcat, zless and zgrep view or search .gz files without decompressing them. bzcat is for .bz2.",
  "Module 9 slides (gzip Utilities)")
M("compress", "Which compression tool offers the BEST compression ratio but is the slowest?",
  "xz", ["gzip", "bzip2", "zip"],
  "xz = best ratio, slowest speed. gzip is the fastest with a lower ratio. bzip2 is balanced.",
  "Module 9 slides (Choosing Compression Tools)")
M("compress", "Which compression tool is described as the FASTEST, with a lower compression ratio?",
  "gzip", ["xz", "bzip2", "7z"],
  "gzip is the fastest for compression and decompression, at the cost of a lower ratio.",
  "Module 9 slides (Choosing Compression Tools)")
M("compress", "Which tool is described as balanced and good for infrequently accessed data?",
  "bzip2", ["gzip", "xz", "unzip"],
  "bzip2 is the balanced option and is suited to infrequent access.",
  "Module 9 slides (Choosing Compression Tools)")
M("compress", "Which of these commands is used to repair a damaged .bz2 file?",
  "bzip2recover", ["bzdiff", "bzcat", "bzless"],
  "bzip2recover recovers data from damaged .bz2 files. bzcat, bzless and bzmore view the contents.",
  "Module 9 slides (File Compression Concepts: bzip2)")
M("compress", "Which tool both compresses AND archives files into a single .zip file?",
  "zip", ["gzip", "bzip2", "xz"],
  "zip compresses and archives in one step. gzip, bzip2 and xz compress a single file and are usually combined with tar.",
  "Module 9 slides (File Compression Concepts: zip)")
M("compress", "Which tar option compresses with bzip2 (.tar.bz2)?",
  "-j", ["-z", "-b", "-Z"],
  "-z = gzip (.tar.gz) and -j = bzip2 (.tar.bz2). Add the same letter with -x to extract and decompress.",
  "Module 9 slides (File Compression with tar)")
M("compress", "Which statement about 7zip (7z) is TRUE?",
  "It is cross-platform, offers high compression and handles large files", ["It can only extract .zip files", "It is the fastest tool but has the lowest ratio", "It is installed as part of gzip"],
  "7z is cross-platform with high compression and large-file support. The slide lists -a (add), -x (extract), -o (output dir), -p (password) and -mx (level); real 7z usually takes a and x without a dash.",
  "Module 9 slides (File Compression Concepts: 7zip)")

# ---------------------------------------------------------------- integrity (12)
M("integrity", "What is the most common method of confirming that a backup has not been changed?",
  "Hashing and comparing the current value to a previous value", ["Compressing it a second time", "Changing its permissions to read-only", "Renaming it with a date"],
  "Integrity checking compares the current hash against a previously recorded one. Any change in the file changes the hash.",
  "Module 9 slides (File Integrity)")
M("integrity", "Which of these hash algorithms is considered WEAK because of collision risk?",
  "MD5", ["SHA-256", "SHA-3", "Argon2"],
  "MD5 and SHA1 are weak and should be avoided for security. SHA-256, SHA-3 and Argon2 are listed as strong.",
  "Module 9 slides (File Integrity: Hash Functions)")
M("integrity", "Which of these is NOT a strong hash algorithm according to the course?",
  "SHA1", ["SHA-256", "SHA-3", "Argon2"],
  "SHA1 is listed as weak along with MD5.",
  "Module 9 slides (File Integrity: Hash Functions)")
M("integrity", "What is a collision attack?",
  "Two different sets of data produce the same hash", ["The same data produces two different hashes", "A hash is reversed to reveal the original password", "A disk is overwritten with the wrong block size"],
  "In a collision, different data yields the same hash, which defeats integrity checking. Short hashes carry a higher collision risk.",
  "Module 9 slides (File Integrity: Hash Functions)")
M("integrity", "Which command compares files against hashes that were saved earlier by md5sum?",
  "md5sum -c", ["md5sum -t", "md5sum -d", "md5sum -v"],
  "-c checks the files against the saved hash list. If a file changed, its hash will not match.",
  "Module 9 slides (File Integrity: md5sum)")
M("integrity", "How many bits long is an MD5 hash, and in what format does md5sum print it?",
  "128 bits, hexadecimal", ["256 bits, binary", "64 bits, decimal", "512 bits, base64"],
  "md5sum generates a 128-bit hash shown in hex. It is fine for integrity checks but not for security-critical uses.",
  "Module 9 slides (File Integrity: md5sum)")
M("integrity", "Which command calculates a SHA-256 hash of a file called backup.tar?",
  "sha256sum backup.tar", ["sha2sum -256 backup.tar", "shasum256 backup.tar", "md5sum -s 256 backup.tar"],
  "The pattern is sha#sum: sha1sum, sha256sum, sha384sum and sha512sum.",
  "Module 9 slides (File Integrity: SHA Commands)")
M("integrity", "HMAC combines a hash function with what to provide both integrity and authenticity?",
  "A shared secret key", ["A public certificate only", "A compression algorithm", "A block size operand"],
  "Sender and recipient share a secret key. HMAC is used in protocols such as HTTPS and SMTP and verifies faster than public-key methods.",
  "Module 9 slides (File Integrity: HMAC)")
M("integrity", "Which dd operand specifies the INPUT file?",
  "if=", ["of=", "bs=", "count="],
  "if= is the input file, of= the output file, bs= the block size, count= the number of blocks and status= the level of information shown.",
  "Module 9 slides (File Modification with dd)")
M("integrity", "Which dd status= value shows ongoing transfer statistics?",
  "progress", ["none", "noxfer", "verbose"],
  "status=none gives minimal output, noxfer suppresses the transfer stats and progress shows ongoing stats.",
  "Module 9 slides (File Modification with dd)")
M("integrity", "An administrator mistypes dd if=/dev/sdb of=/dev/sda while trying to clone a drive. What is the biggest risk?",
  "The destination drive, possibly the system disk, is overwritten", ["The source drive is deleted", "dd refuses to run without a hash", "Only the file permissions are changed"],
  "dd is powerful but dangerous. An improper command can overwrite whole partitions, so always double-check if= and of=.",
  "Module 9 slides (File Modification with dd)")
M("integrity", "Which statement about ddrescue is TRUE?",
  "It makes multiple passes over a failing disk to recover as much data as possible", ["It securely erases a failing disk", "It only works on files, not devices", "It is a faster replacement for md5sum"],
  "ddrescue recovers data from a failing source to a working destination. Options: -f force overwrite, -r retry count, -v verbose.",
  "Module 9 slides (Data Recovery with ddrescue)")

# ---------------------------------------------------------------- packages (14)
M("packages", "What are the two ways to manage software discussed in Module 10?",
  "Package management and compiling source code", ["Package management and virtualization", "Compiling source code and containers only", "Repositories and sandboxes"],
  "Method 1 is package management (pre-compiled software). Method 2 is compiling source code.",
  "Module 10 slides (What is Software Management?)")
M("packages", "Which licensing approach requires modified or redistributed software to preserve the same freedoms?",
  "Copyleft", ["Closed source", "Freeware", "Shareware"],
  "Copyleft (for example the GNU GPL) requires derivative works to keep the same freedoms. Open source describes how software is made available, while copyleft describes the license rules.",
  "Module 10 slides (Open-Source Software vs Copyleft)")
M("packages", "Which of these is closed-source software?",
  "A proprietary paid application whose source code is not available", ["The Linux kernel", "Mozilla Firefox", "Apache HTTP Server"],
  "Closed source is protected by copyright and cannot be duplicated or modified. Linux, Firefox and Apache are open source.",
  "Module 10 slides (Package Management Concepts)")
M("packages", "Which error indicates that a package needs software that is not installed?",
  "Failed dependency", ["Broken repository", "Bad GPG key", "Disk quota exceeded"],
  "Packages list the components they require. A 'failed dependency' error means one or more were not satisfied.",
  "Module 10 slides (Software Dependencies)")
M("packages", "Which of these tools does NOT automatically resolve dependencies?",
  "rpm", ["yum", "dnf", "apt"],
  "Low-level tools (RPM, DPKG) do not resolve dependencies. High-level tools (YUM, DNF, APT, APT-GET) do.",
  "Module 10 slides (Software Installation and Updates)")
M("packages", "Which pair are the Debian-based package managers?",
  "dpkg and apt", ["rpm and yum", "dnf and dpkg", "yum and apt"],
  "Debian uses dpkg (low-level) and APT (high-level), plus apt-get. Red Hat uses RPM, YUM and DNF.",
  "Module 10 slides (Package Managers)")
M("packages", "Which package manager is the default on most current Red Hat-derived distributions such as Rocky Linux?",
  "dnf", ["rpm", "dpkg", "apt-get"],
  "DNF (Dandified YUM) is the default for most current Red Hat-derived distros and is the modern replacement for YUM.",
  "Module 10 slides (Red Hat Package Managers)")
M("packages", "What does the command rpm -ivh package.rpm do?",
  "Installs the package, shows a progress bar and verbose output", ["Removes the package and prints its version", "Queries the package and prints its info", "Installs the package and all dependencies automatically"],
  "-i install, -v verbose and -h progress bar (hash marks). -e erases. rpm does not resolve dependencies for you.",
  "Module 10 slides (RPM commands)")
M("packages", "Which command displays details about one installed package named zip on an RPM-based system?",
  "rpm -qi zip", ["rpm -qa zip", "rpm -ei zip", "rpm -ivh zip"],
  "rpm -qi {package} shows package details. rpm -qa lists ALL installed packages.",
  "Module 10 slides (Why Query?)")
M("packages", "Which yum option automatically answers yes to the prompt to install dependencies?",
  "-y", ["-a", "-q", "-f"],
  "yum install -y {package} skips the yes/no prompt. Without it, YUM asks before installing extra dependencies.",
  "Module 10 slides (yum Subcommands)")
M("packages", "Which yum subcommand reports which package provides a specific file?",
  "provides", ["info", "localinstall", "update"],
  "provides {file name} reports the package that supplies the file. localinstall installs from a local file and info reports package info.",
  "Module 10 slides (yum Subcommands)")
M("packages", "Which command lists installed packages on a Debian-based system and saves them to softwarelist.txt?",
  "dpkg -l > softwarelist.txt", ["rpm -qa > softwarelist.txt", "dnf list installed > softwarelist.txt", "apt show > softwarelist.txt"],
  "On Debian-based systems use dpkg -l or apt list --installed. rpm -qa and dnf list installed are the Red Hat equivalents.",
  "Module 10 slides (Review - Package Queries)")
M("packages", "Which command manages the default version of a program system-wide, letting you see, configure, add and remove alternatives?",
  "update-alternatives", ["apt-get", "createrepo", "rpm --alternatives"],
  "update-alternatives is listed with the Debian-based tools and manages system-wide defaults.",
  "Module 10 slides (Software Installation and Updates)")
M("packages", "A user needs to install a Python library inside an isolated virtual environment. Which tool is the language-specific package manager?",
  "pip", ["cargo", "npm", "dnf"],
  "pip is for Python and uses virtual environments to isolate dependencies. cargo is for Rust and npm is for JavaScript/Node.js.",
  "Module 10 slides (Language-Specific Package Managers)")

# ---------------------------------------------------------------- repos (14)
M("repos", "Which of these is a difference between wget and curl?",
  "wget can download recursively; curl cannot", ["curl can download recursively; wget cannot", "wget supports many protocols; curl only HTTP", "wget needs a GUI; curl is command-line only"],
  "The slide says wget is a command-line utility that can download recursively and supports HTTP, HTTPS and FTP. curl cannot download recursively but supports many protocols.",
  "Module 10 slides (wget vs curl)")
M("repos", "Which curl option saves the download under a name you choose?",
  "-o", ["-O", "-P", "-d"],
  "The slide example is curl -o nmap-7.70.tar.bz2 {URL}. The slide shows the wget example as wget {URL} with no option.",
  "Module 10 slides (wget and curl commands)")
M("repos", "Which tool is better suited for building and managing more complex requests and responses from web servers?",
  "curl", ["wget", "tar", "rpm"],
  "curl supports many protocols and is better for complex requests. wget is better for straightforward file downloads.",
  "Module 10 slides (wget vs curl)")
M("repos", "What is a repository?",
  "A storage location for software packages", ["A tool that compiles source code", "A database of user passwords", "A type of sandbox"],
  "Repos are storage locations that package managers like YUM and APT check when installing or upgrading software.",
  "Module 10 slides (Repositories)")
M("repos", "Which type of repository is stored on one or more systems in a LAN and makes version control simpler?",
  "Centralized internal", ["Local", "Vendor", "Flatpak remote"],
  "A centralized internal repo is managed by the Linux administrator. Local repos are decentralized and vendor repos are controlled by the vendor.",
  "Module 10 slides (Repositories)")
M("repos", "An administrator manages 10 servers and gives each its own repository on its own drive. Which problem does this create?",
  "Version control is difficult because every repo must be maintained separately", ["The servers cannot install any packages", "The repos become read-only", "Packages are installed without dependencies"],
  "Local repos are easy to install from but decentralized, so 10 servers means 10 repos to maintain. One internal repo shared over the LAN is simpler.",
  "Module 10 slides (Repositories)")
M("repos", "Which is NOT a listed reason for maintaining your own repositories?",
  "Faster CPU speed", ["Software version control", "Bandwidth control", "Application installation control"],
  "Reasons include version control, installation control, vendor control, bandwidth control and repo exclusion, which supports stability, security and compliance.",
  "Module 10 slides (Repositories)")
M("repos", "Where are YUM and DNF repository configuration files stored?",
  "/etc/yum.repos.d", ["/etc/apt/sources", "/var/lib/rpm", "/usr/share/repos"],
  "Repo definition files (.repo) live in /etc/yum.repos.d. Global settings are in /etc/yum.conf (YUM) and /etc/dnf/dnf.conf (DNF).",
  "Module 10 slides (Manage YUM/DNF Repository Configuration Files)")
M("repos", "In a .repo file, which field gives the URL where packages and metadata are stored?",
  "baseurl", ["name", "enabled", "gpgcheck"],
  "name is the human-readable name, baseurl is the location (HTTP/HTTPS, FTP or file:///), enabled turns the repo on or off and gpgcheck controls signature verification.",
  "Module 10 slides (Repositories: .repo components)")
M("repos", "What does gpgcheck=0 in a .repo file mean?",
  "Package signatures are NOT verified, which is less secure", ["The repository is disabled", "Only signed packages are installed", "The repository is read-only"],
  "gpgcheck=1 verifies package signatures (recommended). With 0, packages can be installed without proving they are authentic, exposing the system to tampered packages.",
  "Module 10 slides (gpgcheck=0)")
M("repos", "What does enabled=0 do in a .repo file?",
  "The repository is ignored unless manually enabled", ["The repository is deleted", "The repository is used first", "Package signatures are skipped"],
  "enabled=1 means the package manager uses the repo. enabled=0 means it is ignored unless you enable it manually.",
  "Module 10 slides (enabled=1)")
M("repos", "Which command designates a directory of .rpm files as a YUM/DNF repository by building its metadata?",
  "createrepo", ["repoinit", "yum-config-manager --make", "rpm --newrepo"],
  "createrepo updates the XML metadata used to reference the location. You then add a .repo file in /etc/yum.repos.d.",
  "Module 10 slides (YUM Repository Configuration)")
M("repos", "On a Debian-based system, which command lets APT learn about newly added repositories?",
  "apt update", ["apt upgrade", "apt show", "apt-get remove"],
  "Run apt update after changing repositories. Tool configuration can be managed with the apt.conf file.",
  "Module 10 slides (Repositories)")
M("repos", "Which sandboxed package format can run applications WITHOUT root or sudo privileges but has more limited sandboxing than Snaps and Flatpak?",
  "AppImage", ["Docker", "RPM", "Virtual machine"],
  "AppImage is portable and can run without installation, but it has limited sandboxing compared to Snaps and Flatpak.",
  "Module 10 slides (Sandboxed Software)")

# ---------------------------------------------------------------- storage (12, PREVIEW)
M("storage", "Which partitioning scheme supports disks larger than 2 TB and many more than four partitions?",
  "GPT", ["MBR", "FAT32", "LVM"],
  "MBR is limited to about 2 TB and four primary partitions. GPT removes those limits.",
  PV + "CompTIA Linux+ Module 7 (Deploy Standard Storage)")
M("storage", "What is the device name of the SECOND partition on the first SATA/SCSI disk?",
  "/dev/sda2", ["/dev/sdb1", "/dev/sd2a", "/dev/hda2"],
  "Disks are /dev/sda, /dev/sdb and so on. Partitions add a number: sda1, sda2.",
  PV + "CompTIA Linux+ Module 7 (Deploy Standard Storage)")
M("storage", "Which tool is commonly used to create and edit partitions on a disk?",
  "fdisk", ["mkfs", "mount", "lvextend"],
  "fdisk (also gdisk and parted) manages partitions. mkfs creates the file system afterwards.",
  PV + "CompTIA Linux+ Module 7 (Deploy Standard Storage)")
M("storage", "After creating a new partition /dev/sdb1, what must happen before you can store files on it?",
  "Create a file system on it, such as with mkfs.ext4", ["Run lvextend on it", "Add it to /etc/passwd", "Compress it with gzip"],
  "A partition is raw space. mkfs (for example mkfs.ext4 or mkfs.xfs) creates the file system, then you mount it.",
  PV + "CompTIA Linux+ Module 7 (Deploy Standard Storage)")
M("storage", "In LVM, what is the correct order to build a logical volume?",
  "Physical volume, volume group, logical volume", ["Logical volume, volume group, physical volume", "Volume group, physical volume, logical volume", "Physical volume, logical volume, volume group"],
  "pvcreate makes physical volumes, vgcreate pools them into a volume group and lvcreate carves logical volumes from the group.",
  PV + "CompTIA Linux+ Module 7 (Logical Volume Management)")
M("storage", "Which command creates a 5 GB logical volume called data in the volume group vg0?",
  "lvcreate -L 5G -n data vg0", ["vgcreate -L 5G -n data vg0", "pvcreate -L 5G data vg0", "lvextend -L 5G data vg0"],
  "lvcreate -L sets the size and -n the name, followed by the volume group.",
  PV + "CompTIA Linux+ Module 7 (Logical Volume Management)")
M("storage", "An ext4 logical volume is full. After running lvextend, which command makes the file system use the new space?",
  "resize2fs", ["xfs_growfs", "mkfs.ext4", "fsck -a"],
  "lvextend grows the volume but not the file system. Use resize2fs for ext4 and xfs_growfs for XFS.",
  PV + "CompTIA Linux+ Module 7 (Logical Volume Management)")
M("storage", "How many fields are on each line of /etc/fstab?",
  "Six", ["Four", "Five", "Seven"],
  "The fields are device, mount point, file system type, options, dump and fsck pass order.",
  PV + "CompTIA Linux+ Module 7 (Mount Storage)")
M("storage", "Why is it often better to use a UUID instead of /dev/sdb1 in /etc/fstab?",
  "Device names can change between boots, but the UUID stays the same", ["A UUID makes the disk faster", "A UUID encrypts the partition", "/dev names cannot be used in fstab"],
  "Disk order can change when devices are added, so /dev/sdX names are not stable. blkid shows each UUID.",
  PV + "CompTIA Linux+ Module 7 (Mount Storage)")
M("storage", "What is the difference between df and du?",
  "df reports free space per file system; du reports space used by files and directories", ["df lists devices; du lists users", "df repairs file systems; du unmounts them", "They are identical"],
  "df -h shows file-system capacity and free space. du -sh shows how much space a directory uses.",
  PV + "CompTIA Linux+ Module 7 (Mount Storage)")
M("storage", "Which RAID level mirrors data across two disks so one can fail without data loss?",
  "RAID 1", ["RAID 0", "RAID 5 with one disk", "RAID 6 with no parity"],
  "RAID 0 stripes with no redundancy, RAID 1 mirrors, RAID 5 uses single parity and RAID 6 uses double parity. RAID 10 combines mirroring and striping.",
  PV + "CompTIA Linux+ Module 7 (Manage Other Storage Options)")
M("storage", "Which statement about swap space is TRUE?",
  "It is disk space the kernel uses as extra memory when RAM is full", ["It stores the user's home directory", "It is created with createrepo", "It must be a mounted ext4 volume"],
  "Create it with mkswap and enable it with swapon. Swap can be a partition or a file.",
  PV + "CompTIA Linux+ Module 7 (Manage Other Storage Options)")
