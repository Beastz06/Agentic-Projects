"""One-shot backfill: insert `theme` as the first key into existing PRD JSONs.

Context: PRD.theme became a required field (intrinsic identity, code-set from
DiscoveryFinding.theme at draft time). Artifacts generated before that field
existed lack it and no longer validate. This script backfills them per the
agreed boundary.

Boundary (deliberate):
- Canonicals (data/output/prd_<theme>.json)              -> real theme
- C9 sample fixtures (schemas/examples/<theme>_samples/) -> real theme
- Hand-crafted fixtures (schemas/examples/prd*.json)     -> "example"
- Archives (sonnet4_draws/, sonnet5_draws/ run1 copies)  -> NOT touched
  (historical snapshots of an older schema; left as-is intentionally)

Ordering: theme is inserted FIRST, matching fresh model output (which emits
theme first) and the schema's "identity precedes content" field order.

Idempotent: re-running is safe. If `theme` is already present it is moved to
first position and its value is left unchanged (so a hand-edited value is not
clobbered). Run from the repo working directory (D:\\Agentic-Projects\\PMCopilot).
"""
import json
from collections import OrderedDict
from pathlib import Path

# (relative path, theme value)
TARGETS: list[tuple[str, str]] = [
    # canonicals
    ("data/output/prd_streaming.json", "streaming"),
    ("data/output/prd_authentication.json", "authentication"),
    ("data/output/prd_tool_calling.json", "tool_calling"),
    # C9 sample fixtures
    ("schemas/examples/streaming_samples/prd_streaming_run2.json", "streaming"),
    ("schemas/examples/streaming_samples/prd_streaming_run3.json", "streaming"),
    ("schemas/examples/authentication_samples/prd_authentication_run2.json", "authentication"),
    ("schemas/examples/authentication_samples/prd_authentication_run3.json", "authentication"),
    ("schemas/examples/tool_calling_samples/prd_tool_calling_run2.json", "tool_calling"),
    ("schemas/examples/tool_calling_samples/prd_tool_calling_run3.json", "tool_calling"),
    # hand-crafted fixtures
    ("schemas/examples/prd1_full.json", "example"),
    ("schemas/examples/prd2_empty_stories.json", "example"),
    ("schemas/examples/prd3_min_acs.json", "example"),
    ("schemas/examples/prd_malformed_2acs.json", "example"),
]


def backfill_one(path: Path, theme: str) -> str:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw, object_pairs_hook=OrderedDict)

    already = "theme" in data
    existing_value = data.get("theme")

    # Build a new ordered dict with theme first, preserving all other keys/order.
    rebuilt = OrderedDict()
    rebuilt["theme"] = existing_value if already else theme
    for k, v in data.items():
        if k == "theme":
            continue
        rebuilt[k] = v

    path.write_text(json.dumps(rebuilt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if already:
        return f"SKIP-VALUE (theme present={existing_value!r}, moved to first)"
    return f"ADDED theme={theme!r}"


def main() -> None:
    missing: list[str] = []
    for rel, theme in TARGETS:
        p = Path(rel)
        if not p.exists():
            missing.append(rel)
            print(f"  !! MISSING: {rel}")
            continue
        status = backfill_one(p, theme)
        print(f"  {status:40s} {rel}")

    print()
    if missing:
        print(f"WARNING: {len(missing)} file(s) not found — check paths/cwd.")
    else:
        print(f"Done: {len(TARGETS)} files processed.")


if __name__ == "__main__":
    main()
