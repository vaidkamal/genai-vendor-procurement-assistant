# Vendor Comparison and Procurement Assistant
Gen AI for Business — Capstone Project (Topic 4)

A working assistant that turns three inconsistent vendor quotations into a standardised comparison, checks them against procurement policy, proposes a recommendation, and lets a procurement officer review, change, or reject it. Generative AI explains and communicates; deterministic code calculates and decides nothing.

## Business scenario (fictional)
Bramwell & Co. Consulting needs 40 business laptops for new-hire onboarding (request PR-2026-0917, budget USD 60,000, needed in 21 days). Three vendors respond in three formats: a US line-item quote, a German offer letter in EUR with an optional warranty extension, and an all-in "bundle" quote with a 50% deposit. Comparing them by hand takes a procurement analyst an afternoon and is error-prone.

## What the solution does — the working journey
```
data/quotations/*.pdf ──▶ 01_parse ──▶ standardised_quotations.json/csv
                                              │
data/requirement_intake.json ─────────────────┼──▶ 02_compare ──▶ comparison_results.json + report.md
data/procurement_policy.md ───────────────────┘        │
                                                       ├──▶ 03_ai_assistant ──▶ recommendation summary,
                                                       │                        clarification e-mails,
                                                       │                        negotiation prep, policy Q&A
                                                       └──▶ 04_build_dashboard ──▶ app/dashboard.html
                                                                                    (officer reviews, re-weights,
                                                                                     records decision, exports audit log)
```

| Step | File | Generative AI or deterministic? | Why |
|---|---|---|---|
| Read quotes | `src/01_parse_quotations.py` | Deterministic rules by default; **optional Claude extraction** (`--mode llm`) for messy real-world PDFs | Extraction from unstructured text is where an LLM adds value; numbers are always re-validated and totals recomputed in code |
| Standardise | same file | Deterministic | FX conversion, warranty extension, shipping and per-unit cost must be reproducible |
| Score and rank | `src/02_compare_vendors.py` | Deterministic, formulas printed in the report | Auditable; the officer can reproduce every number by hand |
| Policy check | same file | Deterministic (pass / flag / fail) | Policy is a rule set, not a judgement call |
| Explain, draft, answer | `src/03_ai_assistant.py` + dashboard Q&A | **Generative AI (Claude)** | Plain-language summary, vendor e-mails, negotiation points, policy questions |
| Past performance | `data/vendor_performance.json` + `02_compare` | Deterministic | 24-month history (on-time, defects, invoicing, support) becomes a sixth criterion; new vendors are flagged for references (P-08) |
| Clarify by voice | `src/05_voice_clarification.py` | **Simulated, disclosed AI voice agent** | Agent identifies itself as AI, records the call, cannot commit; outcomes logged for the officer (P-09). Audio in `outputs/voice/` |
| Decide | `app/dashboard.html` | **Human** | Policy P-07: only a named officer approves; the tool never places orders |

## Decision criteria (chosen by the team, editable live in the dashboard)
| Criterion | Default weight | Score formula |
|---|---:|---|
| Total cost (USD, all-in) | 30% | cheapest total ÷ vendor total × 100 |
| Technical fit | 15% | 90 if all mandatory specs met, 100 if exceeded, ≤60 if a spec is missing |
| Delivery lead time | 15% | 100 inside the window, −5 per day late |
| Warranty and support | 15% | 70 for ≥3 years + 30 onsite / 15 depot / 10 carry-in |
| Commercial and compliance | 15% | payment terms 40 + advance 30 + validity 15 + ISO 27001 15 |
| Past performance (24 months) | 10% | on-time ×0.4 + (100 − defect%×10) ×0.2 + invoice accuracy ×0.2 + support ×0.2, −10 per open dispute; no history = neutral 60 + reference-check flag |

Why these criteria: cost is the largest single factor but capped at 30% so that a cheap quote with bad terms cannot win outright; technical fit is pass/fail in nature so it carries less weight; delivery matters because the laptops are for a dated onboarding; warranty type drives consultant downtime; commercial/compliance captures cash-flow and policy risk; past performance rewards vendors who have actually delivered for us before.

Result with default weights: **TechSource 97.3 · Alpine 85.1 · MegaByte 82.3**. Moving weight from cost to technical fit and delivery re-ranks MegaByte above Alpine (screenshot 05), showing that the officer's priorities, not the tool, settle close calls.

## Proof that the system cannot buy anything
- No code path calls an e-mail, ERP, banking or e-procurement API; `grep -r "smtplib\|requests.post" src/` returns nothing.
- The dashboard is a static HTML file with no backend; "Record decision" writes to an in-page audit log that the officer exports as JSON for Finance.
- Clarification e-mails are Markdown drafts; the voice agent is scripted to refuse commitment (see transcript) and every AI document carries a "reviewed by a human" footer.
- Policy P-07 and P-09 encode this; the red guardrail banner at the top of the console states it to the user.

## Human review point
The dashboard's decision panel requires a named officer, offers four outcomes (approve / award to a different vendor / request clarification / reject and re-tender), demands a written justification for anything other than accepting the recommendation, and stores every decision with a snapshot of the weights and scores in an exportable audit log. The system has no ability to send e-mails, raise purchase orders, or move money.

## Business metrics the solution could improve
1. **Analyst time per three-quote comparison** — target from ~4 hours to under 45 minutes (measure with a timesheet code on the next 10 purchases).
2. **Policy exceptions caught before PO** — share of purchases where a payment-term, warranty, validity or certification breach is flagged before approval rather than discovered by Finance or Audit afterwards (target 100%).
Secondary: savings from negotiated terms, and quote-to-approval cycle time.

## How to run
```bash
pip install -r requirements.txt
python src/run_pipeline.py                 # rule-based, fully offline
export ANTHROPIC_API_KEY=...               # optional
python src/run_pipeline.py --mode llm      # Claude extracts the quotes and writes the AI documents
python src/03_ai_assistant.py --ask "Can we accept a 50% deposit?"
python src/05_voice_clarification.py       # regenerates the simulated call (audio needs espeak-ng + ffmpeg)
```
Then open `app/dashboard.html` in a browser (no server needed). The in-dashboard Q&A calls the Claude API directly when opened inside claude.ai; for local use, route the call through a small backend that holds the key.

## Folder guide
- `data/` — requirement intake, procurement policy, three fictional quotation PDFs
- `data/vendor_performance.json` — fictional 24-month performance history used for the past-performance criterion
- `src/` — numbered pipeline scripts (00–05) and `run_pipeline.py`
- `outputs/` — standardised data, comparison results and report, AI-written summary / e-mails / negotiation prep, sample approval history, `screenshots/`, `voice/` (simulated call audio, transcript, structured outcome)
- `docs/Requirements_Coverage.md` — line-by-line mapping of the capstone brief to evidence in this folder; `docs/Demo_Script.md` — 8-minute demonstration walkthrough
- `app/` — the review console (`dashboard.html`) and its template
- `docs/` — 3-slide Project Overview and the submission form

## Limitations, risks and what real deployment would need
- **Parsing.** The rule-based parser is tuned to the three demo layouts; real quotes vary far more. Production would use the LLM extraction mode with a strict JSON schema, confidence flags, and a "show source text" link next to every extracted number so the analyst can verify it.
- **Scoring model.** The formulas are simple and linear. They are transparent by design but do not capture total cost of ownership (energy, repair downtime, residual value) or vendor performance history — an obvious extension (procurement-policy P-04 downtime is only partly reflected in warranty type points).
- **FX rates** are fixed constants; production would pull daily rates and record the rate used.
- **AI outputs** can be fluent and wrong. Every AI document carries a "reviewed by a human before use" footer; the recommendation summary is grounded only in `comparison_results.json`, and the policy Q&A is restricted to the policy text. Vendor e-mails are drafts the officer sends from their own mailbox.
- **Data protection.** Demo data is fictional. Real quotes contain commercial-in-confidence pricing; the API calls would need an enterprise agreement with no training on inputs, and access to the dashboard would need SSO and role-based permissions (analyst vs. officer vs. Finance).
- **Voice agent.** The call is simulated with a scripted vendor and offline TTS (a custom Indian-English espeak-ng voice in `data/voices/`; pronunciation is approximate). A live deployment needs telephony (e.g. Twilio), real-time speech models, consent capture at the start of every call, and a mandatory human listen-back of the transcript before any outcome is acted on.
- **Vendor performance data** is fictional and small; production would pull it from the ERP/AP system and refresh it on each run.
- **Audit trail** lives in the browser session and is exported as JSON; production needs a database with immutable logs and integration with the ERP / P2P system so the PO is raised from the approved record.
- **Bias / fairness.** Weights and formulas are explicit and editable, which is the main safeguard; the officer's justification for overriding the ranking is recorded and reviewable.
- **Before go-live:** pilot on 10 historic purchases and compare tool output against the decisions actually taken; sign-off from Procurement, Finance and the CISO; a 30-day period of parallel running.

## AI tools and applications used
Claude (Anthropic) via API for extraction, explanation, e-mail drafting, negotiation prep and policy Q&A; Claude Code / claude.ai used to build the solution; Python (pdfplumber, reportlab), HTML/JavaScript dashboard.
