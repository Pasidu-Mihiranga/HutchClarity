# DEMO.md — How to record the Hutch Clarity demo video

Target length: **5–7 minutes**. No production credentials; synthetic data only.
You do not need to commit the video binary to git — host it where the
hackathon submission asks and link it from the submission pack.

## Before you hit record

1. Clean desktop; hide bookmarks bar; set display to 1280×720 or 1920×1080.
2. Terminal ready with the repo root as cwd.
3. Reset demo state:

```bash
make up-lite
make dev          # legacy UI+API on :8000  (or make dev-new for new API)
# optional: curl -X POST localhost:8000/v1/demo/reset
```

4. Browser tabs pre-opened (do not show passwords):
   - http://localhost:8000/          (customer Why?)
   - http://localhost:8000/desk      (Clarity Desk)
   - http://localhost:8000/docs      (optional, 5 seconds)

## Click script (spoken beats in parentheses)

| Time | Click / action | Say |
|---|---|---|
| 0:00 | Title slide or README headline | "Hutch Clarity: explain every rupee, fix by rule, prove it." |
| 0:20 | Open `/` Why? | "Customer Dilani sees a surprise VAS charge." |
| 0:40 | Enter MSISDN / ask Why? | "She asks why — we never invent evidence." |
| 1:10 | Show cause + evidence list | "Detector vas_silent_renewal: charge without fresh OTP." |
| 1:40 | Show ruled-out causes | "Ruled out list keeps trust high." |
| 2:00 | Tap Confirm / propose | "Rules decide the amount; LLM only explains." |
| 2:30 | Show Trust Receipt + QR | "Signed receipt, QR opens the public verifier." |
| 3:00 | Open `/v/...` verify page | "Anyone can check the signature." |
| 3:30 | Open Desk `/desk` | "Staff queue sorted by money at stake." |
| 4:10 | Open one case cockpit | "Same case, same evidence, supervisor path for L3." |
| 4:50 | Optional: MCP mention | "Agents only propose via MCP; no execute tool." |
| 5:20 | Show architecture.mmd or ADR slide | "Modular monolith, lite/full profiles, ports." |
| 5:50 | Close on Known limitations | "All HUTCH systems mocked; synthetic data only." |

## After recording

- Export MP4 (H.264), under submission size limits.
- Note commit SHA / tag (`0.2.0-baseline`) in the submission form.
- Keep `docs/submission/DEMO_SCRIPT.md` and this file in sync if the UI changes.

## Fail-safe if UI is down

Walk the same story with `scripts/demo.py` in the terminal and a short cut to
OpenAPI `/docs`. Prefer the UI path for judges.
