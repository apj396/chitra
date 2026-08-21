"""
reconcile_vocabulary.py — fix the artifact-type vocabulary and generate §F.12.

The specification declares which artifacts a rule applies to in four places,
and all four disagree:

  1. §G  applies_to              uses verbal_deck / visual_deck; no concept_bible
  2. §F.12 matrix                11 canonical types; no verbal_deck
  3. chitra-sanitizer.validate   10 types; has verbal_deck, lacks concept_bible
  4. the schema set              concept_bible.json exists; verbal_deck.json does not

The schema set is the only one that reflects what actually travels between
agents, so it wins. verbal_deck and visual_deck are sub-objects of
concept_bible, not artifacts, and every applies_to naming them is translated.

Coverage is then reconciled as the union of the translated applies_to and the
matrix row. Union rather than intersection because under-enforcement is the
failure mode being fixed: where the two sources disagree, the one that runs
more checks is the safer reading, and every addition is reported.

Outputs:
    chitra_rules.reconciled.json   rules with corrected applies_to
    F12-generated.md               the matrix, generated rather than authored
    a change report on stdout

Run: python3 reconcile_vocabulary.py
"""

import json
import os
import sys

from chitra_paths import spec_dir
SPEC_DIR = spec_dir()
HERE = os.path.dirname(os.path.abspath(__file__))

# Artifact types that actually exist as schemas and travel between agents.
ARTIFACT_TYPES = [
    "creative_brief", "concept_slate", "concept_bible", "asset_registry",
    "motion_asset_registry", "media_plan", "daily_optimization_log",
    "content_calendar", "social_post", "performance_report", "learnings_dossier",
]

# Records that are checked but are not creative artifacts. Routed by rule_class,
# excluded from the artifact matrix.
PROCESS_TYPES = ["incident_record", "erasure_request", "grievance_record",
                 "tenant_context"]

# Sub-objects that were being used as if they were artifact types.
TRANSLATE = {
    "verbal_deck": "concept_bible",
    "visual_deck": "concept_bible",
    # audio_asset_registry was introduced in v1.3.2 for ASCI-DISC-003 and has no
    # schema. Audio assets are motion_asset_registry entries with no video track.
    "audio_asset_registry": "motion_asset_registry",
}


def load_matrix():
    path = os.path.join(SPEC_DIR, "CHITRA-v1_2_1-Extended-Handoff-Schemas.md")
    text = open(path, encoding="utf-8").read()
    seg = text[text.index("§F.12 RULE-TO-SCHEMA CROSS-REFERENCE MATRIX"):
               text.index("### Reading the matrix")]
    rows, header = {}, None
    for line in seg.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None and "creative_brief" in line:
            header = cells[1:]
            continue
        if header is None or set("".join(cells)) <= set(":- "):
            continue
        rows[cells[0].strip("* ")] = {header[i] for i, c in enumerate(cells[1:])
                                      if i < len(header) and c == "●"}
    return rows


def main():
    rules = json.load(open(os.path.join(HERE, "chitra_rules.json"),
                           encoding="utf-8"))["rules"]
    matrix = load_matrix()

    print("=" * 78)
    print("ARTIFACT VOCABULARY RECONCILIATION")
    print("=" * 78)

    changes, added_from_matrix, translated = [], [], []
    for r in rules:
        before = list(r.get("applies_to", []))
        rule_class = r.get("rule_class", "artifact")

        if rule_class == "process":
            kept = [t for t in before if t in PROCESS_TYPES]
            if kept != before:
                changes.append((r["id"], before, kept, "process rule"))
            r["applies_to"] = kept or before
            continue

        # 1. translate sub-objects to the artifact that carries them
        mapped = []
        for t in before:
            if t in TRANSLATE:
                translated.append((r["id"], t, TRANSLATE[t]))
                mapped.append(TRANSLATE[t])
            elif t in ARTIFACT_TYPES:
                mapped.append(t)
            else:
                mapped.append(t)  # unknown, surfaced below
        mapped = sorted(set(mapped), key=ARTIFACT_TYPES.index
                        if all(m in ARTIFACT_TYPES for m in mapped) else str)

        # 2. union with the matrix row, if the rule has one
        row = matrix.get(r["id"], set())
        extra = sorted(row - set(mapped))
        if extra:
            added_from_matrix.append((r["id"], extra))
        final = [t for t in ARTIFACT_TYPES if t in set(mapped) | row]

        if final != before:
            changes.append((r["id"], before, final, ""))
        r["applies_to"] = final

    print(f"\n1. SUB-OBJECTS TRANSLATED TO THEIR CARRYING ARTIFACT "
          f"({len(translated)} occurrences)")
    by_src = {}
    for rid, src, dst in translated:
        by_src.setdefault((src, dst), []).append(rid)
    for (src, dst), ids in sorted(by_src.items()):
        print(f"   {src} -> {dst}   ({len(ids)} rules)")

    print(f"\n2. COVERAGE RESTORED FROM THE §F.12 MATRIX ({len(added_from_matrix)} rules)")
    for rid, extra in sorted(added_from_matrix):
        print(f"   {rid:<34} + {', '.join(extra)}")

    print(f"\n3. NET CHANGE IN COVERAGE BY ARTIFACT TYPE")
    before_counts = {t: 0 for t in ARTIFACT_TYPES}
    after_counts = {t: 0 for t in ARTIFACT_TYPES}
    original = json.load(open(os.path.join(HERE, "chitra_rules.json"),
                              encoding="utf-8"))["rules"]
    for r in original:
        for t in r.get("applies_to", []):
            if t in before_counts:
                before_counts[t] += 1
    for r in rules:
        for t in r["applies_to"]:
            if t in after_counts:
                after_counts[t] += 1
    print(f"   {'artifact type':<26}{'before':>8}{'after':>8}{'change':>10}")
    print("   " + "-" * 52)
    for t in ARTIFACT_TYPES:
        d = after_counts[t] - before_counts[t]
        flag = "  WAS UNCHECKED" if before_counts[t] == 0 and after_counts[t] else ""
        print(f"   {t:<26}{before_counts[t]:>8}{after_counts[t]:>8}"
              f"{('+' + str(d)) if d > 0 else str(d):>10}{flag}")

    out = os.path.join(HERE, "chitra_rules.reconciled.json")
    json.dump({"registry_version": "1.3.3", "rules": rules},
              open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\n   wrote {out}")

    # ---------------------------------------------------------------- matrix
    lines = ["## §F.12 RULE-TO-ARTIFACT MATRIX (GENERATED)", "",
             "> Generated by `reconcile_vocabulary.py` from each rule's",
             "> `applies_to`. Do not edit. Editing this table by hand is what",
             "> produced the 26-row divergence closed in v1.3.3.", "",
             "| Rule ID | " + " | ".join(ARTIFACT_TYPES) + " |",
             "|---|" + ":-:|" * len(ARTIFACT_TYPES)]
    artifact_rules = [r for r in rules if r.get("rule_class", "artifact") == "artifact"]
    for r in sorted(artifact_rules, key=lambda x: x["id"]):
        cells = ["●" if t in r["applies_to"] else "" for t in ARTIFACT_TYPES]
        lines.append(f"| **{r['id']}** | " + " | ".join(cells) + " |")
    lines += ["", "### Process rules (routed by `rule_class`, not artifact type)", ""]
    for r in sorted([x for x in rules if x.get("rule_class") == "process"],
                    key=lambda x: x["id"]):
        lines.append(f"- **{r['id']}** — {', '.join(r['applies_to'])}")
    lines += ["", f"*{len(artifact_rules)} artifact rules, "
                  f"{len(rules) - len(artifact_rules)} process rules.*"]
    mpath = os.path.join(HERE, "F12-generated.md")
    open(mpath, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"   wrote {mpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
