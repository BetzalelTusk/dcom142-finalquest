"""Every mission: fresh setup must NOT be complete; replaying the reference solution MUST complete it."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finalquest import missions as M

bad = 0
for m in M.MISSIONS:
    fs, sh = M.build(m)
    out = []
    sh.emit = out.append
    sh._ask = lambda p: "y"
    before = M.check(m, fs, sh)
    for c in m["solution"]:
        sh.run(c)
    after = M.check(m, fs, sh)
    ok = all(after) and not all(before)
    if not ok:
        bad += 1
        print("FAIL %-22s before=%s after=%s" % (m["id"], before, after))
        print("".join(out)[-1500:])
    else:
        print("ok   %-22s (%d goals, %d solution cmds)" % (m["id"], len(m["goals"]), len(m["solution"])))
print("missions:", len(M.MISSIONS), "failed:", bad)
sys.exit(1 if bad else 0)
