import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finalquest.vimdojo import PUZZLES, play
alts = {"bad-line": ["jjdd:wq", ":3<CR>dd:wq", "3GddZZ", "3Gdd:x"], "line-42": [":42<CR>dd:wq"], "semicolon": ["2GA;<Esc>:wq", "j$a;<Esc>:wq"],
        "top-banner": ["O# managed by IT<Esc>:wq"], "save-and-quit": ["Go<Esc>iMaxAuthTries 3<Esc>:wq"] , "escape-hatch": []}
wrong = {"escape-hatch": [":q", ":wq"], "top-banner": ["ggo# managed by IT<Esc>:wq"], "semicolon": ["ja;<Esc>:wq"], "save-as": [":w<CR>:q"], "bad-line": ["3Gdd:q"]}
bad = 0
for p in PUZZLES:
    for k in [p["answer"]] + alts.get(p["id"], []):
        v = play(p, k)
        if not p["check"](v):
            bad += 1; print("FAIL", p["id"], repr(k), v.disk, v.quit, v.msgs)
    for k in wrong.get(p["id"], []):
        v = play(p, k)
        if p["check"](v):
            bad += 1; print("WRONGLY PASSED", p["id"], repr(k))
print("puzzles", len(PUZZLES), "bad", bad)
