# Operating CHITRA

This is the guide for running the pipeline and clearing a slate for production.
The [README](README.md) tells you what CHITRA is and proves it works; this tells
you how to drive it. If you have not run `python verify_all.py` yet, start there.

Everything below runs with no API key except the one step that calls the model,
and that step is optional. The offline path exercises the entire pipeline and
the entire compliance surface; only the creative text differs.

---

## The shape of a run

A campaign moves through four states. Nothing skips a state, and the cultural
gate between the third and fourth is a human, not code.

1. **Generate.** Drishti reads an onboarding packet and writes a creative
   brief. Disha interrogates the brief, diverges into twelve territories,
   scores them, kills the weak ones, and writes a concept slate of three to
   five survivors.
2. **Held.** The slate lands with every cultural rule inconclusive. No human
   has looked at it, so it is queued for cultural review and cannot ship.
3. **Review.** A named person reads each approved concept and records a risk
   level. The record is bound to a digest of the exact creative they read.
4. **Cleared.** The slate is re-judged against the recorded reviews. If every
   approved concept is bound and audited, the cultural queue clears.

State 2 is not a failure. A generated slate that reported itself production
ready would mean the human gate had been skipped, which is the one thing this
system is built not to do.

---

## Step 1 — Generate a slate

Offline, no key, no spend, using the bundled packet:

```bash
python run_slice.py --offline
```

With real model output, which needs a key and costs a few cents:

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # Windows: set ANTHROPIC_API_KEY=sk-ant-...
python run_slice.py
```

Either way the artifacts land in `run_output/<timestamp>/`. The one you need for
every later step is `03-concept-slate.json`. Note the timestamp; you will paste
that path repeatedly. Everywhere below, `<ts>` means that folder.

To run a different brief, copy `onboarding_packet.json`, edit it, and pass
`--packet mine.json`. The packet's own `_note` fields explain each section; the
ones that stop a run if missing are the audience research and the metric
targets, because Drishti refuses to invent audience or performance data.

At the end you will see the slate, and a closing line stating no cultural audit
exists and the slate is not cleared for production. That line is the system
working. Move to step 2.

---

## Step 2 — Assemble the reviewer's brief

```bash
python chitra_review.py brief --slate run_output/<ts>/03-concept-slate.json
```

This prints one brief per approved concept: which cultural axes the copy
touches (religion, caste, gender, region, political), the register entries and
precedent for each, and a specific question for the reviewer. It assembles
evidence and issues no verdict; the grade is the human's to give.

Add `--out brief.md` to write it to a file for someone who is not at the
terminal. If an audit already exists for a concept but was recorded against
different creative, the brief drops it and says so rather than showing a stale
"already reviewed" that never belonged to this slate.

---

## Step 3 — Record each review

One command per approved concept. Every flag here matters, and the command
refuses rather than recording something that will not mean what it appears to.

```bash
python chitra_review.py record \
    --slate run_output/<ts>/03-concept-slate.json \
    --concept C01 \
    --level low \
    --reviewer "A Patil" \
    --axis religion=low --axis caste=low --axis gender=low \
    --axis region=low --axis political=low \
    --notes "No religious or regional depiction; festival framing is incidental."
```

- `--slate` is required. The review is bound to a digest of that concept's
  creative, so it cannot later drift onto a different slate that happens to
  reuse the id `C01`. Omit it and the command refuses.
- `--concept` must name a concept that exists in that slate. `C99` is refused.
- `--level` is the overall risk: `low`, `medium`, or `high`.
- `--reviewer` cannot be blank. An audit with no name is a rubber stamp.
- `--axis` records the per-axis grade. The overall level is raised to the worst
  axis automatically, so a `religion=high` makes the concept block on religion
  even if you passed `--level low`.
- `--notes` is free text and is kept on the record and in the ledger.

Repeat for C02, C03, and every other approved concept. A slate is governed only
when all of its concepts are.

### What a grade does

`low` passes. `high` blocks: a cultural rule with a conditional severity moves
from warn to block. `medium` blocks on religion and gender, warns on region.
The thresholds differ per axis by design; the tool prints the escalation when
it happens.

---

## Step 4 — Check what is outstanding

```bash
python chitra_review.py status --slate run_output/<ts>/03-concept-slate.json
```

A table of every approved concept, whether it is audited, its level and
reviewer. It exits non-zero while any concept is unaudited and zero once all
are, so it is safe to use in a script. Any audit that does not bind to this
slate is listed as ignored, with the reason.

---

## Step 5 — Re-judge to clear the slate

```bash
python run_slice.py --slate run_output/<ts>/03-concept-slate.json
```

This makes no model call. It re-runs the slate against the current rules with
the recorded reviews in hand, binding each audit to the creative it named. If
every approved concept is bound and audited, the cultural queue clears and the
slate is cleared for production. Any concept whose audit does not bind is
reported and counts as unreviewed.

That is the whole loop: generate, brief, record, status, re-judge.

---

## Where things live

- `run_output/<ts>/` — one folder per run. `03-concept-slate.json` is the
  artifact every review step points at.
- `cultural_audits.json` — the recorded reviews. Written by `record`, read by
  `status` and by the re-judge. A generated run never reads it, because new
  concepts have not been reviewed. Override the path with `--audits` on any of
  the three commands.
- `audit/chitra-audit.jsonl` — the hash-chained ledger. Every verdict, waiver,
  routing and review lands here. Override with `--ledger`; anything automated
  must, so a scripted run never appends to the real trail.

## Rules that need external systems

Some rules cannot be satisfied offline because they resolve against a service
that is not wired up in this repo: the consent vault, the credential registry,
the trademark pre-check, the DMRA Schedule. Those rules block or go
inconclusive by default, which is the fail-closed direction. `python
analyse_implementability.py` lists exactly which rules these are and why. This
is expected, not a fault: the engine refuses to pass what it cannot verify.

## If a region is not covered by research

The platform refuses to run in a region the audience research does not cover
(ADR-020). To proceed anyway, add a waiver to the packet that names a person and
a date, under `research_coverage_waivers`. The packet's `_note` on that field
gives the exact shape. A waiver without a name does not lift the block, because
that is a compromise rather than a decision anyone owns.
