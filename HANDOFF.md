# Handoff log (Claude Code appends after every milestone)

## Core (done before M1)
models, diff, rules, parser, db, fixtures, 88 tests. Tag: core-verified.

## Core bug
1. 14-day notice measured from each shift; City measures from the start of the Work Period (FAQ 36, 50, 52).
2. Every move paid 1 h; City pays 1 h per date/time/location change (FAQ table, Module 3 Scenario 1).
3. Same-week cancel + add with new hours overpaid; now needs_review.
4. Rest premium counted as owed before the shift is worked; cure period runs from employer's receipt.
Human approved the fix (Oct 18, 5:15 AM). Fixed on branch core-fix, spec prompts/CORE-FIX.md.

## Disputed review tests
none

CORE-FIX round 4 approved by the human (Oct 18) after round 3 FAIL: a week with a changed multi-shift day is all needs_review.
