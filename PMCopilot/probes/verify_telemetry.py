"""Scratch verification for telemetry.py — uv run python -m probes.verify_telemetry"""
import logging
import telemetry


class Capture(logging.Handler):
    """Keeps records instead of rendering them, so we can inspect attributes."""
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


cap = Capture()
pmc = logging.getLogger("pmcopilot")
pmc.addHandler(cap)
pmc.setLevel(logging.DEBUG)

print("--- propagation + type fidelity ---")
telemetry.repair_fire(
    telemetry.drafter_log,
    attempt=2,
    defect_origin="ValidationError",
    detail="risks.0 received a bare string where Risk was expected",
)
print("records:", len(cap.records))
r = cap.records[0]
print("  name:        ", r.name)
print("  pmc_attempt: ", repr(r.pmc_attempt), type(r.pmc_attempt).__name__)
print("  pmc_site:    ", repr(r.pmc_site))
print("  rendered:    ", r.getMessage())

print("\n--- do unprefixed keys actually collide? ---")
for key in ["attempt", "site", "subject", "module", "args"]:
    try:
        telemetry.drafter_log.warning("probe", extra={key: 1})
        print(f"  {key!r}: accepted")
    except KeyError as e:
        print(f"  {key!r}: REJECTED -> {e}")

print("\n--- gap test: foreign trees ---")
before = len(cap.records)
logging.getLogger("httpx").warning("foreign: httpx")
logging.getLogger("langchain.chains").warning("foreign: langchain")
logging.getLogger("pmcopilot.planner").warning("own tree, no helper")
print("new records reaching cap:", len(cap.records) - before)
for rec in cap.records[before:]:
    print("  saw:", rec.name)

print("\n--- root leak check ---")
print("root handlers:", logging.getLogger().handlers)
