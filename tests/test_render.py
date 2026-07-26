import pytest

from spacedeck import paths, render


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEDECK_HOME", str(tmp_path / "runtime"))


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "notes"
    r.mkdir()
    return r


def test_page_embeds_heading_and_body(repo):
    html = render.page(repo, "Prompt", [("Prompt", "State the CLT.")])
    assert "State the CLT." in html
    assert "<h2>Prompt</h2>" in html


def test_page_auto_refreshes(repo):
    assert 'http-equiv="refresh"' in render.page(repo, "Prompt", [("Prompt", "x")])


def test_page_escapes_html_but_leaves_math_alone(repo):
    html = render.page(repo, "Prompt", [("Prompt", "a < b and $x^2$")])
    assert "a &lt; b" in html
    assert "$x^2$" in html


def test_page_renders_several_sections_in_order(repo):
    html = render.page(repo, "Reveal", [("Prompt", "the ask"), ("Answer", "the check")])
    assert html.index("the ask") < html.index("the check")


def test_page_notes_when_math_is_not_vendored(repo):
    html = render.page(repo, "Prompt", [("Prompt", "x")])
    assert "not vendored" in html
    assert "MathJax-script" not in html


def test_page_uses_the_local_bundle_when_present(repo):
    paths.mathjax(repo).write_text("// pretend bundle", encoding="utf-8")
    html = render.page(repo, "Prompt", [("Prompt", "x")])
    assert "MathJax-script" in html
    assert "tex-svg.js" in html


def test_page_never_reaches_a_cdn_when_vendored(repo):
    paths.mathjax(repo).write_text("// pretend bundle", encoding="utf-8")
    html = render.page(repo, "Prompt", [("Prompt", "x")])
    assert "cdn." not in html
    assert "file:" in html


def test_write_creates_the_file(repo):
    p = render.write(repo, "Prompt", [("Prompt", "x")])
    assert p.exists() and p.name == "card.html"


def test_write_overwrites_in_place(repo):
    # Distinctive markers: the stylesheet itself contains the word "first"
    # (section:first-of-type), so a plain "first" not in text assertion lies.
    first = render.write(repo, "Prompt", [("Prompt", "PROMPT_MARKER")])
    second = render.write(repo, "Answer", [("Answer", "ANSWER_MARKER")])
    assert first == second
    text = second.read_text(encoding="utf-8")
    assert "ANSWER_MARKER" in text and "PROMPT_MARKER" not in text


def test_two_repos_render_to_separate_pages(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert render.write(a, "P", [("P", "x")]) != render.write(b, "P", [("P", "y")])


# --- markdown ---------------------------------------------------------------

def test_page_renders_markdown_tables(repo):
    html = render.page(repo, "Answer", [("Answer", "| a | b |\n|---|---|\n| 1 | 2 |")])
    assert "<table>" in html
    assert "|---|" not in html


def test_page_renders_emphasis(repo):
    html = render.page(repo, "Answer", [("Answer", "**Case A** — buy it")])
    assert "<strong>Case A</strong>" in html
    assert "**Case A**" not in html


def test_page_keeps_math_beside_rendered_markdown(repo):
    html = render.page(repo, "Answer", [("Answer", "**net** $F_t - S_t > 0$")])
    assert "<strong>net</strong>" in html
    assert "$F_t - S_t &gt; 0$" in html


def test_a_broken_markdown_pass_still_renders_the_card(repo, monkeypatch):
    def explode(_):
        raise RuntimeError("bad pattern")

    monkeypatch.setattr(render.markdown, "to_html", explode)
    html = render.page(repo, "Answer", [("Answer", "the answer text")])
    assert "the answer text" in html


# --- lifecycle --------------------------------------------------------------

def test_the_reveal_can_stop_the_refresh(repo):
    html = render.page(repo, "Reveal", [("Answer", "x")], refresh=False)
    assert "http-equiv" not in html


def test_write_passes_the_refresh_choice_through(repo):
    target = render.write(repo, "Reveal", [("Answer", "x")], refresh=False)
    assert "http-equiv" not in target.read_text(encoding="utf-8")


def test_clear_deletes_the_page(repo):
    target = render.write(repo, "Prompt", [("Prompt", "x")])
    assert render.clear(repo) is True
    assert not target.exists()


def test_clear_is_quiet_when_there_is_nothing_to_clear(repo):
    assert render.clear(repo) is False


def test_clear_leaves_the_other_runtime_files_alone(repo):
    paths.mathjax(repo).write_text("// bundle", encoding="utf-8")
    render.write(repo, "Prompt", [("Prompt", "x")])
    render.clear(repo)
    assert paths.mathjax(repo).is_file()


def test_clear_touches_only_this_repo(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    render.write(a, "P", [("P", "x")])
    kept = render.write(b, "P", [("P", "y")])
    render.clear(a)
    assert kept.exists()
