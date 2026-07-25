# Wiring spacedeck into a scheduler

A review queue that nothing surfaces decays into "I'll get to it." spacedeck does not
schedule anything itself — it exposes what's due and leaves the scheduling to whatever
already runs your day.

## The interface

```
$ spacedeck due --json
{"count": 2, "subjects": ["probability"], "minutes": 15, "top": ["probability · Ito isometry"]}
```

| field | meaning |
|---|---|
| `count` | cards due today, already capped at `max_cards_per_day` |
| `subjects` | distinct subjects among them, sorted |
| `minutes` | estimated total: 2 per `recall` card, 8 per `derive` card |
| `top` | up to three, oldest-due first, for labelling a block |

`count` is 0 when nothing is due. Treat that as "reserve nothing" rather than "reserve an
empty block".

Exit status is 0 whether or not anything is due. A non-zero status means a real problem —
usually no `spacedeck.toml` in the working directory or above it.

## Pattern 1 — a daily note

Append what's due to today's note each morning. Works with Obsidian, Logseq, plain
Markdown, anything file-based.

```bash
#!/usr/bin/env bash
# append-review.sh — run from the repo holding your cards
set -euo pipefail

note="$HOME/notes/daily/$(date +%F).md"
due=$(spacedeck due --json)
count=$(printf '%s' "$due" | python -c 'import json,sys; print(json.load(sys.stdin)["count"])')

[ "$count" -eq 0 ] && exit 0

minutes=$(printf '%s' "$due" | python -c 'import json,sys; print(json.load(sys.stdin)["minutes"])')
subjects=$(printf '%s' "$due" | python -c 'import json,sys; print(", ".join(json.load(sys.stdin)["subjects"]))')

printf -- '- [ ] review — %s due (~%sm): %s\n' "$count" "$minutes" "$subjects" >> "$note"
```

## Pattern 2 — cron

```cron
# 07:30 daily, from the repo holding your cards
30 7 * * * cd ~/notes && /usr/local/bin/spacedeck due >> ~/.local/state/review.log 2>&1
```

Two things worth getting right: cron's `PATH` is minimal, so use an absolute path to
`spacedeck`; and `spacedeck due` searches upward from the working directory for
`spacedeck.toml`, so `cd` into the repo first.

For a desktop notification instead of a log:

```bash
count=$(spacedeck due --json | python -c 'import json,sys; print(json.load(sys.stdin)["count"])')
[ "$count" -gt 0 ] && notify-send "Review" "$count cards due"
```

## Pattern 3 — an LLM planner

If something builds your day from a prompt, give it the interface rather than the queue
file. The queue file is generated, its format is not a contract, and parsing it means
reimplementing the priority rules.

Drop this into the planner's instructions:

```markdown
**Reserve a review block when cards are due.** Run `spacedeck due --json`. When `count`
is 0, reserve nothing. Otherwise reserve one block of roughly `minutes`, at a
low-energy slot — never the freshest hours, which belong to deep work. Label it with
`count` and up to three entries from `subjects`. The block yields only to fixed
appointments and an imminent deadline.

You reserve the slot and nothing more. Card state — the rung, the interval, the next due
date, the grade history — belongs to the `/review` skill, which is the only thing that
runs an actual recall test. If the user reports a grade in conversation, note it and tell
them to run `/review`. Do not edit a card.
```

That last paragraph matters more than it looks. A scheduler that also advances cards will
promote them from self-reports, and a rung nobody earned is worse than no rung at all.

## Pattern 4 — a shell prompt or status bar

Cheap enough to run on every prompt, since it only reads frontmatter:

```bash
spacedeck_status() {
  local n
  n=$(spacedeck due --json 2>/dev/null | python -c 'import json,sys; print(json.load(sys.stdin)["count"])' 2>/dev/null) || return
  [ "${n:-0}" -gt 0 ] && printf ' ▸%s' "$n"
}
```

## Running without installing

If `spacedeck` isn't on `PATH` — for instance when it's only installed as a Claude Code
plugin — invoke the module directly:

```bash
PYTHONPATH=/path/to/spacedeck python -m spacedeck.cli due --json
```

`uv tool install` from a git URL gives you the `spacedeck` command for cron and scripts:

```bash
uv tool install git+https://github.com/dafu-zhu/spacedeck
```

## What not to build on

`REVIEW.md` is a **generated view**. It is rewritten whole on every session, its layout
changes between versions, and hand-edits are lost. Read `spacedeck due --json` instead.

Card frontmatter is stable and safe to read directly if you need something the CLI does
not expose. Writing it is another matter: intervals, rungs, and retirement interact, and
`spacedeck.ladder.advance()` is the only thing that should decide them.
