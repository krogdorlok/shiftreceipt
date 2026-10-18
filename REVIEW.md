VERDICT: FAIL
Milestone: SWEEP   Round: 1   Tests: 7 failed, 179 passed in 3.72s
## Findings
1. [BLOCKER] agent.py:497  Manager-mode RATE and OT at line 472 change the computed amount but leave the old notice sendable; $20/h or $80 rest claims can be emailed after the inputs change. Invalidate the preview on either change and require a fresh RECEIPT before SEND. Test: tests/review/test_sweep_7.py
2. [BLOCKER] agent.py:583  first_time runs before the sender lock, so concurrent SCHEDULE then GOT can execute in reverse order; GOT is discarded and the wrong notice date can change pay. Acquire the sender lock before dedupe and processing, after the acknowledgement. Test: tests/review/test_sweep_9.py
3. [MAJOR] agent.py:514  Manager mode assumes COVER and every change answer is favorable, then shows $70 without asking any of them; this breaks invariant 3 even though M5 requests an estimate. Collect the coverage and applicable change answers before showing a dollar amount. Test: tests/review/test_sweep_12.py
4. [MAJOR] rules.py:139  A rest shift ending at 3 PM remains excluded from a notice at 8 PM the same day; RECEIPT tells the worker to try after working it but cannot include it until tomorrow. Use the current LA time and the shift end when deciding whether R6 is due. Test: tests/review/test_sweep_10.py
5. [MAJOR] agent.py:332  The standalone card shows an amount without "Not legal advice", breaking invariant 6. Add that note to the card body. Test: tests/review/test_sweep_11.py
6. [MAJOR] README.md:10  The agent address is still `agent1q...`, so the M5 judge README lacks the required usable address. Replace it with the address printed for the configured agent at startup. Test: tests/review/test_sweep_8.py
## Invariants
1: OK
2: OK
3: 3
4: OK
5: OK
6: 5
7: OK
8: OK
## Disputed tests
none
