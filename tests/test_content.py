import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finalquest import content_recall_a, content_recall_b, content_mc_a, content_mc_b, content_storage
from finalquest.content_base import RECALL, MC, TOPICS
from finalquest.grading import check, normalize
bad = 0
for q in RECALL:
    for a in q["answers"]:
        ok, _ = check(a, q["answers"], q["loose"])
        if not ok:
            bad += 1; print("SELF-FAIL", q["prompt"], a)
    # each accepted answer must not also be accepted by a different question with a different prompt? skip
# collisions inside loose questions
# sanity checks
for t in ["tar -czvf backup.tar.gz file10 file20", "tar czvf backup.tar.gz file10 file20", "sudo tar -zcvf backup.tar.gz file10 file20"]:
    print(normalize(t))
print(check("sudo grep -ci 'Failed password' /var/log/secure", ["sudo grep -ic \"Failed password\" /var/log/secure"]))
print(check("ls /nope 2>errors.txt", ["ls /nope 2> errors.txt"]))
print(check("cut -d : -f1 /etc/passwd", ["cut -d: -f1 /etc/passwd"]))
print(check("cut -d: -f 1 /etc/passwd", ["cut -d: -f1 /etc/passwd"]))
dupes = [p for p, c in collections.Counter(q["prompt"] for q in RECALL).items() if c > 1]
mdupes = [p for p, c in collections.Counter(q["q"] for q in MC).items() if c > 1]
for q in MC:
    if q["correct"] in q["wrong"]:
        bad += 1; print("MC correct in wrong:", q["q"])
print("recall", len(RECALL), "mc", len(MC), "dupe prompts", dupes, mdupes, "bad", bad)
print(collections.Counter(q["topic"] for q in RECALL)); print(collections.Counter(q["topic"] for q in MC))
