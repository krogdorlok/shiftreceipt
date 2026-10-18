"""Fill the official OWS Notice to Cure template and email it. Factual only: amounts come from rules.py lines."""
import base64
import io
import os
import smtplib
import sys
from datetime import date
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageChops, ImageFilter, ImageOps
from pypdf import PageObject
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject,
                           TextStringObject)

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
    return "\n".join(out + ([note] if note else []))  # one item per line in a multiline field


def clean_signature(photo: bytes) -> bytes:
    """Photo of a handwritten signature -> PNG with only the ink, transparent background, cropped.
    The paper's brightness (shadows included) is estimated with a wide blur; ink is what is darker than it.
    Raises ValueError if the photo does not look like a signature."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(photo))).convert("L")
    img.thumbnail((1600, 1600))
    paper = img.filter(ImageFilter.GaussianBlur(max(img.size) // 30 or 1))
    ink = ImageChops.subtract(paper, img)                      # 0 on paper, high on ink
    alpha = ink.point(lambda v: 0 if v < 25 else 255 if v > 60 else (v - 25) * 255 // 35)
    share = sum(alpha.histogram()[128:]) / (alpha.size[0] * alpha.size[1])
    box = alpha.getbbox()
    if not box or not 0.002 <= share <= 0.25 or (box[2] - box[0]) < 40:
        raise ValueError("no signature found")
    if box[3] - box[1] > box[2] - box[0]:  # signatures are wide; a tall block of ink is a page of text, not a signature
        raise ValueError("does not look like a signature")
    pad = 8
    box = (max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, img.size[0]), min(box[3] + pad, img.size[1]))
    out = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (20, 30, 80, 0))  # dark blue ink
    out.putalpha(alpha.crop(box))
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def _stamp(writer: PdfWriter, page, rect, png: bytes) -> None:
    """Draw the transparent signature PNG over a field rectangle (bottom aligned, may rise above the line)."""
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    x1, y1, x2, y2 = (float(v) for v in rect)
    h = min((y2 - y1) * 1.35, (x2 - x1 - 8) * img.height / img.width)  # stays below the line above
    w = h * img.width / img.height

    def stream(data: bytes, **keys) -> object:
        s = DecodedStreamObject()
        s.set_data(data)
        s.update({NameObject(k): v for k, v in keys.items()})
        return writer._add_object(s.flate_encode())

    common = {"/Type": NameObject("/XObject"), "/Subtype": NameObject("/Image"), "/Width": NumberObject(img.width),
              "/Height": NumberObject(img.height), "/BitsPerComponent": NumberObject(8)}
    smask = stream(img.getchannel("A").tobytes(), **common, **{"/ColorSpace": NameObject("/DeviceGray")})
    image = stream(img.convert("RGB").tobytes(), **common, **{"/ColorSpace": NameObject("/DeviceRGB"),
                                                              "/SMask": smask})
    overlay = PageObject.create_blank_page(width=page.mediabox.width, height=page.mediabox.height)
    overlay[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): DictionaryObject(
        {NameObject("/Sig"): image})})
    content = DecodedStreamObject()
    content.set_data(f"q {w:.2f} 0 0 {h:.2f} {x1 + 4:.2f} {y1 + 1:.2f} cm /Sig Do Q".encode())
    overlay[NameObject("/Contents")] = writer._add_object(content)
    page.merge_page(overlay)


def render_notice(profile: dict, lines: list[dict], sent_date: date, signature: bytes | None = None) -> bytes:
    """lines: the may-be-owed ledger lines saved with the notice (rule, cents, citation, day, change).
    signature: cleaned PNG from clean_signature, drawn in the signature box; None -> typed name."""
    name = profile["name"]
    text = {F_EMPLOYEE: name, F_EMPLOYER: profile["employer"], F_DATE: sent_date.isoformat(),
            F_TITLE: profile["title"], F_WHO: f"Store manager, {profile['manager']}",
            F_DESC: _description(lines, profile.get("schedule_note", "")),
            F_DATES: ", ".join(sorted({l["day"] for l in lines})), F_WHERE: profile["store"],
            F_PRINT: name, F_SIGN: "" if signature else f"{name} (typed)"}
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
    for page in w.pages:  # the template's description field is single-line: make it wrap, smaller font
        for a in page.get("/Annots") or []:
            a = a.get_object()
            if a.get("/T") == F_DESC:
                a[NameObject("/Ff")] = NumberObject(int(a.get("/Ff", 0)) | 4096)
                a[NameObject("/DA")] = TextStringObject("/Helv 9 Tf 0 g")
    for page in w.pages:
        w.update_page_form_field_values(page, values, auto_regenerate=False)
        if signature:
            for a in page.get("/Annots") or []:
                if a.get_object().get("/T") == F_SIGN:
                    _stamp(w, page, a.get_object()["/Rect"], signature)
    w.set_need_appearances_writer(True)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def send(to: str, pdf_bytes: bytes, worker_name: str) -> str:
    """Returns the message id. Raises on any failure (caller puts the notice back to pending).
    RESEND_API_KEY set: send over HTTPS (works where networks block mail ports). Otherwise Gmail SMTP."""
    subject = f"Notice to Cure under the LA Fair Work Week Ordinance - {worker_name}"
    body = (f"Attached is a Notice to Cure from {worker_name}, sent at their request.\n\n"
            "Under the City of Los Angeles Fair Work Week Ordinance, the employer has 15 calendar days from receipt "
            "of this notice to cure the alleged violations described in the attached Statement of Facts.\n\n"
            "This notice was prepared with ShiftReceipt.")
    if key := os.getenv("RESEND_API_KEY"):
        r = httpx.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {key}"}, timeout=20, json={
            "from": os.getenv("RESEND_FROM") or "ShiftReceipt <onboarding@resend.dev>", "to": [to],
            "subject": subject, "text": body,
            "attachments": [{"filename": "Notice_to_Cure.pdf", "content": base64.b64encode(pdf_bytes).decode()}]})
        r.raise_for_status()
        return r.json()["id"]
    user, password = os.environ["SMTP_USER"], os.environ["SMTP_APP_PASSWORD"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"], msg["To"] = user, to
    msg["Message-ID"] = make_msgid(domain=user.split("@")[-1])
    msg.set_content(body)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename="Notice_to_Cure.pdf")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
            s.login(user, password)
            s.send_message(msg)
    except OSError as e:  # 465 blocked or dropped: try 587 once. Auth and other SMTP replies are not retried.
        if isinstance(e, smtplib.SMTPException) and not isinstance(e, smtplib.SMTPServerDisconnected):
            raise
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
    return msg["Message-ID"]


if __name__ == "__main__" and sys.argv[1:] == ["--fields"]:
    for k, v in (PdfReader(TEMPLATE).get_fields() or {}).items():
        print(repr(k), v.get("/FT"))
