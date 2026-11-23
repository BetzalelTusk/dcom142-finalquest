# FINAL QUEST: Rocky Rescue

A terminal game for the **DCOM 142 final exam** (Linux+ part 1, CompTIA Linux+ XK0-006) at the Community College of Baltimore County. It covers everything taught after the midterm: course Modules 6-12.

It's the sequel to the midterm trainer **[dcom142-cmdquiz](https://github.com/BetzalelTusk/dcom142-cmdquiz)**. This one adds:
- a **simulated Linux machine** you actually type into,
- a campaign with boss fights,
- a vim keystroke dojo,
- a graded multiple-choice exam simulator.

Built by a DCOM 142 student with [Claude Code](https://claude.com/claude-code). Not affiliated with or endorsed by CCBC.

## Download and play

It's one folder of Python, standard library only. You need **Git** and **Python 3.8 or newer**, nothing else. Every gray box below is one command: paste it into a terminal and press **Enter**.

### Windows

**1. Open a terminal.** Press the **Windows key**, type `terminal` and press **Enter**.

**2. Install Git and Python** (skip this if you already have both). If Windows asks to allow changes, click **Yes**.

```
winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
```
```
winget install -e --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements
```

Then **close the terminal and open a new one**, so it can find Git and Python.

**3. Download and play:**

```
git clone https://github.com/BetzalelTusk/dcom142-finalquest
```
```
cd dcom142-finalquest
```
```
python play.py
```

### Mac

Open **Terminal** (⌘ + Space, type `Terminal`) and run `git --version`. If a window offers the **command line developer tools**, click **Install**; that one install gives you both Git and Python. Then:

```
git clone https://github.com/BetzalelTusk/dcom142-finalquest
```
```
cd dcom142-finalquest
```
```
python3 play.py
```

### Android (Termux)

Install **[Termux from F-Droid](https://f-droid.org/packages/com.termux/)**, then:

```
pkg install -y git python
```
```
git clone https://github.com/BetzalelTusk/dcom142-finalquest
```
```
cd dcom142-finalquest && python play.py
```

### Next time, and updates

Open a terminal, then run `cd dcom142-finalquest` and `python play.py`. To get new questions and fixes, run `git pull` inside that folder; your progress is kept.

| Option | Effect |
|---|---|
| `python play.py --no-intro` | skip the boot animation |
| `python play.py --no-anim` | no animations at all |
| `python play.py --plain` | plain ASCII, for terminals that show boxes instead of symbols |

> **Type your answers into the game, not straight into your own terminal.** The game has its own simulated Linux machine, so it works the same on Windows. To reset your progress, delete `.finalquest_save.json` in the game folder.

## Getting around

**Not sure what to do? Pick ▶ Continue.** It always opens your next unfinished mission, puzzle or boss. When you finish something, the game offers **▶ Next** straight away.

Every screen shows where you are as a shell path (`rocky@rocky01:~/campaign/level-4$ pwd`). Every menu works the same way: ↑↓ to move, Enter to pick, a number key to jump, Esc or q to go back. **Press `m` in any menu** (or type `!menuTree` in a mission) to see the whole menu as a tree:

```
~  main menu
├── ▶ continue          jumps to your next unfinished thing
├── campaign/           8 levels: missions · boss · drill · cheat sheet
│   ├── level-1 … level-8
│   └── (level-3 also has vim-dojo/)
├── practice/           drills · lightning · weak-spots · cheat-sheets
├── final-exam/         quick 25 · full 50 · everything · practice
├── profile/            progress · tips · theme · how-to-play · menu-map
└── quit
```

Nothing is more than three levels deep, and nothing appears in two places. A **💡 did you know?** line under the title cycles through 14 features every few seconds (→ skips ahead).

**Sandbox missions** (28) run on a simulated Rocky Linux 9 / Debian 12 box. You're graded on the machine's **final state** (files, inodes, packages, mounts), not on matching one exact command. Goals tick off on their own. Real shell behaviour works: `sudo`, `sudo !!`, pipes, `> >> 2> &> <`, `; && ||`, globs, Tab completion, ↑ history, `man`, permission errors, and the classic `sudo echo x > /etc/file` trap. Storage behaves like the real thing too: **interactive `fdisk`** (`m n p d t w q`) and **`parted`**, the "device busy, run partprobe" message, a mount that **hides** what was in the directory, a mount point owned by root until you `chown` it, swap files made with `dd`, and a `reboot` that drops into **emergency mode** when `/etc/fstab` is wrong.

| Mission command | Does |
|---|---|
| `!goal` | show the goals again |
| `!tip` · `!tips on/off` | ask for a tip / turn tips on or off |
| `!cheat` | this level's commands, without leaving the shell |
| `!stats` | time, commands typed, goals, tips used, stars you're on track for |
| `!menuTree` | the menu map, with "you are here" |
| `!reset` · `!solution` | fresh machine / one possible answer (caps you at 1 star) |
| `exit` | leave the mission |

**Tips are off by default and then never appear.** Turn them on in Profile or with `!tips on`. Then `!tip` asks for one, and a tip appears by itself after 2 minutes without reaching the next goal.

**Vim Dojo** (9 puzzles): type real keystrokes (`ggO# managed<Esc>:wq`) and a mini vim runs them. **Command drills** (211) give word-by-word feedback on what you typed. **Themes:** Rocky, Matrix and Amber CRT (Profile → Theme).

## Coverage

| Level | Course module | CertMaster | Topics | Missions |
|---|---|---|---|---|
| 1 Lost in the Filesystem | Module 6 | 4.1 | FHS, paths, hard/soft links, inodes, `find`, `stat`, `tr wc sort cut awk sed sdiff` | First Boot, Link Lab, Needle in a Haystack, Column Surgeon |
| 2 File Management Frenzy | Module 7 | 4.2 | `ls` options, `cp -R`, `mv`, `rm -fiR`, `rmdir`, `grep -ic`, redirection, pipes, `&& \|\|`, `tee`, `xargs` | Log Hunter, Spring Cleaning, Redirect Rodeo, Pipeline Plumber |
| 3 Editor Wars | Module 8 | 5.1 | vim modes and keys, nano shortcuts, gedit | Vim Dojo (9 puzzles) |
| 4 Backup Bunker | Module 9 | 5.2 | `tar` (-cxtvrfzj), `cpio`, gzip/bzip2/xz/zip/7z, hashing, `md5sum -c`, `sha*sum`, HMAC, `dd`, `ddrescue` | Backup Bunker, Restore Point, Tamper Alert, Compression Contest, Disk Doctor |
| 5 Package Depot | Module 10 | 6.1 | rpm vs yum/dnf, dpkg vs apt, dependencies, queries, pip/npm/cargo | Dependency Hell, Inventory Day, Debian Duty |
| 6 Repo Rebellion | Module 10 | 6.2 | `wget`/`curl`, repo types, `.repo` files, `createrepo`, `gpgcheck`, `apt update`, Snap/Flatpak/AppImage | Download Day, Repo Rebellion |
| 7 Storage Vault | Module 11 | 7.1-7.2 | HDD/SSD, file/block/object storage, MBR vs GPT, primary/extended/logical, `/dev/sdXN`, `hwinfo lsblk lsscsi blkid`, `fdisk`, `parted`, `partprobe`, `growpart`, ext4/XFS/Btrfs/tmpfs, `xfs_*` and ext tools, `fsck`, swap, LVM | Disk Detective, fdisk Drill, New Disk Day, Filesystem Fixer, Swap Shop, LVM Builder |
| 8 Mount Mountain | Module 12 | 7.3-7.4 | mounting, `/etc/fstab`, UUIDs, `mount -a`, reboot and emergency mode, `df`/`du`, RAID (`mdadm`, `/proc/mdstat`), disk quotas | Mount Point Mystery, Boot Breaker, Quota Cop, RAID Rescue |

Sources are the instructor's Fall 2026 slide decks for Modules 6-11 and their Learning Objectives pages. Each question shows the slide it comes from. The repo contains no course files.

**Level 8 is partly a PREVIEW.** The Module 12 deck (7.3-7.4) wasn't posted when this was built. Mounting, `/etc/fstab`, RAID and quota points that are on the Module 11 deck cite it; everything else follows standard CompTIA Linux+ XK0-006 content and is marked `PREVIEW` (17 items). The exam simulator can leave those out.

## Tests

```
python tests/run_all.py
```

- Every reference solution completes its mission, and no mission starts out already complete.
- Every vim puzzle accepts the right keystrokes and rejects the common wrong ones.
- Every accepted answer passes the answer checker.
- The real UI is driven end to end with scripted keystrokes: all 28 missions (plus interactive `fdisk` and `parted` sessions typed key by key), the boss win and loss, exam grading, and every menu.

## Academic integrity

Self-study only. The DCOM 142 syllabus does not allow AI tools on graded work, so don't use this during a quiz, exam or Live Lab.

## License

[MIT](LICENSE)
