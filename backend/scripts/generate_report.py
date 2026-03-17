#!/usr/bin/env python3
"""Generate HTML prediction report."""

import json
from datetime import datetime

with open('/tmp/predictions.json') as f:
    preds = json.load(f)

# Post-process: fix draw predictions (if draw_prob within 5% of leader, consider draw)
for p in preds:
    hp, dp, ap = p['home_prob'], p['draw_prob'], p['away_prob']
    leader = max(hp, dp, ap)
    if dp >= leader - 0.05 and abs(hp - ap) < 0.08:
        p['prediction'] = 'DRAW'
    elif hp >= ap and hp >= dp:
        p['prediction'] = 'HOME'
    elif ap > hp and ap >= dp:
        p['prediction'] = 'AWAY'

# Group by matchday
matchdays = {}
for p in preds:
    md = p['matchday']
    if md not in matchdays:
        matchdays[md] = []
    matchdays[md].append(p)

# Stats
total = len(preds)
home_wins = sum(1 for p in preds if p['prediction'] == 'HOME')
draws = sum(1 for p in preds if p['prediction'] == 'DRAW')
away_wins = sum(1 for p in preds if p['prediction'] == 'AWAY')

html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MiroFish - Premier League Predictions 2025/26</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Segoe UI', -apple-system, sans-serif; background:#0a0a0a; color:#e0e0e0; }}
.header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); padding:40px 20px; text-align:center; border-bottom: 3px solid #e94560; }}
.header h1 {{ font-size:2.2em; color:#fff; margin-bottom:8px; }}
.header .sub {{ color:#a0a0a0; font-size:1em; }}
.header .accent {{ color:#e94560; }}
.stats-bar {{ display:flex; justify-content:center; gap:40px; padding:20px; background:#111; }}
.stat {{ text-align:center; }}
.stat .num {{ font-size:2em; font-weight:700; }}
.stat .label {{ font-size:0.8em; color:#888; margin-top:4px; }}
.stat.home .num {{ color:#4ecdc4; }}
.stat.draw .num {{ color:#ffe66d; }}
.stat.away .num {{ color:#e94560; }}
.container {{ max-width:1100px; margin:0 auto; padding:20px; }}
.matchday-header {{ font-size:1.4em; font-weight:700; color:#fff; margin:30px 0 15px; padding:10px 15px; background:#1a1a2e; border-left:4px solid #e94560; border-radius:4px; }}
.match-card {{ background:#151515; border:1px solid #222; border-radius:8px; margin-bottom:12px; overflow:hidden; transition: transform 0.2s; }}
.match-card:hover {{ transform:translateY(-2px); border-color:#333; }}
.match-row {{ display:flex; align-items:center; padding:15px 20px; gap:10px; }}
.match-date {{ color:#888; font-size:0.8em; width:130px; flex-shrink:0; }}
.team {{ display:flex; align-items:center; gap:8px; width:200px; }}
.team.home {{ justify-content:flex-end; text-align:right; }}
.team.away {{ justify-content:flex-start; text-align:left; }}
.team img {{ width:28px; height:28px; object-fit:contain; }}
.team .name {{ font-weight:600; font-size:0.95em; }}
.team .pos {{ color:#666; font-size:0.75em; }}
.vs {{ color:#555; font-size:0.85em; width:40px; text-align:center; flex-shrink:0; }}
.prediction-badge {{ padding:4px 12px; border-radius:20px; font-weight:700; font-size:0.8em; width:70px; text-align:center; flex-shrink:0; }}
.prediction-badge.HOME {{ background:#4ecdc420; color:#4ecdc4; border:1px solid #4ecdc440; }}
.prediction-badge.DRAW {{ background:#ffe66d20; color:#ffe66d; border:1px solid #ffe66d40; }}
.prediction-badge.AWAY {{ background:#e9456020; color:#e94560; border:1px solid #e9456040; }}
.score-pred {{ font-weight:700; font-size:1.1em; width:50px; text-align:center; color:#fff; flex-shrink:0; }}
.prob-bar {{ flex:1; min-width:200px; }}
.prob-bar-inner {{ display:flex; height:24px; border-radius:12px; overflow:hidden; background:#222; }}
.prob-bar-inner .h {{ background: linear-gradient(90deg, #4ecdc4, #2bbbad); }}
.prob-bar-inner .d {{ background: linear-gradient(90deg, #ffe66d, #ffcc00); }}
.prob-bar-inner .a {{ background: linear-gradient(90deg, #e94560, #d63447); }}
.prob-labels {{ display:flex; justify-content:space-between; font-size:0.7em; color:#888; margin-top:3px; padding:0 2px; }}
.consensus {{ font-size:0.7em; padding:2px 8px; border-radius:10px; flex-shrink:0; }}
.consensus.high {{ background:#4ecdc420; color:#4ecdc4; }}
.consensus.medium {{ background:#ffe66d20; color:#ffe66d; }}
.consensus.low {{ background:#e9456020; color:#e94560; }}
.form {{ font-size:0.7em; letter-spacing:1px; color:#888; }}
.form .W {{ color:#4ecdc4; }}
.form .D {{ color:#ffe66d; }}
.form .L {{ color:#e94560; }}
.footer {{ text-align:center; padding:40px 20px; color:#555; font-size:0.85em; border-top:1px solid #222; margin-top:40px; }}
.method {{ background:#151515; border:1px solid #222; border-radius:8px; padding:20px; margin:20px 0; }}
.method h3 {{ color:#e94560; margin-bottom:10px; }}
.method p {{ color:#aaa; line-height:1.6; }}
@media (max-width:768px) {{
  .match-row {{ flex-wrap:wrap; padding:10px; gap:6px; }}
  .team {{ width:140px; }}
  .prob-bar {{ min-width:100%; order:10; }}
  .match-date {{ width:100%; }}
}}
</style>
</head>
<body>

<div class="header">
<h1>MiroFish <span class="accent">Football Oracle</span></h1>
<div class="sub">Premier League 2025/26 - {total} Match Predictions</div>
<div class="sub" style="margin-top:5px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} | Dual-Layer: ML + 50-Agent Swarm Intelligence</div>
</div>

<div class="stats-bar">
<div class="stat home"><div class="num">{home_wins}</div><div class="label">Home Wins</div></div>
<div class="stat draw"><div class="num">{draws}</div><div class="label">Draws</div></div>
<div class="stat away"><div class="num">{away_wins}</div><div class="label">Away Wins</div></div>
<div class="stat"><div class="num" style="color:#fff;">{total}</div><div class="label">Total Matches</div></div>
</div>

<div class="container">

<div class="method">
<h3>Prediction Method</h3>
<p><strong>Layer 1 - ML Analysis (40%):</strong> Position gap, form points, goal difference per game, attack/defense ratios, home advantage coefficient.</p>
<p><strong>Layer 2 - Swarm Intelligence (60%):</strong> 50 AI agents (5 Fan, 15 Analyst, 8 Media, 12 Insider, 10 Neutral) vote with role-weighted confidence. Dynamic fusion adjusts weights based on consensus level.</p>
</div>
"""

def format_form(form_str):
    if not form_str or form_str == '?':
        return '<span class="form">?</span>'
    chars = []
    for ch in form_str:
        chars.append(f'<span class="{ch}">{ch}</span>')
    return '<span class="form">' + ''.join(chars) + '</span>'

for md in sorted(matchdays.keys()):
    matches = matchdays[md]
    html += f'<div class="matchday-header">Matchday {md}</div>\n'

    for m in sorted(matches, key=lambda x: x['date']):
        pred_class = m['prediction']
        hp = m['home_prob']
        dp = m['draw_prob']
        ap = m['away_prob']

        date_str = m['date'].replace('T', ' ')

        html += f"""
<div class="match-card">
<div class="match-row">
  <div class="match-date">{date_str}<br>{format_form(m['home_form'])} {format_form(m['away_form'])}</div>
  <div class="team home">
    <div><div class="name">{m['home_team']}</div><div class="pos">#{m['home_pos']} | {m['home_pts']}pts</div></div>
    <img src="{m['home_crest']}" alt="" onerror="this.style.display='none'">
  </div>
  <div class="score-pred">{m['predicted_score']}</div>
  <div class="team away">
    <img src="{m['away_crest']}" alt="" onerror="this.style.display='none'">
    <div><div class="name">{m['away_team']}</div><div class="pos">#{m['away_pos']} | {m['away_pts']}pts</div></div>
  </div>
  <div class="prediction-badge {pred_class}">{pred_class}</div>
  <div class="prob-bar">
    <div class="prob-bar-inner">
      <div class="h" style="width:{hp*100:.1f}%"></div>
      <div class="d" style="width:{dp*100:.1f}%"></div>
      <div class="a" style="width:{ap*100:.1f}%"></div>
    </div>
    <div class="prob-labels"><span>{hp:.0%} Home</span><span>{dp:.0%} Draw</span><span>{ap:.0%} Away</span></div>
  </div>
  <div class="consensus {m['consensus']}">{m['consensus']}</div>
</div>
</div>
"""

html += f"""
</div>

<div class="footer">
<p>MiroFish Football Oracle | Dual-Layer Architecture: ML ({'{:.0%}'.format(1-0.6)}) + Swarm Intelligence ({'{:.0%}'.format(0.6)})</p>
<p>50 AI Agents x 5 Roles (Fan/Analyst/Media/Insider/Neutral) | Powered by football-data.org + Open-Meteo</p>
<p style="margin-top:8px; color:#444;">Predictions are for reference only. Past performance does not guarantee future results.</p>
</div>

</body>
</html>"""

output_path = '/home/node/a0/workspace/0bc50884-3715-4523-bf95-eb96178d2dcb/workspace/outputs/pl_predictions.html'
with open(output_path, 'w') as f:
    f.write(html)

print(f"Report generated: {output_path}")
print(f"Total: {total} matches | {home_wins}H / {draws}D / {away_wins}A")
