"""chmod, chown and chgrp: needed for mount points (the Module 11 slides chown /opt/downloads after mounting)."""
import re

from .shell import cmd, getopts
from .vfs import FSError


def _users(fs):
    try:
        return {l.split(":")[0] for l in fs.read("/etc/passwd", "root").split("\n") if l}
    except FSError:
        return set()


def _groups(fs):
    try:
        g = {l.split(":")[0] for l in fs.read("/etc/group", "root").split("\n") if l}
    except FSError:
        g = set()
    return g | _users(fs)      # user private groups


def _targets(ctx, paths, recursive):
    for p in paths:
        node = ctx.fs.lookup(p)
        if node is None:
            ctx.err("cannot access '%s': No such file or directory" % p)
            continue
        yield p, node
        if recursive and node.kind == "d":
            for q in ctx.fs.walk(p):
                if q != ctx.fs.abspath(p):
                    n = ctx.fs.lookup(q, follow=False)
                    if n is not None:
                        yield q, n


def _apply_symbolic(mode, spec, is_dir):
    for clause in spec.split(","):
        m = re.match(r"^([ugoa]*)([+\-=])([rwxX]*)$", clause)
        if not m:
            return None
        who, op, perms = m.groups()
        who = who or "a"
        bits = 0
        for ch in perms:
            if ch == "X" and not (is_dir or mode & 0o111):
                continue
            bits |= {"r": 4, "w": 2, "x": 1, "X": 1}[ch]
        mask = 0
        for w in who:
            for sh in {"u": (6,), "g": (3,), "o": (0,), "a": (6, 3, 0)}[w]:
                mask |= bits << sh
                if op == "=":
                    mode &= ~(7 << sh)
        if op == "+" or op == "=":
            mode |= mask
        else:
            mode &= ~mask
    return mode


@cmd("chmod", help=("change file mode bits", "chmod [-R] MODE FILE...", [("755 / 600", "octal: owner, group, others"), ("u+x,g-w", "symbolic"), ("-R", "recursive")]))
def c_chmod(ctx):
    args = ctx.argv[1:]
    rec = "-R" in args
    args = [a for a in args if a != "-R"]
    if len(args) < 2:
        ctx.err("missing operand")
        return 1
    spec, paths = args[0], args[1:]
    rc = 0
    for p, node in _targets(ctx, paths, rec):
        if not ctx.root and node.owner != ctx.user:
            ctx.err("changing permissions of '%s': Operation not permitted" % p)
            rc = 1
            continue
        if re.match(r"^[0-7]{3,4}$", spec):
            new = int(spec, 8) & 0o7777
        else:
            new = _apply_symbolic(node.mode, spec, node.kind == "d")
            if new is None:
                ctx.err("invalid mode: '%s'" % spec)
                return 1
        node.mode = new
        node.ctime = ctx.fs.tick()
    return rc


@cmd("chown", help=("change file owner and group (root only)", "chown [-R] USER[:GROUP] FILE...", [("-R", "recursive")]))
def c_chown(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="Rvhf")
    if opts is None:
        return 1
    if len(args) < 2:
        ctx.err("missing operand")
        return 1
    spec, paths = args[0], args[1:]
    user, _, group = spec.partition(":")
    if user and user not in _users(ctx.fs):
        ctx.err("invalid user: '%s'" % spec)
        return 1
    if group and group not in _groups(ctx.fs):
        ctx.err("invalid group: '%s'" % spec)
        return 1
    rc = 0
    for p, node in _targets(ctx, paths, "R" in opts):
        if not ctx.root:
            ctx.err("changing ownership of '%s': Operation not permitted" % p)
            rc = 1
            continue
        if user:
            node.owner = user
        if group:
            node.group = group
        elif _ and user:          # "chown bob:" = bob's login group
            node.group = user
        node.ctime = ctx.fs.tick()
    return rc


@cmd("chgrp", help=("change group ownership", "chgrp [-R] GROUP FILE...", [("-R", "recursive")]))
def c_chgrp(ctx):
    opts, args = getopts(ctx, ctx.argv[1:], flags="Rvhf")
    if opts is None:
        return 1
    if len(args) < 2:
        ctx.err("missing operand")
        return 1
    group, paths = args[0], args[1:]
    if group not in _groups(ctx.fs):
        ctx.err("invalid group: '%s'" % group)
        return 1
    rc = 0
    for p, node in _targets(ctx, paths, "R" in opts):
        if not ctx.root and node.owner != ctx.user:
            ctx.err("changing group of '%s': Operation not permitted" % p)
            rc = 1
            continue
        node.group = group
    return rc
