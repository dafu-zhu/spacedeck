"""Read and write card files without disturbing their bodies.

Cards are hand-edited Markdown with a small, fixed frontmatter block. A real YAML
parser would reformat the LaTeX in the bodies, so this parses only the shapes cards
actually use and copies everything else through untouched.
"""

import dataclasses
import datetime
import pathlib
import re

FIELD_ORDER = ["subject", "topic", "tier", "rung", "interval", "next_due", "status"]
TRAILING_ORDER = ["source"]

_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
_HISTORY_ENTRY_RE = re.compile(r"^\s*-\s*\{\s*date:\s*([^,]+?)\s*,\s*grade:\s*([^}]+?)\s*\}\s*$")

_NULLISH = ("null", "", "~")


@dataclasses.dataclass
class Card:
    path: pathlib.Path
    fields: dict
    history: list
    body: str


def looks_like_card(path):
    """True when the file opens with a frontmatter delimiter.

    Lets a cards directory hold a README, an index, or the generated queue file
    without those being mistaken for cards. A file that opens with `---` but is
    otherwise broken is still a card, and `read` will report it rather than let it
    disappear.
    """
    with pathlib.Path(path).open(encoding="utf-8") as fh:
        return fh.readline().rstrip("\r\n") == "---"


def read(path):
    path = pathlib.Path(path)
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing frontmatter opening delimiter")
    try:
        _, front, body = text.split("---\n", 2)
    except ValueError:
        raise ValueError(f"{path}: missing frontmatter closing delimiter") from None

    fields, history, in_history = {}, [], False
    for line in front.splitlines():
        entry = _HISTORY_ENTRY_RE.match(line)
        if in_history and entry:
            history.append({"date": entry.group(1), "grade": entry.group(2)})
            continue
        match = _FIELD_RE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key == "history":
            in_history = True
            continue
        in_history = False
        fields[key] = value
    return Card(path=path, fields=fields, history=history, body=body)


def write(c):
    lines = ["---"]
    for key in FIELD_ORDER:
        if key in c.fields:
            lines.append(f"{key}: {c.fields[key]}")
    lines.append("history:")
    for entry in c.history:
        lines.append(f"  - {{ date: {entry['date']}, grade: {entry['grade']} }}")
    for key in TRAILING_ORDER:
        if key in c.fields:
            lines.append(f"{key}: {c.fields[key]}")
    for key, value in c.fields.items():
        if key not in FIELD_ORDER and key not in TRAILING_ORDER:
            lines.append(f"{key}: {value}")
    lines.append("---")
    c.path.write_text("\n".join(lines) + "\n" + c.body, encoding="utf-8")


def append_history(c, date, grade):
    c.history.append({"date": date.isoformat(), "grade": grade})


def due_date(c):
    raw = c.fields.get("next_due", "null")
    if raw in _NULLISH:
        return None
    return datetime.date.fromisoformat(raw)


def is_stub(c):
    """True when the user hasn't written the encoding yet."""
    body = c.body
    for heading in ("## Prompt", "## Answer"):
        start = body.find(heading)
        if start == -1:
            return True
        rest = body[start + len(heading):]
        section = rest.split("##", 1)[0]
        if not section.strip():
            return True
    return False
