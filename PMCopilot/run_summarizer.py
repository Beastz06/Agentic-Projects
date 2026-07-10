"""C5 run: load canonical PRDs + persisted roadmap -> three digests, one per
audience -> persist + print for the eyeball test."""
import json
from pathlib import Path
from schemas.prd import PRD
from agents.summarizer import summarize, TONE_BLOCKS
from schemas.roadmap import RoadmapItem

OUT = Path("data/output")
THEMES = ["streaming", "authentication", "tool_calling"]

# --- Load canonical PRDs ---
prds = [
    PRD.model_validate_json((OUT / f"prd_{t}.json").read_text(encoding="utf-8"))
    for t in THEMES
]
print(f"Loaded {len(prds)} PRDs: {[p.theme for p in prds]}")

# --- Roadmap: load the persisted canonical (do NOT re-run plan(); the
# sonnet5_draws characterization fixtures and digest grounding refs are all
# pinned to THIS roadmap artifact — regenerating clobbers their provenance). ---
roadmap = [
    RoadmapItem.model_validate(x)
    for x in json.loads((OUT / "roadmap.json").read_text(encoding="utf-8"))
]
print(f"Roadmap: loaded {len(roadmap)} items from {OUT / 'roadmap.json'}")
for item in roadmap:
    print(f"  [{item.quarter}] {item.prd_ref}: effort {item.effort.score}, "
          f"impact {item.impact.score}")

# --- Three digests, one call per audience ---
for audience in sorted(TONE_BLOCKS):
    digest = summarize(prds, roadmap, audience)
    path = OUT / f"digest_{audience}.json"
    path.write_text(digest.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n{'=' * 70}\nAUDIENCE: {audience}  ->  {path}\n{'=' * 70}")
    print(f"HEADLINE: {digest.headline}\n")
    print(digest.body)
    print(f"\nCALL TO ACTION: {digest.call_to_action}")
    print(f"\nKEY CLAIMS ({len(digest.key_claims)}):")
    for c in digest.key_claims:
        print(f"  - {c.text}  [grounded_in: {c.grounded_in}]")
