# CHITRA

A compliance engine for AI-generated advertising, built against Indian regulatory law. Two agents, forty-three enforceable rules, a hash-chained audit ledger, and twelve gates that run on every commit.

**Everything claimed in [`CHITRA-POST-MORTEM.md`](CHITRA-POST-MORTEM.md) is reproducible on your machine in three commands.**

---

## Run it

```bash
git -c credential.helper= clone https://github.com/apj396/chitra.git
cd chitra && pip install -r requirements.txt
python verify_all.py
```

Roughly two seconds. No API key, no network, no accounts. Twelve gates, 412 checks: 385 unit tests across 8 suites, plus 27 assertions on a live pipeline run.

The `-c credential.helper=` is deliberate. It strips any cached GitHub token for that one command, so the clone proves the repository is reachable by someone who is not signed in. Without it a private repository clones fine for its owner and 404s for everyone else, which is exactly what happened here: see §2.1 of the post-mortem.

```
SUMMARY
  PASS  conformance         rules vs their admission schema; citations vs live law
  PASS  field census        rule field reads vs artifact schemas
  PASS  sanitizer           policy engine: enforcement and fail-closed behaviour
  PASS  drishti             agent 1: refusals, halts, schema and compliance repair
  PASS  services            consent vault, credentials, trademark, HITL routing
  PASS  variance            padding versus genuine exploration
  PASS  disha               agent 2: divergence gating, scoring, kill tags, handoff
  PASS  sweep               pinned vendor APIs vs upstream
  PASS  ledger              audit chain: tamper evidence and DPDP erasure
  PASS  review              the human gate: named cultural review
  PASS  offline slice       the whole pipeline, no key, no network, no spend
  PASS  implementability    how much of the rule set genuinely enforces
```

`python verify_all.py --quick` skips the vendor sweep. `--list` shows the gates without running them.

---

## What each gate proves

Not that the code runs. That specific failure modes are absent.

**Conformance.** Every compliance rule validates against the schema the registry uses to admit it, and every citation names an instrument still in force. On the first run against the original specification this reported **52 findings across 25 sites**, including 22 rules that could not load at all.

**Field census.** Every field a rule reads exists on the artifacts it applies to, or is declared as derived. First run: **61 fields, 279 rule/artifact pairs** referencing nothing. Three rules were structurally incapable of failing as a result.

**Sanitizer.** The policy engine enforces, fails closed, and refuses to pass on fields that do not exist. A required field that cannot be resolved yields INCONCLUSIVE, never a falsy pass.

**Ledger.** The audit chain detects edited, deleted, reordered and forged entries and names the first broken sequence number. Erasure is honoured by redaction rather than deletion, so the proof that the erasure happened survives it.

**Review.** A named human gates the pipeline. Five cultural rules cannot be enforced by software and are not pretended to be.

---

## Reproduce the specific claims

Every number in the post-mortem maps to a command.

```bash
# 43 rules, 35 genuinely enforcing, 8 that need a human
python analyse_implementability.py

# the audit chain is tamper-evident: edit a verdict and watch it break
python test_audit.py

# the compatibility sweep against real vendor manifests
python chitra_sweep.py

# what the field census actually checks
python audit_field_paths.py
```

To see a gate fail on purpose, open `chitra_rules.json`, change any `citation` to an empty string, and run `python verify_all.py`. The registry rejects wholesale rather than loading the subset that parsed, because partial load is what turned a schema error into silent under-enforcement.

---

## Running the pipeline

The gates need nothing. Neither does a full pipeline run, if you do not need real model output.

```bash
python run_slice.py --offline              # the whole slice, no key, no spend
```

Drishti reads the onboarding packet and writes a creative brief, Disha interrogates it, diverges into twelve territories, gates for variance, scores, kills and writes a concept slate, both artifacts clear the schema gate and the compliance sanitizer, and the slate is held at the cultural gate. Same code path, same compliance enforcement, same audit entries. Only the model responses are fixtures. This is the recommended way to see what the system does before deciding whether to spend anything, and the `offline slice` gate proves it still works on every commit.

Real model output needs an Anthropic API key.

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # Windows: set ANTHROPIC_API_KEY=sk-ant-...
python run_slice.py                        # about 6 minutes, a few cents
```

`--ledger <path>` sends the audit trail somewhere other than `audit/chitra-audit.jsonl`. Anything automated must pass it. The first real audit trail in this project had 68 test fixtures in its first 112 entries because a test suite wrote to the production ledger, and an unattended pipeline run is the same hazard by a different route.

Artifacts land in `run_output/<timestamp>/`. A generated slate is held at the cultural gate until a named human reviews it:

```bash
python chitra_review.py brief  --slate run_output/<ts>/03-concept-slate.json
python chitra_review.py record --slate run_output/<ts>/03-concept-slate.json \
    --concept C01 --level low --reviewer "Your Name" \
    --axis religion=low --axis caste=low --axis gender=low \
    --axis region=low --axis political=low --notes "..."
python run_slice.py --slate run_output/<ts>/03-concept-slate.json   # no model call
```

Then the evidence:

```bash
python chitra_audit.py verify
python chitra_audit.py query --event cultural.review_recorded
```

---

## Layout

```
specs/                  the specification documents the code reads at runtime
chitra_sanitizer.py     policy engine
chitra_predicates.py    the 43 rules, executable
chitra_facets.py        the seam between artifact schemas and rule vocabulary
chitra_services.py      consent vault, credential registry, trademark, HITL routing
chitra_audit.py         hash-chained append-only ledger
chitra_review.py        the human review workflow
chitra_drishti.py       agent 1: strategic planner
chitra_disha.py         agent 2: creative director
chitra_sweep.py         vendor drift detection
chitra_conformance.py   the conformance gate
audit_field_paths.py    the field census
verify_all.py           every gate
CHITRA-ADR-Register.md  20 architectural decisions with reasoning
```

Agent prompts are read from `specs/` at runtime rather than pasted into the source, so a prompt cannot drift from the specification it implements. That decision cost a defect and caught two.

---

## What is not built

Seven of the nine specified agents. The evaluation harness. Multi-tenant isolation, replication and write-access control on the ledger. A classifier for the eight judgement rules, deliberately: see §4 of the post-mortem.

The ledger is a local file. A hash chain proves tampering occurred; it does not prevent an actor with write access rebuilding the file. Countersigning to append-only external storage is the standard mitigation and is not implemented.

---

## Reading order

1. [`CHITRA-POST-MORTEM.md`](CHITRA-POST-MORTEM.md) — the findings, by defect class
2. [`CHITRA-ADR-Register.md`](CHITRA-ADR-Register.md) — 20 decisions, including three where a position changed under argument and one where the author was overruled
3. `chitra_predicates.py` — the rules as code, each carrying why it enforces the way it does
