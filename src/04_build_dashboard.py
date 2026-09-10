"""
04_build_dashboard.py
---------------------
Injects the pipeline outputs into the dashboard template so the review
console is a single self-contained HTML file (works offline, no server).

Run:  python src/04_build_dashboard.py
Out:  app/dashboard.html
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tpl = (ROOT / "app" / "dashboard_template.html").read_text()
results = json.loads((ROOT / "outputs" / "comparison_results.json").read_text())
policy = (ROOT / "data" / "procurement_policy.md").read_text()
summary = (ROOT / "outputs" / "ai_recommendation_summary.md").read_text()
call_file = ROOT / "outputs" / "voice" / "call_summary.json"
call = json.loads(call_file.read_text()) if call_file.exists() else None

html = (tpl.replace("__REQUEST_ID__", results["request_id"])
           .replace("__DATA__", json.dumps(results))
           .replace("__POLICY__", json.dumps(policy))
           .replace("__AI_SUMMARY__", json.dumps(summary))
           .replace("__CALL__", json.dumps(call)))
(ROOT / "app" / "dashboard.html").write_text(html)
print("wrote app/dashboard.html")
