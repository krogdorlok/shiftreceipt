# ShiftReceipt: LA Hacks build plan (locked Sun Oct 18, 4:25 AM)

Source of truth. Replaces AgentHQ entirely. Submit by 11:00 AM, deadline 12:00 PM.

## 1. Decision

**Build ShiftReceipt.** Every late schedule change in LA retail has a legal price tag (LA Fair Work Week Ordinance). Employers' software calculates it for the employer. Nobody sends the worker the bill. ShiftReceipt does.

How we got here (3 rounds, 9 independent checks):

| Round | What ran | Result |
| --- | --- | --- |
| 1 | 3 independent idea lenses (Model Learning, agents + sponsors, quirky wildcard), 6 finalists | 4 killed by prior art or weak novelty |
| 2 | 3 red-teams on "Overheard" (AI eavesdropper + learned masker) | Partly novel (2014 Plantronics closed-loop masking patent); real door cannot be demoed in a 70 dBA hall; 3/10 live. Dropped |
| 3 | 3 red-teams on ShiftReceipt (novelty, law, build) | Partly novel leaning novel; law verified and scoped; build 7/10. **GO** |

Honest note: it is not the quirkiest idea. It is the only one that is novel, verified against the law, demo-proof in a loud hall, and stacks the most prizes. The quirk is the receipt itself.

## 2. Product

**One line:** Send your schedule screenshots to @shiftreceipt in ASI:One. It shows a receipt of predictability pay you may be owed, every line tied to the rule, then sends the official Notice to Cure to your manager and counts down the 15 days.

**Division of labour (say this to judges):** AI reads, code computes, you send.

| Step | Who | Why |
| --- | --- | --- |
| Read screenshot into shifts | Gemini vision (structured output) | Messy input |
| Confirm shifts, answer "did you request this?" | Worker | A screenshot cannot show who initiated a change |
| Diff versions, apply rules, compute cents | Deterministic Python | Exact, tested, cited |
| Send notice | Worker types SEND n | Nothing leaves without explicit approval |

**Two adapters, one rules engine (Workday framing):**
- Employer mode: "lint this draft change before I publish" → "This change costs $X under Rule 5."
- Worker mode: receipt + Notice to Cure.

**Prior art delta:** Deputy and HotSchedules compute this for employers. Reclamo AI and union apps do general wage theft, not scheduling laws. LA's OWS publishes only blank templates. Nothing found does worker-side version tracking, cited ledger, and the notice-then-complaint workflow.

## 3. Rules to implement (verified, OWS FWWO Rules 2025-03-04)

Money in integer cents, round half up. Rate entered by the user. Dates in America/Los_Angeles.

| ID | Rule | Logic | Cite |
| --- | --- | --- | --- |
| R0 | Coverage | User confirms: retail (NAICS 44-45), 300+ employees globally, works 2+ h/week in City of LA. Any no/unsure → "may not be covered, check OWS", no amounts | Rules 1(a), 2 |
| R1 | Notice | Schedule due 14 calendar days before the work period. Change is "late" if the worker learned of it < 14 days before the shift | Rule 4 |
| R2 | Hours added > 15 min | 1 h at regular rate | Rule 5 |
| R3 | Date, time or location changed, no loss of hours | 1 h per change | Rule 5 |
| R4 | Hours cut by 15 min or more, or on-call not called in, or shift cancelled | 0.5 × rate × hours not worked | Rule 5 |
| R5 | Exemptions | Ask: you requested it? voluntarily covering a coworker? misconduct? Yes → $0 with reason | Rule 5.1, LAMC 185.06.B |
| R6 | Right to rest | Shift starts < 10 h after previous shift ends (not split shift same day) → premium owed = 0.5 × rate × shift hours minus overtime hours (base pay already received; law says 1.5x for entire shift). Ask about written consent | Rule 6 |
| R7 | Cure | Log notice delivery date. Day 15 countdown. Day 16 → complaint draft | Rule 10 |

Ambiguous combos (time moved AND hours cut) → line status "needs review", not a number.

**Out of scope, shown as "not checked":** good-faith estimate deviation, 185.05 additional-hours offers, overtime beyond exclusion, force majeure, statute of limitations, 90-day retaliation presumption, franchise headcount, penalty math.

**Tests (Eshaan, before integration):** 14 days exactly (no pay) vs 13; added 15 min (no) vs 16 (yes); cut 15 min (yes) vs 14 (no); rest 10:00 (no) vs 9:59 (yes); split shift same day excluded; overnight shift across midnight; whole shift added; whole shift cancelled; each exemption; "needs review" combo; cents rounding; R0 any "no" yields no amounts.

## 4. Architecture

```
ASI:One user ──Chat Protocol──> @shiftreceipt (uAgent, mailbox, laptop)
   StartSession → create_metadata_chat({"attachments":"true"})
   ResourceContent (image URL) → httpx GET → Gemini vision → shifts JSON
   → confirm card/text → versions + sha256 + received_at (SQLite, WHERE sender=?)
   → diff → exemption questions → rules engine (pure) → ledger with citations
   → receipt card + text → "SEND n" → fill OWS Notice to Cure PDF → SMTP
   → cure deadline row (+ reminder if time)
Optional 2nd agent: rules_notice (rules + PDF) via ctx.send_and_receive
```

Pitfalls (from the build check):
- Send ChatAcknowledgement first, then "Reading your schedule..."; heavy work in asyncio.to_thread.
- One process per seed. Nobody else runs the agent seed.
- Gemini: never guess AM/PM; Python flags end < start or > 16 h. Pin the model name in .env.
- Cards: MetadataContent, all values strings, payload < 64 KB; clicks arrive as JSON or prose, parse both. Always send the same facts as text.
- Store extracted shifts + image hash only, not images. Redact coworkers' names.

Tables: `versions(id, sender, received_at, sha256, posted_date)`, `shifts(version_id, date, start, end, location)`, `ledger(id, sender, shift_date, rule, cents, status, citation, reason)`, `pending(id, sender, kind, status)`, `notices(id, sender, delivered_at, cure_deadline)`.

## 5. Team and clock

| Who | Owns |
| --- | --- |
| V (agent) | uAgent, Chat Protocol, attachments, mailbox, cards + text fallback, click parsing, Agentverse README, Submission Agent |
| T (extraction + data) | Gemini schema + prompt, 3 test screenshots, SQLite, versions, diff, hash/timestamp |
| Eshaan (rules) | rules.py pure + pytest (section 3), exemption questions, ledger, employer lint mode |
| Julieth (notice + story) | OWS template fill (pypdf), SMTP, receipt design in Paper, demo script, 3:00 video, Devpost |

| Time | Milestone | Gate / cut |
| --- | --- | --- |
| 4:30-4:45 | Kickoff, repo, .env, roles. Julieth makes 3 synthetic screenshots for a fictional store (v1 posted 3 weeks out; v2 with 3 late changes; v3 with a clopening) | |
| 4:45-5:45 | Parallel: echo agent with attachments (V); Gemini on the 3 screenshots (T); rules + tests (E); template field names + SMTP (J) | |
| **5:45** | **Gate 1:** upload image in ASI:One → agent replies with extracted shifts | Fail → text input ("Tue 9-17"), keep going |
| 5:45-7:30 | Integrate: versions, diff, questions, ledger, receipt | |
| **7:30** | **Gate 2:** full worker flow end to end in ASI:One, notice email arrives | Fail → cut ladder now |
| 7:30-8:30 | Employer lint mode, cards polish, 2nd agent split if green, README + badges | |
| 8:30-9:00 | Hardening, 10+ real interactions, avatar, keywords | |
| **9:00** | **Feature freeze** | |
| 9:00-10:15 | 3 rehearsals, record exactly 3:00 video (fits Devpost 2-3 and Fetch 3-5), backup recording | |
| 10:15-11:00 | Repo public, Devpost, register with LAHacks ASI:One Submission Agent | |
| **11:00** | **Submit** | |

**Cut ladder, in order:** reminders → 2nd agent → employer lint → cards (text only) → PDF (inline notice text) → live email (show draft).
**Never cut:** ASI:One flow, confirm step, exemption questions, deterministic cited ledger, SEND approval.

## 6. Demo (90 s)

| Time | Show |
| --- | --- |
| 0:00 | "In LA, a schedule change inside 14 days costs the employer money by law. Studies in three fair-workweek cities found many owed workers are never paid (verify exact figure before saying it)." |
| 0:15 | Employer lint: manager's draft change → "costs $X under Rule 5" (Workday angle, 15 s) |
| 0:30 | Worker in ASI:One drops v1 then v2 screenshot → confirm card → "Did you ask for Tuesday's change?" No |
| 0:55 | Receipt card: 3 lines, each with rule citation; total "may be owed" |
| 1:10 | SEND 1 → Notice to Cure arrives in "manager" inbox live; "Cure deadline: Nov 2" |
| 1:25 | Close: "AI reads, code computes, you send." |

## 7. Prizes to enter

| Prize | Entry condition |
| --- | --- |
| Overall + Applied Intelligence (primary track) | Default |
| Fetch.ai | All mandatory items in section 4/5; Interactive Cards and 2 agents are bonus |
| Workday | Dual-adapter framing; ask the booth what they score |
| MLH Gemini | Vision extraction is core |
| Paper | Only if the receipt and cards are designed in Paper |
| GoDaddy domain | Register shiftreceipt.* if cheap |
| Cognition (Devin) | Only if Devin really builds a piece (e.g., employer lint adapter); keep session links |
| Creao, Base44 | Only if the booth confirms their platform is not required |
| Model Learning, Visa, QNX, veri, ElevenLabs | Skip: no honest fit |

Ask at booths before 9 AM: Workday criteria; Devin, Creao, Base44 platform requirements; Fetch video length.

## 8. Wording and legal rules

- Say "may be owed", never "you are owed". "Not legal advice" plus OWS link and phone (844) 924-3752.
- The notice fills the official OWS Notice to Cure template with the worker's own facts. Factual only: dates, hours, changes.
- Synthetic data only; fictional employer; no real screenshots of real coworkers.
- Never say "files your complaint". We prepare a draft; OWS complaints cannot be anonymous.
- README declares everything was built during the event; no AgentHQ code reused.

## 9. Judge questions

| Question | Answer |
| --- | --- |
| "Deputy already calculates this." | For employers. Workers have no access. Same engine, pointed the other way, plus the legal workflow after the number. And we lint for employers too |
| "Screenshots can be faked." | Each upload is hashed and timestamped on receipt, and the record builds over weeks. OWS investigates with the employer's own 3-year records; we organize the worker's side |
| "Is the AI deciding what I'm owed?" | No. Gemini only reads the image. Pure tested code computes every cent, and each line cites the rule |
| "Is this practicing law?" | It fills the city's own template with the worker's facts, says "may be owed", and links OWS |
| "Why ASI:One?" | Image in, receipt card out, approval in the same chat; extraction and rules split across agents |

## 10. Builder instructions (paste as CLAUDE.md)

```
You are the BUILDER. Codex verifies. Never mark your own work verified.
Project: ShiftReceipt, built during LA Hacks Oct 17-18. Spec: ShiftReceipt_PLAN.md.
Build only the milestone named. Python 3.13, uagents, uagents_core chat protocol,
google-genai structured output, SQLite, pydantic, pypdf, pytest. Secrets in .env.
Invariants:
- Gemini only extracts shifts. It never computes money, rules or dates owed.
- rules.py is pure; every ledger line has a rule id and citation; cents are integers.
- No amount without R0 coverage answers and the exemption answers for that change.
- Nothing is emailed without "SEND <id>" from the same sender while status is pending.
- Every query filters by sender. Store image hash, never the image.
- User-facing text says "may be owed" and "not legal advice". No em dashes.
Each session: run the tests you claim, paste results, list "Needs human check"
steps, append to HANDOFF.md, commit, stop.
```
