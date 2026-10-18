# ShiftReceipt: loophole register and fixes (Sun Oct 18, 4:30 AM)

Companion to ShiftReceipt_PLAN.md. Every item: the hole, the fix, who, and the test that proves it closed.
Verified this morning: image path (Fetch image-analysis example), card rules (Agentverse cards doc), Notice to Cure template (fillable, fields listed below), Gemini docs (structured output shown with `gemini-3.8-flash`).

## 0. The biggest hole: 4 people integrating at 7 AM

**Fix:** freeze the contracts at 4:45 (models.py, function signatures, command grammar, JSON fixtures). Everyone codes against fixtures, not against each other. Nobody waits on Gemini or ASI:One to test their part.

```
models.py (frozen, everyone imports)
  Shift(date, start, end, location=None)      end <= start means overnight
  ScheduleVersion(id, sender, received_at, learned_at, learned_source, sha256, shifts)
  ChangeEvent(id, shift_date, kind, old, new, learned_at, minutes_delta)
      kind: added | cancelled | hours_added | hours_cut | moved | moved_and_added | moved_and_cut | needs_review
  Answers(employee_requested, voluntary_cover, misconduct, already_paid)   each bool | None
  Coverage(retail, over_300, works_2h_la)                                   each bool | None
  LedgerLine(event_id, rule, cents, status, citation, explanation)
      status: may_be_owed | exempt | not_late | needs_answer | needs_review | not_covered | already_paid

diff.py   diff(prev, curr) -> list[ChangeEvent]                    T
rules.py  evaluate(events, answers, coverage, rate_cents) -> list[LedgerLine]
          rest_lines(shifts, rate_cents, ot_minutes) -> list[LedgerLine]     Eshaan
extract.py extract(image_bytes, mime, worker_name, ref_date) -> (list[Shift], warnings)   T
notice.py render_notice(profile, lines) -> pdf bytes; send(to, pdf) -> message_id      Julieth
agent.py  chat, state machine, commands, cards                     V
fixtures/ v1.json v2.json v3.json  (shift lists for the demo screenshots)
```

## 1. ASI:One and Fetch plumbing (owner V)

| # | Hole | Fix | Test |
| --- | --- | --- | --- |
| A1 | Image never reaches the agent | On StartSessionContent send `create_metadata_chat({"attachments":"true"})`; read `ResourceContent.uri` or metadata `url/uri/source/image_url`; http(s) only | Gate 1 at 5:45 |
| A2 | Fetch's example never downloads the image (it hands the URL to OpenAI) | We download with httpx immediately (URL may expire), 10 s timeout, 10 MB cap, content-type image/* only. If GET fails: ask for typed shifts | Upload in ASI:One, log byte count |
| A3 | ASI:One planner answers itself instead of routing | Demo only via the agent's "Chat with Agent" / direct @mention | Rehearsal |
| A4 | Handler blocks other users during Gemini/SMTP | Ack first, short "Reading your schedule..." reply, heavy work in `asyncio.to_thread` | Two senders at once |
| A5 | Same message delivered twice | `seen_msgs(msg_id)` table; skip duplicates | Replay a msg_id |
| A6 | Two laptops run the same seed and steal messages | Seed only in the agent laptop's .env; teammates use their own dev seed and handle | Check Agentverse shows one endpoint |
| A7 | Agent restarts and forgets where the conversation was | Conversation state stored in SQLite per sender, not in memory | Kill and restart mid-flow |
| A8 | Card rejected silently | `card_protocol_version:"1"`, all metadata values strings, payload at top level, < 64 KB. Copy the review/form schema from "Predefined Card Schemas". Every card also sent as text with commands | Break a card on purpose: text still works |
| A9 | Clicks arrive as JSON or as planner prose | Parse JSON first, then regex on the command grammar (section 2) | Unit tests for both |
| A10 | Laptop sleeps or wifi drops during judging | Mac on power, `caffeinate -dimsu`, phone hotspot ready, agent laptop used for nothing else | Lid-closed test 10 min |
| A11 | Fetch discoverability items missing | @handle `shiftreceipt`, avatar, description, keywords, README with both Innovation Lab badges + agent address, 10+ real interactions, Submission Agent registration | Checklist at 8:30 |

## 2. Command grammar (text is the primary interface; cards are a skin)

```
HELP | RESET (demo sender only)
RATE 20.00                     hourly rate
NAME Maria Lopez | MANAGER manager@example.com | EMPLOYER Big Retail Co | TITLE Cashier | STORE Westwood
COVER YES YES YES              retail, 300+ globally, 2+ h/week in LA
GOT 2026-10-05                 when you received the screenshot you just sent (else = upload time)
CONFIRM | EDIT 2026-10-21 13:00-21:00 | DROP 2026-10-21
Q<n> YES|NO                    answer question n
OT <minutes>                   overtime minutes that week (default 0)
RECEIPT | SEND <receipt id>
```

## 3. Reading screenshots (owner T)

| # | Hole | Fix | Test |
| --- | --- | --- | --- |
| G1 | Interactions API image syntax unverified | 4:45 test both `client.interactions.create(...)` and `client.models.generate_content(contents=[Part.from_bytes(...), prompt], config={response_mime_type, response_schema})`. Keep whichever works on all 3 screenshots by 5:15. Model name in .env | 3 fixtures match |
| G2 | AM/PM guessed, year missing | Gemini returns month/day/time strings exactly as shown plus an `ambiguous` flag; Python assigns the year (nearest to upload date) and rejects end == start or duration > 16 h | Unit tests |
| G3 | Team schedule shows coworkers | Prompt extracts only the row matching the worker's NAME; coworker names never stored; images never stored (hash only) | Screenshot with 5 people |
| G4 | Text inside the image says "ignore rules" | Output is schema-locked to shifts; money is never read from the model; dates outside +-60 days dropped | Injection screenshot |
| G5 | Not a schedule / unreadable | Zero shifts → "I could not read a schedule. Type it like: EDIT 2026-10-21 09:00-17:00" | Cat photo |
| G6 | Gemini slow, rate limited, down | 20 s timeout, one retry, then the typed fallback. Mocked in all tests | Mock timeout |
| G7 | Model reads it wrong | Nothing enters the ledger until the worker sends CONFIRM after seeing the parsed shifts | Flow test |

## 4. Versions and diff (owner T)

| # | Hole | Fix | Test |
| --- | --- | --- | --- |
| D1 | First upload has nothing to compare | v1 is the baseline; only the rest rule can apply. Reply says "Send the next version when it changes" | Single upload |
| D2 | Screenshots uploaded out of order | Versions ordered by `learned_at`, not upload order | Upload v2 then v1 |
| D3 | Same screenshot sent twice | Same sha256 for same sender → "already have this one", no new version | Re-upload |
| D4 | Worker backdates `learned_at` | Store both: server `received_at` and worker-stated `learned_at` with `learned_source`; both printed on the notice | Notice shows both |
| D5 | Two shifts on one day | MVP supports one shift per day; more → event `needs_review`, no amount | Fixture |
| D6 | Same change counted again on every rerun | Event id = `{from_v}-{to_v}-{date}-{kind}`; ledger unique on (sender, event_id, rule) | Run evaluate twice |
| D7 | Shift moved to another date | Old date cancelled + new date added is reported as one `moved` event when hours are equal and dates are within the same week | Fixture |

## 5. Rules (owner Eshaan; full table in the plan, Rules 4, 5, 5.1, 6, 10)

| # | Hole | Fix | Test |
| --- | --- | --- | --- |
| R-a | Threshold off by one | Added hours: strictly more than 15 min. Cut hours: 15 min or more. Late: learned less than 14 days before the affected shift's date. Rest: gap strictly under 10 h | Boundary tests each side |
| R-b | Float money | Integer cents; rate in cents; `round half up` on the final division only | 1-cent cases |
| R-c | Coverage unknown | Any Coverage field not True → every line `not_covered`, $0, link to OWS | Unit |
| R-d | Who started the change | Each late event asks Q: requested? covering voluntarily? misconduct? Unanswered → `needs_answer`, $0 | Unit |
| R-e | Already paid on the paycheck | Q: "Was this already paid?" Yes → `already_paid`, $0 | Unit |
| R-f | Rest premium double counts base pay | Premium = 0.5 x rate x shift minutes minus overtime minutes (base pay already received) | Unit |
| R-g | Split shift and overnight | Rest gap only between shifts on different workdays; overnight end = next day | Unit |
| R-h | Combined changes | moved + added: one R2 line. moved + cut: `needs_review` | Unit |
| R-j | Worker is in LA County but not the City (Santa Monica, Culver City, Burbank, Glendale, Beverly Hills) | Coverage question names the City of Los Angeles explicitly and lists common neighbours that are not covered | Copy review |
| R-k | $0 result feels useless | Every $0 line says why and what it still proves; versions are kept as the baseline for future changes; receipt shows running total across weeks | Demo shows one $0 line |
| R-i | Rules not in scope | Receipt footer lists "not checked: good-faith estimate, additional hours, on-call, force majeure, deadlines to sue, penalties" | Snapshot |

## 6. Notice and email (owner Julieth)

Template (official OWS, fillable): employee name, employer name, notice date; checkboxes incl. Rest Between Shifts, Advance Notice of Work Schedule, Predictability Pay; Statement of Facts: job title and duties, who runs the schedule, description, dates, locations; declaration, printed name, signature, date.

| # | Hole | Fix | Test |
| --- | --- | --- | --- |
| N1 | Field names differ from labels | At 4:45 dump field names with pypdf, map once in `FIELDS` dict | Filled PDF opens with values |
| N2 | Template URL changes or download fails | Commit the PDF into the repo (public government form) | Offline run |
| N3 | Signature | Typed name in the signature field plus "signed electronically by typing" line; worker must type `SEND n` | Visual check |
| N4 | Agent becomes a spam cannon | Only to the MANAGER address set in onboarding; max 2 notices per sender per day; From name "ShiftReceipt for <worker>"; body says sent at the worker's request | Third SEND refused |
| N5 | Double send on retry | `pending` row: send only if status = pending, then mark sent with SMTP message id | Double SEND |
| N6 | SMTP fails | Status `failed`, tell the worker, allow retry; never show "sent" without a message id | Wrong password |
| N7 | Cure date wrong | Deadline = send date (LA time) + 15 calendar days; complaint draft only after it | Unit |
| N8 | Gmail app password needs 2FA | Set up the sender account now (section 9) | Test email at 5:30 |

## 7. Data and security (all)

| # | Hole | Fix |
| --- | --- | --- |
| S1 | One user sees another's data | Every query `WHERE sender=?`; test with two senders |
| S2 | SQLite locked from threads | New connection per call, WAL mode, short transactions |
| S3 | Secrets in the public repo | `.env` in .gitignore, `.env.example` committed, `*.db` ignored; Codex scans before push |
| S4 | Logs leak images or emails | Log hashes and ids only |
| S5 | Real worker data in demo | Fictional employer and worker; synthetic screenshots only |

## 8. Demo and submission

| # | Hole | Fix |
| --- | --- | --- |
| X1 | Demo dates look fake | Screenshots show the week of Oct 20 to 26. v1 "GOT 2026-10-05" (worker-stated); v2 received today. Every change is inside 14 days |
| X2 | Judge wants to try it | Demo laptop logged into ASI:One; `RESET` (demo sender only) gives a clean run in 5 s |
| X3 | Live failure on stage | Backup video recorded by 9:45; golden-path test passes before every run |
| X4 | Video length conflict | Exactly 3:00 (fits Devpost 2-3 and Fetch 3-5) |
| X5 | Submission gaps | Public repo, README (what, how, agent address, badges, "built during the event", legal note), Devpost tracks ticked, Fetch Submission Agent, team present at judging |
| X6 | Claims judges can break | "May be owed", "not legal advice", "prepares a draft complaint" (never "files"), statistic only if verified with source |

## 9. What the team must provide (by 4:50)

| Need | From | Why |
| --- | --- | --- |
| Did yesterday's agent reply in ASI:One by @handle? Where is that code? | V | Reuse cuts Gate 1 risk |
| Agent laptop: OS, Python 3.12+ installed, stays plugged in | V | A10 |
| Gemini key works; confirm model name | T | G1 |
| Gmail sender account with 2FA + app password; a teammate inbox as "manager" | Julieth | N8 |
| Phone hotspot | anyone | A10 |
| Paper and Devin access yes/no | Julieth / anyone | Prize entries |
