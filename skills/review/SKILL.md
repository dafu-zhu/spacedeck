---
name: review
description: Run a spaced-review session over the cards in this repo — serve one due card, test recall, grade it, and advance the schedule. Use when the user types /review, /review add, /review init, or /review requeue, or asks to review or drill their course material.
---

# /review — one card, tested properly

Runs the recall test that `spacedeck` schedules. Cards are Markdown files under the
configured `cards_dir`; the engine is the `spacedeck` package shipped with this plugin.

**Source of truth is card frontmatter.** The queue file is generated and must never be
hand-edited. If they disagree, the cards win — run `/review requeue`.

**Never write card body content.** Not `## Prompt`, not `## Answer`, not `## Notes`, not
even a draft "for the user to edit". Composing the recall trigger is itself an encoding
pass, and the user knows which step tripped them up. Ask, wait, and format only what they
give you. This holds even when `source:` points at notes you could summarise.

## Running the engine

Call the CLI rather than reimplementing anything:

```
spacedeck due --json      # what's due, with counts and estimated minutes
spacedeck requeue         # regenerate the queue file
spacedeck serve           # photo upload endpoint (derive cards)
spacedeck publish -m MSG  # push card state to the state branch
spacedeck add SUB TOPIC --rung recall|derive
```

If `spacedeck` is not on PATH, run `python -m spacedeck.cli` with the plugin root on
`PYTHONPATH`.

For grading arithmetic, use the package directly — never compute intervals by hand:

```python
from spacedeck import card, ladder, queue
rung, interval, next_due, status = ladder.advance(rung, interval, grade, today)
```

## Modes

- `/review` — serve one card.
- `/review add <subject> <topic>` — create a card.
- `/review init` — scaffold this repo.
- `/review requeue` — rebuild the queue file.

## Mode: session

### 1. Sync and pick

Run `spacedeck publish` prerequisites first: call `statesync.prepare(cfg)` so cards
published from elsewhere are present locally. Then read the due list.

Present **at most four** due cards in a single-select picker, ordered oldest-due first
with ties broken by tier. Show subject · topic · rung. Four is the picker's option cap;
since only one card is taken per invocation, a deeper list would never be reached.

If nothing is due, say so in one line and stop.

### 2. Serve exactly one card

Render the card's prompt section to the browser page and open it on the first card of a
session:

```python
from spacedeck import render
render.write(cfg.root, "Prompt", [("Prompt", prompt_text)])
render.open_in_browser(cfg.root)
```

Show the prompt **only**. Not the answer, not the notes, not a hint.

Record the current time — a photo picked up later must be newer than this moment.

**`recall` cards:** the user types the answer in the terminal. Loose ASCII is fine; you
are comparing meaning, not syntax. `E_t[S_T] = exp(...)` and proper LaTeX are the same
answer.

**`derive` cards:** the user works on paper. Start the upload endpoint if
`upload.is_running(port)` is False, print the bookmark URL the first time, and wait for
them to type `done`. Then `upload.newest_since(cfg.root, served_at)` and read the image.
If nothing newer is there, ask — never assume they meant to skip it.

### 3. Reveal and grade

Re-render with the answer appended, so the page shows prompt and answer together. The
user self-checks; for `derive` cards, also check their photographed work against the card
yourself and say plainly where it diverges.

Ask for a grade: **again / hard / good / easy**. Nothing else is a grade.

Then write it:

```python
rung, interval, next_due, status = ladder.advance(
    c.fields["rung"], int(c.fields["interval"]), grade, today, cfg.ladder)
```

`rung` comes back unchanged — **the rung is the user's label, not yours.** It says how
they want to be tested on this card, not how well they did. Never promote or demote it.
If a card feels wrong at its rung, say so and let them decide.

Append `{date, grade}` to `history`, write the card, then `spacedeck requeue`, then
`spacedeck publish -m "review: <subject> <topic> <grade>"`. Relay the publish result in
the closing line whenever it is not `pushed` — an offline session must say the push was
skipped rather than imply the state reached the branch.

### 4. Hints

At most one line, only on request, and any hint caps that card at `again`. The memory
wasn't there unaided, and recording otherwise corrupts the user's own schedule. Say
nothing further about it.

### 5. Stub cards

If `card.is_stub(c)` is True, do not test. Ask two questions and stop:

1. **Scope** — "Is this one result, or several?" If several, split it into one card per
   result before anything else. A card collecting several results earns one grade
   averaged over the one they know cold and the one they don't, which sets the wrong
   interval for both.
2. **Rung** — "Do you want to be tested by stating this, or by deriving it on paper?"

Then tell them the path and let them write it. Do not draft it. Do not offer to draft it.

## The encoding guide

Show this when a card needs writing. It describes shape, never content.

- **Prompt** — one question, determinate, answerable from memory in about two minutes.
  Names the setup precisely enough that exactly one answer is right. "Explain X" is too
  loose to grade against.
- **Answer** — the checkable skeleton: the statement, the hypotheses that do real work,
  and why, in three to five lines. Not a proof, not the source re-copied.
- **Notes** — optional. The trap: where they slipped, or the assumption that gets
  silently dropped. Omit it when there isn't one.

One worked example, from probability. It illustrates the shape and is **not** a template
for the user's subject — a language deck or a case-law deck will look nothing like it,
and the repo's own `_template.md` governs headings:

````markdown
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
````

## Mode: add

Run `spacedeck add <subject> <topic> --rung <recall|derive>`. Ask which rung if the user
didn't say. Print the path and stop — no interview, no drafted content.

## Mode: init

Run `spacedeck init`, then report what was created and point at `_template.md` as the
place to reshape cards for this subject.

## Mode: requeue

Run `spacedeck requeue`. If a card fails to parse, report which one and why rather than
skipping it silently — a dropped card is a card that stops being reviewed.

## Guardrails

- Never show overdue counts, day-gaps, streaks, or missed days. The cooling dashboard in
  the queue file is the one place day-counts belong.
- One card per invocation. No "want to do another?" — the user types `/review` again.
- Partial sessions are normal. No apology, no comment.
- A failed card is the system finding a weak spot before an exam does. One honest
  sentence, no pep talk.
- Never mint cards for anything outside this repo's configured `cards_dir`.
- This skill reserves nothing on a calendar. Schedulers read `spacedeck due --json`.
