"""Judge dimension rubrics (C9).

Four dimensions, four separate calls. Each call sees only its own rubric, so
scores stay independent: a shared context produces halo effect (one dimension's
verdict colouring the rest) and reasoning interference (Completeness' theme
enumeration acting as a lens for Grounding).

Reversal condition: at ~10 scenarios the 4x call cost is rounding error. At
10,000 scenarios, or a real-time eval gating every PRD, move to a single call
with isolated per-dimension blocks and accept weaker independence.

TRANSCRIPTION NOTE
Anchor text is verbatim from the Day 13 design. One substitution was applied:
the reference set each dimension names. The original was written under a
single-reference-set assumption that the built system contradicts --
`PRD.md` defines Hallucination against the corpus while the Day 13 template
named `source_findings`. Reference sets are now assigned per dimension:

    set-membership dimensions face ground truth (the retrieved issues);
    statement-craft dimensions face the proximate input.

    Hallucination -> retrieved issues   (is anything here invented?)
    Completeness  -> retrieved issues   (is anything missing?)
    Grounding     -> source findings    (is this claim well-formed?)
    AC Quality    -> nothing            (intra-PRD by definition)

Grounding faces the findings because its three rungs compare a claim against
the specific statement it distorts, and the finding's cluster prose carries the
precision layer the PRD operates at (named symbols, providers, manner
qualifiers) while `frequency` and `severity` carry the quantities as structured
fields. Reversal condition: if PRDs begin making claims whose precision lives
only in issue bodies -- version ranges, exact error strings, reproduction
conditions -- the cluster becomes too lossy and Grounding moves to the corpus.
"""

# Which evidence block each dimension's prompt receives.
EVIDENCE_RETRIEVED_ISSUES = "retrieved_issues"
EVIDENCE_SOURCE_FINDINGS = "source_findings"
EVIDENCE_NONE = None


HALLUCINATION = """\
DIMENSION: Hallucination Rate

Definition:
- Measures material claims in the PRD that have no basis in the RETRIEVED
  ISSUES at all -- wholly invented issues, fabricated facts, conjured user
  counts, constraints, or causes.
- Distortion or overstatement of a real source is OUT OF SCOPE here. That is
  scored under Grounding.
- Severity is ordered by count x materiality. A claim is MATERIAL if it appears
  in the problem statement or drives an acceptance criterion; INCIDENTAL
  otherwise (a descriptive detail on an issue that is not load-bearing).

Anchor scale:
5 -- Zero unsupported claims of any kind. Every issue, fact, and figure in the
     PRD traces to the retrieved issues.
4 -- Unsupported incidental details only (1-2), attached to issues that
     genuinely exist in the source. No invented issues, nothing material
     affected. Example: source describes a real auth-token bug; PRD repeats it
     faithfully but adds "primarily affects enterprise-tier users" -- a detail
     the source never states.
3 -- Either: incidental fabrication is pervasive (most real issues carry some
     invented detail), or exactly one wholly invented issue that is non-central
     (does not drive the problem statement or any AC). Example: 4 issues
     described, 3 sourced; a 4th -- "search indexing latency" -- appears
     nowhere in the corpus but sits in a minor section.
2 -- Multiple invented issues, or one invented issue that is material. The
     PRD's direction is partly built on fiction. Example: the problem statement
     centres on "database migration failures" -- no such issue exists in the
     source.
1 -- The PRD is substantially fiction -- the majority of issues, or the core
     problem, have no basis in the retrieved issues. Example: source is about
     auth and cloud bugs; PRD is about an entirely different product surface.
"""


GROUNDING = """\
DIMENSION: Grounding

Definition:
- Measures distortion or overstatement of real sources in the PRD -- scope
  inflation, severity inflation, or frequency claims the source does not
  contain, judged against the SOURCE FINDINGS.
- Fabrication of content with no source at all is scored under Hallucination,
  NOT here.
- Severity is ordered by count x departure rung. Departure from a source is
  graded on three rungs:
    i.   IMPRECISION -- facts loosened but the claim remains compatible with
         the source ("3 users" -> "several"). Test: could the source still be
         honestly cited as support?
    ii.  UNSUPPORTED ESCALATION -- the claim asserts something the source could
         not establish under any reading: superlatives, comparatives,
         product-wide scope from a single data point. Test: does the claim's
         scope exceed what this source could ever prove?
    iii. CONTRADICTION -- the claim asserts something the source actively
         states otherwise ("intermittent" -> "consistently"). Test: does a
         stated fact in the source negate the claim?

Anchor scale:
5 -- Zero departures of any kind. No imprecision, no escalation, no
     contradiction.
4 -- 1-2 imprecise facts only. No escalation, no contradiction. Example:
     source -- "Three users report auth token refresh fails intermittently on
     mobile Safari"; PRD -- "Several users have hit auth token refresh failures
     on mobile."
3 -- 3+ imprecise facts (or most claims imprecise), or exactly 1 claim with
     unsupported escalation. Example: PRD -- "Auth token refresh failure is the
     most widely reported issue in the product."
2 -- 2+ claims with unsupported escalation, or 1-2 issues containing
     contradictions.
1 -- Contradictions are pervasive -- 3+ issues, or a majority of the PRD's
     claims, actively contradict their sources; the PRD misrepresents the
     corpus. Example: PRD -- "Auth token refresh consistently fails across all
     mobile platforms."
"""


COMPLETENESS = """\
DIMENSION: Completeness

Definition:
- Scores theme coverage -- whether the PRD addresses every distinct problem you
  enumerate from the RETRIEVED ISSUES.
- Content in the PRD not grounded in the retrieved issues is scored under
  Hallucination, NOT here.
- A theme is PROMINENT if 2+ retrieved issues report it; MINOR if exactly one
  issue reports it.
- Severity is ordered by (prominent themes missed) x (minor themes missed),
  with prominent misses weighing more.
- Level 5 requires zero missed themes of any kind: the retrieval is small
  enough that full coverage is a fair bar, and a missed theme -- unlike an
  imprecise phrase -- is a silent omission the reader cannot detect.

MANDATORY PROCEDURE (do all three steps, in order, before selecting a score):
  Step 1 -- ENUMERATE. List the distinct problems reported across the retrieved
    issues, merging issues that describe the same underlying problem. Attach
    the contributing issue IDs to each theme, and mark each theme prominent
    (2+ issues) or minor (exactly 1 issue).
  Step 2 -- MAP. For each enumerated theme, decide whether the PRD addresses it
    and cite the PRD element that does so, or record it as missed.
  Step 3 -- SCORE. Count prominent and minor misses; select the anchor level
    those counts match.

Anchor scale:
5 -- Every enumerated theme is addressed in the PRD -- zero prominent and zero
     minor themes missed.
4 -- All prominent themes covered; 1-2 minor themes missed.
3 -- All prominent themes covered but 3+ minor themes missed, or exactly 1
     prominent theme missed (regardless of minor coverage).
2 -- Exactly 2 prominent themes missed (regardless of minor coverage).
1 -- 3+ prominent themes missed, or a majority of enumerated themes absent --
     the PRD fails to represent the findings.
"""


AC_QUALITY = """\
DIMENSION: AC Quality

Definition:
- Measures whether each acceptance criterion is fit to serve as a test
  specification -- whether an engineer could build a test from it and a
  reviewer could unambiguously say pass/fail.
- This dimension is INTRA-PRD: an AC's quality is judged independently of any
  source evidence. No sources are provided, by design.
- When defect counts satisfy clauses at different levels, assign the LOWER
  score.
- Defect types:
    i.   VAGUE (per-AC) -- slots filled with unobservable terms ("works
         properly", "a user"). Test: can each of Given/When/Then be translated
         into a concrete state, action, and assertion?
    ii.  NON-ATOMIC (per-AC) -- multiple independent outcomes welded into one
         criterion. Test: does the Then assert exactly one verifiable outcome,
         such that a single check would settle it?
    iii. REDUNDANT PAIR (per-SET) -- two ACs in the set test the same behaviour
         in different words. Test: does any pair of ACs reduce to the same
         check? Note this defect's unit is the set, not the individual AC.

Anchor scale:
5 -- All ACs clean; zero redundant pairs.
4 -- All ACs clean; exactly 1 redundant pair.
3 -- Exactly 1 defective AC, or exactly 2 redundant pairs.
2 -- Exactly 2 defective ACs, or 3+ redundant pairs.
1 -- 3+ (or a majority of) defective ACs.
"""


# Per-dimension `findings` shape, injected into the output-format instruction.
# The committed template leaves this as a placeholder ("see dimension note");
# spelling it out per call is what makes a score auditable rather than a bare
# number with prose attached.
FINDINGS_SPEC = {
    "hallucination": (
        'a list of objects, one per unsupported claim: '
        '{"claim": "<the exact PRD text>", "prd_location": "<field path, e.g. '
        'problem_statement or acceptance_criteria[2]>", '
        '"materiality": "material" | "incidental"}. '
        "Empty list if there are none."
    ),
    "grounding": (
        'a list of objects, one per departed claim: '
        '{"claim": "<the exact PRD text>", "prd_location": "<field path>", '
        '"source": "<the finding text it departs from>", '
        '"rung": "imprecision" | "escalation" | "contradiction"}. '
        "Empty list if there are none."
    ),
    "completeness": (
        'a single-element list holding one object with BOTH intermediate '
        'products: {"themes": [{"theme": "<short name>", '
        '"issue_ids": [<ints>], "prominence": "prominent" | "minor"}], '
        '"coverage": [{"theme": "<same name>", '
        '"status": "addressed" | "missed", '
        '"prd_element": "<field path, or null if missed>"}]}. '
        "Every theme in `themes` must appear in `coverage`."
    ),
    "ac_quality": (
        'a list of objects. For a defective AC: '
        '{"type": "vague" | "non_atomic", "ac_index": <1-based int>, '
        '"ac_text": "<the AC>", "reason": "<which slot fails the test>"}. '
        'For a redundant pair: '
        '{"type": "redundant_pair", "ac_indices": [<int>, <int>], '
        '"reason": "<the check both reduce to>"}. '
        "Empty list if there are none."
    ),
}


RUBRICS = {
    "hallucination": {
        "name": "Hallucination Rate",
        "rubric": HALLUCINATION,
        "evidence": EVIDENCE_RETRIEVED_ISSUES,
        "findings_spec": FINDINGS_SPEC["hallucination"],
    },
    "grounding": {
        "name": "Grounding",
        "rubric": GROUNDING,
        "evidence": EVIDENCE_SOURCE_FINDINGS,
        "findings_spec": FINDINGS_SPEC["grounding"],
    },
    "completeness": {
        "name": "Completeness",
        "rubric": COMPLETENESS,
        "evidence": EVIDENCE_RETRIEVED_ISSUES,
        "findings_spec": FINDINGS_SPEC["completeness"],
    },
    "ac_quality": {
        "name": "AC Quality",
        "rubric": AC_QUALITY,
        "evidence": EVIDENCE_NONE,
        "findings_spec": FINDINGS_SPEC["ac_quality"],
    },
}

DIMENSIONS = list(RUBRICS)
