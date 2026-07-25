import datetime
import textwrap
import pytest


from spacedeck import queue

TODAY = datetime.date(2026, 7, 25)

CARD = textwrap.dedent("""\
    ---
    subject: {subject}
    topic: {topic}
    tier: {tier}
    rung: {rung}
    interval: 1
    next_due: {due}
    status: {status}
    history:
      - {{ date: {seen}, grade: good }}
    source: notes/README.md
    ---

    ## Prompt

    q
    """)


def _card(tmp_path, name, **kw):
    kw.setdefault("subject", "probability")
    kw.setdefault("topic", "T")
    kw.setdefault("tier", "P0")
    kw.setdefault("rung", "recall")
    kw.setdefault("status", "active")
    kw.setdefault("due", "2026-07-25")
    kw.setdefault("seen", "2026-07-25")
    d = tmp_path / kw["subject"]
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(CARD.format(**kw), encoding="utf-8")
    return p


def test_load_finds_cards_in_subject_folders(tmp_path):
    _card(tmp_path, "a")
    _card(tmp_path, "b", subject="analysis")
    assert len(queue.load(tmp_path)) == 2


def test_due_excludes_future_and_retired(tmp_path):
    _card(tmp_path, "today")
    _card(tmp_path, "later", due="2026-08-01")
    _card(tmp_path, "gone", status="retired")
    assert [c.fields["topic"] for c in queue.due(queue.load(tmp_path), TODAY)] == ["T"]


def test_due_sorts_oldest_first_then_by_tier(tmp_path):
    _card(tmp_path, "old", topic="OLD", due="2026-07-20")
    _card(tmp_path, "p1", topic="P1", due="2026-07-25", tier="P1")
    _card(tmp_path, "p0", topic="P0", due="2026-07-25", tier="P0")
    order = [c.fields["topic"] for c in queue.due(queue.load(tmp_path), TODAY)]
    assert order == ["OLD", "P0", "P1"]


def test_render_lists_due_and_upcoming_separately(tmp_path):
    _card(tmp_path, "due", topic="DUENOW")
    _card(tmp_path, "soon", topic="SOON", due="2026-07-28")
    out = queue.render(queue.load(tmp_path), TODAY)
    due_block, upcoming_block = out.split("## Upcoming (next 7 days)")
    assert "DUENOW" in due_block and "SOON" not in due_block
    assert "SOON" in upcoming_block


def test_render_excludes_cards_beyond_seven_days(tmp_path):
    _card(tmp_path, "far", topic="FAR", due="2026-09-01")
    assert "FAR" not in queue.render(queue.load(tmp_path), TODAY)


def test_render_counts_active_and_retired(tmp_path):
    _card(tmp_path, "a")
    _card(tmp_path, "b", status="retired")
    out = queue.render(queue.load(tmp_path), TODAY)
    assert "Active cards: 1" in out and "Retired: 1" in out


def test_render_line_format(tmp_path):
    _card(tmp_path, "a", topic="Forward price", rung="derive", due="2026-07-25")
    out = queue.render(queue.load(tmp_path), TODAY)
    assert "- [ ] probability · Forward price — rung: derive — due 2026-07-25" in out


def test_cooling_dashboard_icon_by_staleness(tmp_path):
    _card(tmp_path, "warm", subject="probability", seen="2026-07-25")
    _card(tmp_path, "cool", subject="analysis", seen="2026-07-18")
    _card(tmp_path, "cold", subject="algebra", seen="2026-07-01")
    out = queue.render(queue.load(tmp_path), TODAY)
    assert "- probability 🔥 0d" in out
    assert "- analysis 🥶 7d" in out
    assert "- algebra 🧊 24d" in out


def test_cooling_dashboard_is_warmest_first(tmp_path):
    _card(tmp_path, "cold", subject="algebra", seen="2026-07-01")
    _card(tmp_path, "warm", subject="probability", seen="2026-07-25")
    out = queue.render(queue.load(tmp_path), TODAY)
    assert out.index("probability 🔥") < out.index("algebra 🧊")


def test_rebuild_writes_the_file(tmp_path):
    _card(tmp_path, "a", topic="WRITTEN")
    out = tmp_path / "REVIEW.md"
    queue.rebuild(tmp_path, out, TODAY)
    text = out.read_text(encoding="utf-8")
    assert "WRITTEN" in text
    assert "_Last updated: 2026-07-25_" in text


def test_rebuild_is_idempotent(tmp_path):
    _card(tmp_path, "a")
    out = tmp_path / "REVIEW.md"
    queue.rebuild(tmp_path, out, TODAY)
    first = out.read_text(encoding="utf-8")
    queue.rebuild(tmp_path, out, TODAY)
    assert out.read_text(encoding="utf-8") == first


def test_empty_sections_render_placeholders(tmp_path):
    out = queue.render([], TODAY)
    assert "_(nothing due)_" in out and "_(none)_" in out


def test_load_ignores_non_card_markdown(tmp_path):
    _card(tmp_path, "real")
    (tmp_path / "README.md").write_text("# notes on my cards\n", encoding="utf-8")
    (tmp_path / "probability" / "index.md").write_text("just an index\n", encoding="utf-8")
    assert len(queue.load(tmp_path)) == 1


def test_load_still_raises_on_a_malformed_card(tmp_path):
    _card(tmp_path, "real")
    (tmp_path / "probability" / "broken.md").write_text("---\nsubject: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        queue.load(tmp_path)


def test_queue_file_inside_the_cards_dir_is_not_parsed_as_a_card(tmp_path):
    _card(tmp_path, "a")
    inside = tmp_path / "REVIEW.md"
    queue.rebuild(tmp_path, inside, TODAY)
    first = inside.read_text(encoding="utf-8")
    queue.rebuild(tmp_path, inside, TODAY)
    assert inside.read_text(encoding="utf-8") == first
