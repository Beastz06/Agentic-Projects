# Retro

What worked, what didn't, and what I'd do differently. Written after the fact,
against the artifacts rather than from memory.

## What worked

**Predicting the result before running anything whose output fed a decision.**
The habit paid least when the prediction was right. Before the first summarizer
run I predicted at least six indexed claims per digest, with the customer digest
lowest — reasoning that its tone rules forbid the vocabulary numbers arrive in.
The run returned twelve for customer, six for exec, and zero for engineering.
Both halves wrong, and the inversion corrected a premise: a claim is load-bearing
because it asserts something checkable, not because it contains a figure. The
finding underneath was larger — the engineering digest was the most
assertion-dense of the three and indexed none of them, which is a coverage gap
that structural validation cannot see by construction. A stated prior is what
made an unremarkable-looking output readable as a defect.

**Worked examples instead of clearer instruction.** The acceptance-criteria rules
were already stated in prose in the drafter's system prompt, and were being
ignored. What moved the numbers was pairing each rule with one `bad → good`
example beside it. No schema, model, or retrieval change.
[Results](./README.md#results).

**Baseline first, then fix, then measure again.** The delta is the artifact. A
tuned system with no before-number can claim nothing.

**Splitting structure from quality.** The schema enforces shape; a judge scores
quality. Constraints that force the model to populate a field become fabrication
pressure rather than correctness checks — a minimum on acceptance criteria makes
a refusal case invent them. The rule that came out of it: the model fills only
what it must judge, and code sets everything derivable.

## What didn't

**Instrumentation arrived after the thing it was supposed to measure.** The first
end-to-end pipeline ran a silent repair loop. Success and success-after-two-repairs
were indistinguishable from outside, on a component whose stated goal was passing
validation on the first attempt. The system could not measure its own headline
metric.

**An error bar got used outside what it measured.** A ±0.2 spread, published as a
noise floor, came from scoring one frozen set of outputs twice. It measures judge
consistency. Every comparison in the table beside it was between separate
generations of output, which is a different and much larger source of variance.
The published figure never licensed a single delta in its own document, and it
took re-drafting an unchanged prompt to find out how much larger.
[Detail](./evals/README.md).

**Provenance was assumed rather than recorded.** Each captured fixture stamps the
commit at the head of the branch, with no flag for an uncommitted working tree.
A fix that was live during one capture and committed afterward appears in no diff
between the two recorded hashes. A commit hash is a pointer to a tree, not a
claim about the code that ran.

**Published numbers went unchecked for longer than they should have.** One column
of the results table mixed two sample sizes; a headline improvement figure
described one step of a series as though it were the whole series. Both were
found by re-deriving the table from the raw result files. Nothing in the pipeline
would have caught either.

## What I'd do differently

1. **Instrument before building the thing being instrumented.** Log the retry
   branch on the day the retry loop is written, not on the day an eval needs it.
2. **Write down what an error bar measures, next to the error bar.** A variance
   figure with no stated scope will get applied to whatever comparison is nearby.
3. **Make provenance a hash of the inputs that produced a run** — prompt text,
   retrieved context, working-tree state — rather than a pointer to a commit.
4. **Hold out one re-capture at an unchanged prompt from the start.** Drafter
   variance should have been the first number measured, not the last.
5. **Generate the results table from the raw files.** Every hand-maintained
   number in a README is a number that can drift from its source, and two of them
   did.