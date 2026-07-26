---
name: drill
description: Run a spaced-review session over the cards in this repo — serve one due card, test recall, grade it, and advance the schedule. Use when the user types /drill, /drill add, /drill init, or /drill requeue, or asks to review or drill their course material.
---

# /drill — one card, tested properly

Runs the recall test that `spacedeck` schedules. Cards are Markdown files under the
configured `cards_dir`; the engine is the `spacedeck` package shipped with this plugin.

**Source of truth is card frontmatter.** The queue file is generated and must never be
hand-edited. If they disagree, the cards win — run `/drill requeue`.

**`work:` is relative, always.** It names a card's photo folder beneath the local runtime
root, and it travels with the card to other machines. Never write an absolute path, a home
directory, or a backslash into it. Resolve it with `paths.card_work(cfg.root, rel)`; a card
minted before the field existed still answers through `mint.work_rel_of(c)`.

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

- `/drill` — serve one card.
- `/drill add <subject> <topic>` — create a card.
- `/drill init` — scaffold this repo.
- `/drill requeue` — rebuild the queue file.

## Mode: session

### 1. Sync and pick

Run `spacedeck publish` prerequisites first: call `statesync.prepare(cfg)` so cards
published from elsewhere are present locally. Then read the due list.

Clear anything an interrupted session left on screen before picking:

```python
render.clear(cfg.root)
```

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

**`derive` cards:** the user works on paper. Run `spacedeck serve --detach` — it returns
immediately, is a no-op when a server is already up, and the process outlives this
session so the user never starts one by hand. Show the bookmark URLs only on the first
`derive` card of a session; after that they are noise.

Then wait for the user to type `done`, call
`upload.newest_since(cfg.root, served_at)`, and read the image. If nothing newer is
there, ask — never assume they meant to skip it.

The shot stays in the shared inbox for now. It only belongs to a card once it has been
checked against one, which happens at grading.

Earlier attempts at the same card are `upload.filed_shots(cfg.root, mint.work_rel_of(c))`,
oldest first. Read one only when the user asks to compare — an unrequested "last time you
also missed this" is the day-counting this skill doesn't do.

### 3. Reveal and grade

Re-render with the answer appended, so the page shows prompt and answer together. This is
the session's last write, so turn the refresh off — the page is about to be deleted, and a
tab still polling would replace the answer with a browser error:

```python
render.write(cfg.root, "Reveal",
             [("Prompt", prompt_text), ("Answer", answer_text)], refresh=False)
```

The user self-checks; for `derive` cards, also check their photographed work against the
card yourself and say plainly where it diverges.

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

For a `derive` card, file the photograph against the card it was taken for:

```python
upload.file_shot(cfg.root, mint.work_rel_of(c), shot, today)
```

That moves it out of the shared inbox into the card's own folder under a date-stamped
name, so the inbox stays a queue rather than an archive and each card keeps its own record
of how the derivation went. A second attempt on the same day is numbered, never
overwritten. File it whatever the grade — a failed attempt is the more useful one to keep.

Then delete the page — always, including when the user abandons the card mid-way:

```python
render.clear(cfg.root)
```

The rendered page holds the answer in plain text outside the repo, so it lives exactly as
long as the session. The open tab keeps showing what it already loaded; the user closes
it. Say nothing about any of this.

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

Bodies are Markdown and render as Markdown — tables, emphasis, lists — with math in
`$…$` and `$$…$$`. Write a real pipe table rather than columns aligned with spaces.

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

The card is minted with a `work:` folder, which is created at the same time. That is
where photographed attempts get filed.

## Mode: init

Run `spacedeck init`, then report what was created and point at `_template.md` as the
place to reshape cards for this subject.

## Mode: requeue

Run `spacedeck requeue`. If a card fails to parse, report which one and why rather than
skipping it silently — a dropped card is a card that stops being reviewed.

## Guardrails

- Never show overdue counts, day-gaps, streaks, or missed days. The cooling dashboard in
  the queue file is the one place day-counts belong.
- One card per invocation. No "want to do another?" — the user types `/drill` again.
- Partial sessions are normal. No apology, no comment.
- A failed card is the system finding a weak spot before an exam does. One honest
  sentence, no pep talk.
- The rendered page is runtime state, never a record: written when the card is served,
  frozen at the reveal, deleted when the session ends.
- Never mint cards for anything outside this repo's configured `cards_dir`.
- This skill reserves nothing on a calendar. Schedulers read `spacedeck due --json`.
