"""Fill the official OWS Notice to Cure template and email it. Factual only: amounts come from rules.py lines."""
import io
import os
import smtplib
import sys
from datetime import date
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter

load_dotenv()
TEMPLATE = Path(__file__).parent / "assets" / "notice_to_cure.pdf"
# Field names dumped once from the 2026 OWS template (python notice.py --fields)
F_EMPLOYEE, F_EMPLOYER, F_DATE = "Employee", "Employer", "Date"
F_TITLE, F_WHO = "Job Title and Duties", "Who is in charge of your work schedule?"
F_DESC = "Describe what your Employer did that violated the provisions of the Fair Work Week Ordinance"
F_DATES, F_WHERE = "What date(s) did these incident(s) occur?", "Where did these incident(s) occur?"
F_PRINT, F_SIGN = "Print Name", "Signature_es_:signer:signature"
BOX_PAY, BOX_REST = "Predictability Pay", "Rest Between Shifts"
PAY_RULES = {"R2", "R3", "R4"}


def usd(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


def _description(lines: list[dict], note: str) -> str:
    out = [f"{l['day']}: {l['change']}, {usd(l['cents'])} may be owed ({l['citation']})." for l in lines]
    out.append(f"Total that may be owed: {usd(sum(l['cents'] for l in lines))}.")
    return " ".join(out + ([note] if note else []))


def render_notice(profile: dict, lines: list[dict], sent_date: date) -> bytes:
    """lines: the may-be-owed ledger lines saved with the notice (rule, cents, citation, day, change)."""
    name = profile["name"]
    text = {F_EMPLOYEE: name, F_EMPLOYER: profile["employer"], F_DATE: sent_date.isoformat(),
            F_TITLE: profile["title"], F_WHO: f"Store manager, {profile['manager']}",
            F_DESC: _description(lines, profile.get("schedule_note", "")),
            F_DATES: ", ".join(sorted({l["day"] for l in lines})), F_WHERE: profile["store"],
            F_PRINT: name, F_SIGN: f"{name} (typed)"}
    boxes = {BOX_PAY: any(l["rule"] in PAY_RULES for l in lines), BOX_REST: any(l["rule"] == "R6" for l in lines)}
    reader = PdfReader(TEMPLATE)
    fields = reader.get_fields() or {}
    have = set(fields)
    missing = [k for k in text if k not in have]
    if missing:  # template changed: never crash, put what has no field into the description (or any text field)
        target = F_DESC if F_DESC in have else next((k for k, v in fields.items() if v.get("/FT") == "/Tx"), None)
        extra = " ".join(f"{k}: {text[k]}." if k != F_DESC else text[k] for k in missing)
        if target:
            text[target] = f"{text[target]} {extra}".strip() if target in text else extra
    values = {k: v for k, v in text.items() if k in have}
    values.update({k: "/On" for k, on in boxes.items() if on and k in have})
    w = PdfWriter(clone_from=reader)
    for page in w.pages:
        w.update_page_form_field_values(page, values, auto_regenerate=False)
    w.set_need_appearances_writer(True)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def send(to: str, pdf_bytes: bytes, worker_name: str) -> str:
    """Returns the Message-ID. Raises on any SMTP failure (caller puts the notice back to pending)."""
    user, password = os.environ["SMTP_USER"], os.environ["SMTP_APP_PASSWORD"]
    msg = EmailMessage()
    msg["Subject"] = f"Notice to Cure under the LA Fair Work Week Ordinance - {worker_name}"
    msg["From"], msg["To"] = user, to
    msg["Message-ID"] = make_msgid(domain=user.split("@")[-1])
    msg.set_content(
        f"Attached is a Notice to Cure from {worker_name}, sent at their request.\n\n"
        "Under the City of Los Angeles Fair Work Week Ordinance, the employer has 15 calendar days from receipt "
        "of this notice to cure the alleged violations described in the attached Statement of Facts.\n\n"
        "This notice was prepared with ShiftReceipt.")
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename="Notice_to_Cure.pdf")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
        s.login(user, password)
        s.send_message(msg)
    return msg["Message-ID"]


if __name__ == "__main__" and sys.argv[1:] == ["--fields"]:
    for k, v in (PdfReader(TEMPLATE).get_fields() or {}).items():
        print(repr(k), v.get("/FT"))
