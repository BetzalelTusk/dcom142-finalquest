"""Answer matching for typed-command questions.

Rules: sudo is optional, quote style is ignored, letters in one short-flag group can come in any order
(-czvf == -zcvf), tar's leading dash is optional, extra spaces don't matter, argument order DOES matter.
loose questions (key names, words) ignore case, spaces and punctuation."""
import re


def tokens(s):
    out = []
    i, n = 0, len(s)
    cur, has = "", False
    while i < n:
        ch = s[i]
        if ch in " \t":
            if has:
                out.append(cur)
            cur, has = "", False
            i += 1
        elif ch in "'\"":
            j = s.find(ch, i + 1)
            if j < 0:
                j = n
            cur += s[i + 1:j]
            has = True
            i = j + 1
        elif ch in "|;<>&":
            if has and not (ch == ">" and cur in ("1", "2")):
                out.append(cur)
                cur, has = "", False
            op = ch
            if s[i:i + 2] in ("||", "&&", ">>", "&>", "<<"):
                op = s[i:i + 2]
            if cur in ("1", "2") and has and ch == ">":
                op = cur + op
                cur, has = "", False
            out.append(op)
            i += len(op) - (1 if op[0] in "12" else 0)
        else:
            cur += ch
            has = True
            i += 1
    if has:
        out.append(cur)
    return out


VALUED = {"cut": "dfc", "head": "n", "tail": "n", "sort": "kt", "awk": "F", "lvcreate": "Ln", "lvextend": "L",
          "grep": "e", "mkfs": "t", "wget": "OP", "curl": "o", "xargs": "n", "unzip": "d", "ddrescue": "r", "dnf": "", "yum": ""}


def _join_values(t):
    """'-d :' -> '-d:' and 'head -5' -> 'head -n5' for options known to take a value."""
    out = []
    cmd = None
    i = 0
    while i < len(t):
        tok = t[i]
        if tok in ("|", ";", "&&", "||"):
            cmd = None
            out.append(tok)
            i += 1
            continue
        if cmd is None and tok != "sudo":
            cmd = tok
            out.append(tok)
            i += 1
            continue
        vals = VALUED.get(cmd, "")
        if re.fullmatch(r"-[A-Za-z]", tok) and tok[1] in vals and i + 1 < len(t) and t[i + 1] not in ("|", ";", "&&", "||", ">", ">>", "<"):
            out.append(tok + t[i + 1])
            i += 2
            continue
        if cmd in ("head", "tail") and re.fullmatch(r"-\d+", tok):
            out.append("-n" + tok[1:])
            i += 1
            continue
        out.append(tok)
        i += 1
    return out


def normalize(s):
    t = _join_values(tokens(s.strip()))
    res = []
    start = True
    for k, tok in enumerate(t):
        if start and tok == "sudo":
            continue
        if tok in ("|", ";", "&&", "||"):
            res.append(tok)
            start = True
            continue
        if not start and re.fullmatch(r"-[A-Za-z]+", tok) and res and re.fullmatch(r"-[A-Za-z]+", res[-1]) and len(res) >= 2:
            res[-1] = "-" + "".join(sorted(res[-1][1:] + tok[1:]))   # -l -a == -la
            continue
        first_arg = start is False and res and res[-1] == "tar" and not tok.startswith("-") and re.fullmatch(r"[a-zA-Z]+", tok or "") and set(tok) <= set("cxtvfzjJrpC")
        if first_arg:
            tok = "-" + tok
        if re.fullmatch(r"-[A-Za-z]{2,}", tok):
            # keep a trailing value-taking letter (like tar's f) in place: sort the rest
            letters = tok[1:]
            tok = "-" + "".join(sorted(letters))
        if tok.endswith("/") and len(tok) > 1 and not tok.startswith("/") or (tok.endswith("/") and tok.count("/") > 1):
            tok = tok.rstrip("/") or "/"
        res.append(tok)
        start = False
    return res


def loose_norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def check(answer, accepted, loose=False):
    """-> (correct, best_match)"""
    if loose:
        a = loose_norm(answer)
        for acc in accepted:
            if a == loose_norm(acc):
                return True, acc
        return False, accepted[0]
    na = normalize(answer)
    for acc in accepted:
        if na == normalize(acc):
            return True, acc
    # choose the closest accepted answer for feedback
    import difflib
    best = max(accepted, key=lambda acc: difflib.SequenceMatcher(None, na, normalize(acc)).ratio())
    return False, best


def _display_pairs(s):
    """(normalized_token, as_typed) pairs, so feedback shows what the student actually typed."""
    raw = tokens(s.strip())
    out = []
    for tok in raw:
        n = normalize(tok) if tok not in ("|", ";", "&&", "||") else [tok]
        if not n:
            continue
        out.append((n[0] if len(n) == 1 else tok, tok))
    return out


def diff_words(answer, expected):
    """List of (word, status) for the typed answer: ok / bad ; plus missing expected words."""
    import difflib
    a, e = tokens(answer), tokens(expected)
    sm = difflib.SequenceMatcher(None, normalize(answer), normalize(expected))
    typed = []
    na, ne = normalize(answer), normalize(expected)
    shown = na
    if len(na) == len([t for t in a if t != "sudo" or a.index(t) != 0]):
        shown = [t for i, t in enumerate(a) if not (t == "sudo" and i == 0)]
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            typed += [(w, "ok") for w in shown[i1:i2]]
        elif op == "replace":
            typed += [(w, "bad") for w in shown[i1:i2]]
            typed += [(w, "missing") for w in e[j1:j2]] if len(e) == len(ne) else [(w, "missing") for w in ne[j1:j2]]
        elif op == "delete":
            typed += [(w, "bad") for w in shown[i1:i2]]
        elif op == "insert":
            typed += [(w, "missing") for w in (e[j1:j2] if len(e) == len(ne) else ne[j1:j2])]
    return typed
