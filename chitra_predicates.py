"""
chitra_predicates.py — executable implementations of the v1.3.2 compliance rules.

Every rule in the registry carries a `check` string written as pseudocode. This
module turns each one into a function that runs, and records what each one
actually needs in order to run. That classification is the point of the module.

IMPLEMENTABILITY CLASSES
------------------------
DETERMINISTIC  Computable from the artifact's own content. The sanitizer reads
               the caption, the durations, the placement list, and decides. No
               external call, no trust in the producing agent.

SERVICE        Needs a call to consent-vault, legal-precheck, chitra-regdb or
               similar. Deterministic once the service answers, but the answer
               is not in the artifact.

SELF_DECLARED  Reads a boolean that the producing agent set on its own output.
               The predicate is trivially computable and enforces nothing: the
               agent under audit supplies the audit result. These look like
               deterministic rules in the specification and are the single
               largest correctness gap in the rule set.

JUDGMENT       Requires semantic evaluation of creative content that no boolean
               field can carry honestly. Needs a model or a human. Returns
               INCONCLUSIVE, which routes to human review per v1.2 §H.4.
"""

from dataclasses import dataclass, field
from typing import Optional

DETERMINISTIC = "deterministic"
SERVICE = "service"
SELF_DECLARED = "self_declared"
JUDGMENT = "judgment"

PASS, FAIL, INCONCLUSIVE = "pass", "fail", "inconclusive"


@dataclass
class Result:
    status: str
    message: Optional[str] = None
    evidence: Optional[str] = None
    suggested_fix: Optional[str] = None
    risk_level: Optional[str] = None      # for conditional-severity rules
    fixed_payload: Optional[dict] = None  # for auto_fix_available rules


REGISTRY = {}


def rule(rule_id, klass, note=""):
    def wrap(fn):
        REGISTRY[rule_id] = {"fn": fn, "class": klass, "note": note,
                             "name": fn.__name__}
        return fn
    return wrap


def get(artifact, path, default=None):
    """Read a dotted path from an artifact or a FacetView.

    A FacetView resolves rule vocabulary against the artifact schema, the
    campaign context, and declared derivations, and records a miss when a
    required facet cannot be resolved. A plain dict is read literally, so
    fixtures and hand-built artifacts still work.
    """
    if hasattr(artifact, "resolve"):
        return artifact.resolve(path, default)
    cur = artifact
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def declared(artifact, field_name, expected=False):
    """Read a self-declared boolean. Returns (value, present)."""
    val = get(artifact, field_name, None)
    return val, val is not None


def copy_text(artifact):
    """All human-readable copy in the artifact, flattened to one lowercase string.

    Several rules ask whether a disclosure is present. Asking the artifact for a
    boolean lets the producing agent answer for itself. Reading the copy and
    looking for the disclosure does not.
    """
    return " ".join(_flatten_strings(_unwrap(artifact))).lower()


def credential(ctx, cred_id):
    """Resolve a stated credential through the credential service, if present."""
    svc = ctx.get("services", {}).get("credential_registry")
    return svc.lookup(cred_id) if svc and cred_id else None


# --------------------------------------------------------------------------
# ASCI disclosure — the densest deterministic cluster in the set
# --------------------------------------------------------------------------

VALID_TAGS = {"#ad", "#advertisement", "#sponsored", "#promotion",
              "#paid", "#paidpartnership"}
AMBIGUOUS_TAGS = {"#collab", "#partnership", "#partnerof", "#ambassador"}


@rule("ASCI-DISC-001", DETERMINISTIC,
      "Reads the caption directly. Position and ambiguity are both computable.")
def asci_disc_001(artifact, ctx):
    if get(artifact, "platform_native_label") == "paid_partnership_with":
        return Result(PASS)
    caption = get(artifact, "content.caption", "") or ""
    first_line = (get(artifact, "content.first_line")
                  or caption.split("\n")[0] if caption else "")
    tokens = [t.strip(".,!:;").lower() for t in first_line.split()]
    found = [t for t in tokens if t in VALID_TAGS]
    ambiguous = [t for t in tokens if t in AMBIGUOUS_TAGS]

    if found:
        # Reject a qualifying tag stranded in a trailing hashtag cluster.
        tail = caption.rsplit("\n", 1)[-1] if "\n" in caption else ""
        if tail.strip().startswith("#") and tail.count("#") >= 4 and \
           not first_line.lower().startswith(tuple(VALID_TAGS)):
            return Result(FAIL,
                          "Disclosure appears only inside a trailing hashtag cluster.",
                          f"caption tail == {tail.strip()[:60]!r}",
                          "Move the disclosure to the start of the first line.")
        return Result(PASS)

    if ambiguous:
        return Result(FAIL,
                      "Ambiguous disclosure. ASCI 2026 prohibits #collab or "
                      "#partnership standing alone without #Ad.",
                      f"content.first_line == {first_line!r}",
                      f"Prepend '#Ad ' to first_line; {ambiguous[0]} may remain alongside it.",
                      fixed_payload={"content": {"first_line": f"#Ad {first_line}"}})

    return Result(FAIL,
                  "Paid partnership disclosure missing. ASCI requires #Ad in "
                  "first caption line.",
                  f"content.first_line == {first_line!r} — no qualifying hashtag",
                  "Prepend '#Ad ' to first_line and re-validate.",
                  fixed_payload={"content": {"first_line": f"#Ad {first_line}"}})


@rule("ASCI-DISC-002", DETERMINISTIC,
      "Durations are numbers on the artifact. Fully computable.")
def asci_disc_002(artifact, ctx):
    dur = get(artifact, "duration_sec")
    shown = get(artifact, "disclosure_visible_duration_sec", 0) or 0
    throughout = bool(get(artifact, "disclosure_visible_throughout", False))
    if get(artifact, "format_is_ephemeral", False):
        if throughout:
            return Result(PASS)
        return Result(FAIL, "Ephemeral formats require disclosure for the full duration.",
                      f"disclosure_visible_throughout == {throughout}",
                      "Extend the disclosure overlay across the whole story.")
    if dur is None:
        return Result(INCONCLUSIVE, "duration_sec absent; cannot evaluate.")
    if dur <= 15:
        need = 3
    elif dur <= 120:
        need = dur / 3
    else:
        return Result(PASS) if throughout else Result(
            FAIL, "Video over 2 minutes requires disclosure throughout.",
            f"duration_sec == {dur}, disclosure_visible_throughout == {throughout}",
            "Apply a persistent disclosure overlay.")
    if shown >= need:
        return Result(PASS)
    return Result(FAIL, f"Disclosure visible {shown}s; {need:.0f}s required.",
                  f"duration_sec == {dur}, disclosure_visible_duration_sec == {shown}",
                  f"Extend disclosure visibility to at least {need:.0f}s.")


@rule("ASCI-DISC-003", DETERMINISTIC,
      "Verbal disclosure start time is a timecode. Computable if the field exists.")
def asci_disc_003(artifact, ctx):
    if get(artifact, "is_audio", False):
        ok = get(artifact, "verbal_disclosure_at_segment_start")
        if ok is None:
            return Result(INCONCLUSIVE, "verbal_disclosure_at_segment_start absent.")
        return Result(PASS) if ok else Result(
            FAIL, "Audio brand segment lacks a verbal disclosure at its start.",
            "verbal_disclosure_at_segment_start == false",
            "Record a verbal disclosure at the start of the brand segment.")
    present = get(artifact, "verbal_disclosure_present")
    start = get(artifact, "verbal_disclosure_start_sec")
    if present is None:
        return Result(INCONCLUSIVE, "verbal_disclosure_present absent.")
    if not present:
        return Result(FAIL, "No verbal disclosure. A text overlay alone is not sufficient.",
                      "verbal_disclosure_present == false",
                      "Add a spoken disclosure within the first 10 seconds.")
    if start is None or start > 10:
        return Result(FAIL, f"Verbal disclosure starts at {start}s; must be within 10s.",
                      f"verbal_disclosure_start_sec == {start}",
                      "Move the spoken disclosure into the first 10 seconds.")
    return Result(PASS)


@rule("ASCI-AI-001", DETERMINISTIC,
      "Risk tier and label timings are structured fields; label accuracy is not.")
def asci_ai_001(artifact, ctx):
    tier = get(artifact, "ai_risk_tier", "medium")
    if tier == "high":
        return Result(FAIL, "High-risk AI use is prohibited; labelling does not cure it.",
                      "ai_risk_tier == 'high'",
                      "Withdraw or restructure the creative. A label is not a remedy.")
    if not get(artifact, "ai_label_present", False):
        return Result(FAIL, "AI use declared but no label present.",
                      "ai_label_present == false",
                      "Add a prominent label describing the AI use.")
    if get(artifact, "ai_label_accurately_describes_use") is None:
        return Result(INCONCLUSIVE,
                      "Label accuracy requires reading the label against the actual "
                      "AI use. Not computable from a boolean.")
    if get(artifact, "is_video", False):
        if not get(artifact, "ai_label_within_first_5_sec", False):
            return Result(FAIL, "AI label not visible in the first 5 seconds.",
                          "ai_label_within_first_5_sec == false",
                          "Surface the label at 0:00-0:05, then re-submit.")
        if not get(artifact, "ai_label_at_end", False):
            return Result(FAIL, "AI label not present at end of video.",
                          "ai_label_at_end == false", "Add an end-card label.")
        if get(artifact, "ai_persona_speaks", False) and \
           not get(artifact, "ai_label_visible_throughout_speech", False):
            return Result(FAIL, "AI persona speaks but label not visible throughout speech.",
                          "ai_label_visible_throughout_speech == false",
                          "Add a persistent corner-bug label for the synthetic dialogue.")
    return Result(PASS)


@rule("ASCI-AI-002", DETERMINISTIC, "Category and audience are enum fields.")
def asci_ai_002(artifact, ctx):
    banned = {"junk_food", "high_sugar_beverage", "weight_loss"}
    cat = get(artifact, "product_category")
    if cat in banned:
        return Result(FAIL, f"AI persona may not address under-12 audiences for {cat}.",
                      f"product_category == {cat!r}",
                      "Remove the AI persona or exclude the under-12 audience.")
    return Result(PASS)


@rule("ASCI-BFSI-001", SERVICE,
      "v1.3.4: replaced the self-declared boolean with a credential reference "
      "that must resolve. Absence of the reference is detectable; validity of "
      "the credential is a service lookup.")
def asci_bfsi_001(artifact, ctx):
    cid = get(artifact, "influencer_qualification_credential_id")
    if not cid:
        return Result(FAIL,
                      "BFSI technical advice without a qualification credential "
                      "reference.",
                      "influencer_qualification_credential_id absent",
                      "Attach the influencer's qualification credential id.")
    rec = credential(ctx, cid)
    if rec is None:
        return Result(INCONCLUSIVE, "Credential registry unavailable.")
    if not rec.get("valid"):
        return Result(FAIL, "Qualification credential does not resolve as valid.",
                      f"credential {cid!r} status {rec.get('status')!r}",
                      "Verify the credential or remove the technical advice.")
    if not any(t in copy_text(artifact) for t in
               (rec.get("designation", "\u0000").lower(), "qualified", "certified")):
        return Result(FAIL, "Credential held but the qualification is not stated in "
                            "the creative.",
                      "no qualification wording found in the copy",
                      "State the qualification prominently in the creative.")
    return Result(PASS)


@rule("ASCI-HEALTH-001", SERVICE,
      "v1.3.4: same credential-reference treatment as ASCI-BFSI-001.")
def asci_health_001(artifact, ctx):
    cid = get(artifact, "influencer_qualification_credential_id")
    if not cid:
        return Result(FAIL,
                      "Health or nutrition technical advice without a qualification "
                      "credential reference.",
                      "influencer_qualification_credential_id absent",
                      "Attach the credential id of the person giving the advice.")
    rec = credential(ctx, cid)
    if rec is None:
        return Result(INCONCLUSIVE, "Credential registry unavailable.")
    if not rec.get("valid"):
        return Result(FAIL, "Qualification credential does not resolve as valid.",
                      f"credential {cid!r} status {rec.get('status')!r}",
                      "Verify the credential or remove the technical advice.")
    return Result(PASS)


@rule("ASCI-DARK-001", JUDGMENT,
      "Whether a countdown is fake or button text is confirmshaming still needs "
      "judgement, but v1.3.4 narrows applies_when to artifacts that actually "
      "carry offer mechanics, so most creative never reaches it.")
def asci_dark_001(artifact, ctx):
    listed = get(artifact, "dark_patterns_present", None)
    if listed:
        return Result(FAIL, f"Dark patterns declared: {', '.join(listed)}.",
                      f"dark_patterns_present == {listed}",
                      "Remove the pattern or restructure the offer.")
    return Result(INCONCLUSIVE,
                  "Dark-pattern detection requires evaluating the creative and the "
                  "purchase flow, not a self-reported empty list.")


@rule("ASCI-GREENWASH-001", JUDGMENT,
      "Whether a claim is substantiated requires reading the claim and the evidence.")
def asci_greenwash_001(artifact, ctx):
    for f in ("claim_substantiated_with_third_party_certification",
              "claim_quantified_with_specific_metric",
              "claim_qualified_with_scope_disclosure"):
        if get(artifact, f, False):
            return Result(INCONCLUSIVE,
                          f"{f} asserted; substantiation must be verified against "
                          "the cited evidence.")
    return Result(FAIL, "Environmental claim with no substantiation route declared.",
                  "no substantiation field set",
                  "Attach third-party certification, a quantified metric, or a scope "
                  "qualification.")


# --------------------------------------------------------------------------
# DPDP
# --------------------------------------------------------------------------

def _consent(ctx):
    """Fetch the vault, or explain why there isn't one.

    Unverifiable consent BLOCKS rather than routing to human review, which is
    stricter than every other service dependency in the system and is
    deliberate. A reviewer looking at an inconclusive trademark check can go
    and read the register. A reviewer looking at unverifiable consent cannot
    conjure consent that may never have been given. Sending it to a human
    offers a decision nobody is entitled to make, and the queue will make it.
    """
    return ctx.get("services", {}).get("consent_vault")


@rule("DPDP-CONSENT-001", SERVICE,
      "Bound consent lookup: purpose, status and expiry. Blocks when the vault "
      "cannot answer, because unverifiable consent is not a human's call.")
def dpdp_consent_001(artifact, ctx):
    import chitra_services as _SV

    cid = get(artifact, "consent_artifact_id")
    if not cid:
        return Result(FAIL, "Custom audience or CRM upload without a consent "
                            "artifact.",
                      "consent_artifact_id absent",
                      "Attach a valid consent artifact before targeting.")
    vault = _consent(ctx)
    if vault is None:
        return Result(FAIL,
                      "Consent could not be verified: no consent vault is "
                      "configured. Processing personal data on unverifiable "
                      "consent is the violation, not the check.",
                      "services.consent_vault absent",
                      "Connect the consent vault. This does not go to human "
                      "review: a reviewer cannot supply consent that was never "
                      "given.")
    try:
        ok, why = vault.is_authorised(
            cid, purpose=get(artifact, "processing_purpose"))
    except _SV.ConsentUnavailable as e:
        return Result(FAIL, f"Consent could not be verified: {e}.",
                      f"consent_vault raised ConsentUnavailable for {cid!r}",
                      "Restore the consent vault before processing resumes.")
    if not ok:
        return Result(FAIL, f"Consent is not valid for this processing: {why}.",
                      f"consent_vault.is_authorised({cid!r}) -> {why}",
                      "Obtain fresh, purpose-bound consent or remove the "
                      "audience.")
    return Result(PASS)


@rule("DPDP-CHILDREN-001", SERVICE,
      "v1.3.4: parental consent now resolves through consent-vault, and "
      "behavioural targeting is derived from the plan's own targeting fields "
      "rather than asked of the planner that wrote them.")
def dpdp_children_001(artifact, ctx):
    # Derived, not asserted: behavioural targeting is visible in the plan itself.
    behavioural = {"lookalike", "retargeting", "custom_audience", "interest_graph",
                   "behavioural", "app_activity", "web_activity"}
    used = {str(b).lower() for b in (get(artifact, "targeting_bases", []) or [])}
    used |= {str(b).lower() for b in (get(artifact, "audience_signals", []) or [])}
    hit = used & behavioural
    if hit:
        return Result(FAIL,
                      "Behavioural targeting on an audience including minors is "
                      "prohibited under DPDP section 9.",
                      f"targeting includes {sorted(hit)}",
                      "Remove behavioural signals or exclude minors from the audience.")
    if get(artifact, "uses_targeted_advertising_directed_at_minors", False):
        return Result(FAIL, "Targeted advertising directed at minors is prohibited.",
                      "uses_targeted_advertising_directed_at_minors == true",
                      "Remove the minor-directed targeting.")
    import chitra_services as _SV

    vault = _consent(ctx)
    if vault is None:
        return Result(FAIL,
                      "Parental consent could not be verified: no consent vault "
                      "is configured. Section 9 processing cannot proceed on an "
                      "unverifiable basis.",
                      "services.consent_vault absent",
                      "Connect the consent vault, or exclude minors.")
    cid = get(artifact, "parental_consent_artifact_id")
    try:
        ok, why = vault.is_authorised(cid, consent_type="verifiable_parental")
    except _SV.ConsentUnavailable as e:
        return Result(FAIL, f"Parental consent could not be verified: {e}.",
                      "consent_vault raised ConsentUnavailable",
                      "Restore the consent vault, or exclude minors.")
    if not ok:
        return Result(FAIL, f"Verifiable parental consent not on record: {why}.",
                      f"parental_consent_artifact_id == {cid!r}: {why}",
                      "Obtain verifiable parental consent or exclude minors.")
    return Result(PASS)


@rule("DPDP-RETENTION-001", DETERMINISTIC,
      "v1.3.6: the individual-level-data test is a structural scan of free-text "
      "evidence fields for identifier markers, now written into the rule check "
      "rather than left as an undeclared implementation choice.")
def dpdp_retention_001(artifact, ctx):
    ceiling = ctx.get("tenant", {}).get("dpdp_retention_policy_days")
    keep = get(artifact, "data_retention_period_days")
    logs = get(artifact, "processing_log_retention_days")
    if keep is not None and ceiling is not None and keep > ceiling:
        return Result(FAIL, f"Retention {keep}d exceeds the tenant ceiling {ceiling}d.",
                      f"data_retention_period_days == {keep}",
                      f"Reduce retention to {ceiling} days or fewer.")
    if logs is not None and logs < 365:
        return Result(FAIL, f"Processing-log retention {logs}d is below the one-year floor.",
                      f"processing_log_retention_days == {logs}",
                      "Raise processing-log retention to at least 365 days.")
    hits = _scan_individual_records(artifact)
    if hits:
        return Result(FAIL, "Individual-level data found in a next-cycle artifact.",
                      f"{hits[0]}", "Aggregate to cohort. Minimum cohort size: 100.")
    return Result(PASS)


_ID_MARKERS = ("customer_id", "user_id", "email", "phone", "device_id", "aadhaar")


def _scan_individual_records(node, path="artifact"):
    """Structural probe for individual-level records in free-text evidence."""
    node = _unwrap(node)
    hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            hits += _scan_individual_records(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hits += _scan_individual_records(v, f"{path}[{i}]")
    elif isinstance(node, str):
        low = node.lower()
        for marker in _ID_MARKERS:
            if marker in low:
                hits.append(f"{path} contains {node[:70]!r} — individual record")
                break
    return hits


@rule("DPDP-BREACH-NOTIFY-001", DETERMINISTIC, "Process rule; timestamps are computable.")
def dpdp_breach_notify_001(incident, ctx):
    if not incident.get("notification", {}).get("to_dpbi_sent"):
        return Result(FAIL, "Breach not notified to the Data Protection Board.",
                      "notification.to_dpbi_sent == false", "Notify the DPBI now.")
    if not incident.get("notification", {}).get("to_affected_data_principals_sent"):
        return Result(FAIL, "Affected Data Principals not notified.",
                      "notification.to_affected_data_principals_sent == false",
                      "Notify affected Data Principals now.")
    elapsed = incident.get("notification", {}).get("elapsed_hours")
    if elapsed is not None and elapsed > 72:
        return Result(FAIL, f"Notification sent after {elapsed}h; ceiling is 72h.",
                      f"elapsed_hours == {elapsed}",
                      "Record the delay and its cause in the incident file.")
    return Result(PASS)


@rule("DPDP-SENSITIVE-TARGETING-001", DETERMINISTIC, "Targeting bases are an enum list.")
def dpdp_sensitive_targeting_001(artifact, ctx):
    forbidden = {"religion_alone", "caste", "political_affiliation",
                 "sexual_orientation", "health_condition", "trade_union_membership"}
    bases = set(get(artifact, "targeting_bases", []) or [])
    hit = bases & forbidden
    if not hit:
        return Result(PASS)
    b = sorted(hit)[0]
    # ADR-003 removed the affirmative-brand and legitimate-health carve-outs.
    # Both turned on a self-declared brand posture, which is the pattern
    # v1.3.4 stripped from the execution layer everywhere else, and Meta and
    # Google prohibit orientation-based targeting regardless, so a locally
    # passed artifact would fail at the network API anyway.
    return Result(FAIL, f"Targeting on a prohibited basis: {b}.",
                  f"targeting_bases includes {b!r}",
                  f"Remove {b} from the audience definition. Reach the audience "
                  f"through content and context rather than a protected attribute.")


@rule("DPDP-ERASURE-001", DETERMINISTIC, "Process rule; all fields structural.")
def dpdp_erasure_001(req, ctx):
    if not req.get("data_principal_authorization"):
        return Result(FAIL, "Erasure request without Data Principal authorisation.",
                      "data_principal_authorization absent",
                      "Capture and attach the authorisation.")
    if not req.get("reversal_window_bypassed"):
        return Result(FAIL, "Erasure did not bypass the 30-day reversal window.",
                      "reversal_window_bypassed == false",
                      "Set erasure_request to bypass the soft-delete window.")
    hrs = req.get("completed_within_hours")
    if hrs is not None and hrs > 72:
        return Result(FAIL, f"Erasure completed after {hrs}h; ceiling is 72h.",
                      f"completed_within_hours == {hrs}", "Escalate to the DPO.")
    if not req.get("cascade_to_external_platforms_confirmed"):
        return Result(FAIL, "External platform cascade not confirmed.",
                      "cascade_to_external_platforms_confirmed == false",
                      "Confirm deletion on Meta, Google and WhatsApp audience lists.")
    return Result(PASS)


@rule("DPDP-XBORDER-001", SERVICE, "Requires the current MeitY restricted-country list.")
def dpdp_xborder_001(artifact, ctx):
    dest = get(artifact, "destination_country")
    regdb = ctx.get("services", {}).get("regdb")
    if regdb is None:
        return Result(INCONCLUSIVE, "regdb unavailable; cannot check the MeitY list.")
    if dest in regdb.restricted_countries():
        return Result(FAIL, f"Transfer to {dest} is restricted.",
                      f"destination_country == {dest!r}",
                      "Localise the processing or seek an alternative destination.")
    if not get(artifact, "transfer_basis_documented", False):
        return Result(FAIL, "Cross-border transfer without a documented basis.",
                      "transfer_basis_documented == false",
                      "Document the transfer basis before Phase 3 on 13 May 2027.")
    return Result(PASS)


@rule("DPDP-GRIEVANCE-001", DETERMINISTIC, "Process rule; day counts are computable.")
def dpdp_grievance_001(g, ctx):
    if not g.get("acknowledgement_sent"):
        return Result(FAIL, "Grievance not acknowledged.", "acknowledgement_sent == false",
                      "Send an acknowledgement.")
    d = g.get("resolved_within_days")
    if d is None or d > 90:
        return Result(FAIL, f"Grievance resolution at {d} days exceeds the 90-day window.",
                      f"resolved_within_days == {d}", "Escalate to the grievance officer.")
    return Result(PASS)


# --------------------------------------------------------------------------
# Sectoral
# --------------------------------------------------------------------------

@rule("DMRA-001", SERVICE,
      "Delegates to regdb.dmra_schedule_conditions. Runs in shadow mode until "
      "the 54 Schedule conditions are populated.")
def dmra_001(artifact, ctx):
    regdb = ctx.get("services", {}).get("regdb")
    if regdb is None:
        return Result(INCONCLUSIVE, "regdb unavailable; DMRA Schedule not loaded.")
    schedule = regdb.dmra_schedule_conditions()
    if not schedule:
        return Result(INCONCLUSIVE, "DMRA Schedule is empty; rule cannot enforce.")

    # ADR-010: the Schedule is compiled from secondary sources until a curator
    # verifies it against the Gazette. Match on the copy as well as the declared
    # list, because a claim is made in words, not in a field.
    claimed = {str(c).lower() for c in (get(artifact, "claimed_conditions", []) or [])}
    text = copy_text(artifact)
    hits = sorted({t for t in schedule
                   if t in claimed or (len(t) > 5 and t in text)})
    if hits:
        return Result(FAIL,
                      f"Claim addresses a condition in the DMRA Schedule: {hits[0]}.",
                      f"matched {hits[0]!r} in the artifact",
                      "Remove the therapeutic claim. The DMRA Schedule prohibits "
                      "advertising cure, prevention or diagnosis for this condition.")
    return Result(PASS)


def _requires(artifact, fields, msg, fix):
    missing = [f for f in fields if not get(artifact, f, False)]
    if missing:
        return Result(FAIL, msg, f"missing: {', '.join(missing)}", fix)
    return None


def _forbids(artifact, fields, msg, fix):
    present = [f for f in fields if get(artifact, f, False)]
    if present:
        return Result(FAIL, msg, f"present: {', '.join(present)}", fix)
    return None


GUARANTEE_PHRASES = ("guaranteed return", "assured return", "risk-free return",
                     "guaranteed profit", "assured profit", "100% safe returns",
                     "guaranteed income")


@rule("RBI-BFSI-001", DETERMINISTIC,
      "v1.3.4: reads the copy. A rate disclosure, a terms-apply line and "
      "guarantee language are all detectable in text.")
def rbi_bfsi_001(artifact, ctx):
    import re as _re
    text = copy_text(artifact)
    for phrase in GUARANTEE_PHRASES:
        if phrase in text:
            return Result(FAIL, "Guaranteed-returns language is prohibited in credit "
                                "advertising.",
                          f"copy contains {phrase!r}", "Remove the guarantee language.")
    has_rate = bool(_re.search(r"\b\d+(\.\d+)?\s*%", text)) and \
        any(t in text for t in ("apr", "interest", "rate of interest", "per annum",
                                "p.a."))
    if not has_rate:
        return Result(FAIL, "Credit advertising without an APR or interest rate "
                            "disclosure in the copy.",
                      "no rate figure found alongside APR or interest wording",
                      "State the APR or interest rate in the creative.")
    if not any(t in text for t in ("t&c apply", "t & c apply", "terms and conditions "
                                   "apply", "terms apply", "conditions apply")):
        return Result(FAIL, "Credit advertising without a terms-apply disclosure.",
                      "no terms-apply wording found in the copy",
                      "Add a terms and conditions apply line.")
    return Result(PASS)


@rule("SEBI-MUTUAL-FUND-001", DETERMINISTIC,
      "v1.3.4: the market risk disclaimer is a fixed statutory sentence and is "
      "detectable in the copy. Duration and voiceover were already numeric.")
def sebi_mutual_fund_001(artifact, ctx):
    text = copy_text(artifact)
    if not ("subject to market risk" in text and
            "scheme related document" in text):
        return Result(FAIL, "Standard market risk disclaimer not found in the copy.",
                      "copy does not contain the statutory market-risk sentence",
                      "Add: mutual fund investments are subject to market risks, "
                      "read all scheme related documents carefully.")
    if get(artifact, "is_video", False):
        secs = get(artifact, "market_risk_disclaimer_visible_min_sec", 0) or 0
        if secs < 5:
            return Result(FAIL, f"Risk disclaimer visible {secs}s; 5s required.",
                          f"market_risk_disclaimer_visible_min_sec == {secs}",
                          "Extend the disclaimer to at least 5 seconds.")
        if not get(artifact, "market_risk_disclaimer_voiceover", False):
            return Result(FAIL, "Risk disclaimer requires a voiceover in video.",
                          "market_risk_disclaimer_voiceover == false",
                          "Add the spoken risk disclaimer.")
    return Result(PASS)


@rule("IRDAI-INSURANCE-001", DETERMINISTIC,
      "v1.3.4: an IRDAI registration number has a recognisable form and can be "
      "detected in the copy, like the RERA number.")
def irdai_insurance_001(artifact, ctx):
    import re as _re
    text = copy_text(artifact)
    for phrase in GUARANTEE_PHRASES:
        if phrase in text:
            return Result(FAIL, "Misleading returns language is prohibited in "
                                "insurance advertising.",
                          f"copy contains {phrase!r}", "Remove the returns claim.")
    if not _re.search(r"irdai?\s*(regn?\.?|registration)?\s*(no\.?|number)?\s*:?\s*"
                      r"[a-z0-9/\-]{2,}", text):
        return Result(FAIL, "Insurance advertising without an IRDAI registration "
                            "number in the copy.",
                      "no IRDAI registration number found",
                      "Add the IRDAI registration number to the creative.")
    if not any(t in text for t in ("terms and conditions", "policy terms",
                                   "policy document", "for more details on the "
                                   "risk factors")):
        return Result(FAIL, "Insurance advertising without a policy terms disclosure.",
                      "no policy terms wording found in the copy",
                      "Add the policy terms disclosure.")
    return Result(PASS)


@rule("GAMING-RMG-001", DETERMINISTIC,
      "Total prohibition. Reached only when applies_when matched, so it always fails.")
def gaming_rmg_001(artifact, ctx):
    cat = get(artifact, "product_category")
    return Result(FAIL,
                  "Advertising online money games is prohibited under Act 32 of 2025. "
                  "Direct and indirect promotion both attract imprisonment up to 2 years "
                  "and a fine up to Rs 50 lakh.",
                  f"product_category == {cat!r}" if cat else
                  "involves_online_money_game == true",
                  "Withdraw the campaign. E-sports recognised under the National Sports "
                  "Governance Act 2025 and social games without stakes must be declared "
                  "as esports_recognised or online_social_gaming_no_stakes.")


@rule("TOBACCO-001", DETERMINISTIC, "Total prohibition on category match.")
def tobacco_001(artifact, ctx):
    return Result(FAIL, "Direct tobacco advertising is banned in India.",
                  f"product_category == {get(artifact, 'product_category')!r}",
                  "Withdraw the campaign.")


@rule("ALCOHOL-SURROGATE-001", SERVICE,
      "ADR-013: blocks by default, lifted only by a CA attestation that resolves "
      "in the credential registry. ASCI already requires the brand-extension "
      "thresholds to be certified by an independent CA firm, so the qualifying "
      "test is whether that certificate exists, not whether CHITRA can parse a "
      "balance sheet.")
def alcohol_surrogate_001(artifact, ctx):
    if get(artifact, "directly_promotes_alcohol", False):
        return Result(FAIL, "Direct alcohol promotion is prohibited.",
                      "directly_promotes_alcohol == true", "Withdraw the campaign.")

    att_id = get(artifact, "ca_attestation_id")
    if not att_id:
        return Result(FAIL,
                      "Alcohol-adjacent advertising is blocked by default. "
                      "Surrogate advertising is prohibited under the CCPA "
                      "Guidelines 2022; only a genuine brand extension certified "
                      "against the ASCI Brand Extension Guidelines may proceed.",
                      "no ca_attestation_id on the artifact",
                      "Attach a ca_attestation_id from an independent CA firm "
                      "certifying the extension meets the ASCI thresholds.")

    reg = ctx.get("services", {}).get("credential_registry")
    if reg is None:
        return Result(INCONCLUSIVE, "credential-registry unavailable; cannot "
                                    "resolve the CA attestation.")
    att = reg.ca_attestation(att_id)
    if att is None:
        return Result(FAIL, "CA attestation does not resolve as a valid brand-"
                            "extension certificate.",
                      f"ca_attestation_id {att_id!r} did not resolve",
                      "Supply a current attestation from an independent CA firm.")

    # Even with a valid extension, consumption cues turn the extension ad back
    # into an ad for the restricted product.
    if get(artifact, "uses_alcohol_consumption_imagery", False):
        return Result(FAIL, "Certified brand extension may not use alcohol "
                            "consumption imagery.",
                      "uses_alcohol_consumption_imagery == true",
                      "Remove pouring, glassware and consumption cues.")
    return Result(PASS)


@rule("REAL-ESTATE-RERA-001", DETERMINISTIC,
      "A RERA registration number has a known format and can be detected in copy.")
def real_estate_rera_001(artifact, ctx):
    import re as _re
    text = " ".join(str(v) for v in _flatten_strings(_unwrap(artifact)))
    if _re.search(r"\b[A-Z]{1,3}\s?RERA\s?[A-Z0-9/\-]{6,}", text, _re.I) or \
       get(artifact, "contains_rera_registration_number", False):
        if not get(artifact, "contains_project_details_disclosure", False):
            return Result(FAIL, "RERA number present but project details missing.",
                          "contains_project_details_disclosure == false",
                          "Add carpet area, possession date and approvals.")
        return Result(PASS)
    return Result(FAIL, "Real estate advertising requires a RERA registration number.",
                  "no RERA registration number found in the artifact",
                  "Add the RERA registration number to the creative.")


def _unwrap(node):
    """Traversal helpers walk the real payload, not the facet view."""
    return node.payload if hasattr(node, "payload") else node


def _flatten_strings(node):
    node = _unwrap(node)
    if isinstance(node, dict):
        for v in node.values():
            yield from _flatten_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _flatten_strings(v)
    elif isinstance(node, str):
        yield node


@rule("EDTECH-NEP-001", JUDGMENT,
      "Whether copy makes a fear-of-failure appeal requires reading the copy.")
def edtech_nep_001(artifact, ctx):
    r = _forbids(artifact, ["guarantees_specific_exam_rank_or_marks",
                            "uses_fear_of_failure_appeals_to_parents",
                            "uses_unverified_testimonials_of_minors"],
                 "Prohibited edtech advertising technique declared.",
                 "Remove the guarantee, fear appeal or unverified testimonial.")
    if r:
        return r
    return Result(INCONCLUSIVE,
                  "Fear-of-failure appeals and rank guarantees must be assessed "
                  "against the actual copy.")


@rule("HEALTHCARE-CLAIM-SUB-001", SERVICE,
      "Evidence IDs must resolve; DGCI approval status is an external lookup.")
def healthcare_claim_sub_001(artifact, ctx):
    if not get(artifact, "health_claims_have_evidence_id", False):
        return Result(FAIL, "Health claims without an evidence identifier.",
                      "health_claims_have_evidence_id == false",
                      "Attach the substantiating evidence identifier.")
    if get(artifact, "uses_doctor_endorsement", False):
        regdb = ctx.get("services", {}).get("regdb")
        if regdb is None:
            return Result(INCONCLUSIVE, "regdb unavailable; cannot check DGCI approval.")
        if not regdb.dgci_approved(get(artifact, "product_id")):
            return Result(FAIL, "Doctor endorsement without DGCI approval.",
                          f"product_id {get(artifact, 'product_id')!r} not DGCI-approved",
                          "Remove the endorsement or obtain approval.")
    return Result(PASS)


# --------------------------------------------------------------------------
# IP and platform
# --------------------------------------------------------------------------

@rule("IP-TRADEMARK-001", SERVICE, "Requires legal-precheck clearance.")
def ip_trademark_001(artifact, ctx):
    lp = ctx.get("services", {}).get("legal_precheck")
    if lp is None:
        return Result(INCONCLUSIVE, "legal-precheck unavailable.")
    tenant_id = ctx.get("tenant", {}).get("tenant_id")
    classes = ctx.get("campaign", {}).get("nice_classes")
    hits = (lp.collisions(artifact, tenant_id, classes)
            if hasattr(lp, "collisions") else
            ([] if lp.trademark_clearance_passed(artifact) else [{"mark": "?"}]))
    if hits:
        h = hits[0]
        return Result(FAIL,
                      f"Mark collision: {h['mark']!r} is a {h.get('status','registered')} "
                      f"mark owned by {h.get('owner','another party')}.",
                      f"{h.get('match','exact')} match on {h['mark']!r}"
                      + (f" in Nice class {h['nice_class']}" if h.get("nice_class") else ""),
                      "Change the mark, or obtain clearance from the owner "
                      "before proceeding.")
    if get(artifact, "references_competitor_mark", False) and \
       not get(artifact, "comparative_claim_substantiated", False):
        return Result(FAIL, "Competitor mark referenced without a substantiated claim.",
                      "references_competitor_mark == true, "
                      "comparative_claim_substantiated == false",
                      "Substantiate the comparative claim or remove the reference.")
    return Result(PASS)


@rule("IP-COPYRIGHT-001", DETERMINISTIC,
      "v1.3.6: licence documentation only. The territory check moved to "
      "IP-COPYRIGHT-002, which is a warn, reconciling the rule with the "
      "worked example in v1.2.1 §F.13 Example 3.")
def ip_copyright_001(artifact, ctx):
    for uses, doc, label in (("uses_music", "music_license_documented", "Music"),
                             ("uses_stock_imagery", "stock_license_documented", "Stock imagery"),
                             ("uses_celebrity_likeness", "celebrity_contract_documented",
                              "Celebrity likeness")):
        if get(artifact, uses, False) and not get(artifact, doc, False):
            return Result(FAIL, f"{label} used without documented licence.",
                          f"{uses} == true, {doc} == false",
                          f"Attach the {label.lower()} licence.")
    return Result(PASS)


@rule("IP-COPYRIGHT-002", DETERMINISTIC,
      "Territory clearance against the placement list. Warn, not block: the "
      "licence may well cover the placement and only the paperwork needs "
      "checking.")
def ip_copyright_002(artifact, ctx):
    territory = get(artifact, "music_license_territory")
    placements = get(artifact, "placements", []) or []
    if isinstance(placements, str):
        placements = [placements]
    global_p = [p for p in placements
                if p in ("youtube_long", "youtube_short", "x_video",
                         "linkedin_video", "instagram_reel")]
    if territory and territory != "global" and global_p:
        return Result(FAIL,
                      f"Music licensed for {territory} but placed on globally "
                      f"reaching surfaces: {', '.join(global_p)}. Verify the "
                      "territory is cleared.",
                      f"music_license_territory == {territory!r}, placements "
                      f"include {global_p}",
                      "Confirm territory clearance, or restrict the placements.")
    return Result(PASS)


@rule("CHITRA-HITL-BUDGET-001", DETERMINISTIC,
      "v1.3.6: written because v1.2.1 §F.13 Example 4 reported a violation from "
      "this id and no such rule existed anywhere in the registry.")
def chitra_hitl_budget_001(artifact, ctx):
    threshold = ctx.get("tenant", {}).get("hitl_budget_shift_threshold_pct", 20)
    actions = get(artifact, "actions_taken", []) or []
    if isinstance(actions, dict):
        actions = [actions]
    for i, a in enumerate(actions):
        if not isinstance(a, dict):
            continue
        shift = abs(a.get("budget_shift_percent") or 0)
        if shift <= threshold:
            continue
        if a.get("hitl_triggered") and a.get("human_approver_id"):
            continue
        return Result(FAIL,
                      f"Budget shift of {shift}% recorded without HITL approval.",
                      f"actions_taken[{i}].budget_shift_percent == {shift}; "
                      f"hitl_triggered == {a.get('hitl_triggered')}; "
                      f"human_approver_id is {a.get('human_approver_id')!r}",
                      "Route the action to the brand owner for approval. Until "
                      "approved, revert it or mark it pending.")
    return Result(PASS)


@rule("IP-AI-CONSENT-001", DETERMINISTIC,
      "Consent and content-credential presence are structural; the fabricated-"
      "endorsement test is a judgement the artifact currently self-declares.")
def ip_ai_consent_001(artifact, ctx):
    for f, msg in (("depicts_fabricated_endorsement", "Fabricated endorsement"),
                   ("depicts_fake_authority_figure", "Fake authority figure")):
        if get(artifact, f, False):
            return Result(FAIL, f"{msg} is prohibited outright; consent and labelling "
                                "do not cure it.", f"{f} == true",
                          "Withdraw or restructure the creative.")
    if not get(artifact, "subject_consent_documented", False):
        return Result(FAIL, "Synthetic likeness without documented subject consent.",
                      "subject_consent_documented == false",
                      "Obtain and attach the subject's consent.")
    if not get(artifact, "deepfake_label_present", False):
        return Result(FAIL, "Synthetic likeness without a disclosure label.",
                      "deepfake_label_present == false", "Add the synthetic-media label.")
    if not get(artifact, "content_credentials_attached", False):
        return Result(FAIL, "Content credentials not attached.",
                      "content_credentials_attached == false",
                      "Attach C2PA content credentials at export.")
    return Result(PASS)


@rule("IP-REAL-PERSON-LIKENESS-001", DETERMINISTIC,
      "ADR-018: harvested from the parallel v1.2 derivation. Distinct from "
      "IP-COPYRIGHT-001's celebrity contract test, which covers contracted "
      "talent; this covers any identifiable real person, contracted or not.")
def ip_real_person_likeness_001(artifact, ctx):
    people = get(artifact, "identifiable_real_persons", []) or []
    if isinstance(people, dict):
        people = [people]
    for i, person in enumerate(people):
        if not isinstance(person, dict):
            return Result(INCONCLUSIVE,
                          "identifiable_real_persons entries must carry a release "
                          "reference.")
        if person.get("is_public_figure") and person.get("editorial_context"):
            continue
        if not person.get("release_document_uri"):
            return Result(FAIL,
                          "Identifiable real person depicted without a signed "
                          "release.",
                          f"identifiable_real_persons[{i}] "
                          f"({person.get('name', 'unnamed')}) has no "
                          f"release_document_uri",
                          "Obtain and attach a personality release, or replace "
                          "the depiction.")
    return Result(PASS)


@rule("PLATFORM-TOS-WHATSAPP-001", SERVICE,
      "v1.3.4: opt-in now resolves through consent-vault, which is where opt-in "
      "is recorded. Template approval remains a platform fact.")
def platform_tos_whatsapp_001(artifact, ctx):
    import chitra_services as _SV

    vault = _consent(ctx)
    if vault is None:
        return Result(FAIL,
                      "Opt-in could not be verified: no consent vault is "
                      "configured.",
                      "services.consent_vault absent",
                      "Connect the consent vault before sending marketing "
                      "templates.")
    cid = get(artifact, "opt_in_consent_artifact_id")
    try:
        ok, why = vault.is_authorised(cid, channel="whatsapp")
    except _SV.ConsentUnavailable as e:
        return Result(FAIL, f"Opt-in could not be verified: {e}.",
                      "consent_vault raised ConsentUnavailable",
                      "Restore the consent vault.")
    if not ok:
        return Result(FAIL, f"WhatsApp marketing without valid opt-in: {why}.",
                      f"opt_in_consent_artifact_id == {cid!r}: {why}",
                      "Obtain channel-specific opt-in before sending.")
    return (_requires(artifact, ["template_pre_approved",
                                 "respects_24h_utility_window"],
                      "WhatsApp marketing requires a pre-approved template and "
                      "respect for the 24-hour utility window.",
                      "Pre-approve the template with Meta before sending.")
            or Result(PASS))


@rule("PLATFORM-TOS-META-SPECIAL-CAT-001", DETERMINISTIC, "Enum comparison.")
def platform_tos_meta_special_cat_001(artifact, ctx):
    if not get(artifact, "special_ad_category_declared_in_meta", False):
        return Result(FAIL, "Special ad category not declared to Meta.",
                      f"product_category == {get(artifact, 'product_category')!r}, "
                      "special_ad_category_declared_in_meta == false",
                      "Declare the special ad category in the campaign object.")
    return Result(PASS)


@rule("PLATFORM-TOS-META-PLACEMENT-001", DETERMINISTIC,
      "Placement list comparison. Catches the silently-stripped case before the call.")
def platform_tos_meta_placement_001(artifact, ctx):
    removed = {"instagram_explore_feed", "messenger_stories"}
    placements = get(artifact, "placements", []) or []
    hit = [p for p in placements if p in removed]
    if hit:
        remaining = [p for p in placements if p not in removed]
        return Result(FAIL,
                      f"Placement removed in Meta Marketing API v26.0: {', '.join(hit)}. "
                      "Explore Feed errors; Messenger Stories is stripped silently, so "
                      "the campaign would run with targeting the media plan does not "
                      "describe.",
                      f"placements includes {hit}",
                      f"Remove {', '.join(hit)} from the placement list.",
                      fixed_payload={"placements": remaining})
    return Result(PASS)


# --------------------------------------------------------------------------
# Cultural — every one of these is a judgement call
# --------------------------------------------------------------------------

# Cultural surfaces that introduce risk an inherited audit did not assess.
NEW_CULTURAL_SURFACE = (
    "introduces_new_talent", "introduces_new_language", "introduces_new_setting",
    "introduces_new_festival_reference", "introduces_new_religious_reference",
    "introduces_new_regional_depiction",
)


def resolve_cultural_audit(artifact, ctx):
    """Find the cultural risk audit governing this artifact.

    v1.3.5 scoping decision: the audit is scoped to the CONCEPT, not the
    campaign and not the asset.

    A campaign-scoped audit is too coarse — one campaign can carry concepts
    with entirely different cultural surfaces, and an audit of the first says
    nothing about the second. An asset-scoped audit is too fine — twenty
    resizes of one approved key visual carry one cultural risk between them,
    not twenty, and auditing each is how a review queue collapses.

    An asset therefore inherits its concept's audit, unless it introduces a
    cultural surface the audit did not see. Then it needs its own.

    Returns (audit_or_None, reason).
    """
    audits = ctx.get("cultural_risk_audits", {})

    # A slate carries many concepts and has no concept_id of its own, so a
    # single-id lookup can never resolve for it. Audits are concept-scoped
    # (v1.3.5), so a container resolves as the aggregate of what it contains:
    # governed only if every concept in it is, at the worst level present.
    contained = get(artifact, "contained_concepts")
    if isinstance(contained, list) and contained:
        ids = [c.get("id") for c in contained if isinstance(c, dict) and c.get("id")]
        if ids:
            found = [audits.get(i) for i in ids]
            missing = [i for i, a in zip(ids, found)
                       if not (a and a.get("completed"))]
            if missing:
                return None, ("no completed cultural risk audit for contained "
                              f"concept(s): {', '.join(sorted(missing)[:4])}")
            order = {"low": 0, "medium": 1, "high": 2}
            worst = max((a.get("level", "medium") for a in found),
                        key=lambda l: order.get(l, 1))
            # Aggregate per axis as well as overall. Returning only the worst
            # overall level made every cultural rule read the same number, so a
            # concept graded medium for religion blocked on caste too.
            axes = {}
            for a in found:
                for axis, lvl in (a.get("per_axis") or {}).items():
                    # An axis graded low must still be recorded. Only keeping
                    # levels above the default dropped every low, and a rule
                    # whose axis was absent then fell back to the overall level,
                    # which is the worst axis. That is how a religion-medium
                    # concept blocked on caste.
                    if axis not in axes or \
                            order.get(lvl, 1) > order.get(axes[axis], 0):
                        axes[axis] = lvl
            reviewers = sorted({a.get("reviewer") for a in found
                                if a.get("reviewer")})
            return ({"completed": True, "level": worst,
                     "per_axis": axes or None,
                     "reviewer": ", ".join(reviewers) or None},
                    f"aggregated from {len(ids)} contained concept audit(s); "
                    f"worst level {worst}")

    cid = get(artifact, "concept_id")
    audit = audits.get(cid) if cid else None
    if audit is None:
        # Legacy single-audit context, retained for campaign-scoped callers.
        audit = ctx.get("cultural_risk_audit") or None
        if audit and cid:
            return audit, "campaign-scoped audit applied to a concept-bearing artifact"
    if audit is None or not audit.get("completed"):
        return None, ("no completed cultural risk audit for concept "
                      f"{cid!r}" if cid else "no completed cultural risk audit")
    introduced = [f for f in NEW_CULTURAL_SURFACE if get(artifact, f, False)]
    if introduced:
        return None, (f"artifact introduces {introduced[0].replace('introduces_new_', '')} "
                      f"not covered by the audit for concept {cid!r}; "
                      "inheritance broken, a delta audit is required")
    return audit, f"inherited from the audit for concept {cid!r}"


def _cultural(artifact, ctx, fields, subject, axis=None):
    declared_hits = [f for f in fields if get(artifact, f, False)]
    if declared_hits:
        return Result(FAIL, f"{subject} risk declared on the artifact.",
                      f"{declared_hits[0]} == true",
                      "Route to the cultural review panel.",
                      risk_level="high")
    audit, reason = resolve_cultural_audit(artifact, ctx)
    if audit is None:
        return Result(INCONCLUSIVE,
                      f"{subject} risk cannot be resolved: {reason}.",
                      evidence=reason,
                      suggested_fix="Complete a cultural risk audit for this concept.",
                      risk_level="unknown")

    # Each rule reads its own axis. The overall level is the worst axis, so
    # reading it here made a concept graded medium for religion block on caste
    # as well. A reviewer who grades per axis has said five things, not one.
    per_axis = audit.get("per_axis") or {}
    level = per_axis.get(axis) if axis and axis in per_axis \
        else audit.get("level", "low")
    if level == "low":
        return Result(PASS, risk_level=level)

    # A reviewer who grades a concept medium or high has said something, and
    # until now the system ignored it: any completed audit returned PASS, so
    # the conditional severity introduced in v1.3.4 had no path to fire and
    # the grade was decorative. The rule's escalation_threshold now decides
    # whether that grade blocks or warns.
    reviewer = audit.get("reviewer")
    return Result(FAIL,
                  f"{subject} risk assessed as {level}"
                  + (f" by {reviewer}" if reviewer else "") + ".",
                  evidence=(f"cultural audit level {level}"
                            + (f"; per-axis {audit.get('per_axis')}"
                               if audit.get("per_axis") else "")
                            + f"; {reason}"),
                  suggested_fix=(audit.get("notes")
                                 or "Mitigate the assessed risk, or record a "
                                    "mitigation on the register entry."),
                  risk_level=level)


@rule("CULTURAL-RELIGION-001", JUDGMENT,
      "Whether a depiction mocks a religion is not computable from a boolean.")
def cultural_religion_001(artifact, ctx):
    return _cultural(artifact, ctx, ["mocks_religion"], "Religious representation", axis="religion")


@rule("CULTURAL-CASTE-001", JUDGMENT, "Caste stereotyping requires human judgement.")
def cultural_caste_001(artifact, ctx):
    return _cultural(artifact, ctx,
                     ["uses_caste_stereotypes", "implies_caste_hierarchy"], "Caste", axis="caste")


@rule("CULTURAL-GENDER-001", JUDGMENT, "Stereotype and body-shaming detection.")
def cultural_gender_001(artifact, ctx):
    return _cultural(artifact, ctx,
                     ["reinforces_harmful_gender_stereotypes", "uses_misogyny_for_humor",
                      "uses_body_shaming"], "Gender representation", axis="gender")


@rule("CULTURAL-REGION-001", JUDGMENT, "Accent mockery requires listening to the cut.")
def cultural_region_001(artifact, ctx):
    return _cultural(artifact, ctx,
                     ["mocks_regional_accent_for_humor", "implies_regional_hierarchy"],
                     "Regional representation", axis="region")


@rule("CULTURAL-POLITICAL-001", JUDGMENT, "Partisan positioning requires judgement.")
def cultural_political_001(artifact, ctx):
    return _cultural(artifact, ctx,
                     ["takes_partisan_political_position",
                      "references_living_political_figure_unflatteringly"], "Political", axis="political")


@rule("CHITRA-RESEARCH-COVERAGE-001", DETERMINISTIC,
      "ADR-020: every campaign region must be covered by the audience research "
      "or carry a named waiver. Blocks rather than warns, because a warning is "
      "a thing someone clicks past.")
def chitra_research_coverage_001(artifact, ctx):
    def norm(xs):
        return {str(x).strip().lower() for x in (xs or [])}

    geo = norm(get(artifact, "geography"))
    if not geo:
        return Result(PASS)

    raw_cov = get(artifact, "research_coverage")
    if raw_cov is None:
        # Geography declared and coverage unstated. Not a pass: an unanswered
        # question about substantiation is exactly what this rule exists for.
        return Result(INCONCLUSIVE,
                      "Campaign declares a geography but states no audience "
                      "research coverage, so no region can be substantiated.",
                      evidence=f"geography {sorted(geo)}, research_coverage absent",
                      suggested_fix="Declare research_coverage on the campaign.")
    covered = norm(raw_cov)

    waivers = get(artifact, "research_coverage_waivers") or []
    waived, unsigned = set(), []
    for w in waivers:
        if not isinstance(w, dict):
            continue
        region = str(w.get("region", "")).strip().lower()
        if not region:
            continue
        if w.get("approved_by") and w.get("approved_on"):
            waived.add(region)
        else:
            unsigned.append(region)

    if unsigned:
        return Result(FAIL,
                      f"Research coverage waiver for {unsigned[0]} names no "
                      f"approver or no date. A waiver without a name is a "
                      f"compromise, not a decision.",
                      f"waiver for {unsigned[0]!r} missing approved_by or "
                      f"approved_on",
                      "Record who accepted the risk and when.")

    gap = sorted(geo - covered - waived)
    if gap:
        return Result(FAIL,
                      f"Campaign geography includes {', '.join(gap)}, which the "
                      f"audience research does not cover. Territories for that "
                      f"market would rest on insight never tested there.",
                      f"geography {sorted(geo)} vs research_coverage "
                      f"{sorted(covered)}",
                      f"Remove {gap[0]} from geography, extend the research, or "
                      f"record a waiver naming the approver.")
    return Result(PASS)


@rule("CHITRA-TENANT-ISOLATION-001", DETERMINISTIC,
      "Tenant ids are structural. This is the one internal rule and it is fully "
      "enforceable without trusting the agent.")
def chitra_tenant_isolation_001(artifact, ctx):
    tenant = ctx.get("tenant", {}).get("tenant_id")
    referenced = set(get(artifact, "referenced_tenant_ids", []) or [])
    stray = referenced - {tenant}
    if stray:
        return Result(FAIL, f"Artifact references another tenant: {sorted(stray)[0]}.",
                      f"referenced_tenant_ids == {sorted(referenced)}",
                      "Remove the cross-tenant reference.")
    exclusions = set(ctx.get("tenant", {}).get("competitive_exclusions", []) or [])
    refs = set(get(artifact, "competitor_archive_references", []) or [])
    breach = refs & exclusions
    if breach:
        return Result(FAIL, f"Competitive exclusion breached: {sorted(breach)[0]}.",
                      f"competitor_archive_references includes {sorted(breach)[0]!r}",
                      "Remove the excluded competitor reference.")
    return Result(PASS)


def coverage():
    """Return (implemented, missing) against a rule-id list."""
    return set(REGISTRY)
