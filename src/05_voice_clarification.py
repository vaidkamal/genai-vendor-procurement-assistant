"""
05_voice_clarification.py
-------------------------
Simulated, DISCLOSED voice conversation between the procurement AI voice
agent and a vendor whose quotation raised policy flags.

Why "disclosed": the agent identifies itself as an AI on the first line,
says the call is recorded and transcribed, and states that it cannot accept
an offer, place an order or commit funds. Every commercial change is
captured as a follow-up action for the human procurement officer.

Why "simulated": the vendor side is scripted (no real call is placed). In a
production system the agent's lines would be produced live by Claude from
the same policy flags, and the vendor would be a real person on the phone.

Voices: Indian English by default (custom espeak-ng voice in data/voices/,
installed into the espeak data folder at run time). --accent british uses
the stock en-gb / en-us voices instead.

Run:  python src/05_voice_clarification.py [--accent indian|british]
Out:  outputs/voice/call_transcript_megabyte.md
      outputs/voice/call_megabyte.mp3   (needs espeak-ng + ffmpeg; skipped otherwise)
      outputs/voice/call_summary.json   (structured outcome for the dashboard)
"""
import argparse
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "voice"
OUT.mkdir(parents=True, exist_ok=True)

res = json.loads((ROOT / "outputs" / "comparison_results.json").read_text())
VENDOR = "Megabyte Distribution LLC"
v = next(x for x in res["vendors"] if x["vendor_name"] == VENDOR)
flags = [c for c in v["policy_checks"] if c["status"] == "flag"]

# --------------------------------------------------------------- script
# (Agent, Vendor) turns. Agent lines follow the disclosure -> clarify -> confirm -> no-commitment pattern.
TURNS = [
    ("Agent", "Good morning. This is Bramwell and Company's procurement assistant. I am an AI voice agent calling on behalf of the procurement team about your quotation M B 7 7 0 1 2 for forty laptops. This call is recorded and transcribed for our procurement file. Is now a good time?"),
    ("Vendor", "Sure, go ahead. This is Rohan from MegaByte sales."),
    ("Agent", "Thank you, Rohan. Before we start, please note that I cannot accept an offer, place an order, or commit any payment. Only our procurement officer can do that. I am gathering clarifications so that they can make a decision. Is that clear?"),
    ("Vendor", "Understood."),
    ("Agent", "First point. Your quote asks for a fifty percent deposit with the order. Our procurement policy limits advance payments to thirty percent. Would MegaByte be able to offer net thirty terms, or a deposit of no more than thirty percent with the balance on delivery?"),
    ("Vendor", "We can do thirty percent up front and the balance on delivery for an order of this size. Net thirty is possible but only with a credit check, since you are a new customer for us."),
    ("Agent", "Thank you. I have noted two options: thirty percent deposit with balance on delivery, or net thirty subject to a credit check. Second point. The quote is valid for fourteen days, but our approval cycle needs at least twenty one days. Can you extend the validity to thirty days?"),
    ("Vendor", "Yes, thirty days is fine. I will send a revised quote today."),
    ("Agent", "Noted. Third point. The warranty is described as a three year depot service with a seven to ten day turnaround. Is an onsite, next business day option available, and what would it cost per unit?"),
    ("Vendor", "We can add onsite next business day for thirty five dollars per unit per year, so one hundred and five dollars per unit over three years."),
    ("Agent", "Thank you. To confirm, that would be an additional four thousand two hundred dollars for forty units. I have recorded that as an option; I am not accepting it. Last question. Your delivery is ten business days after the deposit is received. If the deposit is thirty percent, does that timeline stay the same?"),
    ("Vendor", "Yes, ten business days from the deposit, unchanged."),
    ("Agent", "That covers everything. Here is my summary. One, a thirty percent deposit or net thirty with credit check. Two, validity extended to thirty days. Three, an optional onsite warranty at one hundred and five dollars per unit. Four, delivery unchanged. Please confirm all of this in a revised written quotation to procurement at Bramwell, quoting reference P R 2026 0917. Our procurement officer will review it and contact you with a decision. Nothing on this call is a commitment to purchase. Is there anything you would like to add?"),
    ("Vendor", "No, that is all. I will send the revised quote this afternoon."),
    ("Agent", "Thank you, Rohan. Goodbye."),
]

SUMMARY = {
    "vendor": VENDOR,
    "quote_ref": v["quote_ref"],
    "call_date": date.today().isoformat(),
    "agent": "AI voice agent (disclosed at start of call)",
    "vendor_contact": "Rohan, MegaByte sales (fictional)",
    "flags_discussed": [c["rule"] for c in flags],
    "outcomes": [
        {"topic": "Payment terms", "vendor_position": "30% deposit + balance on delivery, or Net 30 subject to credit check", "policy_effect": "Either option satisfies P-03 (≤30% advance)"},
        {"topic": "Quote validity", "vendor_position": "Extended to 30 days", "policy_effect": "Satisfies P-06 once the revised quote arrives"},
        {"topic": "Warranty", "vendor_position": "Onsite NBD available at USD 105 per unit over 3 years (+USD 4,200 total)", "policy_effect": "Optional; would raise total to USD 59,100, still within budget"},
        {"topic": "Delivery", "vendor_position": "10 business days from deposit, unchanged", "policy_effect": "No change"},
    ],
    "commitments_made_by_agent": "None. The agent stated three times that it cannot accept, order or pay.",
    "next_action_for_human": "Await revised written quote, then re-run 01_parse and 02_compare; procurement officer decides in the dashboard.",
}


def write_transcript():
    L = [f"# Simulated voice clarification call — {VENDOR}",
         f"Date {SUMMARY['call_date']} · Quote {v['quote_ref']} · Ref {res['request_id']}\n",
         "> **Disclosure.** The caller is an AI voice agent and says so in its first sentence. The call is recorded and transcribed. "
         "The agent cannot accept offers, place orders or commit funds; all outcomes go to the procurement officer as follow-up actions.\n",
         "> **Simulation.** The vendor's lines are scripted for the capstone. No real call was placed.\n",
         "## Flags that triggered the call"]
    L += [f"- {c['rule']}: {c['detail']}" for c in flags]
    L.append("\n## Transcript\n")
    L += [f"**{who}:** {line}\n" for who, line in TURNS]
    L.append("## Outcome for the procurement officer\n")
    L.append("| Topic | Vendor position | Policy effect |\n|---|---|---|")
    L += [f"| {o['topic']} | {o['vendor_position']} | {o['policy_effect']} |" for o in SUMMARY["outcomes"]]
    L.append(f"\nCommitments made by the agent: {SUMMARY['commitments_made_by_agent']}")
    L.append(f"\nNext action: {SUMMARY['next_action_for_human']}")
    (OUT / "call_transcript_megabyte.md").write_text("\n".join(L))
    (OUT / "call_summary.json").write_text(json.dumps({**SUMMARY, "turns": [{"speaker": a, "text": b} for a, b in TURNS]}, indent=2))


def install_indian_voice():
    """Copy the custom voice definition into espeak-ng's data folder. Returns the voice name or None."""
    src = ROOT / "data" / "voices" / "en-in-x"
    out = subprocess.run(["espeak-ng", "--version"], capture_output=True, text=True).stdout
    data_dir = Path(out.strip().split("Data at: ")[-1]) if "Data at: " in out else None
    if not data_dir or not (data_dir / "voices").exists():
        return None
    dest = data_dir / "voices" / "mb" / "en-in-x"
    try:
        shutil.copy(src, dest)
        return "mb/en-in-x"
    except PermissionError:
        print("cannot write to espeak data folder - falling back to stock voices")
        return None


def render_audio(accent="indian"):
    if not (shutil.which("espeak-ng") and shutil.which("ffmpeg")):
        print("espeak-ng or ffmpeg not found - transcript written, audio skipped")
        return
    indian = install_indian_voice() if accent == "indian" else None
    if indian:
        agent_voice, vendor_voice = (indian, 150, 45), (indian + "+f3", 155, 62)
    else:
        agent_voice, vendor_voice = ("en-gb", 160, 45), ("en-us+f3", 170, 60)
    parts = []
    for i, (who, line) in enumerate(TURNS):
        wav = OUT / f"_turn{i:02d}.wav"
        voice, speed, pitch = agent_voice if who == "Agent" else vendor_voice
        subprocess.run(["espeak-ng", "-v", voice, "-s", str(speed), "-p", str(pitch), "-w", str(wav), line], check=True)
        parts.append(wav)
    listfile = OUT / "_list.txt"
    listfile.write_text("".join(f"file '{p.name}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listfile),
                    "-af", "apad=pad_dur=0.4", "-codec:a", "libmp3lame", "-q:a", "5", str(OUT / "call_megabyte.mp3")], check=True)
    for p in parts:
        p.unlink()
    listfile.unlink()
    print("wrote outputs/voice/call_megabyte.mp3")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--accent", choices=["indian", "british"], default="indian")
    args = ap.parse_args()
    write_transcript()
    render_audio(args.accent)
    print("wrote outputs/voice/call_transcript_megabyte.md and call_summary.json")
