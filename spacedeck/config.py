"""Read `spacedeck.toml` from the consuming repo.

Config lives with the cards, not with the engine, so one installed plugin can serve
several repos with different layouts and different ladders.
"""

import dataclasses
import pathlib
import tomllib

CONFIG_NAME = "spacedeck.toml"

DEFAULTS = {
    # Namespaced on purpose. `reviews/` and `REVIEW.md` are names a repo may already
    # be using for something else entirely, and init must not adopt or overwrite one.
    "cards_dir": "spacedeck",
    "queue_file": "spacedeck/QUEUE.md",
    "ladder": [1, 3, 7, 16, 35],
    "max_cards_per_day": 8,
    "daily_minutes": 15,
    "upload_port": 8765,
    "state_branch": "main",
    "tiers": ["P0", "P1", "P2"],
}


@dataclasses.dataclass
class Config:
    root: pathlib.Path
    cards_dir: pathlib.Path
    queue_file: pathlib.Path
    ladder: list
    max_cards_per_day: int
    daily_minutes: int
    upload_port: int
    state_branch: str
    tiers: list

    @property
    def retire_interval(self):
        return self.ladder[-1]


def find_root(start):
    """Nearest ancestor directory holding a spacedeck.toml, or None."""
    start = pathlib.Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    return None


def load(root):
    root = pathlib.Path(root).resolve()
    path = root / CONFIG_NAME
    if not path.is_file():
        raise FileNotFoundError(
            f"no {CONFIG_NAME} in {root} — run `/drill init` to create one"
        )

    with path.open("rb") as fh:
        raw = tomllib.load(fh).get("spacedeck", {})

    merged = {**DEFAULTS, **raw}
    ladder = list(merged["ladder"])
    if not ladder:
        raise ValueError(f"{path}: ladder must not be empty")
    if any(b <= a for a, b in zip(ladder, ladder[1:])):
        raise ValueError(f"{path}: ladder must be strictly ascending, got {ladder}")

    return Config(
        root=root,
        cards_dir=root / merged["cards_dir"],
        queue_file=root / merged["queue_file"],
        ladder=ladder,
        max_cards_per_day=int(merged["max_cards_per_day"]),
        daily_minutes=int(merged["daily_minutes"]),
        upload_port=int(merged["upload_port"]),
        state_branch=str(merged["state_branch"]),
        tiers=list(merged["tiers"]),
    )
