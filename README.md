# ShiftReceipt

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

**An AI agent that helps retail workers in Los Angeles get paid for last-minute schedule changes.**

Built during LA Hacks AI Hackathon, Oct 17-18 2026.

| Agent | Address |
| --- | --- |
| `shiftreceipt` (@shiftreceipt) | `agent1qffxdzuxgw6ad4k6dmlsfxd4h7ey26mgsfs0nt6lkgz8wv97z4w7wfexzpq` |

## What it does

Under the City of Los Angeles Fair Work Week Ordinance, large retailers must post schedules 14 days before the
work week starts. If they change a schedule after that, the worker may be owed **predictability pay**, and a shift
that starts less than 10 hours after the last one earns a **rest premium**. Most workers never claim it.

ShiftReceipt does it for them, inside one chat:

1. The worker sends a **screenshot** of their schedule. AI reads only their shifts; they check and confirm.
2. When the schedule changes, they send the new one. ShiftReceipt finds every change.
3. It asks one yes/no question per change (did you ask for it?), because the law has exceptions.
4. It shows a **receipt**: each change, the amount that may be owed, and the City rule behind it.
5. It prepares the City's official **Notice to Cure**. The worker signs with a photo of their handwritten signature
   (the background is removed and it is placed on the form), types `SEND 1`, and it is emailed to their manager.

Demo result: $70.00 in schedule-change pay, plus an $80.00 rest premium if the worker works the short-rest shift.

## Where it works

- **ASI:One**, through **Agentverse**: open the agent on [agentverse.ai](https://agentverse.ai) and click
  **Chat with Agent**. The whole flow happens in that chat; there is no separate app.
- The agent runs as a Fetch.ai **uAgent** with the **Agent Chat Protocol**, connected to Agentverse by a mailbox.

## Try it (in the ASI:One chat)

```
NAME Maria Lopez RATE 20 EMPLOYER Big Retail Co TITLE Cashier STORE Westwood, Los Angeles MANAGER you@example.com COVER yes yes yes
```
Then attach `assets/demo/v1_posted_oct3.png`, send `GOT 2026-10-03 CONFIRM`, attach `assets/demo/v2_changed_oct17.png`,
send `GOT 2026-10-17 CONFIRM`, answer `Q1 no Q2 no Q3 no Q4 no Q5 no`, then `SEND 1`, attach a signature photo, and
`SEND 1` again. `HELP` explains everything; `RESET` starts over (demo accounts only).

## Set it up

You need Python 3.10+ and three keys:
- a [Gemini API key](https://aistudio.google.com/apikey) (reads the screenshots),
- a [Resend](https://resend.com) API key (sends the email; the free plan delivers to your own Resend email address),
- an [Agentverse](https://agentverse.ai) account (hosts the agent's mailbox and makes it reachable from ASI:One).

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then fill in AGENT_SEED, GEMINI_API_KEY, RESEND_API_KEY
.venv/bin/python agent.py   # prints the agent address and an Agent Inspector link
```

Open the Agent Inspector link, click **Connect**, choose **Mailbox**. The agent is now live on Agentverse and
reachable from ASI:One. Keep the program running.

`AGENT_SEED` is any long random secret (for example `python3 -c "import secrets; print(secrets.token_hex(32))"`);
the same seed always gives the same agent address. Gmail can be used instead of Resend (`SMTP_USER` and a Gmail
app password), on networks that allow mail ports.

Run the tests (offline; Gemini and email are faked): `.venv/bin/python -m pytest -q`

## How it works

| File | Job |
| --- | --- |
| `agent.py` | the uAgent: chat protocol, conversation steps, replies |
| `extract.py` | Gemini reads the worker's shifts from a screenshot (falls back to another model if one is over quota) |
| `diff.py`, `rules.py` | finds schedule changes and applies the City's pay rules, in plain Python and whole cents |
| `notice.py` | fills the official City Notice to Cure PDF, places the signature, sends the email |
| `parser.py`, `db.py`, `models.py` | reads commands, stores each worker's progress (SQLite), data types |

## Trust and privacy

- AI only reads shifts from images. Every dollar amount comes from fixed rules, with the City citation shown.
- Unclear changes are marked "needs review" instead of guessed.
- Nothing is emailed until the worker signs and types `SEND 1`. At most 2 notices per day.
- Screenshots are never stored (only a fingerprint). The signature photo is kept in memory until that one notice
  is sent, then dropped. Each worker only ever sees their own data.

## Limits

Not checked: good-faith estimate, additional-hours offers, on-call shifts, force majeure, filing deadlines,
penalties. Work weeks are assumed to run Monday to Sunday, with one hourly rate per worker.

**Not legal advice.** ShiftReceipt estimates what may be owed and prepares a draft. Questions: City of LA Office of
Wage Standards, (844) 924-3752, [wagesla.lacity.gov](https://wagesla.lacity.gov).
