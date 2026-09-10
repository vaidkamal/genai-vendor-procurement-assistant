"""Run the whole pipeline in order. Usage: python src/run_pipeline.py [--mode rules|llm]"""
import subprocess, sys
from pathlib import Path
here = Path(__file__).parent
mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "rules"
steps = [
    ["00_generate_sample_quotations.py"],
    ["01_parse_quotations.py", "--mode", mode],
    ["02_compare_vendors.py"],
    ["03_ai_assistant.py"],
    ["05_voice_clarification.py"],
    ["04_build_dashboard.py"],
]
for s in steps:
    print(f"\n=== {s[0]} ===")
    subprocess.run([sys.executable, str(here / s[0]), *s[1:]], check=True)
print("\nDone. Open app/dashboard.html in a browser to review and record the decision.")
