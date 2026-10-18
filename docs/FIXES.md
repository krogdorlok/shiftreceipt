# ShiftReceipt: numbered fixes (Sun Oct 18, 4:35 AM)

Status: DONE = already in shiftreceipt_core.zip with tests. M1-M5 = builder milestone. T1-T3 = tester. YOU = Eshaan.

## Team and process
1. Four people integrating late → one builder, frozen core, testers on scripts. DONE
2. Agent Mac is also the dev Mac → freeze at 9:00; after that restart only to fix a crash. YOU
3. Fixes interrupt building → testers report "case, sent, got, PASS/FAIL"; fixes go in the next milestone window. T1-T3

## ASI:One and Fetch
4. Image never reaches the agent → send `{"attachments":"true"}` on session start; read `uri` or metadata `url/uri/source/image_url`. M1
5. Fetch's example never downloads the image → download at once with httpx: 10 s, 10 MB, image/* only, http(s) only. M1
6. Download fails → typed SCHEDULE block. DONE (parser) + M1 reply text
7. ASI:One answers itself instead of our agent → demo only via "Chat with Agent" / direct @mention. T1
8. One slow user blocks everyone → ack first, Gemini/SMTP/PDF in `asyncio.to_thread`. M1
9. Same message delivered twice → `db.first_time(msg_id)`. DONE
10. Two processes on one seed → seed only in the Mac's .env, one process. YOU
11. Restart loses the conversation → state stored per sender in SQLite. DONE (db) + M3
12. Card rejected silently → version "1", string values, top-level payload, < 64 KB, text receipt always sent too. M5
13. Clicks arrive as JSON or as prose → parser tries JSON, typed command, then prose. DONE
14. Mac sleeps or wifi drops → on power, `caffeinate -dimsu`, phone hotspot ready, Mac used for nothing else. YOU
15. Fetch discoverability items missing → @handle, avatar, description, keywords, README with both badges and agent address, 10+ real chats, Submission Agent registration. M5 + T3

## Reading screenshots
16. Gemini image call syntax unverified → try `generate_content` + `Part.from_bytes`, else `interactions.create`. M2
17. AM/PM guessed, year missing → Gemini flags ambiguous; Python sets the year (`nearest_date`) and rejects end = start or > 16 h. DONE (year) + M2
18. Team schedule shows coworkers → extract only the worker's row; images never stored, hash only. M2 + DONE (db)
19. Text in the image tries to change rules or money → output schema is shifts only; money only from pure code. DONE (design) + M2
20. Not a schedule → zero shifts, typed fallback offered. M2/M3
21. Gemini slow or down → 20 s timeout, one retry, then typed fallback. M2
22. Shifts misread → nothing counts until the worker sends CONFIRM. M3 (flag DONE in db)

## Schedule versions
23. First upload has nothing to compare → baseline; only the rest rule applies. DONE + M3 message
24. Uploaded out of order → ordered by when the worker got it (GOT), not upload time. DONE
25. Same screenshot twice → same hash = same version. DONE
26. Worker backdates GOT → both server time and worker-stated date stored and printed on the notice. DONE (db) + M4
27. Two shifts on one day → "needs review", no amount. DONE
28. Same change counted twice → deterministic event ids; evaluate is idempotent. DONE
29. Shift moved to another day → one "moved" event within the same week. DONE

## Pay rules
30. Off-by-one thresholds → added > 15 min, cut ≥ 15 min, late < 14 days, rest < 10 h; tests on both sides. DONE
31. Float money errors → integer cents, round half up once. DONE
32. Lateness judged on UTC date → LA date. DONE
33. Coverage unknown → every line $0 "not covered". DONE
34. Store in Santa Monica, Culver City etc. → coverage question names the City of LA and its neighbours. M3
35. Screenshot can't show who asked for the change → questions per change; unanswered = $0. DONE + M3
36. Already paid on the paycheck → "already paid" status exists; ask once if time allows. DONE (rules) + M3 optional
37. Rest premium double-counts base pay → owed = 0.5 x rate x shift minus overtime. DONE
38. Split shifts and overnight shifts → split shift excluded; overnight ends next day. DONE
39. Moved AND cut at once → "needs review". DONE
40. Rules we don't cover → "Not checked" footer on every receipt. DONE (text) + M3
41. $0 result feels useless → every $0 line says why; versions kept as baseline; running total across weeks. DONE (reasons) + M3

## Notice and email
42. PDF field names differ from labels → dump with pypdf, map once. M4
43. Template link breaks → commit the official PDF into assets/. T1
44. Signature → typed name plus explicit SEND. M4
45. Agent used to spam people → sends only to the onboarding MANAGER address; max 2 per day. DONE (cap) + M4 (address)
46. Double send on retry → atomic claim of a pending notice. DONE
47. SMTP fails → back to pending, worker retries; "sent" only with a Message-ID. DONE + M4
48. Wrong cure date → LA date of sending + 15 days. DONE
49. Gmail app password needs 2-step verification → set it up now. YOU or T1

## Data and security
50. One user sees another's data → every query filtered by sender; tested. DONE
51. SQLite locked across threads → one connection per call, WAL. DONE
52. Secrets in the public repo → .gitignore and .env.example; scan before making public. DONE + T3
53. Logs leak images or emails → log ids and hashes only. M1-M4
54. Real people's data in the demo → fictional store and worker. T1
55. Anyone can wipe data → RESET only for DEMO_SENDERS. M3 (env DONE)
56. Huge, empty or malicious text → parser caps length and validates every field. DONE

## Demo and submission
57. Demo dates look fake → week Oct 19-25, v1 GOT Oct 4, v2 today. DONE (fixtures)
58. Judge wants to try it → demo Mac logged into ASI:One, RESET for a clean run. T1
59. Live failure on stage → backup video by 9:45; golden script before every run. T1
60. Video length conflict → exactly 3:00. T1
61. Submission gaps → public repo, README, Devpost tracks, Fetch Submission Agent, team present. T2 + T3
62. Overclaiming → "may be owed", "not legal advice", "prepares a draft"; no unverified statistics. DONE (rules text) + T1
63. Sponsor requirements unknown → booth answers from Workday, Cognition, Creao, Base44, Fetch before 9:00. T2
64. Judges think old code is reused → README: built during the event, nothing from AgentHQ. T3
65. Hard judge questions → answers in PLAN section 9; rehearse them. T1

## What I need from you (never paste keys or passwords here)
A. Confirm you are the builder.
B. `python3 --version` on the Mac.
C. If any gate fails: the exact error text or a screenshot of the reply.
D. T2's booth answers (Workday, Cognition/Devin, Creao, Base44, Fetch video length and Submission Agent steps).
E. The hacker guide's text for the three general tracks, if it exists.
F. Optional: the 3 demo screenshots once drawn, so I can check them against the fixtures.
