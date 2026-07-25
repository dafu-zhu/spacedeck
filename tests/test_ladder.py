import datetime

import pytest

from spacedeck import ladder

D = datetime.date(2026, 7, 25)


# --- the rung belongs to the user ----------------------------------------------

@pytest.mark.parametrize("grade", ladder.GRADES)
@pytest.mark.parametrize("rung", ladder.RUNGS)
def test_grading_never_changes_the_rung(rung, grade):
    assert ladder.advance(rung, 3, grade, D)[0] == rung


def test_a_recall_card_stays_recall_however_well_it_goes():
    rung, interval, _, _ = ladder.advance("recall", 1, "easy", D)
    assert (rung, interval) == ("recall", 7)


def test_a_derive_card_stays_derive_however_badly_it_goes():
    rung, interval, _, _ = ladder.advance("derive", 16, "again", D)
    assert (rung, interval) == ("derive", 1)


# --- the interval is earned -----------------------------------------------------

def test_good_steps_one_rung_up_the_ladder():
    assert ladder.advance("recall", 1, "good", D) == ("recall", 3, datetime.date(2026, 7, 28), "active")


def test_again_resets_to_the_first_interval():
    assert ladder.advance("derive", 16, "again", D) == ("derive", 1, datetime.date(2026, 7, 26), "active")


def test_hard_pins_the_interval_to_three():
    assert ladder.advance("derive", 35, "hard", D) == ("derive", 3, datetime.date(2026, 7, 28), "active")


def test_easy_skips_one_ladder_step():
    assert ladder.advance("recall", 3, "easy", D) == ("recall", 16, datetime.date(2026, 8, 10), "active")


def test_ladder_position_caps_at_the_last_entry():
    assert ladder.advance("derive", 16, "easy", D) == ("derive", 35, datetime.date(2026, 8, 29), "active")


def test_unknown_interval_is_treated_as_ladder_start():
    assert ladder.advance("recall", 99, "good", D)[1] == 3


# --- retirement -----------------------------------------------------------------

def test_good_at_the_longest_interval_retires():
    assert ladder.advance("derive", 35, "good", D) == ("derive", None, None, "retired")


def test_easy_at_the_longest_interval_retires():
    assert ladder.advance("recall", 35, "easy", D) == ("recall", None, None, "retired")


def test_hard_at_the_longest_interval_does_not_retire():
    assert ladder.advance("derive", 35, "hard", D)[3] == "active"


def test_again_at_the_longest_interval_does_not_retire():
    assert ladder.advance("derive", 35, "again", D)[3] == "active"


# --- configurable ladder --------------------------------------------------------

def test_a_custom_ladder_is_honoured():
    assert ladder.advance("recall", 2, "good", D, ladder=[2, 5, 9])[1] == 5


def test_a_custom_ladder_sets_its_own_retirement_point():
    assert ladder.advance("recall", 9, "good", D, ladder=[2, 5, 9])[3] == "retired"


def test_a_single_entry_ladder_does_not_index_out_of_range():
    assert ladder.advance("recall", 1, "hard", D, ladder=[1])[1] == 1


# --- validation and estimates ---------------------------------------------------

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
