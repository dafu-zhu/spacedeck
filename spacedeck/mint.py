"""Create a new card.

The body is a skeleton, never content. Composing the recall trigger is itself an
encoding pass, and the user knows which step tripped them up — which their notes do
not record. Nothing here writes a prompt or an answer.

The skeleton is customisable per repo: drop a `_template.md` in the cards directory
and it replaces the built-in one. The shipped headings suit deriving a result from
memory; a language deck or a case-law deck will want different ones.
"""

import datetime
import pathlib
import re
import unicodedata

from . import card

TEMPLATE_NAME = "_template.md"
BUILTIN_TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "templates" / "card.md"


def slugify(topic):
    decomposed = unicodedata.normalize("NFKD", topic)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


def template_path(cards_dir):
    """The repo's own skeleton if it has one, else the shipped default."""
    local = pathlib.Path(cards_dir) / TEMPLATE_NAME
    return local if local.is_file() else BUILTIN_TEMPLATE


def _skeleton(cards_dir):
    return "\n" + template_path(cards_dir).read_text(encoding="utf-8").lstrip("\n")


def create(cards_dir, subject, topic, today, tier="P0", source=""):
    cards_dir = pathlib.Path(cards_dir)
    folder = cards_dir / subject
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{slugify(topic)}.md"
    if path.exists():
        raise FileExistsError(f"card already exists: {path}")

    c = card.Card(
        path=path,
        fields={
            "subject": subject,
            "topic": topic,
            "tier": tier,
            "rung": "recall",
            "interval": "1",
            "next_due": (today + datetime.timedelta(days=1)).isoformat(),
            "status": "active",
            "source": source,
        },
        history=[{"date": today.isoformat(), "grade": "seed"}],
        body=_skeleton(cards_dir),
    )
    card.write(c)
    return path
