# spacedeck

Spaced review over your own course notes, as a Claude Code plugin.

You write the cards. `spacedeck` decides what to show you and when, tests you on it,
and moves the schedule based on how it went. Cards are plain Markdown files in your
repo, with no database, no proprietary format, and no sync service.

## Why another spaced-repetition tool

Most flashcard software optimises for cards you can answer in five seconds. That works
for vocabulary and fails for anything you have to *derive*. A card that asks you to
reproduce a proof needs paper, a way to check the result, and an honest grade. None of
that fits a tap-to-reveal loop on a phone.

spacedeck is built around two rungs instead:

- `recall`: state the definition, the result, the hypotheses. You type it, in about
  twenty seconds.
- `derive`: reproduce the derivation on paper, then photograph it so it can be checked.

A card climbs from `recall` to `derive`, and the interval grows only when you actually
pass. Get it wrong and it drops back to `recall` and returns tomorrow.

## Install

```
/plugin install spacedeck
```

Then, in the repo holding your notes:

```
/drill init
```

That writes `spacedeck.toml`, creates `spacedeck/` for your cards, and generates an empty
`spacedeck/QUEUE.md`. Nothing else in your repo is touched.

Everything lives under one directory named after the tool, so it will not land on a name
your repo already means something by. If any of the three paths already exists, `init`
names it, refuses, and writes nothing at all. It will not adopt a directory you were using
for something else, and it will not overwrite a file you wrote. Point `cards_dir` and
`queue_file` somewhere else if those names don't suit you.

## Commands

`/drill` is the interface. Everything you do day to day goes through it, and the four
commands below are the whole surface.

### /drill

| command | what it does |
|---|---|
| `/drill` | Serves one due card, tests you, grades it, moves the schedule |
| `/drill add <subject> <topic>` | Creates an empty card and prints its path |
| `/drill init` | Sets up the repo you are currently in |
| `/drill requeue` | Rebuilds the queue file from your cards |

Adding a card takes a subject and then a topic. Quote the topic when it contains spaces:

```
/drill add probability "Central limit theorem"
/drill add analysis "Dominated convergence"
```

The subject becomes the folder, the topic becomes the filename. So the first line writes
`spacedeck/probability/central-limit-theorem.md` and leaves the body for you.

`/drill` on its own starts a session. You get a picker of up to four due cards, you choose
one, and that is the session. Run it again for the next card.

### The CLI underneath

You do not need this section to use spacedeck. `/drill` shells out to a `spacedeck`
command for every mechanical step, so the table below is mostly here to tell you what the
skill just did on your behalf.

The exception is scheduling. `spacedeck due --json` is meant to be called by something
else, and a cron job or a daily planner can use it to size a review block without a model
in the loop. [docs/integrations.md](docs/integrations.md) covers that.

| command | what it does |
|---|---|
| `spacedeck init [path]` | Scaffolds the config, cards directory and queue. Defaults to the current directory |
| `spacedeck add <subject> <topic>` | Creates a card and prints its path |
| `spacedeck due [--json]` | Reports what is due. Use `--json` for schedulers |
| `spacedeck requeue` | Regenerates the queue file from card frontmatter |
| `spacedeck serve [--port N] [--detach]` | Runs the phone upload page for `derive` cards |
| `spacedeck setup [--force]` | Vendors the MathJax bundle so math typesets offline |
| `spacedeck publish [-m MSG]` | Pushes card state to the state branch |

`spacedeck add` takes three optional flags: `--rung`, which is `recall` or `derive` and
defaults to `recall`; `--tier`, which defaults to `P0` and breaks ties when several cards
fall due together; and `--source`, a free-text reference back to the notes the card came
from.

`/drill init` runs `init` and then `setup`, so a machine has its math bundle before the
first card. From there the skill calls the rest at the right moments: `publish` after
every grade, `serve` when a `derive` card needs a photo, `requeue` whenever a card
changes.

## A first card

```
/drill add probability "Central limit theorem"
```

This creates `spacedeck/probability/central-limit-theorem.md` with the frontmatter filled
in and the body left empty, then prints the path. You write the encoding yourself.
Composing the recall trigger is itself a learning pass, and you know which step tripped
you up, which your lecture notes do not record.

```markdown
## Prompt

State the CLT for i.i.d. $X_i$: what are the exact hypotheses, what converges,
to what, and in which mode?

## Answer

$X_1, X_2, \dots$ i.i.d. with $\mathbb{E}[X] = \mu$ and
$0 < \mathrm{Var}(X) = \sigma^2 < \infty$. Then

$$\sqrt{n}\,(\bar X_n - \mu)/\sigma \rightsquigarrow N(0,1) \quad \text{(in distribution).}$$

Finite second moment is the entire hypothesis. Nothing higher, and no density or
continuity assumption anywhere.

## Notes

Convergence in distribution only. Dies when $\sigma^2 = \infty$: for Cauchy,
$\bar X_n$ is Cauchy for every $n$ and no normalization rescues it.
```

`## Notes` is optional. Use it for the trap, and leave it out when there isn't one.

## Reviewing

```
/drill
```

You get a picker of what's due, choose one card, and that's the session. Type `/drill`
again for the next one. Nothing tracks "how many you've done today"; a graded card simply
leaves the due set, and when the set is empty you're told so in one line.

Cards render in a browser tab that updates itself: the prompt first, then the answer once
you've committed to a response. Card bodies render as Markdown, so a payoff table comes
out as a table, and math is typeset by MathJax, which is vendored so sessions work
offline. The two never collide: math spans are lifted out before the Markdown pass, so a
`|` inside `\left|` doesn't open a table cell and an `_` inside `S_t` doesn't open italics.

The rendered page is temporary. It is deleted when the session ends, and again when the
next one starts, so the answer never sits on disk outside your repo between reviews.

For `derive` cards you work on paper and photograph it. `spacedeck serve` runs a small
upload page on your own network: bookmark it on your phone's home screen, tap, shoot,
and the image lands on your machine with no cloud account anywhere in the path.

## Where your work goes

Every card owns a folder, named after the card. `spacedeck add` creates it and records it
in the card, so `ito-isometry.md` gets:

```yaml
work: ito-isometry
```

Two subjects can hold a card of the same name, and they must not share a folder, so the
second one registered becomes `ito-isometry-2`. The card records whichever name it got.

The photo waits in a shared inbox while you're being tested, since it doesn't belong to a
card until it has been checked against one. Filing happens at grading, when the photo
moves into that folder under the date: `2026-07-25.jpg`, then `2026-07-25-2.jpg` for a
second attempt the same day, numbered rather than overwritten. So the inbox stays a queue,
and each card accumulates its own record of how that derivation has gone.

The path is relative on purpose. It resolves against the runtime root on whichever machine
opens the card, so a deck synced between machines carries no username, drive letter, or
path separator with it.

Photographs live beside the rest of the runtime state, outside your repo, so `spacedeck
publish` never pushes an image to your state branch.

## Grading

Four grades, the same vocabulary most spaced-repetition tools use:

| grade | rung | next interval |
|---|---|---|
| `again` | drops to `recall` | 1 day |
| `hard` | unchanged | 3 days |
| `good` | advances one | next rung up the ladder |
| `easy` | advances one | skips a ladder step |

The ladder is `1 → 3 → 7 → 16 → 35` days. A card that reaches 35 days at `derive` and is
graded `good` or `easy` retires.

Asking for a hint caps that card at `again`. The memory wasn't there unaided, and
recording otherwise just corrupts your own schedule.

## Scheduling

A queue nothing surfaces decays into "later". `spacedeck due` gives a scheduler what it
needs to reserve a block:

```
$ spacedeck due --json
{"count": 2, "subjects": ["probability"], "minutes": 15, "top": ["probability · Ito isometry"]}
```

See [docs/integrations.md](docs/integrations.md) for wiring it into cron, a daily note, or
an LLM planner.

## Configuration

`spacedeck.toml` in your repo root:

```toml
[spacedeck]
cards_dir = "spacedeck"
queue_file = "spacedeck/QUEUE.md"
ladder = [1, 3, 7, 16, 35]
max_cards_per_day = 8
daily_minutes = 15
upload_port = 8765
state_branch = "main"
tiers = ["P0", "P1", "P2"]
```

## Requirements

Python 3.13 or newer. The package uses only the standard library and has no runtime
dependencies.

## License

MIT
