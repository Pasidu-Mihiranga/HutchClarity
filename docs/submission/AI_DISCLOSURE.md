# AI / LLM Usage Declaration — Hutch Clarity

Completes the disclosure required by the HUTCH Hackathon Final Submission
Guidelines §6.1, §6.2 and §9.

Reproduce every number below with:

```bash
.venv/bin/python scripts/measure_tokens.py
curl -s localhost:8000/v1/ai/usage | jq
```

---

## 1. The headline

**This prototype runs on zero language-model tokens, and that is the design, not a gap.**

The deck's own guardrail is that Clarity "works without the LLM (templates)"
(slide 7). The prototype ships that path running for real: explanations come
from CX-approved templates in Sinhala, Tamil and English. The masking, output
verification, routing and fallback machinery that *would* wrap a model is all
built and tested — a model simply is not configured.

Point `CLARITY_MODEL_BASE_URL` at any OpenAI-compatible endpoint (vLLM,
llama.cpp, Ollama, or a hosted gateway) and the gateway routes through it. None
of the guardrails change.

## 2. Disclosure table (Guidelines §6.1)

| Item | Response |
|---|---|
| AI/LLM provider | **None configured.** Provider-agnostic by design: `OpenAICompatibleProvider` speaks the standard chat-completions shape, so a model self-hosted inside HUTCH and a hosted one use the same code path. |
| Model name & version | n/a in this prototype. Production intent: self-hosted open-weight model as the primary tier, hosted model as fallback (plan §12.2). |
| Purpose of AI usage | Multilingual intake extraction, explanation drafting, staff summaries, cited retrieval, complaint clustering labels. **Never** cause detection, eligibility, amounts or actions. |
| LLM calls per journey | **1 measured** (the explanation), and that call is served by the template tier. See §3. |
| Avg input tokens / request | **0 measured.** With a model configured the design budget is ≈600–1,500 (small tier). |
| Avg output tokens / request | **0 measured.** Design budget ≈80–550; Sinhala and Tamil tokenize to roughly 2.5× English. |
| Avg total tokens / request | **0 measured** |
| RAG / external knowledge | Retrieval is designed (plan §12.5) but **not implemented** in this prototype. Explanations are grounded in the decision record, not retrieved documents. |
| Prompting approach | System prompt + `FACTS` (the deterministic decision record) + `CONTEXT` + masked `USER` text, each explicitly delimited. The user's text is labelled untrusted and treated as a hint, never as instructions. |
| AI-generated vs rule-based | **Rules:** timeline, cause detection, confidence, decision, amounts, actions, receipts, reconciliation. **AI:** language only. |
| Fallback mechanism | Template tier on verifier failure, provider error or timeout. Demonstrated by `test_a_provider_outage_falls_back_to_a_template`. |
| Known limitations | Sinhala/Tamil template wording is **not native-speaker reviewed**. PII name detection in Sinhala/Tamil script is weak. No retrieval, so policy questions outside the rule set go to a human. |

## 3. Measured usage (Guidelines §6.2)

Output of `scripts/measure_tokens.py`:

| Journey | Language | Calls | Input | Output | Total | Tier |
|---|---|---|---|---|---|---|
| VAS charged with no consent | si | 1 | 0 | 0 | 0 | template |
| Reload taken twice | en | 1 | 0 | 0 | 0 | template |
| 'Unlimited' hit a fair-use cap | ta | 1 | 0 | 0 | 0 | template |
| Large reload not credited | en | 1 | 0 | 0 | 0 | template |
| **Total** | | **4** | **0** | **0** | **0** | |

LLM-free share: **100%**. Fallbacks: 0.

### Scalability projection

Because measured usage is zero, a projection has to state its basis. Two scenarios:

| Scenario | Basis | Tokens/day at 10,000 interactions |
|---|---|---|
| **As built** | Every explanation from templates | **0** |
| With a model on the small tier | ≈2,100 tokens per interaction (plan §37.2, an **ASSUMPTION**), minus the ~50% the deck's tier-1 and tier-2 routing absorbs | ≈10–21M |

The second row is an **assumption carried over from the plan**, not a
measurement. It must be re-measured once a model is configured.

## 4. Non-LLM intelligence

Two components use algorithms rather than a language model, and both are
disclosed under Guidelines §6.3:

| Component | Method | Output | Status |
|---|---|---|---|
| **Complaint Autopsy** | Canonical-form mapping + character-trigram TF-IDF with cosine similarity | Clusters, each a **hypothesis** until a CX engineer confirms it | Implemented. Plan §3.3 uses multilingual embeddings + UMAP + HDBSCAN in production. |
| **Foresight** | Statistical baseline over aggregated segments | Complaint themes per segment as **relative bands**, never counts | Implemented. **Not backtested**, so explicitly not usable for a launch decision (plan §3.4 gate). |

Foresight reads **aggregates only** — no individual customer data (deck S8),
asserted by `test_a_report_states_that_it_used_no_individual_data`.

## 5. Guardrails, and how to check them

| Guardrail | Test that proves it |
|---|---|
| A model cannot state an amount the case does not have | `test_a_model_that_invents_an_amount_never_reaches_the_customer` |
| A model cannot promise an action the decision did not allow | `test_a_promise_beyond_the_decision_is_blocked` |
| Raw personal data never reaches a model | `test_customer_text_is_masked_before_it_reaches_a_provider` |
| OTPs and card numbers are refused, not masked | `test_credentials_are_refused_not_masked` |
| A refused message leaves nothing behind | `test_a_refused_message_stores_nothing` |
| A model cannot execute anything through MCP | `test_no_tool_can_execute_anything` |
| A model cannot supply an amount through MCP | `test_a_model_cannot_supply_an_amount` |
| Provider outage still answers the customer | `test_a_provider_outage_falls_back_to_a_template` |

```bash
.venv/bin/pytest tests/unit/test_ai.py tests/unit/test_mcp.py -v
```

## 6. AI tools used to build this

| Item | Response |
|---|---|
| AI coding assistants | **[Team to complete]** — e.g. Claude Code, Copilot, Cursor |
| AI-generated code used? | **[Team to complete: Yes/No, and which parts]** |
| External AI APIs called at runtime | **No.** The prototype makes no outbound model calls. |

> The team remains responsible for the correctness, security and originality of
> everything submitted, however it was produced.
