"""Stakeholder digest schemas (C5).

The StakeholderDigest is what the Stakeholder Summarizer agent produces from
the PRDs + roadmap for one target audience. Consumed downstream by the
Streamlit UI (C8) and the eval harness (C9). Lives in schemas/ so consumers
import the data contract without the agent's runtime deps.

Design stance (the schema IS the design opinion):

Single schema — no draft/promoted split (inverts C4's structure, same test):
- The split is forced only when a field depends on cross-item GLOBAL state
  that code computes after all drafts exist (C4's `quarter`). No field here
  is like that: every field is knowable at authorship time.
- `grounded_in` LOOKS like C4's code-filled `evidence_issue_ids` (same shape:
  a list of source refs) but lands on the OPPOSITE side of the model/code
  line. Fill-party is determined by who holds the PROVENANCE, not by field
  shape: retrieval provenance lived in code (code stamps issue IDs);
  authorship provenance — which theme motivated the sentence the model just
  wrote — exists only in the model. Model fills it.

key_claims is a SIDECAR, not the source of body:
- body is independent prose; key_claims indexes its load-bearing factual
  claims for the judge (C9). The judge's job becomes pure verification
  (does the claim's source contain this fact?) instead of extraction +
  verification over raw prose.
- Sidecar (not body-rendered-from-claims) confines the stringify blast
  radius: if the model stringifies the list, the digest itself survives —
  an encoding-recoverable deviation, not a lost deliverable.
- Index-not-generate keeps it out of the C3 citation trap: the list reflects
  claims ALREADY in the prose, and empty is legal at BOTH layers (no
  min_length here; the prompt affirmatively licenses qualitative digests).
  Trap anatomy: unconditional content demands fabricate; self-indexing with
  legal emptiness doesn't.

Grounding is THEME-level, not artifact-level:
- source refs are PRD.theme values (intrinsic identity, consistent with
  C4's prd_ref). A claim points at a theme; the judge searches EVERYTHING
  under that theme (its PRD and its roadmap item). A source_type
  discriminator (prd vs roadmap_item) was cut as over-engineering: a real
  number is real whichever artifact holds it, so the judge never reads the
  distinction. Accepted cost (parked): this schema cannot express
  PRD-vs-roadmap-item MISATTRIBUTION of a real number — acceptable because
  topic 3's guardrail is invented-number detection.
- Membership (every grounded_in entry ∈ input themes) is closed-set —
  code-checked at the agent layer, reject-and-regenerate on a dangling ref.
  Validity is checked; QUANTITY never is (a floor would rebuild the C3 trap).
"""

from typing import Literal
from pydantic import BaseModel, Field


class Claim(BaseModel):
    # A load-bearing factual claim as it appears (in substance) in the prose.
    text: str
    # PRD.theme values this claim traces to. Model-filled (authorship
    # provenance). Code-checked for MEMBERSHIP against input themes at the
    # agent layer — never for quantity. No floor: [] is legal.
    grounded_in: list[str]


class StakeholderDigest(BaseModel):
    # Which audience this digest addresses. Closed set — schema-enforced.
    # Stamped from the summarize() call argument at promotion; the model's
    # echo of it is verified, not trusted (the caller knows the audience).
    audience: Literal["eng", "exec", "customer"]
    # One-line hook, audience-toned.
    headline: str
    # The narrative. Uncited connective tissue is allowed; load-bearing
    # factual claims must surface in key_claims. Covered by the
    # anti-hallucination prompt discipline (no numbers absent from input).
    body: str
    # The "so what do you want from me" line — the ask that differentiates
    # audiences most visibly. HIGHEST exposure to invented specifics
    # (dates, dollar figures); the no-invented-numbers discipline applies
    # here with full force, not only to body.
    call_to_action: str
    # Sidecar index of load-bearing factual claims. REQUIRED but empty is
    # LEGAL: presence is demanded (the tool contract must not advertise this
    # field as omissible — a default here silently drops it from the schema's
    # `required` array, and the schema overrides prose instructions), while
    # quantity never is (a floor would rebuild the C3 trap). Omission fails
    # validation -> repair loop.
    key_claims: list[Claim]
