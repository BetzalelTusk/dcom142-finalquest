"""Builds the starting machine for every mission: a small Rocky Linux 9 (or Debian 12) box."""
from .vfs import FS
from . import pkg, storage

PASSWD_USERS = ["root:x:0:0:root:/root:/bin/bash", "bin:x:1:1:bin:/bin:/sbin/nologin", "daemon:x:2:2:daemon:/sbin:/sbin/nologin",
                "adm:x:3:4:adm:/var/adm:/sbin/nologin", "sync:x:5:0:sync:/sbin:/bin/sync", "nobody:x:65534:65534:Kernel Overflow User:/:/sbin/nologin",
                "sshd:x:74:74:Privilege-separated SSH:/usr/share/empty.sshd:/sbin/nologin", "apache:x:48:48:Apache:/usr/share/httpd:/sbin/nologin",
                "rocky:x:1000:1000:Rocky Student:/home/rocky:/bin/bash", "alice:x:1001:1001::/home/alice:/bin/bash",
                "bob:x:1002:1002::/home/bob:/bin/bash", "carol:x:1003:1003::/home/carol:/bin/zsh"]

SECURE_LOG = """Nov 15 08:01:12 rocky01 sshd[1201]: Accepted password for rocky from 192.168.1.50 port 50122 ssh2
Nov 15 08:14:40 rocky01 sshd[1255]: Failed password for root from 192.168.1.103 port 40211 ssh2
Nov 15 08:14:44 rocky01 sshd[1255]: Failed password for root from 192.168.1.103 port 40212 ssh2
Nov 15 08:14:49 rocky01 sshd[1255]: Failed password for invalid user admin from 192.168.1.103 port 40213 ssh2
Nov 15 09:02:03 rocky01 sshd[1301]: failed password for bob from 10.0.0.7 port 51515 ssh2
Nov 15 09:30:00 rocky01 sudo[1340]:    rocky : TTY=pts/0 ; PWD=/home/rocky ; USER=root ; COMMAND=/bin/dnf update
Nov 15 10:11:31 rocky01 sshd[1402]: FAILED PASSWORD for alice from 172.16.4.20 port 60001 ssh2
Nov 15 10:45:09 rocky01 sshd[1450]: Connection closed by 192.168.1.103 port 40299 [preauth]
Nov 15 11:20:18 rocky01 sshd[1488]: Failed password for root from 192.168.1.103 port 40300 ssh2
"""

MESSAGES_LOG = """Nov 15 08:00:01 rocky01 systemd[1]: Started Daily Cleanup of Temporary Directories.
Nov 15 08:05:13 rocky01 kernel: sd 2:0:0:0: [sdc] tag#3 FAILED Result: hostbyte=DID_OK driverbyte=DRIVER_OK
Nov 15 08:05:13 rocky01 kernel: blk_update_request: I/O error, dev sdc, sector 2048
Nov 15 08:30:22 rocky01 NetworkManager[812]: <info>  device (ens160): state change: activated
Nov 15 09:12:45 rocky01 systemd[1]: httpd.service: Failed with result 'exit-code'. error
"""


def make_world(distro="rocky"):
    user = "rocky" if distro == "rocky" else "student"
    host = "rocky01" if distro == "rocky" else "deb01"
    fs = FS(user=user, group=user, host=host)
    for d in ["/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/media", "/mnt", "/opt", "/proc", "/sbin", "/srv", "/sys",
              "/usr/bin", "/usr/sbin", "/usr/lib64", "/usr/local/bin", "/usr/share", "/var/log", "/var/lib", "/etc/ssl", "/etc/ssh"]:
        fs.put_dir(d)
    fs.put_dir("/root", mode=0o550)
    fs.put_dir("/tmp", mode=0o777)
    fs.put_dir("/home/" + user, owner=user, mode=0o700)
    users = [u.replace("rocky", user) if u.startswith("rocky") else u for u in PASSWD_USERS]
    fs.put("/etc/passwd", "\n".join(users) + "\n")
    fs.put("/etc/group", "root:x:0:\nwheel:x:10:%s\n%s:x:1000:\n" % (user, user))
    fs.put("/etc/hosts", "127.0.0.1   localhost localhost.localdomain\n::1         localhost localhost.localdomain\n192.168.1.100 linux02\n")
    fs.put("/etc/hostname", host + "\n")
    fs.put("/etc/fstab", "/dev/mapper/rl-root     /                       xfs     defaults        0 0\nUUID=1c2a-77e1          /boot                   xfs     defaults        0 0\n/dev/mapper/rl-swap     none                    swap    defaults        0 0\n")
    fs.put("/etc/ssh/moduli", "# Time Type Tests Tries Size Generator Modulus\n" + "20230101 2 6 100 2047 5 C0FFEE\n" * 4)
    fs.put("/etc/ssl/openssl.cnf", "# OpenSSL configuration\n")
    fs.put("/var/log/secure", SECURE_LOG, mode=0o600)
    fs.put("/var/log/messages", MESSAGES_LOG, mode=0o600)
    for b in ["ls", "cat", "cp", "mv", "rm", "bash", "grep", "tar", "gzip"]:
        fs.put("/usr/bin/" + b, "#!/bin/sh\n", mode=0o755)
    st = pkg.state(fs)
    st["net"] = pkg.default_net()
    if distro == "rocky":
        st["rpmdb"] = {n: "%s-1.%s" % ("5.1" if n == "bash" else "1.0", pkg.BASE_VER) for n in pkg.BASE_RPMS}
        for n in ("zip", "unzip", "wget"):
            st["rpmdb"][n] = pkg.CATALOG[n][0]
            pkg.install_files(fs, n)
        fs.put("/etc/yum.repos.d/rocky.repo", "[baseos]\nname=Rocky Linux 9 - BaseOS\nbaseurl=http://dl.rockylinux.org/pub/rocky/9/BaseOS/x86_64/os/\nenabled=1\ngpgcheck=1\n\n[appstream]\nname=Rocky Linux 9 - AppStream\nbaseurl=http://dl.rockylinux.org/pub/rocky/9/AppStream/x86_64/os/\nenabled=1\ngpgcheck=1\n")
        fs.put("/etc/dnf/dnf.conf", "[main]\ngpgcheck=1\ninstallonly_limit=3\nclean_requirements_on_remove=True\nbest=True\n")
        fs.put("/etc/yum.conf", "[main]\ngpgcheck=1\n")
    else:
        st["dpkg"] = {n: "1.0-1" for n in ("bash", "coreutils", "tar", "gzip", "dpkg", "apt", "curl", "wget")}
        st["apt_updated"] = False
        fs.put("/etc/apt/sources.list", "deb http://deb.debian.org/debian bookworm main\ndeb http://deb.debian.org/debian-security bookworm-security main\n")
        fs.put("/etc/apt/apt.conf", "// APT configuration\n")
    storage.add_disk(fs, "sda", 20480)
    fs.sys["mounts"] = {}
    return fs


def mkfile(fs, path, data="", mode=0o644):
    """Create a file owned by the mission user (parents created as that user too)."""
    import posixpath
    parent = posixpath.dirname(fs.abspath(path))
    if not fs.exists(parent):
        fs.mkdir(parent, fs.user, parents=True)
    n = fs.write(path, data, fs.user, mode=mode)
    return n
