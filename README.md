# spacedeck

Spaced review over your own course notes, as a Claude Code plugin.

You write the cards. `spacedeck` decides what to show you and when, tests you on it,
and moves the schedule based on how it went. Cards are plain Markdown files in your
repo — no database, no proprietary format, no sync service.

## Why another spaced-repetition tool

Most flashcard software optimises for cards you can answer in five seconds. That works
for vocabulary and fails for anything you have to *derive*. A card that asks you to
reproduce a proof needs paper, a way to check the result, and an honest grade — none of
which fit a tap-to-reveal loop on a phone.

spacedeck is built around two rungs instead:

- **recall** — state the definition, the result, the hypotheses. Typed, ~20 seconds.
- **derive** — reproduce the derivation on paper. Photographed and checked.

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

The command is `/drill`, not `/review` — Claude Code ships a built-in `/review` for
GitHub pull requests, and a plugin cannot shadow a built-in.

That writes `spacedeck.toml`, creates the cards directory, and generates an empty queue.
Nothing else in your repo is touched.

## A first card

```
/drill add probability "Central limit theorem"
```

This creates `reviews/probability/central-limit-theorem.md` with the frontmatter filled
in and the body left empty, then prints the path. **You** write the encoding — composing
the recall trigger is itself a learning pass, and you know which step tripped you up,
which your lecture notes do not record.

```markdown
## Prompt

State the CLT for i.i.d. $X_i$: what are the exact hypotheses, what converges,
to what, and in which mode?

## Answer

$X_1, X_2, \dots$ i.i.d. with $\mathbb{E}[X] = \mu$ and
$0 < \mathrm{Var}(X) = \sigma^2 < \infty$. Then

$$\sqrt{n}\,(\bar X_n - \mu)/\sigma \rightsquigarrow N(0,1) \quad \text{(in distribution).}$$

Finite second moment is the entire hypothesis — nothing higher, and no density or
continuity assumption anywhere.

## Notes

Convergence in distribution only. Dies when $\sigma^2 = \infty$: for Cauchy,
$\bar X_n$ is Cauchy for every $n$ and no normalization rescues it.
```

`## Notes` is optional — use it for the trap, and leave it out when there isn't one.

## Reviewing

```
/drill
```

You get a picker of what's due, choose one card, and that's the session. Type `/drill`
again for the next one. Nothing tracks "how many you've done today"; a graded card simply
leaves the due set, and when the set is empty you're told so in one line.

Cards render in a browser tab that updates itself — the prompt first, then the answer once
you've committed to a response. Markdown becomes Markdown, so a payoff table is a table
and not a row of pipes, and math is typeset by MathJax, which is vendored so sessions work
offline. The two never collide: math spans are lifted out before the Markdown pass, so a
`|` inside `\left|` doesn't open a table cell and an `_` inside `S_t` doesn't open italics.

The rendered page is temporary. It is deleted when the session ends, and again when the
next one starts, so the answer never sits on disk outside your repo between reviews.

For `derive` cards you work on paper and photograph it. `spacedeck serve` runs a small
upload page on your own network: bookmark it on your phone's home screen, tap, shoot,
and the image lands on your machine with no cloud account anywhere in the path.

## Where your work goes

Every card owns a folder. `spacedeck add` creates it and records it in the card:

```yaml
work: probability/ito-isometry
```

The photo waits in a shared inbox while you're being tested — it doesn't belong to a card
until it has been checked against one — and filing happens at grading. It moves into that
folder under the date: `2026-07-25.jpg`, then `2026-07-25-2.jpg` for a second attempt the
same day, numbered rather than overwritten. So the inbox stays a queue, and each card
accumulates its own record of how that derivation has gone.

The path is relative on purpose. It resolves against the runtime root on whichever machine
opens the card, so a deck synced between machines carries no username, drive letter, or
path separator with it. Cards written before this field existed still resolve, from their
subject and topic.

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

Asking for a hint caps that card at `again` — the memory wasn't there unaided, and
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
cards_dir = "reviews"
queue_file = "REVIEW.md"
ladder = [1, 3, 7, 16, 35]
max_cards_per_day = 8
daily_minutes = 15
upload_port = 8765
state_branch = "main"
tiers = ["P0", "P1", "P2"]
```

## CLI

Everything mechanical is scriptable without a model. Grading stays in the skill, because
grading is a conversation.

| command | does |
|---|---|
| `spacedeck init` | scaffold config, cards directory, queue |
| `spacedeck due [--json]` | what's due, for schedulers |
| `spacedeck requeue` | regenerate the queue from card frontmatter |
| `spacedeck serve` | run the photo upload endpoint |

## Requirements

Python 3.13+. No runtime dependencies — standard library only.

## License

MIT
