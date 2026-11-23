"""Typed-command recall questions, part B: Modules 9-10 (post-midterm) storage is in content_storage.py."""
from .content_base import R

M9 = "Module 9 slides"
M10 = "Module 10 slides"
PV = "PREVIEW (slides not posted yet): "

# ---------------------------------------------------------------- archive: tar and cpio
R("archive", "Create an archive named backup.tar from file10 and file20 (verbose)",
  "tar -cvf backup.tar file10 file20;;tar -cf backup.tar file10 file20",
  "-c creates, -v is verbose, and -f names the tarball (required). Review exercise: 'Archive using tar command and name the archive file backup.tar'.",
  M10 + " (Review: Archive using tar)", "Three options: create, verbose, file.")
R("archive", "Extract archive.tar into the current directory (verbose)",
  "tar -xvf archive.tar;;tar -xf archive.tar",
  "-x extracts, -v shows each file, -f names the tarball. Without -f tar does not know which tarball to use.",
  M9 + " (Archiving and Extracting Files with tar, Slide 2 of 3)", "Create is -c; the opposite is...")
R("archive", "List the contents of archive.tar WITHOUT extracting it",
  "tar -tf archive.tar;;tar -tvf archive.tar",
  "-t tests/lists the files in a tarball without extracting anything.",
  M9 + " (tar common options: -t)", "-t")
R("archive", "Create a gzip-compressed tarball named backup.tar.gz of all .txt files (verbose)",
  "tar -czvf backup.tar.gz *.txt;;tar -czf backup.tar.gz *.txt",
  "-z pipes the archive through gzip. The slide example is tar -czvf myfiles.tar.gz *.txt. The -f name must come right after the option group.",
  M9 + " (File Compression with tar)", "-z means gzip.")
R("archive", "Create a bzip2-compressed tarball named myfiles.tar.bz2 of all .txt files (verbose)",
  "tar -cjvf myfiles.tar.bz2 *.txt;;tar -cjf myfiles.tar.bz2 *.txt",
  "-j is the tar option for bzip2 (.tar.bz2). Slide example: tar -cjvf myfiles.tar.bz2 *.txt.",
  M9 + " (File Compression with tar)", "-z is gzip, so bzip2 uses another letter.")
R("archive", "Append file30 to the existing archive backup.tar (verbose)",
  "tar -rvf backup.tar file30;;tar -rf backup.tar file30",
  "-r appends files to an existing (uncompressed) archive. You cannot append to a compressed .tar.gz.",
  M9 + " (tar common options: -r)", "-r")
R("archive", "Extract AND decompress myfiles.tar.gz (verbose)",
  "tar -xzvf myfiles.tar.gz;;tar -xzf myfiles.tar.gz",
  "Add z (gzip) or j (bzip2) to -x to extract and decompress in one step.",
  M9 + " (File Compression with tar)", "Extract plus gzip plus file.")
R("archive", "With cpio, copy OUT the files file1 file2 file3 into /tmp/archive.cpio (verbose)",
  "ls file1 file2 file3 | cpio -ov > /tmp/archive.cpio",
  "cpio reads the list of names from stdin (so you pipe ls into it) and writes the archive to stdout. -o = copy out, -v = verbose.",
  M9 + " (Copy In/Copy Out)", "List the files, pipe to cpio, redirect to the archive.")
R("archive", "With cpio, copy IN (restore) the files from /tmp/archive.cpio (verbose)",
  "cpio -iv < /tmp/archive.cpio",
  "-i copies into the filesystem to restore or extract. The archive comes in on stdin with <.",
  M9 + " (Copy In/Copy Out)", "Opposite of -o, with input redirection.")
R("archive", "With cpio, back up everything in the current directory into backup.cpio (verbose)",
  "ls | cpio -ov > backup.cpio",
  "Same pattern as the slide: ls | cpio -ov > archive.cpio. cpio can also create tar files.",
  M9 + " (Copy In/Copy Out)", "ls feeds names to cpio.")

# ---------------------------------------------------------------- compress
R("compress", "Compress archive.tar with gzip (creates archive.tar.gz)",
  "gzip archive.tar",
  "gzip {options} {filenames} compresses to .gz and by default replaces the original file.",
  M9 + " (File Compression Concepts, Slide 2 of 5)", "The command is the name of the format.")
R("compress", "Decompress archive.tar.gz using gunzip",
  "gunzip archive.tar.gz;;gzip -d archive.tar.gz",
  "gunzip is the same as gzip -d. The slide says: use gunzip for .gz files and unzip for .zip files.",
  M9 + " (File Compression Concepts, Slide 2 and 5)", "g + un + zip.")
R("compress", "Test the integrity of archive.tar.gz with gzip",
  "gzip -t archive.tar.gz",
  "gzip -t is the integrity check. Other slide options: -d decompress, -f force, -n/-N omit/save name and timestamp, -q quiet, -r recursive, -v verbose.",
  M9 + " (File Compression Concepts, Slide 2 of 5)", "-t = test")
R("compress", "Page through the compressed file notes.gz WITHOUT decompressing it",
  "zless notes.gz;;zmore notes.gz",
  "zcat, zless and zgrep view or search .gz files without decompressing them first. (zmore also works on real systems.)",
  M9 + " (gzip Utilities: zcat, zless, zgrep)", "z + the pager you prefer.")
R("compress", "Compress archive.tar with xz (creates archive.tar.xz)",
  "xz archive.tar",
  "xz {options} {filenames} gives the best compression ratio but is the slowest.",
  M9 + " (File Compression Concepts, Slide 3 and 5)", "The command is the format's name.")
R("compress", "Decompress archive.tar.xz using xz",
  "xz -d archive.tar.xz;;unxz archive.tar.xz",
  "xz options from the slide: -d decompress, -f force, -q quiet, -v verbose, -t test. (unxz is the shortcut for xz -d.)",
  M9 + " (Compressing with xz)", "-d")
R("compress", "Compress backup.tar with bzip2 (creates backup.tar.bz2)",
  "bzip2 backup.tar",
  "Review exercise: 'Compress backup.tar using bzip2'. bzip2 is balanced and good for infrequent access.",
  M10 + " (Review) / " + M9 + " (File Compression Concepts)", "The command is the format's name.")
R("compress", "Decompress backup.tar.bz2 using bunzip2",
  "bunzip2 backup.tar.bz2;;bzip2 -d backup.tar.bz2",
  "bunzip2 decompresses .bz2 files. Related tools: bzcat (to stdout), bzip2recover, bzless, bzmore.",
  M9 + " (Compressing with bzip2)", "b + un + zip2")
R("compress", "Print the contents of the compressed file notes.bz2 to the screen without decompressing it on disk",
  "bzcat notes.bz2",
  "bzcat decompresses to stdout, like zcat does for gzip.",
  M9 + " (Compressing with bzip2)", "cat for bzip2.")
R("compress", "Recursively zip the directory dir1 into dir1.zip",
  "zip -r dir1.zip dir1",
  "zip both compresses and archives. -r is recursive; the zip file name comes first, then what to add. Slide options: -d delete, -e encrypt, -F fix, -r recursive, -T test.",
  M9 + " (Compressing with zip)", "Zip name first, then the directory.")
R("compress", "Extract data.zip into the current directory",
  "unzip data.zip",
  "Use unzip for .zip files and gunzip for .gz files.",
  M9 + " (Choosing Compression Tools)", "un + zip")
R("compress", "Using 7zip, add file1 and file2 to a new archive named archive.7z",
  "7z a archive.7z file1 file2;;7z -a archive.7z file1 file2",
  "The slide lists -a (add) -x (extract) -o (output dir) -p (password) -mx (level). In real 7z the 'a' and 'x' commands are typed WITHOUT a dash.",
  M9 + " (Compressing with 7zip; slide quirk: dashes)", "Add is the 'a' command.")

# ---------------------------------------------------------------- integrity
R("integrity", "Show the MD5 hash of file10",
  "md5sum file10",
  "md5sum generates a 128-bit MD5 hash in hex. Review exercise: compute md5 and sha1 hash of file10. MD5 is fine for integrity checks, not for security.",
  M10 + " (Review) / " + M9 + " (File Integrity, md5sum)", "md5 + sum")
R("integrity", "Show the SHA-1 hash of file10",
  "sha1sum file10",
  "The SHA commands are sha1sum, sha256sum, sha384sum, sha512sum, syntax sha#sum {filename}. SHA-1 is on the slide's 'weak' list; prefer SHA-256 or stronger.",
  M9 + " (File Integrity, SHA Commands)", "sha + number + sum")
R("integrity", "Show the SHA-256 hash of backup.tar.gz",
  "sha256sum backup.tar.gz",
  "SHA-256 is on the slide's 'strong algorithms' list (along with SHA-3 and Argon2).",
  M9 + " (File Integrity, SHA Commands)", "sha + 256 + sum")
R("integrity", "Verify the files listed in the saved hash list sums.md5",
  "md5sum -c sums.md5",
  "md5sum -c compares files against saved hashes. A change in the file means a change in the hash.",
  M9 + " (File Integrity, md5sum -c)", "-c = check")
R("integrity", "Save the MD5 hash of file10 into hash.txt",
  "md5sum file10 > hash.txt",
  "md5sum writes to stdout, so > saves it. You can later check with md5sum -c hash.txt.",
  M9 + " (File Integrity, md5sum)", "Redirect stdout.")
R("integrity", "Clone the whole drive /dev/sda onto /dev/sdb with dd",
  "dd if=/dev/sda of=/dev/sdb",
  "if= is the input file and of= is the output file. dd is dangerous: a wrong of= can overwrite a whole partition.",
  M9 + " (File Modification with dd)", "if= and of=")
R("integrity", "Make an image of /dev/sda named drive_image.iso with dd",
  "dd if=/dev/sda of=drive_image.iso",
  "Common dd use: backing up partitions and creating disk images.",
  M9 + " (File Modification with dd)", "Output file is the image.")
R("integrity", "Write the image drive_image.iso back onto /dev/sdb with dd",
  "dd if=drive_image.iso of=/dev/sdb",
  "Restoring an image: the image is the input, the device is the output. Double-check before pressing Enter.",
  M9 + " (File Modification with dd)", "Swap input and output compared with imaging.")
R("integrity", "Copy /dev/sda to /dev/sdb with dd using a 4M block size and live progress",
  "dd if=/dev/sda of=/dev/sdb bs=4M status=progress;;dd bs=4M if=/dev/sda of=/dev/sdb status=progress;;dd if=/dev/sda of=/dev/sdb status=progress bs=4M",
  "Operands: bs= block size, count= number of blocks, status= info level. status values are none, noxfer and progress.",
  M9 + " (File Modification with dd: bs, count, status)", "bs= and status=")
R("integrity", "Rescue data from the failing disk /dev/sda onto /dev/sdb with ddrescue",
  "ddrescue /dev/sda /dev/sdb",
  "ddrescue syntax: ddrescue {options} {source device} {destination device}. It makes multiple passes over the failing disk to recover as much as possible.",
  M9 + " (Data Recovery with ddrescue)", "No if= / of= here.")
R("integrity", "ddrescue /dev/sda to /dev/sdb: force overwriting the destination and retry bad sectors 3 times",
  "ddrescue -f -r3 /dev/sda /dev/sdb;;ddrescue -f -r 3 /dev/sda /dev/sdb;;ddrescue -r3 -f /dev/sda /dev/sdb;;ddrescue -r 3 -f /dev/sda /dev/sdb",
  "ddrescue options: -f force overwriting the destination, -r set the number of retries on bad sectors, -v more output detail.",
  M9 + " (Data Recovery with ddrescue)", "-f and -r with a number.")

# ---------------------------------------------------------------- packages
R("packages", "With rpm, install the local package file zip-3.0.rpm showing progress bar and verbose output",
  "rpm -ivh zip-3.0.rpm",
  "rpm -i install, -v verbose, -h progress bar (hash marks). The slide types it with an en dash (rpm -ivh) but the real option uses a plain hyphen. rpm does NOT resolve dependencies.",
  M10 + " (RPM commands)", "install + verbose + hash")
R("packages", "With rpm, erase (uninstall) the package zip",
  "rpm -e zip",
  "rpm -e erases a package but does not resolve dependencies for you.",
  M10 + " (RPM commands, Software Removal)", "-e")
R("packages", "With rpm, list ALL installed packages",
  "rpm -qa",
  "Query packages from the RPM database. -qa lists all installed packages.",
  M10 + " (Why Query?)", "query + all")
R("packages", "With rpm, display the details of the installed package zip",
  "rpm -qi zip",
  "-qi {package} shows version, source and description for a specific package.",
  M10 + " (RPM commands, Why Query?)", "query + info")
R("packages", "With rpm, save the list of all installed packages into softwarelist.txt",
  "rpm -qa > softwarelist.txt",
  "Package queries can be redirected to a file for an inventory. The slide uses exactly this.",
  M10 + " (Review - Package Queries)", "Redirect stdout.")
R("packages", "List all installed packages with rpm, showing them on screen AND saving them to softwarelist.txt",
  "rpm -qa | tee softwarelist.txt",
  "tee shows output and saves it at the same time. This is the instructor's discussion question in the slide notes.",
  M10 + " (Software Installation and Updates; notes) + Module 7 slides (tee)", "A pipe to a command that duplicates output.")
R("packages", "Use yum to install nmap, answering 'yes' automatically to dependency prompts",
  "yum install -y nmap;;yum -y install nmap",
  "The -y option automatically answers yes to installing additional dependencies. Without it, YUM asks first.",
  M10 + " (yum Subcommands)", "-y")
R("packages", "Use yum to remove the package zip",
  "yum remove zip",
  "Review exercise: 'Remove zip using yum'. yum resolves dependencies automatically (it may remove dependent packages).",
  M10 + " (yum Subcommands, Review)", "subcommand: remove")
R("packages", "Use yum to update all installed packages",
  "yum update",
  "update [package name] updates one package, or all installed packages if no argument is given.",
  M10 + " (yum Subcommands)", "No package name.")
R("packages", "Use yum to install the local file httpd-2.4.rpm (resolving dependencies from the configured repos)",
  "yum localinstall httpd-2.4.rpm",
  "localinstall installs a package from a local file but still lets YUM pull dependencies from repositories.",
  M10 + " (yum Subcommands)", "Subcommand is local + install.")
R("packages", "Use yum to find out which package provides the file /usr/bin/zip",
  "yum provides /usr/bin/zip",
  "provides {file name} reports what package provides the specified file.",
  M10 + " (yum Subcommands)", "provides")
R("packages", "Use dnf to install the package zip",
  "dnf install zip",
  "Review exercise: 'Install zip using dnf'. DNF (Dandified YUM) is the default for most current Red Hat-derived distros.",
  M10 + " (DNF Commands, Review)", "Same pattern as yum.")
R("packages", "Use dnf to show the details of the package zip",
  "dnf info zip",
  "dnf info {package}. DNF subcommands on the slide: install, remove, upgrade, info.",
  M10 + " (DNF Commands, Why Query?)", "subcommand: info")
R("packages", "Use dnf to list all installed packages",
  "dnf list installed",
  "yum list installed and dnf list installed both display installed packages.",
  M10 + " (Why Query?)", "list + installed")
R("packages", "Use dnf to upgrade all packages",
  "dnf upgrade;;dnf upgrade -y;;dnf -y upgrade",
  "DNF uses 'upgrade' where the YUM slide used 'update' (dnf update also works as an alias).",
  M10 + " (DNF Commands)", "Not 'update' here.")
R("packages", "On a Debian-based system, list installed packages with dpkg and save the list to softwarelist.txt",
  "dpkg -l > softwarelist.txt",
  "dpkg -l lists installed packages. Debian-based package queries: dpkg -l, dpkg -s {package}, apt list --installed, apt show {package}.",
  M10 + " (Review - Package Queries)", "dpkg + list")
R("packages", "On a Debian-based system, show the status of the package zip with dpkg",
  "dpkg -s zip",
  "dpkg -s {package-name} displays package information.",
  M10 + " (Review - Package Queries)", "-s")
R("packages", "On a Debian-based system, list installed packages with apt and save them to softwarelist.txt",
  "apt list --installed > softwarelist.txt",
  "The slide shows exactly this form for APT-based distros.",
  M10 + " (Review - Package Queries)", "apt list + a long option")
R("packages", "On a Debian-based system, show information about the package zip with apt",
  "apt show zip",
  "apt show {package-name} displays package information.",
  M10 + " (Review - Package Queries)", "show")
R("packages", "Open the menu to choose the system-wide default editor alternative",
  "update-alternatives --config editor",
  "update-alternatives manages the default version of a command system-wide: you can see, configure, add and remove alternatives. (--config is the standard way to choose.)",
  M10 + " (Software Installation and Updates: update-alternatives)", "update-alternatives with a config switch.")
R("packages", "Use pip to install the Python package requests",
  "pip install requests",
  "pip is the Python package installer; it uses virtual environments to isolate dependencies. cargo is Rust's manager, npm is Node.js's.",
  M10 + " (Language-Specific Package Managers)", "pip + subcommand + name")

# ---------------------------------------------------------------- repos: downloads, repositories, sandboxes
R("repos", "Download http://download.samba.org/pub/samba/samba-latest.tar.gz with wget",
  "wget http://download.samba.org/pub/samba/samba-latest.tar.gz",
  "wget downloads files from the web without a browser. This is the slide's own example. wget can download recursively; curl cannot.",
  M10 + " (wget and curl Commands)", "wget + URL")
R("repos", "With curl, download https://nmap.org/dist/nmap-7.70.tar.bz2 and save it as nmap-7.70.tar.bz2",
  "curl -o nmap-7.70.tar.bz2 https://nmap.org/dist/nmap-7.70.tar.bz2",
  "curl -o {output file} {URL}. curl supports many protocols and is better for complex requests; wget supports http, https and ftp.",
  M10 + " (Wget and curl commands)", "-o then the name.")
R("repos", "List the YUM/DNF repository configuration files",
  "ls /etc/yum.repos.d;;ls /etc/yum.repos.d/;;ls -l /etc/yum.repos.d;;ls -l /etc/yum.repos.d/",
  "Repo definitions (.repo files) are stored in /etc/yum.repos.d. This is shared by YUM and DNF.",
  M10 + " (View Repositories / Manage YUM/DNF Repository Configuration Files)", "ls the right directory.")
R("repos", "Turn the directory /repo/Packages into a YUM repository",
  "createrepo /repo/Packages;;createrepo /repo/Packages/",
  "createrepo designates a location as a repo and updates the XML metadata. The location can be a local drive, a central server or Internet-based. You then add a .repo file in /etc/yum.repos.d/.",
  M10 + " (YUM Repository Configuration)", "create + repo")
R("repos", "Display the global DNF configuration file",
  "cat /etc/dnf/dnf.conf;;less /etc/dnf/dnf.conf;;more /etc/dnf/dnf.conf",
  "Global settings live in /etc/yum.conf for YUM and /etc/dnf/dnf.conf for DNF.",
  M10 + " (Manage YUM/DNF Repository Configuration Files)", "It's under /etc/dnf.")
R("repos", "On a Debian-based system, tell APT about newly added repositories",
  "apt update",
  "Sysadmins customize which repos apt may access, then run apt update so APT learns about the new ones. apt.conf manages the tool's configuration.",
  M10 + " (Repositories: Debian-based)", "update")
R("repos", "Type the .repo line that DISABLES a repository",
  "enabled=0",
  "enabled=1 means the repo is active, 0 means it is ignored unless manually enabled.",
  M10 + " (Repositories: enabled=1)", "enabled with a number.", loose=True)
R("repos", "Type the .repo line that turns ON GPG signature verification",
  "gpgcheck=1",
  "gpgcheck=1 verifies package signatures (recommended). gpgcheck=0 installs packages without verifying authenticity, which is less secure.",
  M10 + " (gpgcheck=0 slide)", "gpgcheck with a number.", loose=True)
R("repos", "Install the snap package vlc",
  "snap install vlc",
  "Snaps are self-contained, sandboxed apps installed with a single command. Flatpak (apps come from 'remotes') and AppImage (no root needed) are the other two sandboxed formats. The slides name the tools; the command shape is standard.",
  M10 + " (Snaps / Sandboxed Software; notes: 'Practice Using snap')", "snap + subcommand")
R("repos", "Install the flatpak application org.gimp.GIMP from the remote flathub",
  "flatpak install flathub org.gimp.GIMP",
  "Flatpak pulls applications from repositories called 'remotes' and can be managed per-system or per-user. The slides name flatpak but do not show the command; this is the standard form.",
  M10 + " (Flatpak; notes: 'Install and Run an Application Using flatpak')", "flatpak install + remote + app id")
