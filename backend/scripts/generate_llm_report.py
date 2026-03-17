#!/usr/bin/env python3
"""Generate HTML report from real LLM predictions."""

import json
from datetime import datetime

with open('/tmp/llm_predictions.json') as f:
    preds = json.load(f)

# Group by matchday
matchdays = {}
for p in preds:
    md = p['matchday']
    if md not in matchdays:
        matchdays[md] = []
    matchdays[md].append(p)

total = len(preds)
hw = sum(1 for p in preds if p['prediction'] == 'HOME')
dr = sum(1 for p in preds if p['prediction'] == 'DRAW')
aw = sum(1 for p in preds if p['prediction'] == 'AWAY')
high = sum(1 for p in preds if p['consensus'] == 'high')
avg_conf = sum(p['confidence'] for p in preds) / total

def format_form(f):
    if not f or f == '?': return '<span class="form">-</span>'
    return '<span class="form">' + ''.join(f'<span class="{c}">{c}</span>' for c in f) + '</span>'

def escape(s):
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MiroFish - Premier League AI Predictions 2025/26</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',-apple-system,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.5}}
.header{{background:linear-gradient(135deg,#0d1117 0%,#161b22 40%,#1a1a2e 100%);padding:50px 20px 40px;text-align:center;border-bottom:3px solid #e94560;position:relative;overflow:hidden}}
.header::before{{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 30% 50%,rgba(233,69,96,0.08) 0%,transparent 60%);pointer-events:none}}
.header h1{{font-size:2.4em;color:#fff;margin-bottom:6px;letter-spacing:-0.5px}}
.header .accent{{color:#e94560;font-weight:800}}
.header .sub{{color:#8b949e;font-size:0.95em;margin-top:4px}}
.header .badge{{display:inline-block;background:#e9456020;color:#e94560;border:1px solid #e9456040;padding:3px 12px;border-radius:20px;font-size:0.8em;margin-top:12px;font-weight:600}}
.stats{{display:flex;justify-content:center;gap:0;background:#0d1117;border-bottom:1px solid #21262d}}
.stats .s{{flex:1;max-width:160px;text-align:center;padding:20px 10px;border-right:1px solid #21262d}}
.stats .s:last-child{{border-right:none}}
.stats .n{{font-size:2.2em;font-weight:800;line-height:1}}
.stats .l{{font-size:0.75em;color:#8b949e;margin-top:6px;text-transform:uppercase;letter-spacing:1px}}
.s.home .n{{color:#4ecdc4}}.s.draw .n{{color:#ffe66d}}.s.away .n{{color:#e94560}}.s.total .n{{color:#fff}}.s.conf .n{{color:#a78bfa}}
.container{{max-width:1150px;margin:0 auto;padding:20px}}
.method{{background:#0d1117;border:1px solid #21262d;border-radius:10px;padding:24px;margin:24px 0}}
.method h3{{color:#e94560;margin-bottom:12px;font-size:1.1em}}
.method p{{color:#8b949e;font-size:0.9em;margin-bottom:6px}}
.method strong{{color:#c9d1d9}}
.md-header{{font-size:1.3em;font-weight:700;color:#fff;margin:32px 0 16px;padding:12px 18px;background:linear-gradient(90deg,#0d1117,#161b22);border-left:4px solid #e94560;border-radius:6px}}
.card{{background:#0d1117;border:1px solid #21262d;border-radius:10px;margin-bottom:14px;overflow:hidden;transition:all 0.2s}}
.card:hover{{border-color:#30363d;transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.3)}}
.match{{display:flex;align-items:center;padding:16px 20px;gap:12px}}
.date-col{{width:85px;flex-shrink:0;font-size:0.78em;color:#8b949e;line-height:1.4}}
.team{{display:flex;align-items:center;gap:8px;width:190px}}
.team.home{{justify-content:flex-end;text-align:right}}.team.away{{text-align:left}}
.team img{{width:26px;height:26px;object-fit:contain}}
.team .nm{{font-weight:600;font-size:0.92em;color:#c9d1d9}}
.team .meta{{font-size:0.7em;color:#8b949e}}
.score-box{{width:52px;text-align:center;flex-shrink:0}}
.score-box .sc{{font-size:1.2em;font-weight:800;color:#fff;background:#21262d;padding:4px 8px;border-radius:6px;display:inline-block}}
.pred-badge{{padding:4px 14px;border-radius:20px;font-weight:700;font-size:0.78em;width:68px;text-align:center;flex-shrink:0}}
.pred-badge.HOME{{background:#4ecdc415;color:#4ecdc4;border:1px solid #4ecdc430}}
.pred-badge.DRAW{{background:#ffe66d15;color:#ffe66d;border:1px solid #ffe66d30}}
.pred-badge.AWAY{{background:#e9456015;color:#e94560;border:1px solid #e9456030}}
.bar-wrap{{flex:1;min-width:180px}}
.bar{{display:flex;height:22px;border-radius:11px;overflow:hidden;background:#161b22}}
.bar .h{{background:linear-gradient(90deg,#4ecdc4,#2bbbad)}}.bar .d{{background:linear-gradient(90deg,#ffe66d,#f0c000)}}.bar .a{{background:linear-gradient(90deg,#e94560,#d63447)}}
.bar-labels{{display:flex;justify-content:space-between;font-size:0.68em;color:#8b949e;margin-top:3px;padding:0 4px}}
.cons{{font-size:0.68em;padding:3px 8px;border-radius:10px;flex-shrink:0;font-weight:600}}
.cons.high{{background:#4ecdc415;color:#4ecdc4}}.cons.medium{{background:#ffe66d15;color:#ffe66d}}.cons.low{{background:#e9456015;color:#e94560}}
.reasons{{background:#161b22;padding:12px 20px;border-top:1px solid #21262d;display:none}}
.card:hover .reasons{{display:block}}
.reasons .r{{font-size:0.8em;color:#8b949e;padding:3px 0}}
.reasons .r .role{{color:#a78bfa;font-weight:600;width:70px;display:inline-block}}
.reasons .r .res{{font-weight:600;width:48px;display:inline-block}}
.reasons .r .res.HOME{{color:#4ecdc4}}.reasons .r .res.DRAW{{color:#ffe66d}}.reasons .r .res.AWAY{{color:#e94560}}
.form span{{font-weight:700;font-size:0.85em}}.form .W{{color:#4ecdc4}}.form .D{{color:#ffe66d}}.form .L{{color:#e94560}}
.footer{{text-align:center;padding:40px 20px;color:#484f58;font-size:0.82em;border-top:1px solid #21262d;margin-top:40px}}
@media(max-width:800px){{.match{{flex-wrap:wrap;gap:8px}}.team{{width:130px}}.bar-wrap{{min-width:100%;order:10}}.date-col{{width:100%}}}}
</style>
</head>
<body>
<div class="header">
<h1>MiroFish <span class="accent">Football Oracle</span></h1>
<div class="sub">Premier League 2025/26 Season Predictions</div>
<div class="sub">Powered by Real AI Agent Analysis (Claude Haiku 4.5)</div>
<div class="badge">5 AI Agents x 79 Matches = 395 LLM Calls</div>
</div>

<div class="stats">
<div class="s home"><div class="n">{hw}</div><div class="l">Home Win</div></div>
<div class="s draw"><div class="n">{dr}</div><div class="l">Draw</div></div>
<div class="s away"><div class="n">{aw}</div><div class="l">Away Win</div></div>
<div class="s total"><div class="n">{total}</div><div class="l">Matches</div></div>
<div class="s conf"><div class="n">{avg_conf:.0%}</div><div class="l">Avg Conf</div></div>
</div>

<div class="container">
<div class="method">
<h3>Dual-Layer Prediction Architecture</h3>
<p><strong>Layer 1 - ML Features (Dynamic Weight):</strong> League position, points, form, goal difference, attack/defense ratios, home advantage coefficient.</p>
<p><strong>Layer 2 - AI Agent Swarm (Dynamic Weight):</strong> 5 specialized AI agents (Fan / Analyst / Media / Insider / Neutral) each independently analyze match context via Claude Haiku 4.5, then vote. Results scaled to 50 agents (5+15+8+12+10).</p>
<p><strong>Dynamic Fusion:</strong> When agent consensus is HIGH, agent weight increases to 70%. When LOW, ML weight increases to 55%. Default split: ML 40% / Agent 60%.</p>
<p style="margin-top:8px;color:#e94560;font-size:0.85em;">Hover over any match card to see detailed AI agent reasoning.</p>
</div>
"""

for md in sorted(matchdays.keys()):
    matches = matchdays[md]
    html += f'<div class="md-header">Matchday {md} ({len(matches)} matches)</div>\n'

    for m in sorted(matches, key=lambda x: x['date']):
        hp, dp, ap = m['home_prob'], m['draw_prob'], m['away_prob']
        date_parts = m['date'].replace('T', ' ').split(' ')
        date_str = date_parts[0] if date_parts else ''
        time_str = date_parts[1][:5] if len(date_parts) > 1 else ''

        reasons_html = ''
        for ar in m.get('agent_reasonings', []):
            reasoning = escape(ar.get('reasoning', '')[:120])
            res = ar.get('result', 'HOME')
            reasons_html += f'<div class="r"><span class="role">{ar["role"]}</span> <span class="res {res}">{res}</span> {reasoning}</div>\n'

        html += f"""<div class="card">
<div class="match">
  <div class="date-col">{date_str}<br>{time_str} UTC</div>
  <div class="team home">
    <div><div class="nm">{escape(m['home_team'])}</div><div class="meta">#{m['home_pos']} {m['home_pts']}pts {format_form(m.get('home_form',''))}</div></div>
    <img src="{m['home_crest']}" alt="" onerror="this.style.display='none'">
  </div>
  <div class="score-box"><span class="sc">{m['predicted_score']}</span></div>
  <div class="team away">
    <img src="{m['away_crest']}" alt="" onerror="this.style.display='none'">
    <div><div class="nm">{escape(m['away_team'])}</div><div class="meta">#{m['away_pos']} {m['away_pts']}pts {format_form(m.get('away_form',''))}</div></div>
  </div>
  <div class="pred-badge {m['prediction']}">{m['prediction']}</div>
  <div class="bar-wrap">
    <div class="bar"><div class="h" style="width:{hp*100:.1f}%"></div><div class="d" style="width:{dp*100:.1f}%"></div><div class="a" style="width:{ap*100:.1f}%"></div></div>
    <div class="bar-labels"><span>{hp:.0%}</span><span>{dp:.0%}</span><span>{ap:.0%}</span></div>
  </div>
  <div class="cons {m['consensus']}">{m['consensus']}</div>
</div>
<div class="reasons">{reasons_html}</div>
</div>
"""

html += f"""</div>
<div class="footer">
<p>MiroFish Football Oracle | Dual-Layer: ML + AI Agent Swarm Intelligence</p>
<p>5 AI Agents (Fan/Analyst/Media/Insider/Neutral) via Claude Haiku 4.5 | Data: football-data.org</p>
<p style="margin-top:8px">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC | {total} matches | {high}/{total} high consensus</p>
<p style="margin-top:6px;color:#30363d">Predictions are for entertainment and research purposes only.</p>
</div>
</body></html>"""

out = '/home/node/a0/workspace/0bc50884-3715-4523-bf95-eb96178d2dcb/workspace/outputs/pl_predictions.html'
with open(out, 'w') as f:
    f.write(html)

print(f"Report: {out}")
print(f"{total} matches | {hw}H {dr}D {aw}A | Avg conf: {avg_conf:.0%} | High consensus: {high}/{total}")
