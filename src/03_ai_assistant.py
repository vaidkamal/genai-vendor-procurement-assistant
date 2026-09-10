"""
03_ai_assistant.py
------------------
The generative-AI layer. Claude never computes scores or makes the decision;
it reads the deterministic results and does what LLMs are good at:

  1. Explain the recommendation to a busy approver in plain language
  2. Draft clarification e-mails to vendors whose quotes raised policy flags
  3. Prepare negotiation points for the recommended vendor
  4. Answer natural-language questions about the procurement policy (--ask)

Requires ANTHROPIC_API_KEY. Without a key the script writes a clearly-labelled
template version so the pipeline still runs end-to-end.

Run:  python src/03_ai_assistant.py
      python src/03_ai_assistant.py --ask "Can we pay a 50% deposit?"
Out:  outputs/ai_recommendation_summary.md
      outputs/clarification_emails.md
      outputs/negotiation_prep.md
"""
import argparse
import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
MODEL = "claude-sonnet-4-5"

SYSTEM = """You are a procurement analyst assistant at Bramwell & Co. Consulting.
Ground every statement in the JSON data you are given - never invent prices, dates or certifications.
Be concise and businesslike. Always make clear that the final decision belongs to the procurement officer,
and that you cannot place orders or commit funds."""


def claude(prompt: str, max_tokens: int = 1500) -> str:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(model=MODEL, max_tokens=max_tokens, system=SYSTEM,
                                 messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text


def load():
    res = json.loads((OUT / "comparison_results.json").read_text())
    policy = (ROOT / "data" / "procurement_policy.md").read_text()
    return res, policy


# --------------------------------------------------------------- prompts
def prompt_summary(res):
    return f"""Write a recommendation summary (max 250 words, markdown) for the procurement officer who must approve
this purchase. Structure: one-paragraph recommendation; 3-5 bullet reasons with numbers; a short
"Why not the others" section (one line per other vendor); a closing line reminding that approval is theirs.

COMPARISON DATA:
{json.dumps(res, indent=1)}"""


def prompt_emails(res):
    flagged = [v for v in res["vendors"] if v["policy_status"] == "flag"]
    return f"""For each vendor below, draft a short, courteous clarification e-mail (subject + body, under 150 words each)
from the Bramwell & Co. procurement team. Ask specifically about the flagged policy points, quote our reference
{res['request_id']}, and ask for a written reply within 5 business days. Do not commit to buying anything.

VENDORS AND FLAGS:
{json.dumps([{'vendor': v['vendor_name'], 'quote_ref': v['quote_ref'],
              'flags': [c for c in v['policy_checks'] if c['status'] == 'flag']} for v in flagged], indent=1)}"""


def prompt_negotiation(res):
    rec = res["recommendation"]
    return f"""Prepare 5 negotiation talking points for a call with the recommended vendor {rec['vendor_name']}.
Use leverage from the other quotes (e.g. longer payment terms, extras, larger storage) without revealing
competitor prices. Include one line on what we should NOT concede. Markdown bullets, under 200 words.

COMPARISON DATA:
{json.dumps(res['vendors'], indent=1)}"""


def prompt_ask(policy, res, question):
    return f"""Answer the procurement officer's question using ONLY the policy and the current comparison.
Cite the policy rule id (e.g. P-03) you rely on. If the policy does not cover it, say so.

POLICY:
{policy}

CURRENT COMPARISON (summary):
{json.dumps({'recommendation': res['recommendation'], 'vendors': [{'name': v['vendor_name'], 'policy_status': v['policy_status'], 'flags': [c['detail'] for c in v['policy_checks'] if c['status'] != 'pass']} for v in res['vendors']]}, indent=1)}

QUESTION: {question}"""


# --------------------------------------------------------------- offline
def offline_summary(res):
    r = res["recommendation"]
    lines = ["_Template mode (no API key) - run with ANTHROPIC_API_KEY set for the Claude-written version._\n",
             f"**Recommended vendor: {r['vendor_name']}** (score {r['weighted_score']}, "
             f"{r['margin_over_runner_up']} points ahead of {r['runner_up']}).\n"]
    lines += [f"- {x}" for x in r["key_reasons"]]
    lines.append("\nOther vendors:")
    for v in res["vendors"]:
        if v["vendor_name"] != r["vendor_name"]:
            flags = "; ".join(c["detail"] for c in v["policy_checks"] if c["status"] != "pass") or "no policy issues"
            lines.append(f"- {v['vendor_name']}: score {v['weighted_score']}, USD {v['total_cost_usd']:,.0f}. {flags}")
    lines.append("\nThe final decision rests with the procurement officer. This tool does not place orders.")
    return "\n".join(lines)


def offline_emails(res):
    out = ["_Template mode (no API key)._\n"]
    for v in res["vendors"]:
        flags = [c for c in v["policy_checks"] if c["status"] == "flag"]
        if not flags:
            continue
        out.append(f"### To: {v['vendor_name']} — Subject: Clarification on quotation {v['quote_ref']} ({res['request_id']})\n")
        out.append("Dear Sales Team,\n\nThank you for your quotation. Before we can progress our evaluation we need clarification on the following points:\n")
        out += [f"- {c['detail']}" for c in flags]
        out.append("\nPlease reply in writing within 5 business days. This request does not constitute an order.\n\nKind regards,\nProcurement Team, Bramwell & Co. Consulting\n")
    return "\n".join(out)


def offline_negotiation(res):
    return "_Template mode (no API key)._\n\n- Ask for Net 45 payment terms (another bidder offered them).\n- Ask for free asset tagging.\n- Ask whether a 1 TB SSD option is available at the same price.\n- Confirm the 2% early-payment discount in writing.\n- Do not concede onsite warranty or the 14-day lead time."


# --------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask", help="Ask a policy question instead of generating documents")
    args = ap.parse_args()
    res, policy = load()
    online = bool(os.getenv("ANTHROPIC_API_KEY"))
    stamp = f"\n\n---\n_Generated {date.today().isoformat()} by {'Claude (' + MODEL + ')' if online else 'template mode'} via 03_ai_assistant.py. AI output - reviewed and approved by a human before use._\n"

    if args.ask:
        print(claude(prompt_ask(policy, res, args.ask), 600) if online else
              "Set ANTHROPIC_API_KEY to use the policy Q&A assistant.")
        return

    if not online and (OUT / "ai_recommendation_summary.md").exists() and \
            "by Claude" in (OUT / "ai_recommendation_summary.md").read_text():
        print("offline mode: keeping the existing Claude-written documents in outputs/ (set ANTHROPIC_API_KEY to regenerate)")
        return

    summary = claude(prompt_summary(res)) if online else offline_summary(res)
    emails = claude(prompt_emails(res)) if online else offline_emails(res)
    nego = claude(prompt_negotiation(res), 800) if online else offline_negotiation(res)

    (OUT / "ai_recommendation_summary.md").write_text("# Recommendation summary for approver\n\n" + summary + stamp)
    (OUT / "clarification_emails.md").write_text("# Clarification e-mails to flagged vendors\n\n" + emails + stamp)
    (OUT / "negotiation_prep.md").write_text("# Negotiation preparation\n\n" + nego + stamp)
    print(f"mode: {'Claude API' if online else 'offline template'} - wrote 3 files to outputs/")


if __name__ == "__main__":
    main()
