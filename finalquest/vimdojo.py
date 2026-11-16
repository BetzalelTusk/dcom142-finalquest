"""Vim Dojo: a tiny modal vim emulator. You type real keystrokes; the puzzle checks the saved file.

Keystroke notation: type keys as-is. Use <Esc> for Escape (also accepted: ESC on its own word is NOT special,
use <Esc>), <CR> or <Enter> for Enter. A ':' command at the very end runs even without <CR>."""
import re

TOKEN = re.compile(r"<(esc|cr|enter|bs|c-w)>", re.I)


def parse_keys(s):
    keys = []
    i = 0
    while i < len(s):
        m = TOKEN.match(s, i)
        if m:
            k = m.group(1).lower()
            keys.append({"esc": "<Esc>", "cr": "<CR>", "enter": "<CR>", "bs": "<BS>", "c-w": "<C-w>"}[k])
            i = m.end()
        elif s[i] == "^" and i + 1 < len(s) and s[i + 1] == "[":
            keys.append("<Esc>")
            i += 2
        else:
            keys.append(s[i])
            i += 1
    return keys


class Vim:
    def __init__(self, text, name="file.txt", modified=False, buffer=None):
        self.name = name
        self.disk = {name: text}
        shown = buffer if buffer is not None else text
        self.lines = shown.rstrip("\n").split("\n") if shown else [""]
        self.row = 0
        self.col = 0
        self.mode = "normal"
        self.cmd = ""
        self.pending = ""
        self.quit = False
        self.msgs = []
        self.modified = modified
        self.undo = []
        self.reg = None
        self.split = None

    def snapshot(self):
        self.undo.append((list(self.lines), self.row, self.col))

    def clamp(self):
        self.row = max(0, min(self.row, len(self.lines) - 1))
        ln = self.lines[self.row]
        maxc = max(0, len(ln) - (0 if self.mode == "insert" else 1))
        self.col = max(0, min(self.col, maxc))

    def content(self):
        return "\n".join(self.lines) + "\n"

    def feed(self, keys):
        for k in keys:
            if self.quit:
                break
            getattr(self, "k_" + self.mode)(k)
        if self.mode == "cmd" and not self.quit:
            self.run_cmd()

    # ------------------------------------------------------------------ insert
    def k_insert(self, k):
        if k == "<Esc>":
            self.mode = "normal"
            self.col = max(0, self.col - 1)
            self.clamp()
            return
        if k == "<CR>":
            ln = self.lines[self.row]
            self.lines[self.row:self.row + 1] = [ln[:self.col], ln[self.col:]]
            self.row += 1
            self.col = 0
        elif k == "<BS>":
            if self.col > 0:
                ln = self.lines[self.row]
                self.lines[self.row] = ln[:self.col - 1] + ln[self.col:]
                self.col -= 1
        elif len(k) == 1:
            ln = self.lines[self.row]
            self.lines[self.row] = ln[:self.col] + k + ln[self.col:]
            self.col += 1
        self.modified = True

    # ------------------------------------------------------------------ normal
    def enter_insert(self):
        self.snapshot()
        self.mode = "insert"

    def k_normal(self, k):
        p = self.pending + k
        if k == "<Esc>":
            self.pending = ""
            return
        if k == "<C-w>":
            self.pending = "<C-w>"
            return
        if self.pending == "<C-w>":
            self.pending = ""
            if k in ("s", "v"):
                self.split = "horizontal" if k == "s" else "vertical"
                self.msgs.append("window split %s" % self.split)
            return
        m = re.match(r"^(\d*)(.*)$", p)
        count, op = m.group(1), m.group(2)
        n = int(count) if count else None
        if op == "":
            self.pending = p
            return
        done = True
        ln = self.lines[self.row]
        if op == "i":
            self.enter_insert()
        elif op == "I":
            self.col = len(ln) - len(ln.lstrip())
            self.enter_insert()
        elif op == "a":
            self.col = min(len(ln), self.col + 1)
            self.enter_insert()
        elif op == "A":
            self.col = len(ln)
            self.enter_insert()
        elif op == "o":
            self.snapshot()
            self.lines.insert(self.row + 1, "")
            self.row += 1
            self.col = 0
            self.mode = "insert"
            self.modified = True
        elif op == "O":
            self.snapshot()
            self.lines.insert(self.row, "")
            self.col = 0
            self.mode = "insert"
            self.modified = True
        elif op in ("h",):
            self.col -= n or 1
        elif op in ("l",):
            self.col += n or 1
        elif op in ("j",):
            self.row += n or 1
        elif op in ("k",):
            self.row -= n or 1
        elif op == "0":
            self.col = 0
        elif op == "$":
            self.col = len(ln)
        elif op == "w":
            for _ in range(n or 1):
                m2 = re.compile(r"\s+\S").search(self.lines[self.row], self.col)
                if m2:
                    self.col = m2.end() - 1
                elif self.row < len(self.lines) - 1:
                    self.row += 1
                    self.col = 0
        elif op == "G":
            self.row = (n - 1) if n else len(self.lines) - 1
            self.col = 0
        elif op == "g":
            done = False
        elif op == "gg":
            self.row = (n - 1) if n else 0
            self.col = 0
        elif op == "x":
            self.snapshot()
            self.lines[self.row] = ln[:self.col] + ln[self.col + (n or 1):]
            self.modified = True
        elif op in ("d", "y"):
            done = False
        elif op == "dd":
            self.snapshot()
            k_ = n or 1
            self.reg = ("lines", self.lines[self.row:self.row + k_])
            del self.lines[self.row:self.row + k_]
            if not self.lines:
                self.lines = [""]
            self.col = 0
            self.modified = True
        elif op in ("dw", "de"):
            self.snapshot()
            m2 = re.compile(r"\S+\s*" if op == "dw" else r"\S+").match(ln, self.col)
            end = m2.end() if m2 else self.col + 1
            self.reg = ("chars", ln[self.col:end])
            self.lines[self.row] = ln[:self.col] + ln[end:]
            self.modified = True
        elif op == "yy":
            self.reg = ("lines", self.lines[self.row:self.row + (n or 1)])
        elif op in ("p", "P"):
            if self.reg:
                self.snapshot()
                if self.reg[0] == "lines":
                    at = self.row + (1 if op == "p" else 0)
                    self.lines[at:at] = list(self.reg[1])
                    self.row = at
                else:
                    at = self.col + (1 if op == "p" else 0)
                    self.lines[self.row] = ln[:at] + self.reg[1] + ln[at:]
                self.modified = True
        elif op == "u":
            if self.undo:
                self.lines, self.row, self.col = self.undo.pop()
                self.modified = True
        elif op == ":":
            self.mode = "cmd"
            self.cmd = ""
        elif op == "Z":
            done = False
        elif op == "ZZ":
            self.write(self.name)
            self.quit = True
        elif op == "ZQ":
            self.quit = True
        else:
            self.msgs.append("(key '%s' is not simulated here)" % op)
        if done:
            self.pending = ""
        else:
            self.pending = p
        self.clamp()

    # ------------------------------------------------------------------ command line
    def k_cmd(self, k):
        if k == "<Esc>":
            self.mode = "normal"
            self.cmd = ""
        elif k == "<CR>":
            self.run_cmd()
        elif k == "<BS>":
            self.cmd = self.cmd[:-1]
        else:
            self.cmd += k

    def write(self, name):
        self.disk[name] = self.content()
        if name == self.name:
            self.modified = False
        self.msgs.append('"%s" %dL written' % (name, len(self.lines)))

    def run_cmd(self):
        c = self.cmd.strip()
        self.mode = "normal"
        self.cmd = ""
        if c in ("w",):
            self.write(self.name)
        elif c.startswith("w ") and len(c) > 2:
            self.write(c[2:].strip())
        elif c in ("wq", "x", "wq!"):
            self.write(self.name)
            self.quit = True
        elif c == "q":
            if self.modified:
                self.msgs.append("E37: No write since last change (add ! to override)")
            else:
                self.quit = True
        elif c == "q!":
            self.quit = True
        elif c.isdigit():
            self.row = int(c) - 1
            self.col = 0
            self.clamp()
        elif c:
            self.msgs.append("E492: Not an editor command: %s" % c)


CONF = "Port 22\nPermitRootLogin yes\nPasswordAuthentication yes\nX11Forwarding no\n"

PUZZLES = [
    {"id": "escape-hatch", "title": "Escape Hatch", "file": "sshd_config", "text": CONF, "modified": True, "buffer": CONF.replace("PermitRootLogin yes", "PermitRootLogin yesssssss qqq"),
     "task": "You fat-fingered some changes in sshd_config. Quit WITHOUT saving anything.",
     "check": lambda v: v.quit and v.disk["sshd_config"] == CONF, "answer": ":q!", "why": ":q refuses when there are unsaved changes (E37). :q! quits and throws them away."},
    {"id": "save-and-quit", "title": "Save & Quit", "file": "sshd_config", "text": CONF,
     "task": "Add a new LAST line: MaxAuthTries 3   then save and quit.",
     "check": lambda v: v.quit and v.disk["sshd_config"] == CONF + "MaxAuthTries 3\n", "answer": "GoMaxAuthTries 3<Esc>:wq",
     "why": "G jumps to the last line, o opens a new line below and enters Insert mode, <Esc> returns to Command mode, :wq saves and quits."},
    {"id": "top-banner", "title": "Top Banner", "file": "hosts", "text": "127.0.0.1 localhost\n192.168.1.100 linux02\n",
     "task": "Make '# managed by IT' the new FIRST line of the file, then save and quit.",
     "check": lambda v: v.quit and v.disk["hosts"] == "# managed by IT\n127.0.0.1 localhost\n192.168.1.100 linux02\n", "answer": "ggO# managed by IT<Esc>:wq",
     "why": "gg = top of file. O opens a line ABOVE the cursor (o would open it below)."},
    {"id": "bad-line", "title": "Delete the Bad Line", "file": "app.conf", "text": "name=web\nport=8080\nDEBUG=true\nworkers=4\n",
     "task": "Delete the whole line DEBUG=true (line 3), then save and quit.",
     "check": lambda v: v.quit and v.disk["app.conf"] == "name=web\nport=8080\nworkers=4\n", "answer": "3Gdd:wq",
     "why": "3G jumps to line 3 (jj from the top works too). dd deletes the whole line."},
    {"id": "line-42", "title": "Line 42", "file": "big.log", "text": "".join("entry %d\n" % i if i != 42 else "CORRUPT ENTRY\n" for i in range(1, 61)),
     "task": "This 60-line log has garbage on line 42. Jump straight there, delete that line, save and quit.",
     "check": lambda v: v.quit and "CORRUPT" not in v.disk["big.log"] and v.disk["big.log"].count("\n") == 59, "answer": "42Gdd:wq",
     "why": "42G jumps to line 42 (the slides' example). :42 does the same from Execute mode."},
    {"id": "semicolon", "title": "End of the Line", "file": "script.js", "text": "let a = 1;\nlet b = 2\nlet c = 3;\n",
     "task": "Line 2 is missing its semicolon. Add ';' at the END of line 2, save and quit.",
     "check": lambda v: v.quit and v.disk["script.js"] == "let a = 1;\nlet b = 2;\nlet c = 3;\n", "answer": "jA;<Esc>:wq",
     "why": "A appends at the end of the current line (a appends after the cursor; I inserts at the start)."},
    {"id": "comment-out", "title": "Comment It Out", "file": "crontab", "text": "0 3 * * * /usr/local/bin/backup.sh\n",
     "task": "Disable the job by putting '#' at the START of line 1. Save and quit.",
     "check": lambda v: v.quit and v.disk["crontab"] == "#0 3 * * * /usr/local/bin/backup.sh\n", "answer": "I#<Esc>:wq",
     "why": "I inserts at the beginning of the line, wherever the cursor is."},
    {"id": "save-as", "title": "Save As", "file": "httpd.conf", "text": "Listen 80\nServerName www.example.com\n",
     "task": "Before touching anything, save a copy of this buffer as httpd.conf.bak, then quit. httpd.conf must stay unchanged.",
     "check": lambda v: v.quit and v.disk.get("httpd.conf.bak") == "Listen 80\nServerName www.example.com\n" and v.disk["httpd.conf"] == "Listen 80\nServerName www.example.com\n",
     "answer": ":w httpd.conf.bak<CR>:q", "why": ":w NEWNAME writes the buffer to a new file. Then :q (nothing modified, so no ! needed)."},
    {"id": "word-surgeon", "title": "Word Surgeon", "file": "note.txt", "text": "this is very important\n",
     "task": "Delete the word 'very ' (cursor starts at the beginning of the line). Save and quit.",
     "check": lambda v: v.quit and v.disk["note.txt"] == "this is important\n", "answer": "wwdw:wq",
     "why": "w moves forward one word (twice to reach 'very'); dw deletes a word. The slides list d as 'delete the word at the cursor'."},
]


def play(p, keys):
    v = Vim(p["text"], p["file"], p.get("modified", False), p.get("buffer"))
    v.feed(parse_keys(keys))
    return v
