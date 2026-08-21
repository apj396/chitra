"""
test_variance.py — ADR-014 applied at generation time.

Fixtures are two twelve-territory slates for the same brief. Both satisfy the
schema minimum. One is twelve territories; the other is three territories
wearing twelve titles. The schema cannot tell them apart, which is the point.

Run: python3 test_variance.py
"""

import sys

from chitra_eval_extras import (ConceptSlateVarianceScorer, VarianceGate,
                                HeadlineVarianceScorer, CONCEPT_LENSES)

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def C(title, proposition, visual, hook, lens):
    return {"title": title, "proposition": proposition,
            "visual_direction": visual, "verbal_hook": hook, "lens": lens}


# A padded slate: three real ideas, each reworded four times, one lens.
PADDED = [
    C("Monsoon Dry", "Detergent built for clothes that cannot dry outside",
      "Balcony with wet washing, grey light", "Built for clothes that cannot dry",
      "insight_led"),
    C("Rain Ready", "A detergent made for washing that will not dry outdoors",
      "Wet washing on a balcony rail, grey sky", "Made for washing that will not dry",
      "insight_led"),
    C("Dry Indoors", "Detergent for clothes that cannot be dried outside",
      "Washing hung indoors under grey light", "For clothes that cannot dry outside",
      "insight_led"),
    C("Balcony Blues", "Built for washing that cannot dry on the balcony",
      "Grey balcony, wet clothes on a rail", "Built for washing that cannot dry",
      "insight_led"),
    C("Sour Note", "Ends the sour smell of clothes dried indoors",
      "Close on a shirt collar, mother frowning", "No more sourness indoors",
      "insight_led"),
    C("No Sour", "Stops the sour smell when clothes dry indoors",
      "Shirt collar close-up, a frown", "Stops sourness when drying indoors",
      "insight_led"),
    C("Fresh Indoors", "Removes the sour smell from indoor-dried clothes",
      "Collar close-up with a frowning mother", "Removes indoor sourness",
      "insight_led"),
    C("Sourless", "Kills the sour smell of clothes dried inside",
      "A frown, a collar, close up", "Kills the sour smell inside",
      "insight_led"),
    C("Price Hold", "Better cleaning without paying more this monsoon",
      "Price tag, two packs side by side", "Better clean, same price",
      "insight_led"),
    C("Same Price", "Better cleaning at no extra cost this monsoon",
      "Two packs beside a price tag", "Better clean at no extra cost",
      "insight_led"),
    C("Value Wash", "Better washing without spending more in the rains",
      "Side by side packs and a price tag", "Better wash, no extra spend",
      "insight_led"),
    C("Costless Clean", "Better cleaning and no extra spend during monsoon",
      "Packs side by side, price visible", "Better cleaning, no extra spend",
      "insight_led"),
]

# A genuinely divergent slate: twelve territories across five lenses.
DIVERGENT = [
    C("The Weather Did It", "The monsoon is the problem, not the powder",
      "Split screen: sky above, laundry below", "Blame the sky, not the soap",
      "insight_led"),
    C("Balcony Out of Service", "Your drying space closes for three months a year",
      "A shuttered-shop sign hung on a balcony rail", "Closed for the season",
      "provocative_contrarian"),
    C("The Smell Nobody Names", "Households live with a sourness they never discuss",
      "Dinner table, a guest sniffs, nobody speaks", "Everyone notices. Nobody says.",
      "insight_led"),
    C("Ganpati Whites", "Festival clothes cannot wait for sunshine",
      "Ganesh Chaturthi morning, a kurta still damp", "Ready before the pandal is",
      "cultural_moment_led"),
    C("Chair Census", "Documenting what furniture does in the rains",
      "Stark photography of chairs draped in washing", "Chairs are not clotheslines",
      "format_led"),
    C("The Dryness Report", "A weekly humidity bulletin as a media property",
      "Weather-report format, city by city drying index", "Today's drying index: 12%",
      "format_led"),
    C("Ask the Grandmother", "The people who solved this before machines existed",
      "Real elders, unscripted, on what they did", "She has done ninety monsoons",
      "testimonial_proof_led"),
    C("Three Days Later", "Proof shot on a schedule nobody else would attempt",
      "Time-stamped footage across seventy-two hours", "Filmed over three days. No cuts.",
      "testimonial_proof_led"),
    C("We Do Not Do Stains", "A detergent that refuses the category's own promise",
      "Text-only campaign, no product, no laundry", "Stains are easy. Weather is not.",
      "category_disruption_led"),
    C("Iron It Out", "Partnering with the pressing-wallah, not against him",
      "Documentary on street pressing stalls in the rains", "He knew first",
      "category_disruption_led"),
    C("Kartik Cupboard", "What Diwali cleaning finds at the back of the almirah",
      "Almirah opened, last year's damp still there", "The cupboard remembers July",
      "cultural_moment_led"),
    C("Sourness Has a Season", "Naming the smell so it can be sold against",
      "Typographic campaign that names the problem", "It has a name now",
      "insight_led"),
]


def test_scorer_separates_the_two_slates():
    sc = ConceptSlateVarianceScorer()
    p, d = sc.score(PADDED), sc.score(DIVERGENT)
    check("padded slate flagged", p.verdict != "genuine spread", p.verdict)
    check("divergent slate passes", d.verdict == "genuine spread",
          f"{d.verdict} weighted={d.weighted_similarity:.3f} "
          f"groups={d.collapsed_groups}")
    check("padded weighted similarity is higher",
          p.weighted_similarity > d.weighted_similarity,
          f"{p.weighted_similarity:.3f} vs {d.weighted_similarity:.3f}")
    check("both satisfy the schema minimum",
          len(PADDED) == 12 and len(DIVERGENT) == 12,
          "the minimum alone cannot distinguish them")


def test_proposition_weighted_above_title():
    """Twelve distinct titles over three propositions is still three concepts."""
    fresh = ["Kingfisher", "Anvil", "Saffron", "Lighthouse", "Marigold", "Compass",
             "Tabla", "Harbour", "Peacock", "Lantern", "Zephyr", "Almirah"]
    disguised = [dict(c, title=fresh[i]) for i, c in enumerate(PADDED)]
    r = ConceptSlateVarianceScorer().score(disguised)
    check("distinct titles do not rescue identical propositions",
          r.verdict != "genuine spread", r.verdict)
    check("titles now score as fully distinct",
          r.per_field["title"] < 0.05, f"title={r.per_field['title']:.3f}")
    check("collapse is still detected through the propositions",
          len(r.dominant_cluster) >= 3, str(r.collapsed_groups))

    # The mean is a weak signal on a slate of a few tight clusters: within-group
    # similarity is high, across-group similarity near zero, so the average
    # lands low. Clustering is what catches this shape, which is why the
    # verdict does not rest on the mean alone.
    check("mean similarity alone would have missed it",
          r.weighted_similarity < ConceptSlateVarianceScorer.PADDING_WEIGHTED,
          f"weighted={r.weighted_similarity:.3f}")


def test_lens_monoculture_detected():
    single = [dict(c, lens="insight_led") for c in DIVERGENT]
    r = ConceptSlateVarianceScorer().score(single)
    check("one lens twelve times is flagged even when wording diverges",
          r.verdict == "insufficient lens divergence", r.verdict)
    check("lens coverage counted", r.lens_coverage == 1, str(r.lens_counts))
    check("divergent slate spans several lenses",
          ConceptSlateVarianceScorer().score(DIVERGENT).lens_coverage >= 4,
          str(ConceptSlateVarianceScorer().score(DIVERGENT).lens_counts))


def test_gate_regenerates_indices_not_the_slate():
    g = VarianceGate()
    res = g.enforce(PADDED)
    check("gate rejects the padded slate", not res.passed)
    check("gate keeps survivors rather than discarding everything",
          0 < len(res.keep) < 12, f"keep={res.keep}")
    check("keep and regenerate partition the slate",
          sorted(res.keep + res.regenerate) == list(range(12)),
          f"keep={res.keep} regen={res.regenerate}")
    check("feedback names the collapsing groups",
          "same territory" in res.feedback, res.feedback[:120])
    check("feedback instructs a different lens, not a reword",
          "different lens" in res.feedback and "Do not reword" in res.feedback)

    ok = g.enforce(DIVERGENT)
    check("gate passes the divergent slate", ok.passed,
          ok.feedback or str(ok.report))
    check("passing slate keeps all twelve", ok.keep == list(range(12)))


def test_gate_enforces_the_minimum_first():
    res = VarianceGate().enforce(DIVERGENT[:8])
    check("short slate rejected on count before variance", not res.passed)
    check("asks for exactly the shortfall", res.regenerate == list(range(8, 12)),
          str(res.regenerate))
    check("count feedback is about quantity", "at least 12" in res.feedback,
          res.feedback)


def test_repaired_slate_passes():
    """The gate's own instruction, followed, produces a passing slate."""
    g = VarianceGate()
    first = g.enforce(PADDED)
    repaired = [PADDED[i] for i in first.keep]
    # Follow the instruction literally: replace each dropped territory with a
    # fresh one on a different lens.
    pool = [c for c in DIVERGENT if c["lens"] != "insight_led"] + \
           [c for c in DIVERGENT if c["lens"] == "insight_led"]
    repaired += pool[:12 - len(repaired)]
    check("gate collapses the padded slate to roughly its distinct territories",
          len(first.keep) <= 5,
          f"kept {len(first.keep)} of 12; the slate has 3 real ideas, and one "
          f"synonym-level rewording survives, which is the documented lexical limit")
    second = g.enforce(repaired)
    check("regenerating only the collapsed territories fixes the slate",
          second.passed, second.feedback or str(second.report))


def test_embedder_hook():
    """A semantic embedder can be swapped in without touching the gate."""
    def naive(text):
        return [float(text.lower().count(ch)) for ch in "abcdefghijklmnopqrstuvwxyz"]
    sc = ConceptSlateVarianceScorer(embedder=naive)
    r = sc.score(DIVERGENT)
    check("embedder hook is used without error", r.n == 12 and r.per_field)
    check("lexical default remains the documented limit",
          "lexical" in ConceptSlateVarianceScorer.__doc__.lower())


def test_headline_scorer_unchanged():
    sc = HeadlineVarianceScorer()
    padded = [f"Built for clothes that cannot dry {x}" for x in
              ["outside", "outdoors", "in the rain", "on the balcony", "in monsoon",
               "in the wet", "without sun", "indoors", "in humidity", "in damp",
               "in the damp air", "without sunlight", "in wet weather",
               "in the rains", "in monsoon season"]]
    check("existing headline scorer still flags padding",
          sc.rubric_entry(padded)["level"] == "weak")


def main():
    for fn in (test_scorer_separates_the_two_slates,
               test_proposition_weighted_above_title,
               test_lens_monoculture_detected,
               test_gate_regenerates_indices_not_the_slate,
               test_gate_enforces_the_minimum_first,
               test_repaired_slate_passes,
               test_embedder_hook,
               test_headline_scorer_unchanged):
        try:
            fn()
        except Exception as e:
            RESULTS.append((f"{fn.__name__} raised", False, f"{type(e).__name__}: {e}"))

    w = max(len(n) for n, _, _ in RESULTS)
    failed = sum(not ok for _, ok, _ in RESULTS)
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{w}}  {'' if ok else detail}")
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
