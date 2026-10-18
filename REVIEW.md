VERDICT: FAIL
Milestone: CORE-FIX   Round: 1   Tests: 2 failed, 93 passed in 0.12s
## Findings
1. [BLOCKER] rules.py:38  A whitespace-only location counts as named, so adding a real location produces an unsupported $20 line. Strip both locations before checking whether both are named; mark a move with no countable change needs_review. Test: tests/review/test_core_fix_1.py
2. [BLOCKER] diff.py:59  With two equal-length shifts removed and two added in one week, first-match pairing invents location changes and claims $80 although another pairing yields $40. Mark ambiguous pairs needs_review until the worker identifies the moves. Test: tests/review/test_core_fix_2.py
## Invariants
1-8: OK
## Disputed tests
none
