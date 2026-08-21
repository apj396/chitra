"""Extract the reissued rule set from the v1.3.2 patch into a registry file.

The rules live in the specification document. Hand-copying them into a second
file is exactly the divergence that produced P0-2, so the registry is generated
from the document and never edited directly.
"""
import json, re, sys

FENCE = re.compile(r"^```(\w*)\s*$")
RULE_START = re.compile(r"^-\s+id:\s*(\S+)\s*$", re.M)
SCALAR = re.compile(r"^  ([a-z_]+):\s*(.*)$")

def blocks(path):
    lang, buf = None, []
    for line in open(path, encoding="utf-8").read().splitlines():
        m = FENCE.match(line)
        if m and lang is None:
            lang, buf = m.group(1) or "text", []
        elif m and lang is not None:
            yield lang, "\n".join(buf); lang = None
        elif lang is not None:
            buf.append(line)

def parse(text):
    rules, cur = [], None
    for line in text.splitlines():
        m = RULE_START.match(line)
        if m:
            if cur: rules.append(cur)
            cur = {"id": m.group(1)}
            continue
        if cur is None: continue
        s = SCALAR.match(line)
        if s:
            k, v = s.group(1), s.group(2).strip()
            if not v or k in cur: continue
            if v in ("true", "false"): cur[k] = v == "true"
            elif v.startswith("["):
                cur[k] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
            else: cur[k] = v.strip('"').strip("'")
    if cur: rules.append(cur)
    return rules

out = []
for lang, text in blocks(sys.argv[1]):
    if lang in ("yaml", "yml") and RULE_START.search(text):
        out.extend(parse(text))
seen = {}
for r in out: seen[r["id"]] = r
rules = list(seen.values())
json.dump({"registry_version": "1.3.2", "rules": rules},
          open(sys.argv[2], "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"extracted {len(rules)} rules -> {sys.argv[2]}")
