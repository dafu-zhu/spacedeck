from spacedeck import markdown

# --- the reason this module exists ------------------------------------------

def test_math_survives_the_markdown_pass_verbatim():
    html = markdown.to_html("The forward $F_t = S_t e^{r(T_2-t)}$ holds.")
    assert "$F_t = S_t e^{r(T_2-t)}$" in html


def test_underscores_in_math_do_not_become_emphasis():
    html = markdown.to_html("$S_t$ and $F_t$ both move.")
    assert "<em>" not in html
    assert "$S_t$" in html and "$F_t$" in html


def test_less_than_in_math_is_escaped_not_swallowed():
    # MathJax reads decoded text, so the delimiters must survive escaping.
    html = markdown.to_html("Case $F_t < S_t$ — buy the asset.")
    assert "$F_t &lt; S_t$" in html


def test_a_pipe_inside_math_does_not_split_a_table_cell():
    html = markdown.to_html("| a | $\\left| x \\right|$ |\n|---|---|\n| 1 | 2 |")
    assert html.count("</th>") == 2  # the pipes inside the math made no third cell
    assert "\\left| x \\right|" in html


def test_dollars_inside_a_fenced_block_are_not_math():
    html = markdown.to_html("```\ncost is $5 and $6\n```")
    assert "<pre><code>" in html
    assert "cost is $5 and $6" in html


# --- the arbitrage table from a real card -----------------------------------

ARBITRAGE = """**Case $F_t > S_t e^{r(T_2-t)}$** — buy the asset, short the forward:

| | time $t$ | time $T_2$ |
|---|---|---|
| buy stock | $-S_t$ | deliver it |
| **net** | 0 | $F_t - S_t e^{r(T_2-t)} > 0$ |

Riskless profit from zero cost."""


def test_a_real_card_renders_table_and_bold():
    html = markdown.to_html(ARBITRAGE)
    assert "<table>" in html and "</table>" in html
    assert "<strong>Case" in html
    assert "<strong>net</strong>" in html
    assert "|---|" not in html  # the delimiter row must never reach the page
    assert "**" not in html


def test_a_real_card_keeps_every_math_span():
    html = markdown.to_html(ARBITRAGE)
    assert "$-S_t$" in html
    assert "$F_t - S_t e^{r(T_2-t)} &gt; 0$" in html


def test_table_header_and_body_are_separated():
    html = markdown.to_html(ARBITRAGE)
    assert html.index("<thead>") < html.index("<tbody>")
    assert html.count("<tr>") == 3  # one header, two rows


def test_an_empty_leading_cell_is_kept():
    html = markdown.to_html("| | a |\n|---|---|\n| b | c |")
    assert "<th></th>" in html


def test_table_alignment_is_honoured():
    html = markdown.to_html("| a | b |\n|:--|--:|\n| 1 | 2 |")
    assert 'style="text-align: right"' in html
    assert "text-align: left" not in html  # left is the default; no style needed


# --- ordinary Markdown ------------------------------------------------------

def test_bold_and_italic():
    html = markdown.to_html("**bold** and *slanted* text")
    assert "<strong>bold</strong>" in html
    assert "<em>slanted</em>" in html


def test_underscore_inside_a_word_is_not_emphasis():
    assert "<em>" not in markdown.to_html("call some_helper_name here")


def test_inline_code_is_not_reformatted():
    html = markdown.to_html("run `spacedeck due --json` first")
    assert "<code>spacedeck due --json</code>" in html


def test_headings_start_below_the_section_label():
    assert "<h3>Setup</h3>" in markdown.to_html("# Setup")
    assert "<h4>Detail</h4>" in markdown.to_html("## Detail")


def test_bullet_list():
    html = markdown.to_html("- first\n- second")
    assert html == "<ul><li>first</li><li>second</li></ul>"


def test_ordered_list():
    html = markdown.to_html("1. first\n2. second")
    assert html.startswith("<ol>") and "<li>second</li>" in html


def test_a_paragraph_joins_soft_wrapped_lines():
    html = markdown.to_html("one line\nand its continuation")
    assert html == "<p>one line and its continuation</p>"


def test_two_trailing_spaces_force_a_break():
    assert "<br>" in markdown.to_html("one line  \nnext line")


def test_blank_line_starts_a_new_paragraph():
    assert markdown.to_html("first\n\nsecond").count("<p>") == 2


def test_links():
    html = markdown.to_html("see [the notes](https://example.com/x)")
    assert '<a href="https://example.com/x">the notes</a>' in html


def test_horizontal_rule():
    assert "<hr>" in markdown.to_html("above\n\n---\n\nbelow")


def test_block_quote():
    html = markdown.to_html("> quoted claim")
    assert "<blockquote>" in html and "quoted claim" in html


def test_html_in_card_text_is_escaped():
    html = markdown.to_html("compare a < b and <script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_body_renders_nothing():
    assert markdown.to_html("") == ""
    assert markdown.to_html("   \n  ") == ""


def test_display_math_stays_one_block():
    html = markdown.to_html("Then\n\n$$\n\\sqrt{n}(\\bar X_n - \\mu)/\\sigma\n$$\n\ndone.")
    assert "$$\n\\sqrt{n}(\\bar X_n - \\mu)/\\sigma\n$$" in html


def test_windows_line_endings():
    assert markdown.to_html("- a\r\n- b") == "<ul><li>a</li><li>b</li></ul>"
