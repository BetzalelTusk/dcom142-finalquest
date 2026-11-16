"""End-to-end: drive the real UI with scripted keystrokes."""
import sys, os, io, random, tempfile, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finalquest import ui, game, missions as M, vimdojo
ui.HOTKEYS["m"] = ("menu map", game.menu_tree)
game.SAVE = os.path.join(tempfile.mkdtemp(), "save.json")
random.shuffle = lambda x, *a, **k: None          # deterministic option order: correct answer first

def drive(fn, *keys, **kw):
    ui.end_script()
    ui.feed(*keys)
    buf = io.StringIO()
    err = None
    with contextlib.redirect_stdout(buf):
        try:
            r = fn(**kw)
        except ui.ScriptExhausted:
            err = "script exhausted"; r = None
    ui.end_script()
    return r, buf.getvalue(), err

def lines_for(cmds):
    ks = []
    for c in cmds: ks += [c, "enter"]
    return ks

fails = 0
def expect(name, cond, outp=""):
    global fails
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails += 1; print(outp[-2500:])

# 1. every mission through the real mission runner, typing the reference solution
for m in M.MISSIONS:
    r, o, e = drive(game.play_mission, *lines_for(m["solution"]), m=m)
    expect("mission %s via UI" % m["id"], r == "won" and "MISSION COMPLETE" in o, o)

# 2. mission helpers: !goal, !tip while tips are OFF, !tips on, !tip, !reset, !solution, Esc, then exit leaves
game.sv().d["tips"] = False
m = M.MISSIONS[0]
r, o, e = drive(game.play_mission, *(lines_for(["!goal", "!tip", "!tips on", "!tip", "!hint", "ls", "!menuTree", "!cheat", "!stats", "!reset", "!solution", "bogus", "!help"]) + ["esc"] + lines_for(["exit"])), m=m)
expect("mission helper commands + exit", r == "quit" and "Tips are OFF" in o and "Tips: ON" in o and "(1/3)" in o and "(2/3)" in o and "machine reset" in o
       and "one possible solution" in o and "command not found" in o and "Esc pressed" in o and "logout" in o
       and "MENU MAP" in o and "you are here" in o and "cheat sheet · Level 1" in o and "goals 0/3" in o, o)
game.sv().d["tips"] = False

# 3. vim dojo: wrong then right
p = vimdojo.PUZZLES[0]
r, o, e = drive(game.play_dojo, *lines_for([":q", "?", p["answer"]]), p=p)
expect("vim dojo wrong-then-right", r == "won" and "E37" in o and "CLEAN" in o and game.sv().d["vim"].get(p["id"]), o)
r, o, e = drive(game.play_dojo, *lines_for(["skip"]), p=p)
expect("vim dojo skip shows answer", r == "lost" and p["answer"] in o, o)

# 4. recall question: wrong, then retry right ; and hint
q = [x for x in game.RECALL if not x["loose"]][0]
r, o, e = drive(game.ask_recall, *lines_for(["?", "nonsense cmd", q["answers"][0]]), q=q)
expect("recall retry-right with hint", r == "retry-right" and "hint:" in o and "you typed" in o, o)
r, o, e = drive(game.ask_recall, *lines_for(["wrong one", ""]), q=q)
expect("recall Enter-after-miss shows answer", r == "wrong" and "Answer:" in o, o)

# 5. MC: correct is first option (shuffle disabled) unless true/false
q = game.MC[0]
idx = game.mc_options(q).index(q["correct"])
r, o, e = drive(game.ask_mc, str(idx + 1), q=q)
expect("mc correct", r[0] == "right", o)
r, o, e = drive(game.ask_mc, "down" if idx == 0 else "up", "enter", q=q)
expect("mc wrong via arrows", r[0] == "wrong" and "Answer:" in o, o)

# 6. boss fight, perfect play
lvl = 4
real_pick = game.pick
game.pick = lambda pool, n, rng=None: list(pool)[:n]
lv = game.LEVELS[lvl - 1]
qs = [q for q in game.MC if q["topic"] in lv["topics"]][:6] + [q for q in game.RECALL if q["topic"] in lv["topics"]][:4]
keys = ["enter"]
for q in qs:
    if q["kind"] == "recall": keys += [q["answers"][0], "enter"]
    else: keys += [str(game.mc_options(q).index(q["correct"]) + 1)]
r, o, e = drive(game.boss_fight, *keys, level=lvl)
expect("boss fight perfect", r == "won" and "VICTORY" in o, o)
keys = ["enter"]
for q in qs[:3]:
    if q["kind"] == "recall": keys += ["xx", "enter"]
    else: keys += [str((game.mc_options(q).index(q["correct"]) + 1) % len(game.mc_options(q)) + 1)]
r, o, e = drive(game.boss_fight, *keys, level=lvl)
expect("boss fight defeat", r == "lost" and "DEFEATED" in o, o)
r, o, e = drive(game.boss_fight, "esc", level=lvl)
expect("boss fight backed out", r == "quit", o)
game.pick = real_pick

# 7. exam: 3 questions all right then decline review
qs = game.MC[:3]
keys = [str(game.mc_options(q).index(q["correct"]) + 1) for q in qs] + ["n", "enter"]
r, o, e = drive(game.run_exam, *keys, qs=qs)
expect("exam grading 3/3", "3 / 3" in o and "EXAM RESULTS" in o, o)

# 8. Continue -> next unfinished mission -> win -> "Next:" chains into the following mission -> exit
game.SAVE = os.path.join(tempfile.mkdtemp(), "fresh.json"); game.SAVE_DATA = None
first = M.MISSIONS[0]
keys = ["1"] + lines_for(first["solution"]) + ["1"] + lines_for(["exit"]) + ["q"]
r, o, e = drive(game.main_menu, *keys)
expect("continue -> mission -> next chains", e is None and "First Boot" in o and "Next: Level 1 · Mission: Link Lab" in o and "Link Lab" in o and "logout" in o, o)
expect("you-are-here path shown", "~/campaign/level-1/first-boot" in o, o)

# 9. main menu tour: profile (how to play, progress, menu map, tips toggle, theme), practice (cheat sheet, weak spots), exam toggle, campaign, m hotkey, tooltip
game.sv().d["tips"] = False
keys = ["5", "4", "enter", "1", "enter", "5", "enter", "2", "3", "esc",
        "3", "4", "2", "enter", "esc", "3", "enter", "esc",
        "4", "5", "esc", "2", "1", "esc", "esc", "m", "<idle>", "right", "q"]
r, o, e = drive(game.main_menu, *keys)
expect("main menu tour", e is None and "HOW TO PLAY" in o and "PROGRESS" in o and o.count("MENU MAP") >= 2 and "Tips: ON" in o and "Theme: Matrix" in o
       and "Paths" in o and "Nothing here yet" in o and "[ ] Include Storage" in o and "LEVEL 1" in o and "did you know?" in o and "logout" in o, o)
tips_seen = set(l.split("did you know? ")[1].split("   (")[0] for l in o.splitlines() if "did you know? " in l)
expect("tooltip cycles through features (idle + →)", len(tips_seen) >= 3, " | ".join(tips_seen))
ui.set_theme("rocky"); game.sv().d["theme"] = "rocky"; game.sv().d["tips"] = False

# 10. campaign level 7 cheat sheet via number key
r, o, e = drive(game.main_menu, "2", "7", "6", "enter", "esc", "esc", "q")
expect("campaign level 7 cheat sheet", e is None and "Storage" in o and "lvcreate" in o, o)

# 11. the real playtest that got stuck: building /projects at the root instead of ~/projects
m = M.MISSIONS[0]
session = ["pwd", "cd ..", "cd ..", "pwd", "mkdir projects", "sudo mkdir projects", "ls", "cd projects", "mkdir logs", "sudo !!", "ls"]
fix = ["cd", "mkdir -p projects/logs", "touch projects/a.txt projects/b.txt", "cd projects"]
game.sv().d["tips"] = False
game.TIP_DELAY = 0
r, o, e = drive(game.play_mission, *(lines_for(session) + ["<idle>", "<idle>"] + lines_for(["!tip"] + fix)), m=m)
expect("tips OFF: nothing appears, even when idle", r == "won" and "─ tip" not in o and "Close!" not in o and "Tips are OFF" in o and "sudo mkdir logs" in o, o)
game.sv().d["tips"] = True
r, o, e = drive(game.play_mission, *(lines_for(session) + lines_for(["!tip"]) + ["<idle>"] + lines_for(fix)), m=m)
expect("tips ON: !tip gives the most relevant tip, idle gives another", r == "won" and "Close! You built a projects folder at" in o
       and "2+ min" in o and o.count("Close!") == 1, o)
game.TIP_DELAY = 120
r, o, e = drive(game.play_mission, *(lines_for(session[:6]) + ["<idle>"] * 3 + lines_for(["exit"])), m=m)
expect("tips ON but under 2 minutes: no automatic tip", "2+ min" not in o, o)
game.sv().d["tips"] = False
m = [x for x in M.MISSIONS if x["id"] == "dependency-hell"][0]
r, o, e = drive(game.play_mission, *lines_for(["sudo rpm -ivh Downloads/httpd-2.4.57-5.el9.x86_64.rpm", "exit"]), m=m)
expect("simulator teaching notes stay hidden when tips are OFF", "Failed dependencies" in o and "low-level tool" not in o, o)


# 12. Ctrl+V pastes the clipboard as fast keystrokes. A paste must never submit answers, pick menu options or reveal answers.
def as_keys(text):
    return [("enter" if ch == "\n" else ch) for ch in text]

qs = [q for q in game.RECALL if not q["loose"]][:3]
clip = "mkdir -p projects/logs\n\ntouch projects/a.txt\n\nmore 1 2 j k m q\n"
pasted = ["<paste>"] + as_keys(clip) + ["</paste>"]
r, o, e = drive(game.ask_recall, *(pasted + ["enter"]), q=qs[0])
expect("paste at a question: first line kept, only the player's own Enter submits it, nothing cascades",
       r in ("wrong", "right", "retry-right") or e == "script exhausted", o)
expect("paste at a question: no answer revealed by the paste", "kept only the first one" in o and "skipped" not in o and "Answer:" not in o, o)
q = game.MC[0]
r, o, e = drive(game.ask_mc, *(pasted + ["esc"]), q=q)
expect("paste in a multiple-choice menu picks nothing", r[0] == "quit" and "paste ignored" in o and "MENU MAP" not in o, o)
r, o, e = drive(game.run_exam, "<paste>", "c", "d", " ", "enter", "</paste>", "esc", "n", qs=game.MC[:2])
expect("paste during the exam records no answer", "EXAM RESULTS" not in o, o)
r, o, e = drive(game.ask_mc, "<paste>", "down", "down", "</paste>", "enter", q=q)
expect("held-down arrows (fast repeats) still move in menus", r[0] in ("right", "wrong"), o)
m = M.MISSIONS[0]
r, o, e = drive(game.play_mission, *(["<paste>"] + as_keys("mkdir -p projects/logs\ntouch projects/zzz\n") + ["</paste>", "enter"] + lines_for(["ls projects", "exit"])), m=m)
expect("paste in a mission runs only the first line, after your own Enter", "kept only the first one" in o and "logs" in o and "zzz" not in o.split("kept only")[1], o)

print("failures:", fails)
sys.exit(1 if fails else 0)
