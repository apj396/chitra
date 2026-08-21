"""
chitra_eval_extras.py — two additions to the v1.3 eval harness.

  HeadlineVarianceScorer   ADR-014. Schema minimums stay as a forcing function,
                           so we instrument whether they are working. If an
                           agent asked for 15 headlines returns 14 syntactic
                           permutations of the first, the minimum has produced
                           padding rather than exploration, and that should be
                           visible in data rather than argued about.

  JudgePanelHealthCheck    ADR-011. Verifies the pinned judge models are still
                           served before a calibration run. A silent model
                           substitution invalidates the calibration set the
                           bias-corrected estimator depends on, and nothing in
                           v1.3 checked for it.
"""

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

STOP = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "for", "on",
        "with", "your", "you", "is", "it", "that", "this", "at", "by", "from"}


def _tokens(text):
    return [t for t in re.findall(r"[a-z']+", text.lower()) if t not in STOP]


def _bag(text):
    c = Counter(_tokens(text))
    n = math.sqrt(sum(v * v for v in c.values())) or 1.0
    return {k: v / n for k, v in c.items()}


def _cosine(a, b):
    return sum(v * b.get(k, 0.0) for k, v in a.items())


@dataclass
class VarianceReport:
    n: int
    mean_pairwise_similarity: float
    max_pairwise_similarity: float
    distinct_ratio: float
    near_duplicate_pairs: list = field(default_factory=list)
    structural_clusters: int = 0
    verdict: str = ""

    def to_dict(self):
        return {"n": self.n,
                "mean_pairwise_similarity": round(self.mean_pairwise_similarity, 3),
                "max_pairwise_similarity": round(self.max_pairwise_similarity, 3),
                "distinct_ratio": round(self.distinct_ratio, 3),
                "near_duplicate_pairs": self.near_duplicate_pairs,
                "structural_clusters": self.structural_clusters,
                "verdict": self.verdict}


class HeadlineVarianceScorer:
    """Lexical and structural spread across a generated array.

    Deliberately not a judge call. Padding is a measurable property of the
    array, and measuring it locally costs nothing and cannot drift with a
    model version. The judge panel scores whether the headlines are any good;
    this scores whether they are different from each other, which is a
    different question and the one the minimum was meant to force.
    """

    NEAR_DUPLICATE = 0.72
    PADDING_MEAN = 0.42

    def score(self, headlines):
        texts = [h.get("text", h) if isinstance(h, dict) else str(h)
                 for h in headlines]
        texts = [t for t in texts if t and t.strip()]
        n = len(texts)
        if n < 2:
            return VarianceReport(n=n, mean_pairwise_similarity=0.0,
                                  max_pairwise_similarity=0.0, distinct_ratio=1.0,
                                  verdict="too few to score")

        bags = [_bag(t) for t in texts]
        sims, dupes = [], []
        for i in range(n):
            for j in range(i + 1, n):
                s = _cosine(bags[i], bags[j])
                sims.append(s)
                if s >= self.NEAR_DUPLICATE:
                    dupes.append({"i": i, "j": j, "similarity": round(s, 3),
                                  "a": texts[i][:60], "b": texts[j][:60]})

        all_tokens = [t for text in texts for t in _tokens(text)]
        distinct = len(set(all_tokens)) / max(len(all_tokens), 1)

        # Structural clustering: same opening two tokens and same length band
        # is the signature of a template filled repeatedly.
        shapes = Counter()
        for t in texts:
            toks = _tokens(t)
            shapes[(tuple(toks[:2]), len(toks) // 3)] += 1
        clusters = sum(1 for v in shapes.values() if v >= 3)

        mean_s = sum(sims) / len(sims)
        if mean_s >= self.PADDING_MEAN or clusters:
            verdict = "padding suspected"
        elif dupes:
            verdict = "some near-duplicates"
        else:
            verdict = "genuine spread"

        return VarianceReport(n=n, mean_pairwise_similarity=mean_s,
                              max_pairwise_similarity=max(sims),
                              distinct_ratio=distinct, near_duplicate_pairs=dupes,
                              structural_clusters=clusters, verdict=verdict)

    def rubric_entry(self, headlines):
        """Shaped for the v1.3 §2 rubric: a criterion with a 4-level anchor."""
        r = self.score(headlines)
        if r.verdict == "genuine spread" and r.mean_pairwise_similarity < 0.25:
            level = "excellent"
        elif r.verdict == "genuine spread":
            level = "strong"
        elif r.verdict == "some near-duplicates":
            level = "adequate"
        else:
            level = "weak"
        return {"criterion": "array_variance",
                "applies_to": "any schema-minimum-enforced array",
                "level": level,
                "confidence": "high",
                "evidence": r.to_dict(),
                "note": "Measured locally, not judged. Detects whether a schema "
                        "minimum produced exploration or padding."}


# --------------------------------------------------------------------------
# ADR-014 extended — concept slates and generation-time enforcement
# --------------------------------------------------------------------------

# The six lenses Disha's scaffold names for the divergent phase. A slate that
# uses one lens twelve times has not diverged, however different the wording.
CONCEPT_LENSES = ["insight_led", "category_disruption_led", "cultural_moment_led",
                  "format_led", "provocative_contrarian", "testimonial_proof_led"]

# Fields weighted by how much sameness in them actually matters. Two concepts
# with different titles and the same proposition are one concept.
CONCEPT_FIELD_WEIGHTS = {
    "proposition": 0.5,
    "visual_direction": 0.2,
    "verbal_hook": 0.2,
    "title": 0.1,
}


@dataclass
class SlateVarianceReport:
    n: int
    per_field: dict = field(default_factory=dict)
    weighted_similarity: float = 0.0
    lens_coverage: int = 0
    lens_counts: dict = field(default_factory=dict)
    dominant_cluster: list = field(default_factory=list)
    collapsed_groups: list = field(default_factory=list)
    verdict: str = ""

    def to_dict(self):
        return {"n": self.n,
                "per_field": {k: round(v, 3) for k, v in self.per_field.items()},
                "weighted_similarity": round(self.weighted_similarity, 3),
                "lens_coverage": self.lens_coverage,
                "lens_counts": self.lens_counts,
                "dominant_cluster": self.dominant_cluster,
                "collapsed_groups": self.collapsed_groups,
                "verdict": self.verdict}


class ConceptSlateVarianceScorer:
    """Variance across a slate of concept objects, not flat strings.

    Three measures, because concepts collapse in three different ways:

      per-field similarity   twelve concepts can carry twelve distinct titles
                             over three propositions. Proposition sameness is
                             weighted at half the total for that reason.
      lens coverage          the scaffold names six divergence lenses. Twelve
                             insight-led concepts is one lens twelve times.
      dominant cluster       the largest mutually-similar group. A slate can
                             look varied on the mean while eight of twelve sit
                             on top of each other.

    LIMIT, stated plainly: this is lexical. It catches an agent rewording one
    idea, which is the common failure. It does not catch an agent expressing
    one idea in genuinely different vocabulary, which is the sophisticated
    failure and needs the judge panel. Pass an `embedder` to upgrade the
    similarity function without changing anything else here.
    """

    # Collapse is detected on the PROPOSITION matrix, not the blended one.
    # An idea lives in its proposition; a distinct title on a duplicated idea
    # is a disguise, and blending let it drag a collapsed pair under the bar.
    # Measured separation on fixture data: within-idea 0.31 to 0.67,
    # across-idea 0.00 to 0.17. Set at 0.45 rather than at the bottom of the
    # within-idea band, because a false positive makes an agent throw away
    # good work while a false negative only lets one duplicate through, and
    # two short propositions sharing two content words ("clothes", "cannot")
    # scored 0.34 while being genuinely different territories. Synonym-level
    # rewording below this bar is past what lexical similarity can see; that
    # is what the embedder hook and the judge panel are for.
    COLLAPSE = 0.45
    COLLAPSE_BLENDED = 0.55
    PADDING_WEIGHTED = 0.38
    MIN_LENS_COVERAGE = 3

    def __init__(self, embedder=None, field_weights=None):
        self.embedder = embedder
        self.weights = field_weights or CONCEPT_FIELD_WEIGHTS

    def _sim_matrix(self, texts):
        if self.embedder is not None:
            vecs = [self.embedder(t) for t in texts]
            def dot(a, b):
                n1 = math.sqrt(sum(x * x for x in a)) or 1.0
                n2 = math.sqrt(sum(x * x for x in b)) or 1.0
                return sum(x * y for x, y in zip(a, b)) / (n1 * n2)
            return [[dot(vecs[i], vecs[j]) for j in range(len(texts))]
                    for i in range(len(texts))]
        bags = [_bag(t) for t in texts]
        return [[_cosine(bags[i], bags[j]) for j in range(len(texts))]
                for i in range(len(texts))]

    def _field_texts(self, concepts, name):
        out = []
        for c in concepts:
            v = c.get(name, "") if isinstance(c, dict) else str(c)
            if isinstance(v, list):
                v = " ".join(str(x) for x in v)
            out.append(str(v or ""))
        return out

    def score(self, concepts):
        n = len(concepts)
        if n < 2:
            return SlateVarianceReport(n=n, verdict="too few to score")

        per_field, matrices = {}, {}
        for name, w in self.weights.items():
            texts = self._field_texts(concepts, name)
            if not any(t.strip() for t in texts):
                continue
            m = self._sim_matrix(texts)
            matrices[name] = m
            pairs = [m[i][j] for i in range(n) for j in range(i + 1, n)]
            per_field[name] = sum(pairs) / len(pairs)

        total_w = sum(self.weights[k] for k in per_field) or 1.0
        weighted = sum(per_field[k] * self.weights[k] for k in per_field) / total_w

        # Combined matrix for clustering, same weighting.
        combined = [[0.0] * n for _ in range(n)]
        for name, m in matrices.items():
            w = self.weights[name] / total_w
            for i in range(n):
                for j in range(n):
                    combined[i][j] += m[i][j] * w

        # Cluster on propositions where available; fall back to the blend.
        if "proposition" in matrices:
            cmat, thresh = matrices["proposition"], self.COLLAPSE
        else:
            cmat, thresh = combined, self.COLLAPSE_BLENDED

        # Transitive grouping: A~B and B~C puts all three in one territory,
        # which is how a reworded chain actually looks.
        seen, groups = set(), []
        for i in range(n):
            if i in seen:
                continue
            grp, frontier = [i], [i]
            seen.add(i)
            while frontier:
                k = frontier.pop()
                for j in range(n):
                    if j not in seen and cmat[k][j] >= thresh:
                        seen.add(j)
                        grp.append(j)
                        frontier.append(j)
            if len(grp) > 1:
                groups.append(sorted(grp))
        dominant = max(groups, key=len) if groups else []

        lenses = [c.get("lens") for c in concepts if isinstance(c, dict) and c.get("lens")]
        counts = dict(Counter(lenses))

        if weighted >= self.PADDING_WEIGHTED or len(dominant) >= 3:
            verdict = "padding suspected"
        elif lenses and len(counts) < self.MIN_LENS_COVERAGE:
            verdict = "insufficient lens divergence"
        elif groups:
            verdict = "some collapse"
        else:
            verdict = "genuine spread"

        return SlateVarianceReport(
            n=n, per_field=per_field, weighted_similarity=weighted,
            lens_coverage=len(counts), lens_counts=counts,
            dominant_cluster=dominant, collapsed_groups=groups, verdict=verdict)


@dataclass
class GateResult:
    passed: bool
    keep: list = field(default_factory=list)
    regenerate: list = field(default_factory=list)
    feedback: str = ""
    report: Optional[dict] = None

    def to_dict(self):
        return {"passed": self.passed, "keep": self.keep,
                "regenerate": self.regenerate, "feedback": self.feedback,
                "report": self.report}


class VarianceGate:
    """Generation-time enforcement. ADR-014, applied where it is cheapest.

    The schema minimum forces an agent to produce twelve. It cannot tell
    whether it produced twelve ideas or one idea twelve times. This gate can,
    and it runs before the kill pass, so a padded slate is regenerated rather
    than scored, ranked and shipped.

    It rejects INDICES, not the slate. Keeping the eight that stand apart and
    regenerating the four that collapsed is cheaper than a full retry and
    gives the agent a specific instruction instead of "try again."
    """

    def __init__(self, scorer=None, min_items=12):
        self.scorer = scorer or ConceptSlateVarianceScorer()
        self.min_items = min_items

    def enforce(self, concepts):
        n = len(concepts)
        if n == 0:
            return GateResult(
                passed=False, keep=[], regenerate=list(range(self.min_items)),
                feedback=(f"No territories were readable in that response. "
                          f"Return exactly {self.min_items} territories as "
                          f'{{"territories": [...]}} and nothing else: no '
                          f"preamble, no markdown fence, no commentary."))
        if n < self.min_items:
            return GateResult(
                passed=False, keep=list(range(n)),
                regenerate=list(range(n, self.min_items)),
                feedback=(f"Divergent phase requires at least {self.min_items} "
                          f"territories; {n} supplied. Generate "
                          f"{self.min_items - n} more."))

        r = self.scorer.score(concepts)
        if r.verdict == "genuine spread":
            return GateResult(passed=True, keep=list(range(n)),
                              report=r.to_dict())

        # Keep the first member of each collapsed group; regenerate the rest.
        drop = set()
        for grp in r.collapsed_groups:
            drop.update(grp[1:])

        lines = []
        if r.collapsed_groups:
            for grp in r.collapsed_groups:
                titles = [str(concepts[i].get("title", f"#{i}")) for i in grp]
                lines.append(f"Concepts {grp} are the same territory: "
                             f"{'; '.join(titles)}. Keeping {grp[0]}.")
        if r.lens_counts and r.lens_coverage < self.scorer.MIN_LENS_COVERAGE:
            used = ", ".join(sorted(r.lens_counts))
            unused = [l for l in CONCEPT_LENSES if l not in r.lens_counts]
            lines.append(f"Only {r.lens_coverage} lens(es) used ({used}). "
                         f"Try: {', '.join(unused[:4])}.")
            drop.update(range(max(0, n - 3), n))
        if not lines:
            lines.append(f"Weighted similarity across the slate is "
                         f"{r.weighted_similarity:.2f}; the propositions are too "
                         f"close to be distinct territories.")

        regenerate = sorted(drop)
        return GateResult(
            passed=False,
            keep=[i for i in range(n) if i not in drop],
            regenerate=regenerate,
            feedback=(" ".join(lines) + f" Regenerate {len(regenerate)} "
                      f"territor{'y' if len(regenerate) == 1 else 'ies'} on a "
                      f"different lens. Do not reword the survivors."),
            report=r.to_dict())


# --------------------------------------------------------------------------
# ADR-011 — judge panel health check
# --------------------------------------------------------------------------

@dataclass
class PanelHealth:
    checked: list = field(default_factory=list)
    unavailable: list = field(default_factory=list)
    families: dict = field(default_factory=dict)

    @property
    def healthy(self):
        return not self.unavailable

    def to_dict(self):
        return {"healthy": self.healthy, "checked": self.checked,
                "unavailable": self.unavailable, "families": self.families}


class JudgePanelHealthCheck:
    """Confirms the pinned panel is still served before a calibration run.

    v1.3 §4.2 pins three model identifiers labelled current as of May 2026 and
    nothing verifies them. If a provider retires or silently reroutes one, the
    calibration set gathered against the old panel no longer describes the new
    one, and every score after that is measured with a ruler that changed
    length. Failing loudly beats drifting quietly.
    """

    def __init__(self, panel, prober=None):
        self.panel = panel
        self.prober = prober

    def run(self):
        h = PanelHealth()
        for entry in self.panel:
            mid = entry["model"] if isinstance(entry, dict) else entry
            fam = entry.get("family") if isinstance(entry, dict) else None
            h.checked.append(mid)
            if fam:
                h.families.setdefault(fam, []).append(mid)
            ok = True
            if self.prober is not None:
                try:
                    ok = bool(self.prober(mid))
                except Exception:
                    ok = False
            else:
                ok = None  # no prober configured; unverified rather than healthy
            if ok is False:
                h.unavailable.append(mid)
        return h

    def gate(self):
        """Raise rather than let a calibration run start on an unverified panel."""
        h = self.run()
        if self.prober is None:
            raise RuntimeError(
                "Judge panel health check has no prober configured. Calibration "
                "must not run against an unverified panel: pin verification is "
                "what keeps scores comparable across runs.")
        if not h.healthy:
            raise RuntimeError(
                f"Judge panel unavailable: {', '.join(h.unavailable)}. Re-select "
                f"the panel and recalibrate; do not substitute silently.")
        if len(h.families) < 3:
            raise RuntimeError(
                f"Panel spans {len(h.families)} model families; three independent "
                f"families are required for the self-enhancement guard.")
        return h
