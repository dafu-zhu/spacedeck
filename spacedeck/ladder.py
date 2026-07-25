"""Spaced-repetition ladder arithmetic.

Two things are deliberately separate:

**The rung is yours.** `recall` or `derive` says how you want to be tested on a card —
state it from memory, or reproduce it on paper. That is a property of the material,
not of your performance, so grading never changes it. A derivation was always a
derivation; being promoted "up to derive" after one good day made no sense. Set it
when you create the card and edit it whenever you disagree with your past self.

**The interval is earned.** Grades move the card along LADDER and nowhere else.
"""

import datetime

LADDER = [1, 3, 7, 16, 35]
RUNGS = ("recall", "derive")
GRADES = ("again", "hard", "good", "easy")

RETIRE_INTERVAL = LADDER[-1]

#: Rough per-card cost, for schedulers sizing a review block.
MINUTES = {"recall": 2, "derive": 8}


def _position(interval, ladder):
    """Index of `interval` on the ladder; anything unrecognised starts over."""
    try:
        return ladder.index(interval)
    except ValueError:
        return 0


def estimate_minutes(rung):
    """How long one card at `rung` usually takes."""
    if rung not in RUNGS:
        raise ValueError(f"unknown rung: {rung!r}")
    return MINUTES[rung]


def advance(rung, interval, grade, today, ladder=None):
    """Return (rung, interval, next_due, status) after applying `grade`.

    `rung` is echoed back unchanged — it is the user's label, not the engine's.
    A retired card returns (rung, None, None, "retired").
    """
    ladder = list(ladder) if ladder else LADDER
    if grade not in GRADES:
        raise ValueError(f"unknown grade: {grade!r}")
    if rung not in RUNGS:
        raise ValueError(f"unknown rung: {rung!r}")

    if grade in ("good", "easy") and interval == ladder[-1]:
        return rung, None, None, "retired"

    if grade == "again":
        position = 0
    elif grade == "hard":
        # Pinned outright rather than nudged: recall that needed effort should come
        # back soon even if the card had been sitting at a long interval.
        position = min(1, len(ladder) - 1)
    else:
        step = 1 if grade == "good" else 2
        position = min(_position(interval, ladder) + step, len(ladder) - 1)

    new_interval = ladder[position]
    return rung, new_interval, today + datetime.timedelta(days=new_interval), "active"
