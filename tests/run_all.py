"""Run every test suite: python tests/run_all.py"""
import subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
bad = 0
for t in ["test_content.py", "test_missions.py", "test_vim.py", "test_game.py"]:
    r = subprocess.run([sys.executable, os.path.join(here, t)], capture_output=True, text=True, encoding="utf-8")
    last = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    print(("PASS " if r.returncode == 0 else "FAIL ") + t + "  ->  " + last)
    bad += r.returncode != 0
sys.exit(1 if bad else 0)
