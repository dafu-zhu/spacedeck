import datetime
import textwrap

import pytest

from spacedeck import card

SAMPLE = textwrap.dedent("""\
    ---
    subject: probability
    topic: Central limit theorem
    tier: P0
    rung: derive
    interval: 3
    next_due: 2026-07-22
    status: active
    history:
      - { date: 2026-07-18, grade: seed }
      - { date: 2026-07-19, grade: good }
    source: notes/README.md
    ---

    ## Prompt

    State the CLT for i.i.d. $X_i$.

    ## Answer

    Finite variance is the whole hypothesis.
    """)


def _write(tmp_path, text=SAMPLE):
    p = tmp_path / "clt.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_read_parses_scalar_fields(tmp_path):
    c = card.read(_write(tmp_path))
    assert c.fields["subject"] == "probability"
    assert c.fields["rung"] == "derive"
    assert c.fields["interval"] == "3"


def test_read_parses_history_entries(tmp_path):
    c = card.read(_write(tmp_path))
    assert c.history == [
        {"date": "2026-07-18", "grade": "seed"},
        {"date": "2026-07-19", "grade": "good"},
    ]


def test_read_keeps_body_verbatim(tmp_path):
    c = card.read(_write(tmp_path))
    assert "State the CLT for i.i.d. $X_i$." in c.body
    assert c.body.startswith("\n## Prompt")


def test_round_trip_is_byte_identical(tmp_path):
    p = _write(tmp_path)
    original = p.read_text(encoding="utf-8")
    card.write(card.read(p))
    assert p.read_text(encoding="utf-8") == original


def test_write_persists_changed_fields(tmp_path):
    p = _write(tmp_path)
    c = card.read(p)
    c.fields["rung"] = "recall"
    c.fields["interval"] = "1"
    c.fields["next_due"] = "2026-07-26"
    card.write(c)
    reread = card.read(p)
    assert (reread.fields["rung"], reread.fields["interval"]) == ("recall", "1")
    assert "Finite variance is the whole hypothesis." in reread.body


def test_append_history_adds_entry(tmp_path):
    p = _write(tmp_path)
    c = card.read(p)
    card.append_history(c, datetime.date(2026, 7, 25), "hard")
    card.write(c)
    assert card.read(p).history[-1] == {"date": "2026-07-25", "grade": "hard"}


def test_due_date_parses(tmp_path):
    assert card.due_date(card.read(_write(tmp_path))) == datetime.date(2026, 7, 22)


def test_due_date_is_none_when_null(tmp_path):
    p = _write(tmp_path, SAMPLE.replace("next_due: 2026-07-22", "next_due: null"))
    assert card.due_date(card.read(p)) is None


def test_unknown_keys_survive_round_trip(tmp_path):
    p = _write(tmp_path, SAMPLE.replace("source: notes", "extra: keepme\nsource: notes"))
    card.write(card.read(p))
    assert "extra: keepme" in p.read_text(encoding="utf-8")


def test_missing_opening_delimiter_raises(tmp_path):
    p = tmp_path / "broken.md"
    p.write_text("no frontmatter here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        card.read(p)


def test_missing_closing_delimiter_raises(tmp_path):
    p = tmp_path / "broken.md"
    p.write_text("---\nsubject: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        card.read(p)


def test_body_is_empty_when_card_is_freshly_minted(tmp_path):
    p = _write(tmp_path, "---\nsubject: x\nstatus: active\nhistory:\n---\n")
    assert card.read(p).body == ""


def test_is_stub_false_for_a_filled_card(tmp_path):
    assert not card.is_stub(card.read(_write(tmp_path)))


def test_is_stub_true_when_sections_are_empty(tmp_path):
    empty = SAMPLE.split("## Prompt")[0] + "## Prompt\n\n## Answer\n\n## Notes\n"
    assert card.is_stub(card.read(_write(tmp_path, empty)))


def test_is_stub_true_when_answer_is_empty_but_prompt_is_written(tmp_path):
    half = SAMPLE.split("## Answer")[0] + "## Answer\n\n"
    assert card.is_stub(card.read(_write(tmp_path, half)))


def test_is_stub_true_when_headings_are_missing_entirely(tmp_path):
    bare = SAMPLE.split("## Prompt")[0]
    assert card.is_stub(card.read(_write(tmp_path, bare)))
