"""Spaced-repetition ladder arithmetic.

A card advances by one grade at a time. The stored `interval` is the card's
position on LADDER, so scheduling never has to be re-derived from history — an
edit to a card's history can't knock it off the ladder.
"""

import datetime

LADDER = [1, 3, 7, 16, 35]
RUNGS = ("recall", "derive")
GRADES = ("again", "hard", "good", "easy")

RETIRE_INTERVAL = LADDER[-1]

#: Rough per-card cost, for schedulers sizing a review block.
MINUTES = {"recall": 2, "derive": 8}


def _position(interval):
    """Index of `interval` on the ladder; anything unrecognised starts over."""
    try:
        return LADDER.index(interval)
    except ValueError:
        return 0


def _next_rung(rung):
    return RUNGS[min(RUNGS.index(rung) + 1, len(RUNGS) - 1)]


def estimate_minutes(rung):
    """How long one card at `rung` usually takes."""
    if rung not in RUNGS:
        raise ValueError(f"unknown rung: {rung!r}")
    return MINUTES[rung]


def advance(rung, interval, grade, today):
    """Return (rung, interval, next_due, status) after applying `grade`.

    A retired card returns (rung, None, None, "retired").
    """
    if grade not in GRADES:
        raise ValueError(f"unknown grade: {grade!r}")
    if rung not in RUNGS:
        raise ValueError(f"unknown rung: {rung!r}")

    if grade in ("good", "easy") and rung == RUNGS[-1] and interval == RETIRE_INTERVAL:
        return rung, None, None, "retired"

    if grade == "again":
        rung, position = RUNGS[0], 0
    elif grade == "hard":
        # Pinned outright rather than nudged: recall that needed effort should be
        # re-tested soon even when the rung was earned long ago.
        position = 1
    else:
        step = 1 if grade == "good" else 2
        rung = _next_rung(rung)
        position = min(_position(interval) + step, len(LADDER) - 1)

    new_interval = LADDER[position]
    return rung, new_interval, today + datetime.timedelta(days=new_interval), "active"
