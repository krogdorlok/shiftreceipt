VERDICT: FAIL
Milestone: M3   Round: 3   Tests: 3 failed, 161 passed in 2.05s
## Findings
1. [BLOCKER] agent.py:215  DROP of the last shift leaves an empty confirmed version, which _events excludes; an eight-hour cancellation disappears and the receipt says $0. Track the dropped version's week and compare that empty version with its predecessor. Test: tests/review/test_m3_7.py
2. [BLOCKER] agent.py:445  Truncating a 2,001-character paste can turn RATE 200 into RATE 20 and save the wrong hourly rate. Reject oversize messages before parsing or writing any command. Test: tests/review/test_m3_8.py
3. [MAJOR] agent.py:447  A multiline paste with "HELP" and "Do not send receipt 7" calls send_notice without a typed SEND command, bypassing the single-line gate. Apply the explicit SEND check to each pasted line before run. Test: tests/review/test_m3_9.py
## Invariants
1: OK
2: OK
3: OK
4: 3
5: OK
6: OK
7: OK
8: OK
## Disputed tests
none
