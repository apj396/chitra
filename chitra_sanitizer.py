"""
chitra_sanitizer.py — executable implementation of CHITRA v1.2 §H, as corrected
by v1.3.2 §3.3.

Differences from the v1.2 §H.2 pseudocode, all deliberate:

  * Each rule's check runs exactly once. The original computed
    human_review_required with a second pass that re-invoked every check,
    doubling every consent-vault and legal-precheck round trip (audit P1-6).
  * severity == "conditional" resolves against the rule's escalation_threshold
    before aggregation, so it always lands in violations or warnings.
  * An unrecognised severity raises instead of falling through. The original
    if/elif silently dropped three cultural rules (audit P0-4).
  * load() rejects the entire registry if any rule fails rule_object.json,
    rather than returning the subset that parsed (v1.3.2 §3.4). Partial load is
    what turned a schema error into silent under-enforcement.
  * INCONCLUSIVE is a first-class outcome. A rule that cannot be evaluated
    routes to human review and never counts as a pass.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from jsonschema import Draft202012Validator

import chitra_facets as FCT
import chitra_predicates as P

HERE = os.path.dirname(os.path.abspath(__file__))


class SanitizerConfigurationError(Exception):
    """Raised at load or evaluation time for a registry the sanitizer cannot honour."""


class RegistryRejected(SanitizerConfigurationError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"registry rejected: {len(errors)} rule(s) fail rule_object.json")


@dataclass
class Rule:
    id: str
    source: list
    citation: str
    applies_to: list
    severity: str
    auto_fix_available: bool
    human_review_on_fail: bool
    check: str = ""
    applies_when: str = ""
    escalation_threshold: Optional[str] = None
    failure_message: Optional[str] = None
    rule_class: str = "artifact"
    shadow_mode: bool = False
    version: str = "1.0.0"
    raw: dict = field(default_factory=dict)

    @property
    def predicate(self):
        entry = P.REGISTRY.get(self.id)
        return entry["fn"] if entry else None

    @property
    def implementability(self):
        entry = P.REGISTRY.get(self.id)
        return entry["class"] if entry else "unimplemented"


@dataclass
class SanitizerResult:
    passed: bool
    checks_run: list
    violations: list
    warnings: list
    human_review_required: bool
    human_review_reason: Optional[str] = None
    inconclusive: list = field(default_factory=list)
    redacted_payload: Optional[dict] = None
    skipped_shadow: list = field(default_factory=list)

    def to_dict(self):
        d = {
            "pass": self.passed,
            "checks_run": self.checks_run,
            "violations": self.violations,
            "warnings": self.warnings,
            "human_review_required": self.human_review_required,
        }
        if self.human_review_reason:
            d["human_review_reason"] = self.human_review_reason
        if self.inconclusive:
            d["inconclusive"] = self.inconclusive
        if self.redacted_payload is not None:
            d["redacted_payload"] = self.redacted_payload
        if self.skipped_shadow:
            d["skipped_shadow"] = self.skipped_shadow
        return d


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

ALLOWED_SEVERITIES = {"block", "warn", "info", "conditional"}


class RuleRegistry:
    def __init__(self, rules, schema=None):
        self.rules = rules
        self.schema = schema
        self._by_type = {}
        for r in rules:
            for t in r.applies_to:
                self._by_type.setdefault(t, []).append(r)

    @classmethod
    def load(cls, rules_path=None, schema_path=None, allow_partial=False):
        rules_path = rules_path or os.path.join(HERE, "chitra_rules.json")
        data = json.load(open(rules_path, encoding="utf-8"))
        schema = None
        if schema_path and os.path.exists(schema_path):
            schema = json.load(open(schema_path, encoding="utf-8"))

        errors = []
        if schema is not None:
            v = Draft202012Validator(schema)
            for raw in data["rules"]:
                payload = dict(raw)
                for e in v.iter_errors(payload):
                    errors.append((raw.get("id", "?"), e.message))
        if errors and not allow_partial:
            # v1.3.2 §3.4: fail closed on a registry that does not fully validate.
            raise RegistryRejected(errors)

        rules = []
        for raw in data["rules"]:
            sev = raw.get("severity")
            if sev not in ALLOWED_SEVERITIES:
                raise SanitizerConfigurationError(
                    f"rule {raw.get('id')} declares unhandled severity {sev!r}")
            if sev == "conditional" and not raw.get("escalation_threshold"):
                raise SanitizerConfigurationError(
                    f"rule {raw.get('id')} is conditional but declares no "
                    "escalation_threshold")
            known = {f for f in Rule.__dataclass_fields__ if f != "raw"}
            rules.append(Rule(**{k: v for k, v in raw.items() if k in known}, raw=raw))
        return cls(rules, schema)

    def for_artifact(self, artifact_type):
        return list(self._by_type.get(artifact_type, []))

    def for_class(self, rule_class):
        return [r for r in self.rules if r.rule_class == rule_class]

    def get(self, rule_id):
        return next((r for r in self.rules if r.id == rule_id), None)


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
# Trailing quote optional: the rule extractor strips it, so a pattern that
# required it never matched, _escalates fell through to its fail-safe True,
# and every conditional rule blocked at any level. The fail-safe hid the bug.
_THRESHOLD = re.compile(r"level\s*>=\s*'?(\w+)'?")


def _escalates(rule, result, ctx):
    """Resolve a conditional rule to block or warn.

    escalation_threshold is a pseudocode expression in the specification. Only
    the cultural_risk_audit.level form is used by any current rule, so that form
    is parsed and anything else is treated as escalating, which fails safe.
    """
    m = _THRESHOLD.search(rule.escalation_threshold or "")
    if not m:
        return True
    floor = _RISK_ORDER.get(m.group(1), 0)
    level = result.risk_level or ctx.get("cultural_risk_audit", {}).get("level")
    return _RISK_ORDER.get(level, 3) >= floor


def _applies(rule, artifact, ctx):
    """Evaluate applies_when.

    Rule bodies are pseudocode in the specification, so gating lives with the
    predicate: a rule whose applies_when is a constant or an unmodelled
    expression runs, and its predicate returns PASS when the rule is not
    engaged. The two total-prohibition rules gate on category here because
    reaching their predicate at all means failure.
    """
    if rule.id == "GAMING-RMG-001":
        cats = {"fantasy_sports_real_money", "rummy_real_money", "poker_real_money",
                "online_real_money_gaming", "gambling_gaming"}
        return (P.get(artifact, "involves_online_money_game", False)
                or P.get(artifact, "product_category") in cats)
    if rule.id == "TOBACCO-001":
        return P.get(artifact, "product_category") in {"tobacco", "cigarettes",
                                                       "tobacco_surrogate"}
    if rule.id == "ASCI-DARK-001":
        # v1.3.4: a dark pattern needs a surface to live on. Most creative has
        # none, and firing unconditionally sent every artifact to human review.
        mechanics = {"countdown_timer", "stock_indicator", "scarcity_badge",
                     "subscription_flow", "checkout_path", "free_trial_auto_renew",
                     "drip_pricing", "consent_gate", "unsubscribe_flow",
                     "pre_ticked_option", "urgency_banner"}
        surfaces = {str(x).lower() for x in (P.get(artifact, "offer_mechanics", []) or [])}
        surfaces |= {str(x).lower() for x in (P.get(artifact, "ui_elements", []) or [])}
        return bool(surfaces & mechanics
                    or P.get(artifact, "has_commercial_flow", False)
                    or P.get(artifact, "dark_patterns_present"))
    if rule.id == "ASCI-DISC-001":
        return bool(P.get(artifact, "paid_partnership", False)
                    or P.get(artifact, "material_connection", False))
    if rule.id in ("ASCI-DISC-002", "ASCI-DISC-003"):
        return bool(P.get(artifact, "paid_partnership", False)
                    and (P.get(artifact, "is_video", False)
                         or P.get(artifact, "is_audio", False)))
    if rule.id == "ASCI-AI-001":
        return P.get(artifact, "ai_risk_tier", "none") in ("medium", "high")
    if rule.id == "ASCI-AI-002":
        return bool(P.get(artifact, "uses_ai_persona", False)
                    and P.get(artifact, "audience_includes_under_12", False))
    if rule.id == "DPDP-CONSENT-001":
        return any(P.get(artifact, f, False) for f in
                   ("uses_custom_audience", "uses_crm_upload", "uses_whatsapp_marketing"))
    if rule.id == "DPDP-CHILDREN-001":
        return bool(P.get(artifact, "target_audience.includes_minors", False))
    if rule.id == "PLATFORM-TOS-META-SPECIAL-CAT-001":
        return P.get(artifact, "product_category") in {"credit", "employment", "housing",
                                                       "elections_politics"}
    if rule.id == "PLATFORM-TOS-META-PLACEMENT-001":
        return P.get(artifact, "platform_family") == "meta" or bool(
            P.get(artifact, "placements"))
    if rule.id == "PLATFORM-TOS-WHATSAPP-001":
        return P.get(artifact, "channel") == "whatsapp"
    if rule.id == "IP-AI-CONSENT-001":
        return any(P.get(artifact, f, False) for f in
                   ("uses_voice_clone", "uses_face_swap", "uses_likeness_synthesis"))
    if rule.id == "IP-COPYRIGHT-001":
        return any(P.get(artifact, f, False) for f in
                   ("uses_music", "uses_stock_imagery", "uses_celebrity_likeness"))
    if rule.id == "ASCI-GREENWASH-001":
        return bool(P.get(artifact, "contains_environmental_claim", False))
    if rule.id in ("ASCI-BFSI-001",):
        return (P.get(artifact, "sector") == "BFSI"
                and P.get(artifact, "contains_technical_advice", False))
    if rule.id in ("ASCI-HEALTH-001",):
        return (P.get(artifact, "sector") in ("healthcare", "nutrition")
                and P.get(artifact, "contains_technical_advice", False))
    if rule.id == "DMRA-001":
        return bool(P.get(artifact, "contains_health_claim", False))
    if rule.id == "DPDP-XBORDER-001":
        return bool(P.get(artifact, "involves_cross_border_transfer", False))
    sector_rules = {
        "RBI-BFSI-001": {"banking_lending_credit"},
        "SEBI-MUTUAL-FUND-001": {"mutual_funds_securities"},
        "IRDAI-INSURANCE-001": {"insurance"},
        "ALCOHOL-SURROGATE-001": {"alcohol", "alcohol_surrogate"},
        "REAL-ESTATE-RERA-001": {"real_estate"},
        "EDTECH-NEP-001": {"edtech"},
        "HEALTHCARE-CLAIM-SUB-001": {"healthcare", "medical_device", "supplements",
                                     "nutraceutical"},
    }
    if rule.id in sector_rules:
        return P.get(artifact, "product_category") in sector_rules[rule.id]
    return True


def sanitize(artifact_type, artifact, context=None, registry=None,
             apply_auto_fix=False):
    ctx = context or {}
    registry = registry or RuleRegistry.load()

    # v1.3.6: rules read a flat vocabulary; artifacts are nested and differently
    # named. The FacetView is the one seam between them, and it records when a
    # required facet cannot be resolved so absence cannot masquerade as False.
    view = FCT.FacetView(artifact, artifact_type, ctx)
    artifact = view

    candidates = registry.for_artifact(artifact_type)
    violations, warnings, inconclusive, checks_run, shadow = [], [], [], [], []
    human_review, review_reasons = False, []
    fixed = {}

    for rule in candidates:
        if not _applies(rule, artifact, ctx):
            continue
        checks_run.append(rule.id)

        fn = rule.predicate
        if fn is None:
            raise SanitizerConfigurationError(
                f"rule {rule.id} has no predicate implementation")

        view.take_misses()
        result = fn(artifact, ctx)          # evaluated exactly once
        misses = view.take_misses()

        if misses and result.status == P.PASS:
            # A rule cannot pass on fields that do not exist. This is the
            # defect class that let ALCOHOL-SURROGATE-001 and DMRA-001 approve
            # every artifact they were given.
            result = P.Result(
                P.INCONCLUSIVE,
                message=("Cannot evaluate: required field(s) not present on this "
                         f"artifact: {', '.join(sorted(misses))}."),
                evidence=f"unresolved facets: {sorted(misses)}",
                suggested_fix="Supply the field on the artifact, or in campaign "
                              "context if it is a campaign-level fact.")

        if result.status == P.PASS:
            continue

        entry = {
            "rule_id": rule.id,
            "source": rule.source[0] if rule.source else None,
            "message": result.message or rule.failure_message,
            "evidence": result.evidence,
            "suggested_fix": result.suggested_fix,
            "severity": rule.severity,
            "auto_fix_available": rule.auto_fix_available,
        }

        if result.status == P.INCONCLUSIVE:
            entry["reason"] = "inconclusive"
            inconclusive.append(entry)
            human_review = True
            review_reasons.append(f"{rule.id} could not be evaluated")
            continue

        if rule.shadow_mode:
            entry["shadow_mode"] = True
            shadow.append(entry)
            continue

        severity = rule.severity
        if severity == "conditional":
            severity = "block" if _escalates(rule, result, ctx) else "warn"
            entry["resolved_severity"] = severity

        if severity == "block":
            violations.append(entry)
        elif severity == "warn":
            warnings.append(entry)
        elif severity == "info":
            pass
        else:
            raise SanitizerConfigurationError(
                f"rule {rule.id} declares unhandled severity {rule.severity!r}")

        if rule.human_review_on_fail:
            human_review = True
            review_reasons.append(f"{rule.id} has human_review_on_fail=true")

        # v1.3.6: driven by whether a fix was actually produced. Branching on
        # rule.auto_fix_available meant reading a field 37 of 39 rules leave
        # false while the field is schema-required on all of them.
        if apply_auto_fix and result.fixed_payload:
            fixed = _merge(fixed, result.fixed_payload)

    return SanitizerResult(
        passed=(len(violations) == 0 and len(inconclusive) == 0),
        checks_run=checks_run,
        violations=violations,
        warnings=warnings,
        human_review_required=human_review,
        human_review_reason="; ".join(review_reasons) or None,
        inconclusive=inconclusive,
        redacted_payload=(fixed or None),
        skipped_shadow=shadow,
    )


def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out
