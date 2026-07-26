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


def existing_work_names(cards_dir):
    """Every folder name already claimed by a card in this deck."""
    names = set()
    for path in pathlib.Path(cards_dir).rglob("*.md"):
        try:
            if card.looks_like_card(path):
                names.add(card.read(path).fields.get("work", ""))
        except (OSError, ValueError):
            continue
    names.discard("")
    return names


def work_rel(topic, taken=()):
    """A card's own folder: the card's name, flat under the local work root.

    Relative and separator-free by design. This string is written into the card
    and travels with it, so it must never carry a drive letter, a home directory,
    or a repo slug; each machine resolves it against its own `paths.work`.

    Two subjects can hold a card of the same name and they must not share a
    folder, so the second one registered takes a numeric suffix. The card records
    whichever name it got, and nothing recomputes it afterwards.
    """
    base = slugify(topic)
    name, n = base, 2
    while name in taken:
        name = f"{base}-{n}"
        n += 1
    return name


def work_rel_of(c):
    """The `work:` field, or the name it would have had for a card minted before it."""
    return c.fields.get("work") or slugify(c.fields["topic"])


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
            "work": work_rel(topic, existing_work_names(cards_dir)),
            "source": source,
        },
        history=[{"date": today.isoformat(), "grade": "seed"}],
        body=_skeleton(cards_dir),
    )
    card.write(c)
    return path
