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


def test_work_rel_is_subject_over_topic_slug():
    assert mint.work_rel("probability", "Ito isometry") == "probability/ito-isometry"


def test_work_rel_carries_nothing_machine_specific():
    """This string is written into a card and travels with it to other machines."""
    rel = mint.work_rel("Real Analysis", "Dominated convergence")
    assert rel == "real-analysis/dominated-convergence"
    assert "\\" not in rel
    assert not rel.startswith("/")
    assert ":" not in rel  # no drive letter
    assert "~" not in rel


def test_a_new_card_records_its_work_folder(tmp_path):
    c = card.read(mint.create(tmp_path, "probability", "Ito isometry", TODAY))
    assert c.fields["work"] == "probability/ito-isometry"


def test_work_rel_of_falls_back_for_a_card_minted_before_the_field(tmp_path):
    path = mint.create(tmp_path, "probability", "Ito isometry", TODAY)
    c = card.read(path)
    del c.fields["work"]
    card.write(c)
    assert mint.work_rel_of(card.read(path)) == "probability/ito-isometry"


def test_work_rel_of_prefers_what_the_card_says(tmp_path):
    c = card.read(mint.create(tmp_path, "probability", "Ito isometry", TODAY))
    c.fields["work"] = "somewhere/else"
    assert mint.work_rel_of(c) == "somewhere/else"


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
