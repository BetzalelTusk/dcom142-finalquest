#!/usr/bin/env python3
"""FINAL QUEST: Rocky Rescue - a terminal game for the DCOM 142 final (Modules 6-12).

    python finalquest.py              full experience
    python finalquest.py --no-intro   skip the boot animation
    python finalquest.py --no-anim    no animations
    python finalquest.py --plain      ASCII only (for terminals that show boxes instead of symbols)

Standard library only. Python 3.8+. Self-study only: do not use during graded work.
"""
from finalquest.game import main

if __name__ == "__main__":
    main()
