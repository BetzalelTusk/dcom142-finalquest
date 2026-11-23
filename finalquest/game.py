"""FINAL QUEST: Rocky Rescue. A terminal game for the DCOM 142 final (Modules 6-12)."""
import json
import os
import random
import sys
import time

from . import ui
from .ui import c, out, box
from . import content_recall_a, content_recall_b, content_mc_a, content_mc_b, content_storage  # noqa: F401  (register questions)
from .content_base import RECALL, MC, TOPICS, is_preview
from . import grading, missions as M, vimdojo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE = os.path.join(ROOT, ".finalquest_save.json")

LEVELS = [
    {"n": 1, "title": "Lost in the Filesystem", "mod": "Module 6 · Lesson 4.1", "topics": ["paths", "textproc"],
     "boss": "The Inode Imp", "story": "rocky01 just came back from a crash and nobody knows where anything lives. Map the filesystem, untangle the links, and carve the reports out of /etc/passwd."},
    {"n": 2, "title": "File Management Frenzy", "mod": "Module 7 · Lesson 4.2", "topics": ["filemgmt", "redir"],
     "boss": "The Redirect Hydra", "story": "Someone is brute-forcing SSH and the home directories are overflowing. Hunt through the logs, clean up, and plumb the pipes."},
    {"n": 3, "title": "Editor Wars", "mod": "Module 8 · Lesson 5.1", "topics": ["editors"],
     "boss": "The Modal Minotaur", "story": "No GUI on this server. It's vim or nano, keyboard only. Survive the Dojo and the Minotaur that has trapped a thousand admins inside vim."},
    {"n": 4, "title": "Backup Bunker", "mod": "Module 9 · Lesson 5.2", "topics": ["archive", "compress", "integrity"],
     "boss": "The Bit-Rot Behemoth", "story": "A disk is dying and the backups have never been tested. Archive, compress, hash, image and rescue before the Behemoth eats the data."},
    {"n": 5, "title": "Package Depot", "mod": "Module 10 · Lesson 6.1", "topics": ["packages"],
     "boss": "The Dependency Dragon", "story": "The web server needs installing on two different distros. rpm or dnf? dpkg or apt? Pick wrong and the Dependency Dragon wakes up."},
    {"n": 6, "title": "Repo Rebellion", "mod": "Module 10 · Lesson 6.2", "topics": ["repos"],
     "boss": "The Rogue Repo Kraken", "story": "Software has to come from somewhere: the web, a vendor repo, your own local repo, or a sandbox. One misconfigured .repo file and the Kraken drags everything under."},
    {"n": 7, "title": "Storage Vault", "mod": "Module 11 · Lessons 7.1-7.2", "topics": ["storage"],
     "boss": "The Volume Golem", "story": "New disks keep arriving and nobody knows what's on them. Detect them, partition them with fdisk and parted, format, fix and label filesystems, add swap, and pool disks with LVM."},
    {"n": 8, "title": "Mount Mountain", "mod": "Module 12 · Lessons 7.3-7.4 (PREVIEW)", "topics": ["mounts"],
     "boss": "The Fstab Phantom", "story": "PREVIEW: the Module 12 deck isn't posted yet. Mounting, fstab, RAID and quotas that ARE on the Module 11 slides are used as-is; the rest follows standard Linux+ XK0-006 material. Hidden files, broken boots, failing mirrors and greedy users."},
]

RANKS = [(0, "Intern"), (150, "Junior Admin"), (400, "SysAdmin"), (800, "Senior SysAdmin"), (1400, "Root Wizard"), (2200, "Kernel Legend")]

BADGES = {
    "first-mission": ("First Shell", "Finish any mission"),
    "three-star": ("Flawless", "Earn 3 stars on a mission"),
    "boss": ("Boss Slayer", "Defeat any boss"),
    "all-bosses": ("Final Form", "Defeat every boss"),
    "vim-escape": ("I Escaped Vim", "Clear the Escape Hatch puzzle"),
    "dojo": ("Dojo Master", "Clear every Vim Dojo puzzle"),
    "exam-80": ("Exam Ready", "Score 80%+ on a 25+ question exam simulation"),
    "streak-10": ("On Fire", "10 correct answers in a row"),
    "lightning-10": ("Lightning Hands", "10+ correct in one Lightning round"),
    "all-missions": ("Root of All", "Finish every mission"),
}

for i, q in enumerate(RECALL):
    q["id"] = "r:" + q["prompt"][:80]
    q["kind"] = "recall"
for i, q in enumerate(MC):
    q["id"] = "m:" + q["q"][:80]
    q["kind"] = "mc"


# ============================================================================= save data
class Save:
    def __init__(self):
        self.d = {"xp": 0, "q": {}, "missions": {}, "vim": {}, "bosses": {}, "exams": [], "badges": [], "best_streak": 0}
        try:
            with open(SAVE, encoding="utf-8") as f:
                self.d.update(json.load(f))
        except (OSError, ValueError):
            pass
        self.streak = 0

    def write(self):
        try:
            with open(SAVE, "w", encoding="utf-8") as f:
                json.dump(self.d, f, indent=1)
        except OSError:
            pass

    def qstat(self, qid):
        return self.d["q"].setdefault(qid, {"r": 0, "w": 0, "s": 0})

    def record(self, q, correct):
        st = self.qstat(q["id"])
        if correct:
            st["r"] += 1
            st["s"] += 1
            self.streak += 1
            self.d["best_streak"] = max(self.d["best_streak"], self.streak)
            if self.streak >= 10:
                self.badge("streak-10")
        else:
            st["w"] += 1
            st["s"] = 0
            self.streak = 0
        self.write()

    def mastered(self, q):
        return self.d["q"].get(q["id"], {}).get("s", 0) >= 2

    def weak(self, q):
        st = self.d["q"].get(q["id"])
        return bool(st) and st["w"] > 0 and st["s"] < 2

    def add_xp(self, n):
        before = rank(self.d["xp"])
        self.d["xp"] += n
        self.write()
        after = rank(self.d["xp"])
        return after if after != before else None

    def badge(self, key):
        if key not in self.d["badges"]:
            self.d["badges"].append(key)
            self.write()
            name, desc = BADGES[key]
            out(c("  🏅 BADGE UNLOCKED: %s" % name if not ui.PLAIN else "  * BADGE UNLOCKED: %s" % name, "byellow", "bold") + c("  (%s)" % desc, "gray"))


def rank(xp):
    r = RANKS[0][1]
    for need, name in RANKS:
        if xp >= need:
            r = name
    return r


def next_rank(xp):
    for need, name in RANKS:
        if xp < need:
            return need, name
    return None, None


SAVE_DATA = None


def sv():
    global SAVE_DATA
    if SAVE_DATA is None:
        SAVE_DATA = Save()
    return SAVE_DATA


# ============================================================================= visuals
LOGO = [
    "███████╗██╗███╗   ██╗ █████╗ ██╗          ██████╗ ██╗   ██╗███████╗███████╗████████╗",
    "██╔════╝██║████╗  ██║██╔══██╗██║         ██╔═══██╗██║   ██║██╔════╝██╔════╝╚══██╔══╝",
    "█████╗  ██║██╔██╗ ██║███████║██║         ██║   ██║██║   ██║█████╗  ███████╗   ██║   ",
    "██╔══╝  ██║██║╚██╗██║██╔══██║██║         ██║▄▄ ██║██║   ██║██╔══╝  ╚════██║   ██║   ",
    "██║     ██║██║ ╚████║██║  ██║███████╗    ╚██████╔╝╚██████╔╝███████╗███████║   ██║   ",
    "╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝     ╚══▀▀═╝  ╚═════╝ ╚══════╝╚══════╝   ╚═╝   ",
]
SMALL_LOGO = ["  ___ ___ _  _   _   _       ___  _   _ ___ ___ _____ ",
              " | __|_ _| \\| | /_\\ | |     / _ \\| | | | __/ __|_   _|",
              " | _| | || .` |/ _ \\| |__  | (_) | |_| | _|\\__ \\ | |  ",
              " |_| |___|_|\\_/_/ \\_\\____|  \\__\\_\\\\___/|___|___/ |_|  "]
GRAD = [51, 45, 39, 33, 27, 63, 99, 135]

BOOT = ["Starting rocky01 (Rocky Linux 9.4)...", "Mounting /home", "Loading %d command drills" % len(RECALL), "Loading %d exam questions" % len(MC),
        "Spawning %d sandbox missions" % len(M.MISSIONS), "Waking %d bosses" % len(LEVELS), "Reached target Final Exam"]


def header(where=None):
    """Status bar, plus a 'you are here' path styled like a shell working directory."""
    s = sv()
    xp = s.d["xp"]
    need, nm = next_rank(xp)
    prog = ""
    if need:
        prev = max(n for n, _ in RANKS if n <= xp)
        prog = " " + ui.bar((xp - prev) / float(need - prev), 12, color="bcyan") + c(" next: %s" % nm, "gray")
    out(c(" FINAL QUEST ", "bold", "inv", "bcyan") + "  " + c(rank(xp), "byellow", "bold") + c("  ·  %d XP" % xp, "gray") + prog)
    if where is not None:
        LAST_WHERE[0] = where
        out(c("  rocky@rocky01:", "bgreen", "bold") + c("~" + ("/" + where if where else ""), "bblue", "bold") + c("$ ", "byellow", "bold") + c("pwd", "gray"))


def title_screen():
    ui.clear()
    wide = ui.term_width() >= 88 and not ui.PLAIN
    art = LOGO if wide else SMALL_LOGO
    for i, line in enumerate(art):
        out(c(line, fg=ui.grad(i)) if ui.COLOR else line)
        ui.pause(0.04)
    out(c("  ROCKY RESCUE  ·  DCOM 142 Linux final review  ·  Modules 6-12", "bold", "bwhite" if False else "white"))
    out("")
    if ui.ANIM and "--no-intro" not in ui.ARGS:
        for b in BOOT:
            ui.write("  " + c("[", "gray") + c("  OK  ", "bgreen") + c("]", "gray") + " " + b + "\n")
            ui.pause(0.07)
        out("")


# ============================================================================= question runners
def show_explain(q, typed=None):
    lines = []
    if q["kind"] == "recall":
        ans = q["answers"]
        lines.append(c("Answer: ", "bold") + c(ans[0], "bgreen", "bold"))
        if len(ans) > 1:
            lines.append(c("Also accepted: ", "gray") + c("  |  ".join(ans[1:4]), "green"))
    else:
        lines.append(c("Answer: ", "bold") + c(q["correct"], "bgreen", "bold"))
    lines.append("")
    lines.append(q["explain"])
    lines.append(c("Source: " + q["src"], "gray", "ital"))
    out(box(lines, "why", color="blue"))


def show_diff(typed, expected):
    parts = []
    for w, st in grading.diff_words(typed, expected):
        if st == "ok":
            parts.append(c(w, "bgreen"))
        elif st == "bad":
            parts.append(c(w, "bred", "ul"))
        else:
            parts.append(c("[" + w + "]", "byellow"))
    out("  " + c("you typed  ", "gray") + " ".join(parts))
    out("  " + c("legend     ", "gray") + c("match", "bgreen") + "  " + c("wrong", "bred", "ul") + "  " + c("[missing]", "byellow"))


def ask_recall(q, num=None, total=None, retries=1, show_feedback=True, hearts=None):
    """-> 'right', 'retry-right', 'wrong', 'quit'"""
    tag = TOPICS[q["topic"]][0]
    head = c("%s" % (("Q%d/%d" % (num, total)) if num else "Q"), "bold", "bcyan") + c("  ·  type the command  ·  " + tag, "gray")
    if hearts is not None:
        head += "   " + hearts
    out(head)
    out(box([c(q["prompt"], "bold")], color="cyan"))
    out(c("  ?=hint   Enter on empty line after a miss=show answer   skip   q=quit", "gray"))
    tries = 0
    hinted = False
    while True:
        try:
            ans = ui.read_line(c("  ❯ " if not ui.PLAIN else "  > ", "bgreen", "bold"))
        except EOFError:
            return "quit"
        if ans is None or ans.strip() == "q":
            return "quit"
        a = ans.strip()
        if a == "?":
            hinted = True
            h = q.get("hint") or ""
            first = q["answers"][0].split()[0] if not q["loose"] else ""
            if q["answers"][0].split()[0] == "sudo" and len(q["answers"][0].split()) > 1:
                first = q["answers"][0].split()[1]
            msg = h if h else ("It starts with '%s'." % first if first and len(q["answers"][0]) > 3 else "Think about the slide this comes from: " + q["src"])
            out(c("  hint: ", "byellow") + msg)
            continue
        if a == "skip" or (a == "" and tries > 0):
            sv().record(q, False)
            out(c("  ✗ skipped" if not ui.PLAIN else "  x skipped", "bred"))
            show_explain(q)
            return "wrong"
        if a == "":
            continue
        ok, best = grading.check(a, q["answers"], q["loose"])
        if ok:
            sv().record(q, True)
            out(c("  ✔ correct" if not ui.PLAIN else "  ok correct", "bgreen", "bold") + (c("  (streak %d)" % sv().streak, "byellow") if sv().streak >= 3 else ""))
            if show_feedback and (tries > 0 or hinted):
                out(c("  " + q["explain"], "gray"))
            return "right" if tries == 0 and not hinted else "retry-right"
        tries += 1
        if tries > retries:
            sv().record(q, False)
            out(c("  ✗ not quite" if not ui.PLAIN else "  x not quite", "bred", "bold"))
            if not q["loose"]:
                show_diff(a, best)
            show_explain(q)
            return "wrong"
        out(c("  ✗ not quite. One more try" if not ui.PLAIN else "  x not quite. One more try", "byellow") + c(" (Enter = show answer)", "gray"))
        if not q["loose"]:
            show_diff(a, best)


def mc_options(q, rng=random):
    opts = [q["correct"]] + list(q["wrong"])
    if set(o.lower() for o in opts) <= {"true", "false"}:
        return sorted(opts, key=lambda o: o.lower() != "true")
    rng.shuffle(opts)
    return opts


def ask_mc(q, num=None, total=None, feedback=True, hearts=None):
    """-> ('right'|'wrong'|'quit', chosen)"""
    tag = TOPICS[q["topic"]][0]
    head = c(("Q%d/%d" % (num, total)) if num else "Q", "bold", "bmag") + c("  ·  multiple choice  ·  " + tag, "gray")
    if hearts is not None:
        head += "   " + hearts
    out(head)
    out(box([c(q["q"], "bold")], color="magenta"))
    opts = mc_options(q)
    letters = "ABCD"
    choice = ui.menu([("%s) %s" % (letters[i], o), i) for i, o in enumerate(opts)], footer="↑↓ + Enter, or 1-%d · q = quit" % len(opts) if not ui.PLAIN else "arrows + Enter, or 1-%d, q = quit" % len(opts))
    if choice is None:
        return "quit", None
    picked = opts[choice]
    right = picked == q["correct"]
    sv().record(q, right)
    if feedback:
        if right:
            out(c("  ✔ correct" if not ui.PLAIN else "  ok correct", "bgreen", "bold") + (c("  (streak %d)" % sv().streak, "byellow") if sv().streak >= 3 else "") + c("  " + q["explain"], "gray"))
        else:
            out(c("  ✗ wrong" if not ui.PLAIN else "  x wrong", "bred", "bold") + c("  you picked: " + picked, "gray"))
            show_explain(q)
    return ("right" if right else "wrong"), picked


def pick(pool, n, rng=random):
    """Weighted sample: weak and unseen questions come up more often; mastered ones less."""
    s = sv()

    def w(q):
        st = s.d["q"].get(q["id"])
        if not st:
            return 3.0
        return 1.0 + 3.0 * st["w"] / (st["r"] + st["w"]) - (0.6 if st["s"] >= 2 else 0.0)
    pool = list(pool)
    chosen = []
    while pool and len(chosen) < n:
        tot = sum(max(0.2, w(q)) for q in pool)
        r = rng.random() * tot
        acc = 0
        for i, q in enumerate(pool):
            acc += max(0.2, w(q))
            if acc >= r:
                chosen.append(pool.pop(i))
                break
    return chosen


def practice_loop(make, title, where):
    """Run rounds until the player stops. make() -> list of questions."""
    while True:
        qs = make()
        if not qs:
            return
        run_set(qs, title, where=where)
        ch = ui.menu([("↻ Another round", "again"), ("← Back", "back")], back=True)
        if ch != "again":
            return


def run_set(questions, title, xp_right=10, xp_retry=5, where=None):
    ui.clear()
    header(where)
    out(c("\n  %s  ·  %d questions  ·  q to stop early\n" % (title, len(questions)), "bold"))
    right = 0
    for i, q in enumerate(questions, 1):
        if q["kind"] == "recall":
            r = ask_recall(q, i, len(questions))
        else:
            r, _ = ask_mc(q, i, len(questions))
        if r == "quit":
            break
        if r == "right":
            right += 1
            lvl = sv().add_xp(xp_right + min(10, sv().streak))
        elif r == "retry-right":
            right += 1
            lvl = sv().add_xp(xp_retry)
        else:
            lvl = None
        if lvl:
            rank_up(lvl)
        out("")
    out(box(["%s: %d / %d correct" % (title, right, len(questions)), "XP now %d  ·  rank %s" % (sv().d["xp"], rank(sv().d["xp"]))], "round over", color="green"))
    return right


def rank_up(name):
    out("")
    out(c("  ★ ★ ★  PROMOTED TO %s  ★ ★ ★" % name.upper() if not ui.PLAIN else "  *** PROMOTED TO %s ***" % name.upper(), "byellow", "bold"))
    ui.pause(0.4)


# ============================================================================= missions
import re as _re

# words worth spotting at a glance in briefings and objectives: paths, file names, commands, quoted text
_HL = _re.compile(
    r"(~?/[\w.\-/]+|~(?=\s|$|\))"
    r"|\b[\w\-]+\.(?:txt|tar|gz|bz2|xz|csv|rpm|repo|img|md5|sha256|log|conf|zip|7z|cpio|html|key)\b"
    r"|\b(?:sudo|tar|gzip|bzip2|xz|grep|find|ln|dd|ddrescue|rpm|yum|dnf|apt|dpkg|wget|curl|createrepo|tee|xargs|md5sum|"
    r"sha256sum|sha1sum|wc|tr|cut|sort|mkfs|mount|lvextend|lvcreate|vgcreate|pvcreate|fstab|httpd|zip|nmap|tree|localtool|XFS|ext4|LVM)\b"
    r"|'[^']+'|\"[^\"]+\"|\b\d+G\b)")


def accent():
    return ui.grad(1)


def label_col():
    return ui.grad(7)


def cmd_col():
    return ui.grad(6)


def hl(text, base=None):
    """Highlight the important words in a sentence (bold, accent colour). base = colour for the rest."""
    parts = []
    last = 0
    for mt in _HL.finditer(text):
        if mt.start() > last:
            seg = text[last:mt.start()]
            parts.append(c(seg, *base) if base else seg)
        parts.append(c(mt.group(0), "bold", fg=accent()))
        last = mt.end()
    seg = text[last:]
    parts.append(c(seg, *base) if base else seg)
    return "".join(parts)


def chip(word):
    return c(word, "bold", fg=cmd_col())


def shell_help_lines():
    sep = c("  ·  ", "gray")
    return [c("Type Linux commands at the prompt", "white") + sep + c("Tab", "bold") + c(" completes", "gray") + sep + c("↑", "bold") + c(" recalls", "gray"),
            sep.join([chip("!goal"), chip("!tip"), chip("!cheat"), chip("!stats"), chip("!menuTree"), chip("!reset"), chip("!solution"), chip("exit")])]


SHELL_HELP = shell_help_lines()


def mission_screen(m, fs, sh, status, where=None):
    goals = [(i, g) for i, g in enumerate(m["goals"]) if not g.startswith("(")]
    notes = [g for g in m["goals"] if g.startswith("(")]
    done = sum(1 for i, _ in goals if status[i])
    width = min(ui.term_width(), 92)
    inner = width - 4
    lab = lambda s: c(s, "bold", fg=label_col())
    lines = ["", lab("BRIEFING"), hl(m["brief"]), "",
             lab("OBJECTIVES") + "   " + (c("%d/%d done" % (done, len(goals)), "bgreen", "bold") if done == len(goals)
                                         else c("%d/%d done" % (done, len(goals)), "gray"))]
    for n, (i, g) in enumerate(goals, 1):
        if status[i]:
            mark = c("✔" if not ui.PLAIN else "[x]", "bgreen", "bold")
            text = c(g, "green")
        else:
            mark = c("○" if not ui.PLAIN else "[ ]", fg=accent())
            text = hl(g)
        lines.append(" %s %s  %s" % (c("%d" % n, "bold", fg=label_col()), mark, text))
    for g in notes:
        lines.append("      " + c(g.strip("()"), "gray", "ital"))
    lines.append("")
    lines.append(c(("─" if not ui.PLAIN else "-") * inner, fg=ui.grad(5)))
    lines.extend(shell_help_lines())
    dist = "Rocky Linux 9" if m["distro"] == "rocky" else "Debian 12"
    lvl_ms = [x for x in M.MISSIONS if x["level"] == m["level"]]
    num = "%d.%d" % (m["level"], lvl_ms.index(m) + 1)
    title = c("MISSION " + num, "bold", fg=label_col()) + "  " + c(m["title"].upper(), "bold", "white")
    right = c(dist, "gray")
    out(ui.gbox(lines, title, right, width=width, hang=lambda ln: 6 if _re.match(r"^ \S+ \S+  ", ANSI_RE_STRIP(ln)) else None))


def ANSI_RE_STRIP(s):
    return ui.ANSI_RE.sub("", s)


def stars_for(cmds, par, hints, peeked):
    if peeked:
        return 1
    s = 1
    if hints <= 1:
        s += 1
    if cmds <= par + 2 and hints == 0:
        s += 1
    return min(3, s)


def real_goals(m):
    return [i for i, g in enumerate(m["goals"]) if not g.startswith("(")]


TIP_DELAY = 120   # seconds without reaching the next goal before an automatic tip (only when tips are ON)


def tips_on():
    return bool(sv().d.get("tips", False))


def tips_label():
    return "Tips: ON" if tips_on() else "Tips: OFF"


def play_mission(m):
    """-> 'won' or 'quit'"""
    from . import shell as shell_mod
    fs, sh = M.build(m)
    sh._ask = lambda p: ui.read_line(p) or ""
    status = M.check(m, fs, sh)
    ui.clear()
    header("campaign/level-%d/%s" % (m["level"], m["id"]))
    mission_screen(m, fs, sh, status)
    st = {"hints": 0, "hint_i": 0, "last": time.time(), "peeked": False, "typed": 0, "start": time.time()}
    goals_idx = real_goals(m)
    home = fs.env["HOME"]
    mission_text = " ".join(m["goals"] + m["solution"] + [m["brief"]])
    queue = []        # situational tips noticed so far, newest last. Never printed unless asked for / timed out with tips ON
    noticed = set()

    def top_names(f):
        names = set()
        for d in ("/", "/home"):
            try:
                names |= {d.rstrip("/") + "/" + n for n in f.listdir(d)}
            except Exception:
                pass
        return names

    baseline = top_names(fs)

    def notice(key, msg):
        if key not in noticed:
            noticed.add(key)
            queue.append(msg)

    def next_tip():
        """Most relevant tip: the latest thing noticed about what you did, else the mission's next hint."""
        if queue:
            return queue.pop()
        hs = m["hints"]
        if st["hint_i"] < len(hs):
            st["hint_i"] += 1
            return "(%d/%d) %s" % (st["hint_i"], len(hs), hs[st["hint_i"] - 1])
        return None

    def show_tip(msg, auto=False):
        st["hints"] += 1
        st["last"] = time.time()
        title = "tip (you've been on this goal 2+ min · !tips off to stop these)" if auto else "tip"
        return box([msg], title, color="yellow")

    def idle_check():
        if tips_on() and time.time() - st["last"] >= TIP_DELAY:
            msg = next_tip()
            st["last"] = time.time()
            if msg:
                return show_tip(msg, auto=True)
        return None

    warned = set()

    def show_warning(msg):
        """Real mistakes are always shown (tips on or off), once each."""
        if msg in warned:
            return
        warned.add(msg)
        out(box([msg], "heads up" if not ui.PLAIN else "warning", color="yellow"))

    sh.emit = ui.write
    del shell_mod.PENDING_NOTES[:]
    del shell_mod.WARNINGS[:]
    while True:
        try:
            line = ui.read_line(sh.colored_prompt(), history=sh.history, complete=sh.complete, tick=(1.0, idle_check))
        except EOFError:
            return "quit"
        if line is None:
            out(c("  (Esc pressed) type exit to leave the mission, or !goal to see what's left", "gray"))
            continue
        cmdline = line.strip()
        if cmdline in ("exit", "logout", "!quit", "!q", "!exit", "!back"):
            done = sum(1 for i in goals_idx if status[i])
            out(c("  logout. Left the mission with %d/%d goals done (missions restart fresh next time)." % (done, len(goals_idx)), "gray"))
            return "quit"
        if cmdline in ("!goal", "!goals"):
            mission_screen(m, fs, sh, M.check(m, fs, sh))
            continue
        if cmdline in ("!help", "!h", "!?", "help"):
            for l in SHELL_HELP:
                out("  " + l)
            if cmdline == "help":
                out(c("  (in real bash, help lists shell builtins; man COMMAND explains a command)", "gray"))
            continue
        if cmdline.lower() in ("!menutree", "!tree", "!map"):
            menu_tree()
            continue
        if cmdline == "!cheat":
            lv = LEVELS[m["level"] - 1]
            out(box(cheat_lines(lv["topics"])[1:], "cheat sheet · Level %d · %s" % (lv["n"], lv["title"]), color="cyan"))
            continue
        if cmdline == "!stats":
            secs = int(time.time() - st["start"])
            done = sum(1 for i in goals_idx if status[i])
            out(box(["goals %d/%d  ·  commands typed %d (par %d)  ·  tips used %d  ·  time %d:%02d" % (done, len(goals_idx), st["typed"], m["par"], st["hints"], secs // 60, secs % 60),
                     "on track for: " + c(stars_str(stars_for(st["typed"], m["par"], st["hints"], st["peeked"])), "byellow", "bold") + c("   (3 stars = no tips, no solution, within par+2)", "gray"),
                     "%s · %d XP" % (rank(sv().d["xp"]), sv().d["xp"])], "stats", color="cyan"))
            continue
        if cmdline.startswith("!tips"):
            arg = cmdline[5:].strip().lower()
            if arg in ("on", "off"):
                sv().d["tips"] = arg == "on"
                sv().write()
                st["last"] = time.time()
            out(c("  " + tips_label() + (". !tip asks for one; a tip also appears after 2 min without progress." if tips_on() else ". No tips will appear. !tips on turns them back on."), "byellow"))
            continue
        if cmdline in ("!tip", "!hint"):
            if not tips_on():
                out(c("  Tips are OFF. Type !tips on to allow them (or use the main menu).", "gray"))
                continue
            msg = next_tip()
            if msg:
                out(show_tip(msg))
            else:
                out(c("  No more tips for this mission. !solution shows one way to do it.", "gray"))
            continue
        if cmdline == "!solution":
            st["peeked"] = True
            out(box([c(s, "bgreen") for s in m["solution"]], "one possible solution (max 1 star now)", color="yellow"))
            continue
        if cmdline == "!reset":
            fs, sh2 = M.build(m)
            sh2.history = sh.history
            sh = sh2
            sh.emit = ui.write
            sh._ask = lambda p: ui.read_line(p) or ""
            baseline = top_names(fs)
            del queue[:]
            noticed.clear()
            warned.clear()
            status = M.check(m, fs, sh)
            out(c("  machine reset to the starting state.", "gray"))
            mission_screen(m, fs, sh, status)
            continue
        if cmdline.startswith("!") and not cmdline.startswith("!!"):
            out(c("  unknown game command. Game commands: !goal  !tip  !tips on/off  !cheat  !stats  !menuTree  !reset  !solution   (exit leaves)", "gray"))
            continue
        if not cmdline:
            continue
        st["typed"] += 1
        sh.run(cmdline)
        # notice mistakes silently; they only surface as tips
        for n_ in shell_mod.PENDING_NOTES:
            notice("note:" + n_, n_)
        del shell_mod.PENDING_NOTES[:]
        for w_ in shell_mod.WARNINGS:
            show_warning(w_)
        del shell_mod.WARNINGS[:]
        for key in ("warn", "dead"):
            fn_ = m.get(key)
            if fn_:
                try:
                    msg = fn_(fs, sh)
                except Exception:
                    msg = None
                if msg:
                    show_warning(msg + ("  Type !reset for a fresh machine." if key == "dead" else ""))
        outside = not (fs.cwd == home or fs.cwd.startswith(home + "/"))
        if sh.last_status != 0 and outside and "~/" in mission_text:
            notice("outside", "You're in %s, outside your home directory. Errors like Permission denied mean you don't own this spot. "
                              "This mission's ~/ paths live under %s: type cd (or cd ~) to go home. "
                              "Using sudo here just builds things in the wrong place." % (fs.cwd, home))
        new_top = [p for p in top_names(fs) - baseline if p.split("/")[-1] not in mission_text]
        if new_top:
            notice("top:" + new_top[0], "You created %s, which this mission doesn't ask for. ~/something means %s/something. "
                                        "It's a throwaway machine so it's harmless; !reset starts over." % (new_top[0], home))
            baseline = top_names(fs)
        near = m.get("near")
        if near:
            try:
                msg = near(fs, sh)
            except Exception:
                msg = None
            if msg:
                notice("near:" + msg, msg)
        new = M.check(m, fs, sh)
        for i, (a, b) in enumerate(zip(status, new)):
            if b and not a and i in goals_idx:
                st["last"] = time.time()
                done = sum(1 for k in goals_idx if new[k])
                out(c("  ✔ objective %d/%d  " % (done, len(goals_idx)) if not ui.PLAIN else "  [x] objective %d/%d  " % (done, len(goals_idx)), "bgreen", "bold") + hl(m["goals"][i]))
        status = new
        if all(status):
            mission_won(m, st["typed"], st["hints"], st["peeked"])
            return "won"


def mission_won(m, typed, hints, peeked):
    s = sv()
    stars = stars_for(typed, m["par"], hints, peeked)
    prev = s.d["missions"].get(m["id"], {})
    best = max(stars, prev.get("stars", 0))
    s.d["missions"][m["id"]] = {"stars": best, "cmds": min(typed, prev.get("cmds", 999))}
    xp = 40 + 20 * stars if not prev else 10 * stars
    lvl = s.add_xp(xp)
    star_s = ("★" * stars + "☆" * (3 - stars)) if not ui.PLAIN else ("*" * stars + "." * (3 - stars))
    out("")
    lab = lambda t: c(t, "bold", fg=label_col())
    out(ui.gbox(["", c("MISSION COMPLETE", "bgreen", "bold") + "     " + c(star_s, "byellow", "bold"), "",
                 lab("commands") + "  %s  %s" % (c(str(typed), "bold", "white"), c("(par %d)" % m["par"], "gray"))
                 + "     " + lab("tips") + "  " + c(str(hints), "bold", "white")
                 + ("     " + c("solution viewed", "byellow") if peeked else "")
                 + "     " + c("+%d XP" % xp, "bold", fg=accent()),
                 "", c("3 stars = no solution peek, no tips, within par+2 commands", "gray")],
                c("✔ " if not ui.PLAIN else "", "bgreen", "bold") + c(m["title"].upper(), "bold", "white")))
    if lvl:
        rank_up(lvl)
    s.badge("first-mission")
    if stars == 3:
        s.badge("three-star")
    if len(s.d["missions"]) >= len(M.MISSIONS):
        s.badge("all-missions")


def stars_str(n):
    if ui.PLAIN:
        return "*" * n + "." * (3 - n)
    return "★" * n + "☆" * (3 - n)


def check_mark(done):
    if ui.PLAIN:
        return "[x]" if done else "[ ]"
    return c("✔", "bgreen", "bold") if done else c("☐", "gray")


# ============================================================================= vim dojo
def dojo_menu():
    while True:
        ui.clear()
        header("campaign/level-3/vim-dojo")
        out(c("\n  VIM DOJO", "bold") + c("  ·  type real vim keystrokes on one line. <Esc> = Escape, <CR> = Enter\n", "gray"))
        opts = []
        for p in vimdojo.PUZZLES:
            done = sv().d["vim"].get(p["id"])
            opts.append(("%s %s" % (check_mark(bool(done)), p["title"]), p))
        opts.append(("← Back", "back"))
        ch = ui.menu(opts)
        if ch in (None, "back"):
            return
        chain("Vim Dojo: " + ch["title"], lambda p=ch: play_dojo(p))


def render_buffer(text, cursor_line=0):
    lines = []
    for i, l in enumerate(text.rstrip("\n").split("\n"), 1):
        if len(lines) > 14:
            lines.append(c("   ... (%d more lines)" % (text.count("\n") - 15), "gray"))
            break
        lines.append(c("%3d " % i, "byellow" if i == cursor_line + 1 else "gray") + l)
    lines.append(c("~", "bblue"))
    return lines


DOJO_KEYS = "Keys:  i I a A o O = insert   <Esc> = back to Command mode   gg / G / 42G = jump   dd = delete line   dw = delete word   :w :wq :q :q! = save/quit"


def play_dojo(p):
    """-> 'won', 'lost' (skipped) or 'quit'"""
    ui.clear()
    header("campaign/level-3/vim-dojo/%s" % p["id"])
    shown = p.get("buffer", p["text"])
    out(box(render_buffer(shown) + ["", c('"%s" %dL  -- cursor on line 1, column 1, Command mode --' % (p["file"], shown.count("\n")), "gray")],
            "vim %s%s" % (p["file"], "  [+] unsaved changes" if p.get("modified") else ""), color="blue"))
    out(box([c(p["task"], "bold"), "", c(DOJO_KEYS, "gray")], "task: " + p["title"], color="yellow"))
    out(c("  Type the whole keystroke sequence, e.g. ", "gray") + c("ggO# hi<Esc>:wq", "bgreen") + c("     ? = hint   skip = show answer   q = leave", "gray"))
    tries = 0
    while True:
        try:
            k = ui.read_line(c("  vim keys❯ " if not ui.PLAIN else "  vim keys> ", "bblue", "bold"))
        except EOFError:
            return "quit"
        if k is None or k.strip() in ("q", "exit"):
            return "quit"
        if k.strip() == "?":
            out(c("  hint: ", "byellow") + p["why"])
            continue
        if k.strip() == "skip":
            out(c("  answer: ", "bgreen") + c(p["answer"], "bgreen", "bold") + c("   " + p["why"], "gray"))
            return "lost"
        if not k.strip():
            continue
        v = vimdojo.play(p, k)
        tries += 1
        for msg in v.msgs[-3:]:
            out(c("  vim: " + msg, "red" if msg.startswith("E") else "gray"))
        if p["check"](v):
            first = not sv().d["vim"].get(p["id"])
            sv().d["vim"][p["id"]] = True
            lvl = sv().add_xp(30 if first else 5)
            out(c("  ✔ CLEAN. " if not ui.PLAIN else "  ok CLEAN. ", "bgreen", "bold") + c(p["why"], "gray"))
            if p["id"] == "escape-hatch":
                sv().badge("vim-escape")
            if all(sv().d["vim"].get(x["id"]) for x in vimdojo.PUZZLES):
                sv().badge("dojo")
            if lvl:
                rank_up(lvl)
            return "won"
        state = "vim is still open" if not v.quit else "vim closed"
        out(c("  ✗ not yet (%s). " % state if not ui.PLAIN else "  x not yet (%s). " % state, "bred") + c("File on disk now:", "gray"))
        out(box(render_buffer(v.disk.get(p["file"])), color="gray"))
        if tries >= 2:
            out(c("  stuck? ? = hint, skip = show the answer", "gray"))


# ============================================================================= boss fights
BOSS_ART = {
    1: ["   (\\_/)  ", "  ( o.O ) inode #666", "  (> <)   "],
    2: ["  ~>~>~>  ", " <(o)(o)(o)>  > >> 2> &>", "  ~<~<~<  "],
    3: ["   /\\_/\\  ", "  ( :q! )  ESC ESC ESC", "   \\_^_/  "],
    4: ["  [####...]", "  [##?#.?.]  bad sectors", "  [#.?..#.]"],
    5: ["   __/\\__  ", "  <  dep  >  Failed dependencies", "   \\/  \\/  "],
    6: ["   ,---.   ", "  ( gpg? )  enabled=0", "  /|/|\\|\\  "],
    7: ["  [PV][PV] ", "  [==VG==]  n p w q", "  [LV][LV] "],
    8: ["   .-\"-.   ", "  ( UUID? )  emergency mode", "   '-..-'   "],
}


def boss_fight(level):
    """-> 'won', 'lost' or 'quit'"""
    lv = LEVELS[level - 1]
    pool_mc = [q for q in MC if q["topic"] in lv["topics"]]
    pool_r = [q for q in RECALL if q["topic"] in lv["topics"]]
    qs = pick(pool_mc, 6) + pick(pool_r, 4)
    random.shuffle(qs)
    hp_boss = len(qs)
    hearts = 3
    ui.clear()
    header("campaign/level-%d/boss" % level)
    art = BOSS_ART.get(level, [])
    out(box([c(a, "bred", "bold") for a in art] + ["", c(lv["boss"] + " blocks the way!", "bold"),
             "10 questions: some multiple choice, some type-the-command. Each miss costs a heart, and you have 3. No retries, no hints.",
             c("Tip: run this level's Drill and Concept check first.", "gray")], "BOSS · Level %d" % level, color="red"))
    ch = ui.menu([("⚔ Fight!" if not ui.PLAIN else "Fight!", "fight"), ("← Not yet", "back")])
    if ch != "fight":
        return "quit"
    for i, q in enumerate(qs, 1):
        hb = c("BOSS ", "bred") + ui.bar(hp_boss / float(len(qs)), 10, color="bred") + "  " + c("YOU ", "bgreen") + ui.hearts(hearts, 3)
        if q["kind"] == "recall":
            r = ask_recall(q, i, len(qs), retries=0, hearts=hb)
        else:
            r, _ = ask_mc(q, i, len(qs), hearts=hb)
        if r == "quit":
            out(c("  you retreat. The boss is still there.", "gray"))
            return "quit"
        if r in ("right", "retry-right"):
            hp_boss -= 1
            out(c("  ⚔ hit! " if not ui.PLAIN else "  hit! ", "bgreen", "bold") + c("boss HP %d/%d" % (hp_boss, len(qs)), "gray"))
        else:
            hearts -= 1
            out(c("  ✹ the boss strikes back! hearts left: %d" % hearts if not ui.PLAIN else "  ouch! hearts left: %d" % hearts, "bred", "bold"))
            if hearts <= 0:
                out(box([c("DEFEATED", "bred", "bold"), "%s survives with %d HP. Review the drills and try again." % (lv["boss"], hp_boss)], color="red"))
                return "lost"
        out("")
    s = sv()
    first = str(level) not in s.d["bosses"]
    s.d["bosses"][str(level)] = max(hearts, s.d["bosses"].get(str(level), 0))
    lvl = s.add_xp(120 if first else 25)
    out(box([c("VICTORY! %s is defeated." % lv["boss"], "bgreen", "bold"), "hearts left: %d   +%d XP" % (hearts, 120 if first else 25)], color="green"))
    s.badge("boss")
    if len(s.d["bosses"]) >= len(LEVELS):
        s.badge("all-bosses")
    if lvl:
        rank_up(lvl)
    return "won"


# ============================================================================= what's next
def level_steps(lv):
    """Ordered (label, action, done) for everything that counts toward finishing a level."""
    s = sv()
    steps = []
    for m in M.MISSIONS:
        if m["level"] == lv["n"]:
            steps.append(("Mission: " + m["title"], (lambda m=m: play_mission(m)), m["id"] in s.d["missions"]))
    if lv["n"] == 3:
        for p in vimdojo.PUZZLES:
            steps.append(("Vim Dojo: " + p["title"], (lambda p=p: play_dojo(p)), bool(s.d["vim"].get(p["id"]))))
    steps.append(("BOSS: " + lv["boss"], (lambda n=lv["n"]: boss_fight(n)), str(lv["n"]) in s.d["bosses"]))
    return steps


def next_step():
    """(label, action, level) for the first unfinished thing in campaign order, or None when all done."""
    for lv in LEVELS:
        for label, fn, done in level_steps(lv):
            if not done:
                return ("Level %d · %s" % (lv["n"], label), fn, lv["n"])
    return None


def chain(label, fn):
    """Play something, then offer what to do next so the player never hits a dead end."""
    while True:
        res = fn()
        if res == "quit":
            return
        nxt = next_step()
        opts = []
        if res == "won":
            if nxt:
                opts.append(("▶ Next: " + nxt[0], "next"))
            else:
                opts.append(("▶ Everything cleared! Take a practice final exam", "exam"))
            opts.append(("↻ Play it again", "again"))
        else:
            opts.append(("↻ Try again", "again"))
            if nxt and not nxt[0].endswith(label):
                opts.append(("▶ Skip ahead: " + nxt[0], "next"))
        opts.append(("← Back", "back"))
        out("")
        ch = ui.menu(opts)
        if ch == "next":
            label, fn = nxt[0], nxt[1]
        elif ch == "exam":
            exam_menu()
            return
        elif ch != "again":
            return


# ============================================================================= campaign
def level_progress(lv):
    steps = level_steps(lv)
    done = len([1 for _, _, d in steps[:-1] if d])
    return done, len(steps) - 1, steps[-1][2]


def campaign():
    while True:
        ui.clear()
        header("campaign")
        out(c("\n  CAMPAIGN  ·  one level per course module. Play them in order, or jump anywhere.\n", "bold"))
        nxt = next_step()
        here = nxt[2] if nxt else None
        opts = []
        start = 0
        for i, lv in enumerate(LEVELS):
            done, tot, boss = level_progress(lv)
            if boss and done == tot:
                mark = c("★", "byellow") if not ui.PLAIN else "*"
            elif done or boss:
                mark = c("◐", "byellow") if not ui.PLAIN else "~"
            else:
                mark = c("○", "gray") if not ui.PLAIN else "o"
            detail = "%s · %d/%d done · boss %s" % (lv["mod"].split(" · ")[0], done, tot, "✔" if boss else "–")
            if lv["n"] == here:
                detail += c("   ◀ you are here", "byellow", "bold")
                start = i
            opts.append(("%s Level %d  %-24s" % (mark, lv["n"], lv["title"]), lv, detail))
        opts.append(("← Main menu", "back"))
        ch = ui.menu(opts, start=start)
        if ch in (None, "back"):
            return
        level_screen(ch)


def level_screen(lv):
    pos = 0
    while True:
        ui.clear()
        header("campaign/level-%d" % lv["n"])
        out(box([c(lv["story"], "white"), "", c("Covers: " + "; ".join(TOPICS[t][1] for t in lv["topics"]), "gray")],
                "LEVEL %d · %s · %s" % (lv["n"], lv["title"], lv["mod"]), color="cyan"))
        nxt = next_step()
        nxt_label = nxt[0] if nxt and nxt[2] == lv["n"] else None
        opts = [(c("play", "gray"), False)]
        steps = level_steps(lv)
        for label, fn, done in steps:
            if label.startswith("Vim Dojo"):
                continue
            is_next = nxt_label is not None and nxt_label.endswith(label)
            extra = ""
            if label.startswith("Mission"):
                m = [x for x in M.MISSIONS if "Mission: " + x["title"] == label][0]
                st = sv().d["missions"].get(m["id"])
                extra = c(stars_str(st["stars"]), "byellow") if st else ("Debian 12" if m["distro"] == "debian" else "")
            else:
                b = sv().d["bosses"].get(str(lv["n"]))
                extra = ("beaten " + "♥" * b) if b else "10 questions, 3 hearts"
            if is_next:
                extra += c("   ◀ next", "byellow", "bold")
            opts.append(("%s %s" % (check_mark(done), label.replace("BOSS: ", "⚔ BOSS: " if not ui.PLAIN else "BOSS: ")), ("step", fn, label), extra))
        if lv["n"] == 3:
            vd = len([p for p in vimdojo.PUZZLES if sv().d["vim"].get(p["id"])])
            dojo_row = ("%s Vim Dojo  (%d/%d puzzles)" % (check_mark(vd == len(vimdojo.PUZZLES)), vd, len(vimdojo.PUZZLES)), ("dojo",),
                        c("   ◀ next", "byellow", "bold") if nxt_label and "Vim Dojo" in nxt_label else "")
            opts.insert(1, dojo_row)
        opts.append((c("study", "gray"), False))
        opts.append(("Drill: type the commands", ("drill",), "8 questions"))
        opts.append(("Concept check: multiple choice", ("mc",), "8 questions"))
        opts.append(("Cheat sheet", ("sheet",), "every command for this level"))
        opts.append(("← Campaign", "back"))
        start = next((i for i, o in enumerate(opts) if "◀ next" in (o[2] if len(o) > 2 else "")), pos)
        ch = ui.menu(opts, start=start)
        if ch in (None, "back"):
            return
        pos = [o[1] for o in opts].index(ch)
        kind = ch[0]
        if kind == "step":
            chain(ch[2], ch[1])
        elif kind == "dojo":
            dojo_menu()
        elif kind == "drill":
            practice_loop(lambda: pick([q for q in RECALL if q["topic"] in lv["topics"]], 8), "Level %d drill" % lv["n"], "campaign/level-%d/drill" % lv["n"])
        elif kind == "mc":
            practice_loop(lambda: pick([q for q in MC if q["topic"] in lv["topics"]], 8), "Level %d concept check" % lv["n"], "campaign/level-%d/concepts" % lv["n"])
        elif kind == "sheet":
            cheat_sheet(lv["topics"])


# ============================================================================= practice
def practice_menu():
    while True:
        ui.clear()
        header("practice")
        out(c("\n  PRACTICE  ·  quick reps on any topic. (Missions and the Vim Dojo live in the Campaign.)\n", "bold"))
        weak_n = len([q for q in RECALL + MC if sv().weak(q)])
        ch = ui.menu([("Command drills", "drill", "type the command · pick a topic or mix them"),
                      ("Lightning round", "lightning", "60 seconds, as many as you can"),
                      ("Weak spots", "weak", ("%d to review" % weak_n) if weak_n else "nothing missed yet"),
                      ("Cheat sheets", "sheet", "every command, by topic"),
                      ("← Main menu", "back")])
        if ch in (None, "back"):
            return
        {"drill": drill_menu, "lightning": lightning, "weak": weak_spots, "sheet": cheat_menu}[ch]()


def drill_menu():
    while True:
        ui.clear()
        header("practice/drills")
        out(c("\n  COMMAND DRILLS  ·  10 questions per round. Missed ones come back more often.\n", "bold"))
        opts = [("Mixed: every topic", "all", "Modules 6-12")]
        for t, (mod, desc) in TOPICS.items():
            qs = [q for q in RECALL if q["topic"] == t]
            m_ = len([q for q in qs if sv().mastered(q)])
            opts.append(("%-10s %s" % (t, desc[:40]), t, "%s · %d/%d mastered" % (mod.replace(" (PREVIEW)", "*"), m_, len(qs))))
        opts.append(("← Practice", "back"))
        ch = ui.menu(opts)
        if ch in (None, "back"):
            return
        pool = RECALL if ch == "all" else [q for q in RECALL if q["topic"] == ch]
        practice_loop(lambda: pick(pool, 10), "Drill: %s" % ch, "practice/drills/%s" % ch)


def lightning():
    ui.clear()
    header("practice/lightning")
    out(box(["60 seconds. Type commands as fast as you can.", "No retries, no hints. The clock is checked after each answer. q stops early.", "Questions marked PREVIEW (Module 12 items not on a slide yet) are left out."], "LIGHTNING ROUND", color="yellow"))
    if ui.menu([("⏱ Start the clock" if not ui.PLAIN else "Start the clock", "go"), ("← Back", "back")]) != "go":
        return
    pool = [q for q in RECALL if not is_preview(q) and not q["loose"]]
    random.shuffle(pool)
    start = time.time()
    right = n = 0
    for q in pool:
        left = 60 - (time.time() - start)
        if left <= 0:
            break
        r = ask_recall(q, None, None, retries=0, show_feedback=False, hearts=c("⏱ %ds" % left if not ui.PLAIN else "%ds left" % left, "byellow", "bold"))
        if r == "quit":
            break
        n += 1
        if r in ("right", "retry-right"):
            right += 1
        out("")
    sv().add_xp(right * 6)
    if right >= 10:
        sv().badge("lightning-10")
    out(box(["%d correct out of %d attempted" % (right, n), "+%d XP" % (right * 6)], "TIME!", color="yellow"))
    ui.press_enter()


def weak_spots():
    pool = [q for q in RECALL + MC if sv().weak(q)]
    if not pool:
        ui.clear()
        header("practice/weak-spots")
        out(box(["Nothing here yet. Questions you miss anywhere in the game land here until you get them right twice in a row."], "WEAK SPOTS", color="green"))
        ui.press_enter()
        return
    practice_loop(lambda: pick([q for q in RECALL + MC if sv().weak(q)], 12), "Weak spots", "practice/weak-spots")


# ============================================================================= exam simulator
def exam_menu():
    while True:
        ui.clear()
        header("final-exam")
        preview = sv().d.get("exam_preview", True)
        pool = [q for q in MC if preview or not is_preview(q)]
        out(c("\n  FINAL EXAM SIMULATOR", "bold") + c("  ·  multiple choice, graded at the end like the real thing\n", "gray"))
        ch = ui.menu([("Quick exam", 25, "25 questions"), ("Full exam", 50, "50 questions"), ("Everything", len(pool), "all %d questions" % len(pool)),
                      ("Practice exam", "practice", "20 questions, feedback after each one"),
                      (("[x] " if preview else "[ ] ") + "Include Module 12 PREVIEW questions", "toggle", "not on a slide yet (%d) · Enter toggles" % len([q for q in MC if is_preview(q)])),
                      ("← Main menu", "back")])
        if ch in (None, "back"):
            return
        if ch == "toggle":
            sv().d["exam_preview"] = not preview
            sv().write()
            continue
        if ch == "practice":
            practice_loop(lambda: pick(pool, 20), "Practice exam", "final-exam/practice")
            continue
        run_exam(random.sample(pool, min(ch, len(pool))))


def run_exam(qs):
    ui.clear()
    header("final-exam/in-progress")
    start = time.time()
    answers = []
    for i, q in enumerate(qs, 1):
        r, picked = ask_mc(q, i, len(qs), feedback=False)
        if r == "quit":
            if not ui.confirm("  End the exam now and grade what you answered?"):
                return
            break
        answers.append((q, r == "right", picked))
        out("")
    if not answers:
        return
    secs = int(time.time() - start)
    right = sum(1 for _, ok, _ in answers if ok)
    pct = 100.0 * right / len(answers)
    by_topic = {}
    for q, ok, _ in answers:
        t = by_topic.setdefault(q["topic"], [0, 0])
        t[1] += 1
        t[0] += ok
    ui.clear()
    header("final-exam/results")
    grade = "A" if pct >= 90 else "B" if pct >= 80 else "C" if pct >= 70 else "D" if pct >= 60 else "F"
    lines = [c("Score: %d / %d  =  %.0f%%   grade %s" % (right, len(answers), pct, grade), "bold", "bgreen" if pct >= 70 else "bred"),
             c("time: %d min %02d s  (%.0f s per question)" % (secs // 60, secs % 60, secs / float(len(answers))), "gray"), "",
             c("Weakest topics first:", "gray")]
    for t, (r_, n_) in sorted(by_topic.items(), key=lambda kv: kv[1][0] / float(kv[1][1])):
        lines.append("%-10s %s %d/%d  %s" % (t, ui.bar(r_ / float(n_), 16, color="green" if r_ / float(n_) >= 0.7 else "red"), r_, n_, c(TOPICS[t][0], "gray")))
    out(box(lines, "EXAM RESULTS", color="magenta"))
    s = sv()
    s.d["exams"].append({"score": right, "total": len(answers), "t": int(time.time())})
    s.add_xp(right * 4)
    if len(answers) >= 25 and pct >= 80:
        s.badge("exam-80")
    s.write()
    missed = [(q, p) for q, ok, p in answers if not ok]
    if missed and ui.confirm("  Review the %d you missed?" % len(missed)):
        for k, (q, p) in enumerate(missed, 1):
            out("")
            out(box([c(q["q"], "bold"), c("you picked: " + str(p), "bred")], "missed %d/%d" % (k, len(missed)), color="magenta"))
            show_explain(q)
            ui.press_enter()
    else:
        ui.press_enter()


# ============================================================================= cheat sheets, progress, help
def pager(lines):
    h = ui.term_height() - 3
    i = 0
    while i < len(lines):
        for l in lines[i:i + h]:
            out(l)
        i += h
        if i < len(lines):
            ui.write(c("  -- more (Enter = next page, q = stop) --", "gray"))
            k = ui.readkey()
            ui.write("\r" + ui.ESC + "[K" if ui.COLOR else "\n")
            if k in ("q", "esc"):
                return


def cheat_lines(topics):
    lines = []
    for t in topics:
        mod, desc = TOPICS[t]
        lines.append("")
        lines.append(c("━━ %s · %s ━━" % (mod, desc) if not ui.PLAIN else "== %s - %s ==" % (mod, desc), "bcyan", "bold"))
        for q in [q for q in RECALL if q["topic"] == t]:
            lines.append("  " + c(q["answers"][0], "bgreen") + c("   " + q["prompt"], "gray"))
    return lines


def cheat_sheet(topics=None):
    ui.clear()
    header("practice/cheat-sheets")
    pager(cheat_lines(topics or list(TOPICS)))
    ui.press_enter()


def cheat_menu():
    while True:
        ui.clear()
        header("practice/cheat-sheets")
        out(c("\n  CHEAT SHEETS  ·  every command in the game, grouped by topic\n", "bold"))
        opts = [("All topics", "all", "long: use the pager")] + [("%-10s %s" % (t, TOPICS[t][1][:44]), t, TOPICS[t][0]) for t in TOPICS] + [("← Practice", "back")]
        ch = ui.menu(opts)
        if ch in (None, "back"):
            return
        cheat_sheet(None if ch == "all" else [ch])


def progress():
    ui.clear()
    header("profile/progress")
    s = sv()
    lines = [c("Mastered = answered right twice in a row.", "gray")]
    for t, (mod, desc) in TOPICS.items():
        qs = [q for q in RECALL + MC if q["topic"] == t]
        m_ = len([q for q in qs if s.mastered(q)])
        seen = len([q for q in qs if q["id"] in s.d["q"]])
        lines.append("%-10s %s %3d/%-3d  %s" % (t, ui.bar(m_ / float(len(qs)), 18), m_, len(qs), c("seen %d" % seen, "gray")))
    lines.append("")
    lines.append("Missions %d/%d  ·  Vim Dojo %d/%d  ·  Bosses %d/%d  ·  best streak %d" % (
        len(s.d["missions"]), len(M.MISSIONS), len([1 for v in s.d["vim"].values() if v]), len(vimdojo.PUZZLES), len(s.d["bosses"]), len(LEVELS), s.d["best_streak"]))
    if s.d["exams"]:
        best = max(s.d["exams"], key=lambda e: e["score"] / float(e["total"]))
        lines.append("Best exam %d/%d (%.0f%%)  ·  exams taken %d" % (best["score"], best["total"], 100.0 * best["score"] / best["total"], len(s.d["exams"])))
    out(box(lines, "PROGRESS", color="cyan"))
    bl = []
    for k, (name, desc) in BADGES.items():
        got = k in s.d["badges"]
        bl.append((c("🏅 " if not ui.PLAIN else "* ", "byellow") + c(name, "bold") if got else c("·  " + name, "gray")) + c("  " + desc, "gray"))
    out(box(bl, "BADGES %d/%d" % (len(s.d["badges"]), len(BADGES)), color="yellow"))
    ui.press_enter()


def how_to_play():
    ui.clear()
    header("profile/how-to-play")
    k = lambda s: c(s, "byellow", "bold")
    out(box([
        c("Not sure what to do? Pick ▶ Continue on the main menu. It always takes you to your next unfinished thing.", "bold"),
        "",
        k("Menus") + "        ↑↓ move · Enter pick · number key jumps · Esc or q goes back · m menu map",
        k("Questions") + "    type the command and press Enter.  ? hint · skip · q stop",
        "             a miss gets one more try; Enter on an empty line shows the answer",
        "             sudo is optional · quote style doesn't matter · -la is the same as -al",
        k("Missions") + "     a simulated Linux shell: type real commands. Goals tick off on their own.",
        "             !goal · !tip · !cheat · !stats · !menuTree · !reset · !solution · exit leaves",
        k("Tips") + "         OFF by default, and then they never appear. Turn them on in Profile",
        "             or with !tips on: then !tip asks for one, and one shows up by itself",
        "             if you go 2 minutes without reaching the next goal",
        k("Vim Dojo") + "     type keystrokes on one line: ggO# hi<Esc>:wq",
        "             <Esc> means the Escape key, <CR> means Enter",
        k("Bosses") + "       10 questions, 3 hearts, no retries. Beat all 7 for the Final Form badge",
        "",
        c("Where you are is always shown under the status bar, like a shell path:", "gray"),
        "  " + c("rocky@rocky01:", "bgreen", "bold") + c("~/campaign/level-4", "bblue", "bold") + c("$ ", "byellow", "bold") + c("pwd", "gray"),
    ], "HOW TO PLAY", color="cyan"))
    out(box([
        "Covers everything after the DCOM 142 midterm: Modules 6-12 (CertMaster 4.1-7.4), from the instructor's Fall 2026 slides (Modules 6-11) and Learning Objectives pages.",
        "The Module 12 deck (7.3-7.4) isn't posted yet: Level 8 uses the mount/fstab/RAID/quota slides from the Module 11 deck, and marks everything else PREVIEW.",
        "%d typed-command drills · %d multiple-choice questions · %d missions · %d vim puzzles · %d bosses" % (len(RECALL), len(MC), len(M.MISSIONS), len(vimdojo.PUZZLES), len(LEVELS)),
        c("Self-study only: the syllabus doesn't allow AI tools on graded work.", "byellow"),
    ], "ABOUT", color="gray"))
    ui.press_enter()


# ============================================================================= menu map (!menuTree)
def menu_nodes():
    """(name, path, description, children) describing every menu in the game."""
    lv = [("level-%d" % l["n"], "campaign/level-%d" % l["n"], l["title"] + ("  (preview)" if "PREVIEW" in l["mod"] else ""),
           ([("vim-dojo/", "campaign/level-3/vim-dojo", "%d keystroke puzzles" % len(vimdojo.PUZZLES), [])] if l["n"] == 3 else []))
          for l in LEVELS]
    return ("~", "", "main menu", [
        ("▶ continue" if not ui.PLAIN else "> continue", "#continue", "jumps to your next unfinished thing", []),
        ("campaign/", "campaign", "%d levels: missions · boss · drill · cheat sheet" % len(LEVELS), lv),
        ("practice/", "practice", "quick reps", [
            ("drills/", "practice/drills", "type the command, by topic", []),
            ("lightning", "practice/lightning", "60 seconds", []),
            ("weak-spots", "practice/weak-spots", "what you've missed", []),
            ("cheat-sheets/", "practice/cheat-sheets", "every command, by topic", []),
        ]),
        ("final-exam/", "final-exam", "quick 25 · full 50 · everything · practice", []),
        ("profile/", "profile", "you and your settings", [
            ("progress", "profile/progress", "mastery bars, ranks, badges", []),
            ("tips", "profile/tips", "on/off (off = never shown)", []),
            ("theme", "profile/theme", "Rocky · Matrix · Amber CRT", []),
            ("how-to-play", "profile/how-to-play", "controls", []),
            ("menu-map", "profile/menu-map", "this tree (m in menus, !menuTree in missions)", []),
        ]),
        ("quit", "#quit", "logout", []),
    ])


LAST_WHERE = [""]


def menu_tree(where=None):
    """Print the menus like the Linux `tree` command, marking where you are."""
    where = LAST_WHERE[0] if where is None else where
    best = ""

    def walk(node):
        nonlocal best
        _, path, _, kids = node
        if path and not path.startswith("#") and (where == path or where.startswith(path + "/")) and len(path) > len(best):
            best = path
        for k in kids:
            walk(k)
    root = menu_nodes()
    walk(root)
    lines = [c("$ tree ~", "gray")]
    counts = [0, 0]

    def name_s(name, path):
        s = c(name, "bblue", "bold") if name.endswith("/") or name == "~" else c(name, "white")
        if path == best:
            s = c(name, "byellow", "bold", "inv")
        return s

    def rec(node, prefix):
        kids = node[3]
        for i, ch in enumerate(kids):
            last = i == len(kids) - 1
            branch = ("└── " if last else "├── ") if not ui.PLAIN else ("`-- " if last else "|-- ")
            name, path, desc, sub = ch
            counts[0 if (name.endswith("/") or sub) else 1] += 1
            here = c("  ◀ you are here" if not ui.PLAIN else "  <- you are here", "byellow", "bold") if path == best else ""
            pad = " " * max(1, 24 - len(prefix + branch + name))
            lines.append(c(prefix + branch, "gray") + name_s(name, path) + pad + c(desc, "gray") + here)
            rec(ch, prefix + (("    " if last else "│   ") if not ui.PLAIN else ("    " if last else "|   ")))
    here_root = c("  ◀ you are here" if not ui.PLAIN else "  <- you are here", "byellow", "bold") if best == "" else ""
    lines.append(name_s("~", "") + "  " + c("main menu", "gray") + here_root)
    rec(root, "")
    lines.append("")
    lines.append(c("%d menus, %d screens · Esc always goes back one level" % (counts[0] + 1, counts[1]), "gray"))
    out(box(lines, "MENU MAP", color="cyan"))


def menu_map_screen():
    ui.clear()
    header("profile/menu-map")
    menu_tree()
    ui.press_enter()


# ============================================================================= feature tooltip
FEATURES = [
    "Lost? Press m in any menu (or type !menuTree in a mission) to see every menu as a tree.",
    "▶ Continue always opens your next unfinished mission, puzzle or boss.",
    "Missions are graded on the machine's final state: any correct command works, not just one answer.",
    "In missions, Tab completes file names and ↑ recalls earlier commands, just like bash.",
    "Forgot sudo? Type sudo !! to rerun your last command as root.",
    "!cheat in a mission shows that level's commands without leaving the shell.",
    "!stats in a mission shows your time, commands typed, goals and tips used.",
    "Vim Dojo: type ggO# hi<Esc>:wq and a mini vim runs your keystrokes.",
    "Boss fights: 10 questions, 3 hearts, no retries. Beat all 7 for the Final Form badge.",
    "Weak spots: anything you miss comes back until you get it right twice in a row.",
    "The exam simulator grades at the end and lists your weakest topics first.",
    "Try the Matrix or Amber CRT theme: Profile → Theme.",
    "man works inside missions: try man tar or man rpm.",
    "!reset gives you a fresh machine; exit leaves the mission.",
]


def feature_line(step):
    i = (sv().d.get("feature_i", 0) + step) % len(FEATURES)
    bulb = "💡" if not ui.PLAIN else "*"
    return c("  %s did you know? " % bulb, "byellow", "bold") + c(FEATURES[i], "white") + c("   (%d/%d · → next)" % (i + 1, len(FEATURES)), "gray")


# ============================================================================= profile
THEME_ORDER = ["rocky", "matrix", "amber"]


def profile_menu():
    while True:
        ui.clear()
        header("profile")
        s = sv()
        out(c("\n  PROFILE  ·  your progress and settings\n", "bold"))
        th = s.d.get("theme", "rocky")
        ch = ui.menu([("Progress & badges", "progress", "%s · %d XP · %d/%d badges" % (rank(s.d["xp"]), s.d["xp"], len(s.d["badges"]), len(BADGES))),
                      (tips_label(), "tips", "Enter toggles · " + ("!tip in missions, plus one after 2 min stuck" if tips_on() else "no tips appear anywhere")),
                      ("Theme: " + ui.THEMES[th]["name"], "theme", "Enter cycles: Rocky → Matrix → Amber CRT"),
                      ("How to play", "help", "controls and commands"),
                      ("Menu map", "map", "every menu as a tree"),
                      ("← Main menu", "back")])
        if ch in (None, "back"):
            return
        if ch == "tips":
            s.d["tips"] = not tips_on()
            s.write()
        elif ch == "theme":
            nxt = THEME_ORDER[(THEME_ORDER.index(th) + 1) % len(THEME_ORDER)]
            s.d["theme"] = nxt
            ui.set_theme(nxt)
            s.write()
        else:
            {"progress": progress, "help": how_to_play, "map": menu_map_screen}[ch]()


# ============================================================================= main
def main_menu():
    start = 0
    while True:
        ui.clear()
        title_small()
        nxt = next_step()
        s = sv()
        opts = [("▶ Continue" if not ui.PLAIN else "> Continue", "continue", (nxt[0] if nxt else "all cleared! try the final exam")),
                ("Campaign", "campaign", "%d levels · %d/%d missions · %d/%d bosses" % (len(LEVELS), len(s.d["missions"]), len(M.MISSIONS), len(s.d["bosses"]), len(LEVELS))),
                ("Practice", "practice", "drills · lightning · weak spots · cheat sheets"),
                ("Final exam", "exam", "%d multiple-choice questions, graded at the end" % len(MC)),
                ("Profile", "profile", "progress · tips %s · theme · how to play · menu map" % ("on" if tips_on() else "off")),
                ("Quit", "quit", "")]
        ch = ui.menu(opts, start=start, back=True, ticker=(6.0, feature_line),
                     footer=("↑↓ move · Enter select · m menu map · q quit" if not ui.PLAIN else "arrows move, Enter selects, m menu map, q quits"))
        s.d["feature_i"] = s.d.get("feature_i", 0) + 1
        start = [o[1] for o in opts].index(ch) if ch in [o[1] for o in opts] else 0
        if ch in (None, "quit"):
            s.write()
            out(c("\n  logout. Good luck on the final. Stay root. 🐧\n" if not ui.PLAIN else "\n  logout. Good luck on the final.\n", "bcyan"))
            return
        if ch == "continue":
            if nxt:
                chain(nxt[0], nxt[1])
            else:
                exam_menu()
            continue
        {"campaign": campaign, "practice": practice_menu, "exam": exam_menu, "profile": profile_menu}[ch]()


def title_small():
    for i, line in enumerate(SMALL_LOGO):
        out(c(line, fg=ui.grad(i + 2)) if ui.COLOR else line)
    out(c("  ROCKY RESCUE · DCOM 142 final review · Modules 6-12", "gray"))
    header("")


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        out(__doc__ or "")
        out("usage: python play.py [--no-intro] [--no-anim] [--plain]")
        return
    ui.set_theme(sv().d.get("theme", "rocky"))
    ui.HOTKEYS["m"] = ("menu map", menu_tree)
    try:
        title_screen()
        if ui.interactive() and "--no-intro" not in ui.ARGS:
            ui.press_enter("  press Enter to log in to rocky01 ")
        if not sv().d.get("seen_help"):
            sv().d["seen_help"] = True
            sv().write()
            how_to_play()
        main_menu()
    except KeyboardInterrupt:
        ui.show_cursor()
        out(c("\n  bye! progress is saved.", "gray"))
    except EOFError:
        ui.show_cursor()
        out("")
