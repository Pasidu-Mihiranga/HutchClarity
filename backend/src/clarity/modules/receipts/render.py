"""Rendering a Trust Receipt as PNG and PDF (deck S6, plan §15.2).

A receipt has to survive leaving the app: shown at a shop, attached to a
regulator submission, or kept by someone who no longer has the Hutch app. So it
renders to an image and a PDF, in Sinhala, Tamil or English.

Rendering runs through a headless browser because that is what shapes Sinhala
and Tamil correctly - the deck calls this out as the reason for the choice
("Playwright render · correct Sinhala/Tamil", S13). A naive PDF library
produces broken glyph clusters for both scripts.

**Safety.** The render input is a template plus already-verified values, never
free text, and the page loads no external resource. Plan §7.2 T9 runs this in
an isolated pool with no network egress for the same reason.

Playwright is an optional extra: if it is not installed, :func:`render` raises
a clear error and callers fall back to the SMS form and the public verify page.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from clarity.contracts.receipt import RecurrenceResult, TrustReceipt
from clarity.kernel.common import Language


class RenderFormat(StrEnum):
    PNG = "png"
    PDF = "pdf"


class RendererUnavailable(RuntimeError):
    """Playwright or its browser is not installed."""


@dataclass
class RenderedReceipt:
    format: RenderFormat
    content: bytes
    language: Language

    @property
    def media_type(self) -> str:
        return "image/png" if self.format is RenderFormat.PNG else "application/pdf"


_STRINGS: dict[Language, dict[str, str]] = {
    Language.EN: {
        "title": "Trust Receipt",
        "what_happened": "What happened",
        "what_corrected": "What we corrected",
        "safeguard": "Safeguard",
        "recurrence": "Recurrence test",
        "verify": "Scan to verify, or quote this number on 1788, on WhatsApp, or to TRCSL.",
        "issued": "Issued",
        "number": "Number",
        "returned": "Returned",
        "signed": "Signed",
        "verified": "VERIFIED",
    },
    Language.SI: {
        "title": "විශ්වාස රිසිට්පත",
        "what_happened": "සිදු වූයේ කුමක්ද",
        "what_corrected": "අප නිවැරදි කළ දේ",
        "safeguard": "ආරක්ෂණය",
        "recurrence": "නැවත සිදුවීම් පරීක්ෂණය",
        "verify": "තහවුරු කිරීමට ස්කෑන් කරන්න, හෝ 1788, WhatsApp හෝ TRCSL වෙත මෙම අංකය දක්වන්න.",
        "issued": "නිකුත් කළ දිනය",
        "number": "අංකය",
        "returned": "ආපසු ගෙවූ මුදල",
        "signed": "අත්සන් කර ඇත",
        "verified": "තහවුරු කර ඇත",
    },
    Language.TA: {
        "title": "நம்பிக்கை ரசீது",
        "what_happened": "என்ன நடந்தது",
        "what_corrected": "நாங்கள் சரிசெய்தது",
        "safeguard": "பாதுகாப்பு",
        "recurrence": "மீண்டும் நிகழ்வு சோதனை",
        "verify": "சரிபார்க்க ஸ்கேன் செய்யவும், அல்லது 1788, WhatsApp அல்லது TRCSL இல் இந்த எண்ணைக் குறிப்பிடவும்.",
        "issued": "வழங்கப்பட்டது",
        "number": "எண்",
        "returned": "திரும்பப் பெற்றது",
        "signed": "கையொப்பமிடப்பட்டது",
        "verified": "சரிபார்க்கப்பட்டது",
    },
}

_ACTION_WORDS: dict[Language, dict[str, str]] = {
    Language.EN: {
        "REFUND": "Returned to your balance",
        "DEACTIVATE_VAS": "Subscription switched off",
        "BLOCK_MERCHANT_UNTIL_OPTIN": "Merchant blocked until you opt in",
        "SET_SPEND_CAP": "Spending cap set",
        "ENABLE_DATA_STOP": "Data stops when a pack ends",
        "ENABLE_FUP_ALERTS": "Fair-use alerts switched on",
    },
    Language.SI: {
        "REFUND": "ඔබගේ ශේෂයට ආපසු එක් කරන ලදී",
        "DEACTIVATE_VAS": "දායකත්වය නවත්වන ලදී",
        "BLOCK_MERCHANT_UNTIL_OPTIN": "ඔබ අනුමත කරන තෙක් වෙළෙන්දා අවහිර කර ඇත",
        "SET_SPEND_CAP": "වියදම් සීමාව සකසා ඇත",
        "ENABLE_DATA_STOP": "පැකේජය අවසන් වූ විට දත්ත නවතී",
        "ENABLE_FUP_ALERTS": "සාධාරණ භාවිත දැනුම්දීම් සක්‍රීයයි",
    },
    Language.TA: {
        "REFUND": "உங்கள் இருப்புக்குத் திரும்பச் சேர்க்கப்பட்டது",
        "DEACTIVATE_VAS": "சந்தா நிறுத்தப்பட்டது",
        "BLOCK_MERCHANT_UNTIL_OPTIN": "நீங்கள் ஒப்புக்கொள்ளும் வரை வணிகர் தடுக்கப்பட்டார்",
        "SET_SPEND_CAP": "செலவு வரம்பு அமைக்கப்பட்டது",
        "ENABLE_DATA_STOP": "தொகுப்பு முடிந்ததும் தரவு நிற்கும்",
        "ENABLE_FUP_ALERTS": "நியாயமான பயன்பாட்டு எச்சரிக்கைகள் இயக்கப்பட்டன",
    },
}


def receipt_html(receipt: TrustReceipt, language: Language = Language.EN) -> str:
    """Build the receipt page. Every value is escaped; nothing external loads."""
    strings = _STRINGS[language]
    words = _ACTION_WORDS[language]
    payload = receipt.payload
    esc = html.escape

    rows = "".join(
        f"<li><span>{esc(words.get(a.type.value, a.type.value))}</span>"
        + (f"<strong>LKR {esc(f'{a.amount_lkr:.2f}')}</strong>" if a.amount_lkr is not None else "")
        + (
            f"<em>{esc(a.before.get('balance_lkr', ''))} &rarr; "
            f"{esc(a.after.get('balance_lkr', ''))}</em>"
            if a.before.get("balance_lkr") and a.after.get("balance_lkr")
            else ""
        )
        + "</li>"
        for a in payload.actions
    )

    recurrence = ""
    if payload.recurrence_test is not None:
        passed = payload.recurrence_test.result is RecurrenceResult.PASSED
        recurrence = (
            f'<div class="row"><span>{esc(strings["recurrence"])}</span>'
            f'<b class="{"ok" if passed else "warn"}">'
            f"{esc(payload.recurrence_test.result.value)}</b></div>"
        )

    safeguard = ""
    if payload.safeguard is not None:
        safeguard = (
            f'<div class="row"><span>{esc(strings["safeguard"])}</span>'
            f"<b>{esc(words.get(payload.safeguard.type.value, payload.safeguard.type.value))}</b></div>"
        )

    total = payload.total_corrected_lkr
    return f"""<!doctype html>
<html lang="{language.value}"><head><meta charset="utf-8">
<style>
  @page {{ size: 420px 620px; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; width: 420px; min-height: 620px; padding: 28px;
         font: 14px/1.6 -apple-system, "Noto Sans Sinhala", "Noto Sans Tamil", sans-serif;
         color: #1a1a1a; background: #fff; }}
  .head {{ display: flex; justify-content: space-between; align-items: flex-start;
           border-bottom: 3px solid #c2410c; padding-bottom: 12px; }}
  h1 {{ font-size: 19px; margin: 0; }}
  .id {{ font-family: ui-monospace, Menlo, monospace; font-size: 14px;
         font-weight: 700; margin-top: 4px; }}
  .stamp {{ background: #dcfce7; color: #14532d; font-size: 10px; font-weight: 700;
            letter-spacing: .06em; padding: 5px 10px; border-radius: 5px; }}
  h2 {{ font-size: 10px; text-transform: uppercase; letter-spacing: .08em;
        color: #6b6b6b; margin: 20px 0 8px; }}
  p.what {{ margin: 0; font-size: 13px; }}
  ul {{ list-style: none; padding: 0; margin: 0; }}
  li {{ display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;
        padding: 7px 0; border-bottom: 1px dashed #e4e4e7; font-size: 13px; }}
  li em {{ font-style: normal; color: #6b6b6b; font-size: 11px; width: 100%; }}
  .row {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; }}
  .row span {{ color: #6b6b6b; }}
  .ok {{ color: #047857; }} .warn {{ color: #b45309; }}
  .total {{ margin-top: 14px; padding: 12px; background: #fff7ed;
            border-radius: 8px; display: flex; justify-content: space-between;
            font-size: 16px; font-weight: 700; }}
  footer {{ margin-top: 20px; padding-top: 14px; border-top: 1px solid #e4e4e7;
            font-size: 10px; color: #6b6b6b; }}
  .sig {{ font-family: ui-monospace, Menlo, monospace; font-size: 9px;
          word-break: break-all; color: #9b9b9b; margin-top: 6px; }}
</style></head>
<body>
  <div class="head">
    <div><h1>{esc(strings["title"])}</h1><div class="id">{esc(payload.receipt_id)}</div></div>
    <span class="stamp">{esc(strings["verified"])}</span>
  </div>

  <h2>{esc(strings["what_happened"])}</h2>
  <p class="what">{esc(payload.what_happened.summary)}</p>

  {f"<h2>{esc(strings['what_corrected'])}</h2><ul>{rows}</ul>" if rows else ""}

  {f'<div class="total"><span>{esc(strings["returned"])}</span><span>LKR {esc(f"{total:.2f}")}</span></div>' if total else ""}

  <h2>&nbsp;</h2>
  {safeguard}
  {recurrence}
  <div class="row"><span>{esc(strings["number"])}</span><b>{esc(payload.subject.msisdn_masked)}</b></div>
  <div class="row"><span>{esc(strings["issued"])}</span><b>{esc(payload.issued_at.strftime("%d %b %Y, %H:%M"))}</b></div>

  <footer>
    {esc(strings["verify"])}<br>{esc(receipt.verify_url)}
    <div class="sig">{esc(strings["signed"])} Ed25519 · {esc(receipt.signature.kid)}<br>{esc(receipt.payload_hash)}</div>
  </footer>
</body></html>"""


def render(
    receipt: TrustReceipt,
    *,
    language: Language = Language.EN,
    format: RenderFormat = RenderFormat.PNG,
) -> RenderedReceipt:
    """Render a receipt. Raises :class:`RendererUnavailable` without Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise RendererUnavailable(
            "receipt rendering needs playwright: pip install playwright && playwright install chromium"
        ) from error

    markup = receipt_html(receipt, language)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                channel="chromium",
                args=[
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-sync",
                    "--host-resolver-rules=MAP * ~NOTFOUND",
                ],
            )
            try:
                context = browser.new_context(viewport={"width": 420, "height": 620})
                context.route("**/*", lambda route: route.abort())
                page = context.new_page()
                page.set_content(markup, wait_until="load")
                content = (
                    page.screenshot(full_page=True)
                    if format is RenderFormat.PNG
                    else page.pdf(width="420px", height="620px", print_background=True)
                )
            finally:
                browser.close()
    except RendererUnavailable:
        raise
    except Exception as error:  # pragma: no cover - browser/runtime failures
        raise RendererUnavailable(f"receipt could not be rendered: {error}") from error

    return RenderedReceipt(format=format, content=content, language=language)


def write(receipt: TrustReceipt, path: Path, **kwargs: object) -> Path:
    """Render and save. Used by the demo and by regulator exports."""
    rendered = render(receipt, **kwargs)  # type: ignore[arg-type]
    path.write_bytes(rendered.content)
    return path
