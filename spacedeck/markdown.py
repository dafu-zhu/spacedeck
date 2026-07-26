"""Markdown for card bodies, with the math left alone.

Cards are Markdown read by two different readers, and they disagree about
punctuation. `_` opens emphasis for one and a subscript for the other; `|` ends
a table cell for one and sits inside `\\left|` for the other; `<` opens a tag for
one and means less-than for the other. So math and code come out first and are
replaced by placeholders, the Markdown pass runs over what is left, and the
stashed spans go back in escaped but never reformatted.

The subset is deliberately small — paragraphs, headings, emphasis, code, links,
lists, block quotes, rules, and pipe tables. Nested lists are not supported and
render flat. Anything unrecognised passes through as text, because a card that
renders plainly beats a card that renders wrongly.
"""

import html as html_mod
import re

# A placeholder can appear inside a table cell or an emphasis run, so it must
# contain nothing either pass reacts to: NUL, digits, NUL.
_PLACEHOLDER = "\x00{}\x00"
_PLACEHOLDER_RE = re.compile(r"\x00(\d+)\x00")

# Ordered: fenced code, display math, inline math, inline code. Leftmost-longest
# would break `$$x$$` into two inline spans, so display math is tried first.
_STASH_RE = re.compile(
    r"```[^\n]*\n.*?(?:\n```|\Z)"       # fenced code block
    r"|\$\$.+?\$\$"                     # display math
    r"|\$(?:\\.|[^$\\\n])+\$"           # inline math, one line
    r"|`[^`\n]+`",                      # inline code
    re.DOTALL,
)

_HEADING = re.compile(r"(#{1,6})\s+(.*)$")
_HR = re.compile(r"\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_BULLET = re.compile(r"\s*[-*+]\s+(.*)$")
_ORDERED = re.compile(r"\s*\d+[.)]\s+(.*)$")
_DELIM = re.compile(r"^[\s|:-]+$")


def to_html(text):
    """Render one card body. Math spans come back escaped but otherwise verbatim."""
    if not text or not text.strip():
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    vault = []
    lines = _stash(text, vault).split("\n")
    return _restore("\n".join(_blocks(lines, vault)), vault)


# --- stashing ---------------------------------------------------------------

def _stash(text, vault):
    def take(match):
        vault.append(match.group(0))
        return _PLACEHOLDER.format(len(vault) - 1)

    return _STASH_RE.sub(take, text)


def _restore(html, vault):
    def put(match):
        raw = vault[int(match.group(1))]
        if raw.startswith("```"):
            return _fence_html(raw)
        if raw.startswith("`"):
            return f"<code>{html_mod.escape(raw[1:-1])}</code>"
        return html_mod.escape(raw)  # math: escaped for HTML, untouched for MathJax

    return _PLACEHOLDER_RE.sub(put, html)


def _fence_html(raw):
    body = raw[3:]
    body = body.split("\n", 1)[1] if "\n" in body else ""
    body = body.removesuffix("```")
    return f"<pre><code>{html_mod.escape(body.strip('\n'))}</code></pre>"


def _lone_fence(line, vault):
    match = _PLACEHOLDER_RE.fullmatch(line.strip())
    return bool(match) and vault[int(match.group(1))].startswith("```")


# --- block level ------------------------------------------------------------

def _blocks(lines, vault):
    out, i = [], 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
        elif _lone_fence(lines[i], vault):
            out.append(lines[i].strip())
            i += 1
        elif _HEADING.match(lines[i]):
            out.append(_heading(lines[i]))
            i += 1
        elif _is_table(lines, i):
            block, i = _table(lines, i)
            out.append(block)
        elif _HR.match(lines[i]):
            out.append("<hr>")
            i += 1
        elif _BULLET.match(lines[i]) or _ORDERED.match(lines[i]):
            block, i = _list(lines, i, vault)
            out.append(block)
        elif lines[i].lstrip().startswith(">"):
            block, i = _quote(lines, i, vault)
            out.append(block)
        else:
            block, i = _paragraph(lines, i, vault)
            out.append(block)
    return out


def _starts_block(lines, i, vault):
    line = lines[i]
    return (
        not line.strip()
        or _lone_fence(line, vault)
        or bool(_HEADING.match(line))
        or _HR.match(line) is not None
        or _is_table(lines, i)
        or _BULLET.match(line) is not None
        or _ORDERED.match(line) is not None
        or line.lstrip().startswith(">")
    )


def _heading(line):
    hashes, text = _HEADING.match(line).groups()
    # The page already spends h2 on the section label, so a card's own headings
    # start below it.
    level = min(len(hashes) + 2, 6)
    return f"<h{level}>{_inline(text)}</h{level}>"


def _paragraph(lines, i, vault):
    buf = [lines[i]]
    j = i + 1
    while j < len(lines) and not _starts_block(lines, j, vault):
        buf.append(lines[j])
        j += 1
    parts = []
    for k, raw in enumerate(buf):
        segment = _inline(raw.strip())
        if k < len(buf) - 1:
            segment += "<br>" if raw.endswith("  ") else " "
        parts.append(segment)
    return "<p>" + "".join(parts) + "</p>", j


def _list(lines, i, vault):
    ordered = _ORDERED.match(lines[i]) is not None
    matcher = _ORDERED if ordered else _BULLET
    items, j = [], i
    while j < len(lines):
        match = matcher.match(lines[j])
        if match:
            items.append([match.group(1)])
            j += 1
        elif items and lines[j].strip() and not _starts_block(lines, j, vault):
            items[-1].append(lines[j].strip())  # lazy continuation
            j += 1
        else:
            break
    tag = "ol" if ordered else "ul"
    cells = "".join(f"<li>{_inline(' '.join(parts))}</li>" for parts in items)
    return f"<{tag}>{cells}</{tag}>", j


def _quote(lines, i, vault):
    buf, j = [], i
    while j < len(lines) and lines[j].lstrip().startswith(">"):
        buf.append(re.sub(r"^\s*>\s?", "", lines[j]))
        j += 1
    return "<blockquote>" + "".join(_blocks(buf, vault)) + "</blockquote>", j


# --- tables -----------------------------------------------------------------

def _is_table(lines, i):
    if i + 1 >= len(lines) or "|" not in lines[i]:
        return False
    delim = lines[i + 1]
    return "|" in delim and "-" in delim and _DELIM.fullmatch(delim) is not None


def _cells(line):
    line = line.strip()
    line = line.removeprefix("|")
    line = line.removesuffix("|")
    return [cell.strip() for cell in line.split("|")]


def _aligns(delim):
    out = []
    for cell in _cells(delim):
        left, right = cell.startswith(":"), cell.endswith(":")
        out.append("center" if left and right else "right" if right else None)
    return out


def _cell(tag, text, align):
    style = f' style="text-align: {align}"' if align else ""
    return f"<{tag}{style}>{_inline(text)}</{tag}>"


def _row(tag, cells, aligns):
    out = []
    for k, text in enumerate(cells):
        out.append(_cell(tag, text, aligns[k] if k < len(aligns) else None))
    return "<tr>" + "".join(out) + "</tr>"


def _table(lines, i):
    header = _cells(lines[i])
    aligns = _aligns(lines[i + 1])
    rows, j = [], i + 2
    while j < len(lines) and lines[j].strip() and "|" in lines[j]:
        rows.append(_cells(lines[j]))
        j += 1
    html = ["<table><thead>", _row("th", header, aligns), "</thead>"]
    if rows:
        html.append("<tbody>")
        html.extend(_row("td", row, aligns) for row in rows)
        html.append("</tbody>")
    html.append("</table>")
    return "".join(html), j


# --- inline -----------------------------------------------------------------

def _inline(text):
    text = html_mod.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(?=\S)([^*]+?)(?<=\S)\*", r"<em>\1</em>", text)
    # Leading guard keeps `some_name` and a stray trailing underscore intact.
    text = re.sub(r"(?<![\w\\])_(?=\S)([^_]+?)(?<=\S)_(?!\w)", r"<em>\1</em>", text)
    return text
