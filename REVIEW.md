VERDICT: FAIL
Milestone: M3   Round: 1   Tests: 6 failed, 153 passed in 1.74s
## Findings
1. [MAJOR] agent.py:427  A start-session message sends attachment metadata but no onboarding question, so a new worker is never asked for the required fields. Also send one prompt listing only missing fields in spec order. Test: tests/review/test_m3_1.py
2. [MAJOR] agent.py:283  A second schedule replaces pending_vid; confirming it strands the first unconfirmed version, and resending the first says "Already have this one." Keep and present all unconfirmed versions for confirmation, including a resent duplicate. Test: tests/review/test_m3_2.py
3. [MAJOR] agent.py:390  Multiline commands bypass parser.py's 2,000-character input limit and can cause unbounded database writes from one message. Enforce the limit on the whole text before splitting or running commands. Test: tests/review/test_m3_3.py
4. [MAJOR] agent.py:296  Each image received during onboarding overwrites the prior image, so only the last schedule survives. Queue images or extract and save each once NAME is known. Test: tests/review/test_m3_4.py
5. [MAJOR] agent.py:122  An image received after NAME remains only in PENDING_IMAGES until all other fields arrive; a restart loses it despite the required persistent flow. Extract and save shifts as soon as NAME is available. Test: tests/review/test_m3_5.py
6. [MAJOR] agent.py:292  A duplicate image during onboarding is not recognized because the SHA check looks only in the database. Check the pending image SHA too and reply "Already have this one." Test: tests/review/test_m3_6.py
## Invariants
1-8: OK
## Disputed tests
none
