"""Build docs/testing/report.html from results.json + screenshots (run after e2e)."""
import json, html
from pathlib import Path
d = Path(__file__).parent
r = json.loads((d / "results.json").read_text())
passed = sum(1 for x in r["results"] if x["ok"])
rows = []
for i, x in enumerate(r["results"], 1):
    shots = "".join(f'<a href="{s}" target="_blank"><img src="{s}" loading="lazy"></a>' for s in [x.get("shot"), x.get("shot2")] if s)
    rows.append(f'''<section class="step {'ok' if x['ok'] else 'fail'}">
  <div class="meta"><span class="badge">{'PASS' if x['ok'] else 'FAIL'}</span><span class="n">{i:02d}</span><h2>{html.escape(x['name'])}</h2><span class="ms">{x['ms']} ms</span></div>
  <p>{html.escape(x.get('detail') or x.get('error') or '')}</p>
  <div class="shots">{shots}</div>
</section>''')
page = f'''<!doctype html><html><head><meta charset="utf-8"><title>Valora — end-to-end test report</title>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>
body{{margin:0;background:#f7f6f2;color:#141413;font-family:Geist,system-ui,sans-serif}} .wrap{{max-width:1100px;margin:0 auto;padding:40px 24px}}
h1{{font-family:"Instrument Serif",serif;font-weight:400;font-size:42px;margin:0;letter-spacing:-.01em}} h1 em{{color:#b85c3c}} .sub{{color:#4a4945;margin-top:8px}}
.summary{{display:flex;gap:18px;margin:26px 0 34px}} .card{{background:#fffefb;border:1px solid rgba(20,20,19,.1);border-radius:14px;padding:14px 18px}} .card b{{display:block;font-size:26px}} .card span{{font-size:12px;color:#807e77}}
.step{{background:#fffefb;border:1px solid rgba(20,20,19,.1);border-radius:16px;padding:18px 20px;margin-bottom:18px}} .step.fail{{border-color:#d03b3b}}
.meta{{display:flex;align-items:center;gap:12px}} .meta h2{{font-size:16px;margin:0;flex:1}} .n{{font-family:ui-monospace,monospace;font-size:11px;color:#807e77}} .ms{{font-family:ui-monospace,monospace;font-size:11px;color:#807e77}}
.badge{{font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;background:#e3eee6;color:#2f6b45}} .fail .badge{{background:#fde7e7;color:#b02a2a}}
p{{font-size:13.5px;color:#4a4945;margin:10px 0 12px}} .shots{{display:flex;gap:12px;flex-wrap:wrap}} .shots img{{max-width:100%;width:520px;border:1px solid rgba(20,20,19,.12);border-radius:10px;box-shadow:0 10px 30px -12px rgba(20,20,19,.25)}}
</style></head><body><div class="wrap">
<h1>Valora — <em>end-to-end</em> test report</h1>
<div class="sub">Driven through the real UI (Chrome DevTools Protocol) against the live FastAPI backend · {html.escape(r['ranAt'])} · LLM disabled for this session (rules engine), no credits spent</div>
<div class="summary"><div class="card"><b>{passed}/{len(r['results'])}</b><span>steps passed</span></div><div class="card"><b>{sum(x['ms'] for x in r['results'])/1000:.0f}s</b><span>total wall time</span></div><div class="card"><b>{sum(1 for x in r['results'] if x.get('shot'))}</b><span>screenshots</span></div></div>
{''.join(rows)}
</div></body></html>'''
(d / "report.html").write_text(page)
print("report:", d / "report.html", f"{passed}/{len(r['results'])}")
