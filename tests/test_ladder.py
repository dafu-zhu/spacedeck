import datetime

import pytest

from spacedeck import ladder

D = datetime.date(2026, 7, 25)


def test_good_at_recall_promotes_to_derive_and_steps_ladder():
    assert ladder.advance("recall", 1, "good", D) == ("derive", 3, datetime.date(2026, 7, 28), "active")


def test_again_resets_rung_and_interval():
    assert ladder.advance("derive", 16, "again", D) == ("recall", 1, datetime.date(2026, 7, 26), "active")


def test_hard_keeps_rung_and_pins_interval_to_three():
    assert ladder.advance("derive", 35, "hard", D) == ("derive", 3, datetime.date(2026, 7, 28), "active")


def test_easy_skips_one_ladder_step():
    assert ladder.advance("recall", 3, "easy", D) == ("derive", 16, datetime.date(2026, 8, 10), "active")


def test_ladder_position_caps_at_last_entry():
    assert ladder.advance("derive", 16, "easy", D) == ("derive", 35, datetime.date(2026, 8, 29), "active")


def test_rung_caps_at_derive():
    rung, _, _, _ = ladder.advance("derive", 3, "good", D)
    assert rung == "derive"


def test_good_at_derive_on_max_interval_retires():
    assert ladder.advance("derive", 35, "good", D) == ("derive", None, None, "retired")


def test_easy_at_derive_on_max_interval_retires():
    assert ladder.advance("derive", 35, "easy", D) == ("derive", None, None, "retired")


def test_recall_at_max_interval_does_not_retire():
    rung, interval, _, status = ladder.advance("recall", 35, "good", D)
    assert (rung, interval, status) == ("derive", 35, "active")


def test_unknown_interval_is_treated_as_ladder_start():
    assert ladder.advance("recall", 99, "good", D)[1] == 3


def test_rejects_unknown_grade():
    with pytest.raises(ValueError):
        ladder.advance("recall", 1, "green", D)


def test_rejects_unknown_rung():
    with pytest.raises(ValueError):
        ladder.advance("apply", 1, "good", D)


def test_estimate_minutes_differs_by_rung():
    assert ladder.estimate_minutes("recall") < ladder.estimate_minutes("derive")


def test_estimate_minutes_rejects_unknown_rung():
    with pytest.raises(ValueError):
        ladder.estimate_minutes("apply")
