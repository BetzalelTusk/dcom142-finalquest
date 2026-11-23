"""Shared registries for the question banks. Content files import R and M from here."""
RECALL = []   # typed-command questions
MC = []       # multiple-choice concept questions

TOPICS = {
    "paths":     ("Module 6",  "Paths, FHS, links, find, stat"),
    "textproc":  ("Module 6",  "tr, wc, sort, cut, head, sdiff, awk, sed"),
    "filemgmt":  ("Module 7",  "ls options, cp, mv, rm, cat, head/tail, less/more"),
    "redir":     ("Module 7",  "grep, redirection, pipes, chaining, tee, xargs"),
    "editors":   ("Module 8",  "vim, nano, gedit"),
    "archive":   ("Module 9",  "tar and cpio"),
    "compress":  ("Module 9",  "gzip, bzip2, xz, zip, 7z"),
    "integrity": ("Module 9",  "hashes, HMAC, dd, ddrescue"),
    "packages":  ("Module 10", "rpm, yum, dnf, dpkg, apt, dependencies"),
    "repos":     ("Module 10", "wget/curl, repositories, sandboxed software"),
    "storage":   ("Module 11", "disks, fdisk/parted, partitions, filesystems, swap, LVM"),
    "mounts":    ("Module 12", "mount, fstab, reboot, df/du, RAID, quotas"),
}

PV = "PREVIEW (slides not posted yet): "


def is_preview(q):
    return q["src"].startswith("PREVIEW")


def R(topic, prompt, answers, explain, src, hint="", loose=False):
    """Typed-answer question. `answers` is one string, alternatives separated by ';;'.
    sudo is optional, quotes are ignored, letters in a short-flag group may come in any order."""
    assert topic in TOPICS, topic
    RECALL.append({"topic": topic, "prompt": prompt, "answers": [a.strip() for a in answers.split(";;") if a.strip()],
                   "explain": explain, "src": src, "hint": hint, "loose": loose})


def M(topic, q, correct, wrong, explain, src):
    """Multiple choice. `wrong` is a list of 1-3 distractors (1 = true/false style)."""
    assert topic in TOPICS, topic
    assert 1 <= len(wrong) <= 3, q
    MC.append({"topic": topic, "q": q, "correct": correct, "wrong": list(wrong), "explain": explain, "src": src})
