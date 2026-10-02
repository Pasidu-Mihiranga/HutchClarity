"""Simple HTML Trust Receipt template."""

from __future__ import annotations

import html
from typing import Any


def render_receipt_html(payload: dict[str, Any]) -> str:
    """Escape all values; load no external resources."""
    esc = html.escape
    receipt_id = esc(str(payload.get("receipt_id", "")))
    summary = esc(str(payload.get("summary", "Trust Receipt")))
    subscriber = esc(str(payload.get("subscriber_ref", "")))
    amount = payload.get("amount_lkr")
    amount_html = f"<strong>LKR {esc(str(amount))}</strong>" if amount is not None else ""
    action_type = esc(str(payload.get("action_type", "")))
    case_id = esc(str(payload.get("case_id", "")))
    issued = esc(str(payload.get("issued_at", "")))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Trust Receipt {receipt_id}</title>
<style>
  body {{ margin: 0; padding: 28px; font: 14px/1.6 system-ui, sans-serif;
         color: #1a1a1a; background: #fff; max-width: 420px; }}
  h1 {{ font-size: 18px; margin: 0 0 4px; }}
  .id {{ font-family: ui-monospace, Menlo, monospace; font-weight: 700; }}
  .stamp {{ display: inline-block; background: #dcfce7; color: #14532d;
            font-size: 10px; font-weight: 700; letter-spacing: .06em;
            padding: 5px 10px; border-radius: 5px; }}
  h2 {{ font-size: 10px; text-transform: uppercase; letter-spacing: .08em;
        color: #6b6b6b; margin: 20px 0 8px; }}
  .row {{ display: flex; justify-content: space-between; padding: 6px 0;
          border-bottom: 1px dashed #e4e4e7; }}
</style></head><body>
  <div style="display:flex;justify-content:space-between;align-items:flex-start;
              border-bottom:3px solid #c2410c;padding-bottom:12px;">
    <div>
      <h1>Trust Receipt</h1>
      <div class="id">{receipt_id}</div>
    </div>
    <span class="stamp">SIGNED</span>
  </div>
  <h2>What happened</h2>
  <p>{summary}</p>
  <h2>What we corrected</h2>
  <div class="row"><span>{action_type or "—"}</span>{amount_html}</div>
  <h2>Details</h2>
  <div class="row"><span>Subscriber</span><b>{subscriber}</b></div>
  <div class="row"><span>Case</span><b>{case_id or "—"}</b></div>
  <div class="row"><span>Issued</span><b>{issued}</b></div>
</body></html>"""
