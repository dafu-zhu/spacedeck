import datetime

import pytest

from spacedeck import card, mint

TODAY = datetime.date(2026, 7, 25)


def test_slugify_lowercases_and_hyphenates():
    assert mint.slugify("Central limit theorem (L5)") == "central-limit-theorem-l5"


def test_slugify_collapses_repeated_separators():
    assert mint.slugify("A  --  B") == "a-b"


def test_slugify_transliterates_accents_and_drops_symbols():
    assert mint.slugify("Itô's isometry!") == "ito-s-isometry"


def test_create_writes_to_subject_folder(tmp_path):
    p = mint.create(tmp_path, "probability", "Ito isometry", TODAY)
    assert p == tmp_path / "probability" / "ito-isometry.md"
    assert p.exists()


def test_created_card_starts_at_recall_due_tomorrow(tmp_path):
    c = card.read(mint.create(tmp_path, "probability", "Ito isometry", TODAY))
    assert c.fields["rung"] == "recall"
    assert c.fields["interval"] == "1"
    assert c.fields["next_due"] == "2026-07-26"
    assert c.fields["status"] == "active"


def test_created_card_has_seed_history(tmp_path):
    c = card.read(mint.create(tmp_path, "probability", "Ito isometry", TODAY))
    assert c.history == [{"date": "2026-07-25", "grade": "seed"}]


def test_created_card_is_a_stub_awaiting_the_user(tmp_path):
    c = card.read(mint.create(tmp_path, "probability", "Ito isometry", TODAY))
    assert card.is_stub(c)


def test_created_body_carries_the_section_headings(tmp_path):
    body = card.read(mint.create(tmp_path, "probability", "X", TODAY)).body
    assert "## Prompt" in body and "## Answer" in body


def test_create_refuses_to_overwrite(tmp_path):
    mint.create(tmp_path, "probability", "Ito isometry", TODAY)
    with pytest.raises(FileExistsError):
        mint.create(tmp_path, "probability", "Ito isometry", TODAY)


def test_create_records_tier_and_source(tmp_path):
    c = card.read(mint.create(tmp_path, "probability", "X", TODAY, tier="P1", source="notes/ch3.md"))
    assert c.fields["tier"] == "P1"
    assert c.fields["source"] == "notes/ch3.md"


# --- customisable card skeleton -------------------------------------------------

CUSTOM = "## Question\n\n## Working\n\n## Source\n"


def test_repo_template_overrides_the_builtin(tmp_path):
    (tmp_path / "_template.md").write_text(CUSTOM, encoding="utf-8")
    body = card.read(mint.create(tmp_path, "history", "Treaty of Westphalia", TODAY)).body
    assert "## Question" in body and "## Working" in body
    assert "## Prompt" not in body


def test_builtin_template_is_used_when_the_repo_has_none(tmp_path):
    body = card.read(mint.create(tmp_path, "probability", "X", TODAY)).body
    assert "## Prompt" in body


def test_template_path_reports_which_one_is_in_play(tmp_path):
    assert mint.template_path(tmp_path).name == "card.md"
    (tmp_path / "_template.md").write_text(CUSTOM, encoding="utf-8")
    assert mint.template_path(tmp_path) == tmp_path / "_template.md"


def test_template_is_not_mistaken_for_a_card(tmp_path):
    from spacedeck import queue

    (tmp_path / "_template.md").write_text(CUSTOM, encoding="utf-8")
    mint.create(tmp_path, "probability", "X", TODAY)
    assert len(queue.load(tmp_path)) == 1
