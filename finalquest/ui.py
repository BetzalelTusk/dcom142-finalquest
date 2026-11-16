"""Terminal layer: colours, boxes, arrow-key menus, a line editor with history and Tab completion.

Everything reads keys through readkey(), which tests can replace by queueing keys with feed().
Standard library only. Works on Windows, macOS and Linux.
"""
import os
import re
import shutil
import sys
import time

ARGS = set(sys.argv[1:])
if os.name == "nt":
    os.system("")  # enable ANSI escapes in the Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

PLAIN = "--plain" in ARGS
COLOR = (sys.stdout.isatty() or "--color" in ARGS) and not os.environ.get("NO_COLOR")
_SCRIPT = None          # list of queued keys when running under a test
ANIM = sys.stdout.isatty() and "--no-anim" not in ARGS


def interactive():
    return _SCRIPT is not None or (sys.stdin.isatty() and sys.stdout.isatty())


# ----------------------------------------------------------------------------- colours
CODES = {"reset": 0, "bold": 1, "dim": 2, "ital": 3, "ul": 4, "inv": 7,
         "red": 31, "green": 32, "yellow": 33, "blue": 34, "magenta": 35, "cyan": 36, "white": 37,
         "gray": 90, "bred": 91, "bgreen": 92, "byellow": 93, "bblue": 94, "bmag": 95, "bcyan": 96}


THEMES = {
    "rocky":  {"name": "Rocky", "map": {}, "grad": [51, 45, 39, 33, 27, 63, 99, 135]},
    "matrix": {"name": "Matrix", "map": {"cyan": "green", "bcyan": "bgreen", "blue": "green", "bblue": "bgreen", "magenta": "green",
                                         "bmag": "bgreen", "yellow": "green", "byellow": "bgreen", "white": "green"},
               "grad": [46, 46, 40, 40, 34, 34, 28, 28]},
    "amber":  {"name": "Amber CRT", "map": {"cyan": "yellow", "bcyan": "byellow", "blue": "yellow", "bblue": "byellow", "magenta": "yellow",
                                            "bmag": "byellow", "green": "yellow", "bgreen": "byellow", "white": "yellow"},
               "grad": [220, 214, 214, 208, 208, 202, 202, 166]},
}
THEME = THEMES["rocky"]


def set_theme(name):
    global THEME
    THEME = THEMES.get(name, THEMES["rocky"])


def grad(i):
    g = THEME["grad"]
    return g[i % len(g)]


def c(text, *styles, fg=None):
    """Wrap text in ANSI styles (remapped by the current theme). fg = 0-255 for a 256-colour foreground."""
    if not COLOR:
        return str(text)
    seq = [str(CODES[THEME["map"].get(s, s)]) for s in styles]
    if fg is not None:
        seq.append("38;5;%d" % fg)
    return "\x1b[%sm%s\x1b[0m" % (";".join(seq), text) if seq else str(text)


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def vlen(s):
    return len(ANSI_RE.sub("", s))


def clip(s, width):
    """Cut a string with ANSI codes to `width` visible characters (adds … when cut)."""
    if vlen(s) <= width:
        return s
    out_, n, i = "", 0, 0
    while i < len(s) and n < width - 1:
        m = ANSI_RE.match(s, i)
        if m:
            out_ += m.group(0)
            i = m.end()
            continue
        out_ += s[i]
        n += 1
        i += 1
    return out_ + "…" + ("\x1b[0m" if COLOR else "")


def term_width():
    return max(40, min(110, shutil.get_terminal_size((100, 30)).columns - 1))


def term_height():
    return max(15, shutil.get_terminal_size((100, 30)).lines)


def wrap(text, width):
    """Word-wrap text that may contain ANSI codes (codes count as zero width)."""
    out = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            if line and vlen(line) + 1 + vlen(word) > width:
                out.append(line)
                line = word
            else:
                line = (line + " " + word) if line else word
        out.append(line)
    return out


def pad(s, width):
    return s + " " * max(0, width - vlen(s))


BOX = {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"}
BOX_PLAIN = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|"}


def box(lines, title="", width=None, color="cyan", fg=None):
    b = BOX_PLAIN if PLAIN else BOX
    width = width or min(term_width(), 92)
    inner = width - 4
    body = []
    for ln in lines:
        if vlen(ln) <= inner:
            body.append(ln)
            continue
        lead = len(ln) - len(ln.lstrip(" "))
        plain = ANSI_RE.sub("", ln).lstrip(" ")
        hang = lead + (2 if plain[:1] in "☐✔[•-*" else 0)
        parts = wrap(ln[lead:], inner - hang)
        body.append(" " * lead + parts[0])
        body.extend(" " * hang + x for x in parts[1:])
    top = b["tl"] + b["h"] * (width - 2) + b["tr"]
    if title:
        t = " %s " % title
        top = b["tl"] + b["h"] + t + b["h"] * max(0, width - 3 - vlen(t)) + b["tr"]
    sty = lambda s: c(s, color, fg=fg) if fg is None else c(s, fg=fg)
    out = [sty(top)]
    for ln in body:
        out.append(sty(b["v"]) + " " + pad(ln, inner) + " " + sty(b["v"]))
    out.append(sty(b["bl"] + b["h"] * (width - 2) + b["br"]))
    return "\n".join(out)


def bar(frac, width=20, full="█", empty="░", color="green"):
    if PLAIN:
        full, empty = "#", "."
    frac = max(0.0, min(1.0, frac))
    n = int(round(frac * width))
    return c(full * n, color) + c(empty * (width - n), "gray")


def hearts(n, total):
    if PLAIN:
        return "[" + "#" * n + "." * (total - n) + "]"
    return c("♥ " * n, "bred") + c("♡ " * (total - n), "gray")


# ----------------------------------------------------------------------------- output helpers
def out(s=""):
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def write(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def clear():
    if COLOR and sys.stdout.isatty():
        write("\x1b[2J\x1b[H")
    else:
        out("\n" * 2)


def pause(t):
    if ANIM:
        time.sleep(t)


def typewriter(text, delay=0.006):
    if not ANIM:
        out(text)
        return
    for ch in text:
        write(ch)
        if ch not in " \n":
            time.sleep(delay)
    write("\n")


def hide_cursor():
    if COLOR and sys.stdout.isatty():
        write("\x1b[?25l")


def show_cursor():
    if COLOR and sys.stdout.isatty():
        write("\x1b[?25h")


# ----------------------------------------------------------------------------- key input
def feed(*keys):
    """Queue keys for tests. A multi-character string is split into single keys except names like 'enter'."""
    global _SCRIPT
    if _SCRIPT is None:
        _SCRIPT = []
    for k in keys:
        if len(k) > 1 and k not in NAMED:
            _SCRIPT.extend(list(k))
        else:
            _SCRIPT.append(k)


def feed_line(text):
    feed(text, "enter")


def script_done():
    return _SCRIPT is not None and not _SCRIPT


def end_script():
    global _SCRIPT
    _SCRIPT = None


NAMED = {"enter", "esc", "up", "down", "left", "right", "backspace", "tab", "home", "end", "del", "ctrl-c", "ctrl-d", "<idle>"}


class ScriptExhausted(Exception):
    pass


def readkey(timeout=None):
    """Return the next key name. With a timeout, returns None if no key arrived in time.
    Test scripts can queue '<idle>' to simulate a timeout."""
    if _SCRIPT is not None:
        if not _SCRIPT:
            raise ScriptExhausted()
        k = _SCRIPT.pop(0)
        if k == "<idle>":
            return None if timeout is not None else readkey()
        return k
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if line == "":
            raise EOFError
        return "enter" if line.strip() == "" else line.rstrip("\n")
    if os.name == "nt":
        import msvcrt
        if timeout is not None:
            end = time.time() + timeout
            while not msvcrt.kbhit():
                if time.time() >= end:
                    return None
                time.sleep(0.03)
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return {"H": "up", "P": "down", "K": "left", "M": "right", "G": "home", "O": "end", "S": "del"}.get(msvcrt.getwch(), "?")
        return _norm(ch)
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        if timeout is not None and not select.select([fd], [], [], timeout)[0]:
            return None
        ch = os.read(fd, 1).decode("utf-8", "ignore")
        if ch == "\x1b":
            if select.select([fd], [], [], 0.03)[0]:
                rest = os.read(fd, 8).decode("utf-8", "ignore")
                m = {"[A": "up", "[B": "down", "[C": "right", "[D": "left", "[H": "home", "[F": "end",
                     "[3~": "del", "OH": "home", "OF": "end", "[1~": "home", "[4~": "end"}
                return m.get(rest, "?")
            return "esc"
        return _norm(ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _norm(ch):
    if ch in ("\r", "\n"):
        return "enter"
    if ch in ("\x7f", "\x08"):
        return "backspace"
    if ch == "\t":
        return "tab"
    if ch == "\x1b":
        return "esc"
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch == "\x04":
        return "ctrl-d"
    return ch


# ----------------------------------------------------------------------------- line editor
def read_line(prompt, history=None, complete=None, default="", timeout=None, tick=None):
    """Edit a line with arrows, Home/End, Delete, history (up/down) and Tab completion.
    complete(buf, pos) -> list of candidate replacements for the word before the cursor.
    tick=(seconds, fn): while waiting for keys, call fn() every `seconds`; if it returns text, print it
    above the prompt and redraw the line (used for timed tips).
    Returns the text. Raises KeyboardInterrupt on Ctrl+C, EOFError on Ctrl+D (empty line) or ESC returns None."""
    if not interactive():
        line = sys.stdin.readline()
        if line == "":
            raise EOFError
        return line.rstrip("\n")
    buf = list(default)
    pos = len(buf)
    hist = list(history or [])
    hi = len(hist)
    saved = None
    tabbed = False
    plen = vlen(prompt)

    def draw():
        write("\r" + prompt + "".join(buf) + "\x1b[K")
        back = len(buf) - pos
        if back:
            write("\x1b[%dD" % back)

    draw()
    while True:
        k = readkey(timeout=tick[0] if tick else None)
        if k is None:
            msg = tick[1]() if tick else None
            if msg:
                write("\r\x1b[K" + msg + ("" if msg.endswith("\n") else "\n"))
                draw()
            continue
        if k == "enter":
            write("\n")
            return "".join(buf)
        if k == "esc":
            write("\n")
            return None
        if k == "ctrl-d":
            if not buf:
                write("\n")
                raise EOFError
            continue
        if k == "backspace":
            if pos:
                del buf[pos - 1]
                pos -= 1
        elif k == "del":
            if pos < len(buf):
                del buf[pos]
        elif k == "left":
            pos = max(0, pos - 1)
        elif k == "right":
            pos = min(len(buf), pos + 1)
        elif k == "home":
            pos = 0
        elif k == "end":
            pos = len(buf)
        elif k == "up":
            if hist and hi > 0:
                if hi == len(hist):
                    saved = "".join(buf)
                hi -= 1
                buf = list(hist[hi])
                pos = len(buf)
        elif k == "down":
            if hi < len(hist):
                hi += 1
                buf = list(hist[hi]) if hi < len(hist) else list(saved or "")
                pos = len(buf)
        elif k == "tab":
            if complete:
                word_start = "".join(buf[:pos]).rfind(" ") + 1
                cands = complete("".join(buf), pos)
                if len(cands) == 1:
                    buf[word_start:pos] = list(cands[0])
                    pos = word_start + len(cands[0])
                elif cands:
                    pre = os.path.commonprefix(cands)
                    if len(pre) > pos - word_start:
                        buf[word_start:pos] = list(pre)
                        pos = word_start + len(pre)
                    elif tabbed:
                        write("\n" + "  ".join(os.path.basename(x.rstrip("/")) + ("/" if x.endswith("/") else "") for x in cands) + "\n")
                    tabbed = True
                    draw()
                    continue
            tabbed = False
            draw()
            continue
        elif len(k) == 1 and k >= " ":
            buf.insert(pos, k)
            pos += 1
        else:
            continue
        tabbed = False
        draw()


def read_key_line(prompt):
    """Prompt and return one raw key (used for 'press any key')."""
    write(prompt)
    k = readkey()
    write("\n")
    return k


def press_enter(msg="  press Enter to continue "):
    write(c(msg, "gray"))
    try:
        while True:
            k = readkey()
            if k in ("enter", "esc", " ", "q"):
                break
    finally:
        write("\n")


# ----------------------------------------------------------------------------- menu
ESC = "\x1b"
NAV = "↑↓ move · Enter select · Esc back"
NAV_PLAIN = "arrows move, Enter selects, Esc goes back"


HOTKEYS = {}   # key -> (label, fn) available in every menu, e.g. "m" -> menu map


def menu(options, title=None, subtitle=None, start=0, back=True, footer=None, width=None, ticker=None):
    """options: list of (label, value, detail); detail optional. Returns the chosen value, or None on Esc/q.
    value=False makes a row that can't be selected (a heading or a locked item); the cursor skips it.
    Selectable rows are numbered 1-9 so a number key jumps straight to them.
    ticker=(seconds, fn(step) -> line): a line drawn above the options that changes every `seconds` (and on →)."""
    if footer is None:
        footer = (NAV if back else NAV.replace(" · Esc back", "")) if not PLAIN else (NAV_PLAIN if back else "arrows move, Enter selects")
        for key, (label, _) in HOTKEYS.items():
            footer += " · %s %s" % (key, label)
    selectable = [i for i, o in enumerate(options) if o[1] is not False]
    numbers = {i: k + 1 for k, i in enumerate(selectable) if k < 9}
    if not interactive():
        for i, o in enumerate(options):
            out(("  %d) %s" % (numbers[i], o[0])) if i in numbers else "     " + o[0])
        line = sys.stdin.readline().strip()
        if line.isdigit():
            for i, k in numbers.items():
                if k == int(line):
                    return options[i][1]
        return None
    if not selectable:
        return None
    idx = start if start in selectable else selectable[0]
    n = len(options)
    # line the detail column up: pad every selectable label to the widest one (capped)
    lw = min(36, max([vlen(o[0]) for o in options if o[1] is not False and len(o) > 2 and o[2]] or [0]))
    first = True
    step = 0
    hide_cursor()
    try:
        while True:
            lines = []
            if ticker:
                lines.append(ticker[1](step))
            for i, o in enumerate(options):
                label, val = o[0], o[1]
                detail = o[2] if len(o) > 2 else ""
                num = ("%d" % numbers[i]) if i in numbers else " "
                padded = label + " " * max(0, lw - vlen(label)) if detail else label
                if val is False:
                    row = "     " + label
                elif i == idx:
                    row = c(" ▸ " if not PLAIN else " > ", "byellow") + c(num + " ", "byellow") + c(padded, "bold", "byellow")
                else:
                    row = "   " + c(num + " ", "gray") + padded
                if detail:
                    row += "  " + c(detail, "gray")
                lines.append(row)
            if not first:
                write(ESC + "[%dA" % (len(lines) + (1 if footer else 0)))
            tw = shutil.get_terminal_size((100, 30)).columns - 1   # every row must fit on one line or the redraw drifts
            for ln in lines:
                write("\r" + clip(ln, tw) + ESC + "[K\n")
            if footer:
                write("\r" + clip(c("   " + footer, "gray"), tw) + ESC + "[K\n")
            first = False
            k = readkey(timeout=ticker[0] if ticker else None)
            if k is None:
                step += 1
                continue
            pos = selectable.index(idx)
            if k in HOTKEYS:
                show_cursor()
                write("\n")
                HOTKEYS[k][1]()
                write("\n")
                hide_cursor()
                first = True
                continue
            if k == "right" and ticker:
                step += 1
                continue
            if k in ("up", "k"):
                idx = selectable[(pos - 1) % len(selectable)]
            elif k in ("down", "j", "tab"):
                idx = selectable[(pos + 1) % len(selectable)]
            elif k in ("home",):
                idx = selectable[0]
            elif k in ("end",):
                idx = selectable[-1]
            elif k == "enter":
                return options[idx][1]
            elif k in ("esc", "q", "backspace", "left") and back:
                return None
            elif k.isdigit():
                for i, num in numbers.items():
                    if num == int(k):
                        return options[i][1]
    finally:
        show_cursor()


def confirm(question, default=True):
    write(c(question, "bold") + c(" [Y/n] " if default else " [y/N] ", "gray"))
    while True:
        k = readkey()
        if k == "enter":
            write("\n")
            return default
        if k.lower() in ("y", "n"):
            write(k + "\n")
            return k.lower() == "y"
        if k == "esc":
            write("\n")
            return False
