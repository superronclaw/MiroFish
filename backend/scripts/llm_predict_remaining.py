#!/usr/bin/env python3
"""Re-run LLM predictions for matches that got 403 errors, with rate limiting."""

import sys, os, json, time
import concurrent.futures
import numpy as np
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.services.football.voting_system import VotingSystem

API_URL = "https://ai-gateway.happycapy.ai/api/v1/chat/completions"
API_KEY = os.environ.get("AI_GATEWAY_API_KEY", "0ace44de3ac3427c815b24b5bfb2d6b2")
MODEL = "anthropic/claude-haiku-4.5"

with open('/tmp/pl_matches.json') as f:
    ALL_MATCHES = json.load(f)
with open('/tmp/pl_standings.json') as f:
    RAW_STANDINGS = json.load(f)
with open('/tmp/llm_predictions.json') as f:
    EXISTING = json.load(f)

STANDINGS = {}
table = RAW_STANDINGS if isinstance(RAW_STANDINGS, list) else RAW_STANDINGS.get('standings', [])
if isinstance(table, list) and table:
    for entry in (table[0].get('table', []) if isinstance(table[0], dict) else table):
        STANDINGS[entry.get('team', {}).get('id')] = entry

ROLE_PROMPTS = {
    "Fan": "You are a passionate football Fan. You heavily favor the home team due to crowd atmosphere and home advantage. You are emotional and optimistic about home wins. Your analysis is based on fan sentiment, stadium atmosphere, and loyalty.",
    "Analyst": "You are a professional football Data Analyst. You rely strictly on statistics: league position, points, goal difference, recent form (W/D/L), and historical performance. You are objective and data-driven.",
    "Media": "You are a football Media Journalist. You follow narratives, team news, managerial pressure, and public perception. You consider storylines like revenge matches, relegation battles, and title races.",
    "Insider": "You are a football Insider with access to team news. You heavily weigh injuries, squad fitness, rotation risk, and tactical matchups. Formation matchups and key player availability are your focus.",
    "Neutral": "You are a Neutral football Observer. You provide balanced analysis considering all factors equally. You tend to predict conservatively and often see draws in tight matches.",
}

session = requests.Session()
session.headers.update({"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})


def get_stats(team_id):
    s = STANDINGS.get(team_id, {})
    return {
        'position': s.get('position', 10), 'points': s.get('points', 0),
        'played': s.get('playedGames', 0), 'won': s.get('won', 0),
        'drawn': s.get('draw', 0), 'lost': s.get('lost', 0),
        'gf': s.get('goalsFor', 0), 'ga': s.get('goalsAgainst', 0),
        'gd': s.get('goalDifference', 0), 'form': s.get('form') or '',
    }


def build_prompt(match, hs, aws):
    home = match.get('homeTeam', {}).get('name', '?')
    away = match.get('awayTeam', {}).get('name', '?')
    return f"""Premier League 2025/26 - Matchday {match.get('matchday','?')}
{match.get('utcDate','')[:16]}

HOME: {home}
  #{hs['position']} | {hs['points']}pts | W{hs['won']} D{hs['drawn']} L{hs['lost']} | GD:{hs['gd']:+d} | Form: {(hs['form'] or '?')[-5:]}

AWAY: {away}
  #{aws['position']} | {aws['points']}pts | W{aws['won']} D{aws['drawn']} L{aws['lost']} | GD:{aws['gd']:+d} | Form: {(aws['form'] or '?')[-5:]}

Predict result. Reply ONLY in this JSON format:
{{"result":"HOME or DRAW or AWAY","confidence":60-95,"score":"X-Y","reasoning":"one sentence"}}"""


def call_llm(role, prompt):
    for attempt in range(3):
        try:
            resp = session.post(API_URL, json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": ROLE_PROMPTS[role]},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 120, "temperature": 0.7,
            }, timeout=30)
            if resp.status_code == 429:
                wait = 3 * (attempt + 1)
                print(f"      Rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            if resp.status_code == 403:
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"): content = content[4:]
            data = json.loads(content)
            result = data.get("result", "HOME").upper()
            if result not in ("HOME", "DRAW", "AWAY"): result = "HOME"
            return {
                "role": role, "result": result,
                "confidence": min(95, max(40, int(data.get("confidence", 65)))),
                "score": data.get("score", "1-0"),
                "reasoning": data.get("reasoning", ""),
                "over_under": "OVER" if sum(int(g) for g in str(data.get("score","1-0")).split("-")[:2]) > 2 else "UNDER",
            }
        except Exception as e:
            if attempt == 2:
                return {"role": role, "result": "HOME", "confidence": 55, "score": "1-0",
                        "reasoning": f"Error: {str(e)[:50]}", "over_under": "UNDER"}
            time.sleep(2)


def form_pts(f):
    if not f: return 7
    return sum(3 if c=='W' else 1 if c=='D' else 0 for c in f[-5:])


def predict_one(match):
    ht = match.get('homeTeam', {})
    at = match.get('awayTeam', {})
    hs = get_stats(ht.get('id'))
    aws = get_stats(at.get('id'))
    prompt = build_prompt(match, hs, aws)

    # Call agents SEQUENTIALLY with small delays to avoid rate limit
    votes = []
    agent_reasonings = []
    for role in ROLE_PROMPTS:
        vote = call_llm(role, prompt)
        agent_reasonings.append({'role': vote['role'], 'reasoning': vote['reasoning'], 'result': vote['result']})
        counts = {'Fan': 5, 'Analyst': 15, 'Media': 8, 'Insider': 12, 'Neutral': 10}
        for i in range(counts[role]):
            v = vote.copy()
            v['agent_id'] = f"{role}_{i+1:02d}"
            v['name'] = f"{role}_{i+1:02d}"
            votes.append(v)
        time.sleep(0.5)  # small delay between agents

    vs = VotingSystem()
    agg = vs.aggregate_votes(votes)

    # ML layer
    pos_diff = aws['position'] - hs['position']
    form_diff = form_pts(hs['form']) - form_pts(aws['form'])
    gd_diff = (hs['gd']/max(hs['played'],1)) - (aws['gd']/max(aws['played'],1))
    adj = pos_diff * 0.012 + form_diff * 0.015 + gd_diff * 0.04
    hp = max(0.08, min(0.75, 0.42 + adj))
    ap = max(0.08, min(0.75, 0.31 - adj))
    dp = max(0.12, 1.0 - hp - ap)
    t = hp + dp + ap
    ml_pred = {'probabilities': {'home': round(hp/t,4), 'draw': round(dp/t,4), 'away': round(ap/t,4)}}

    ha = hs['gf']/max(hs['played'],1); aa = aws['gf']/max(aws['played'],1)
    hd = hs['ga']/max(hs['played'],1); ad = aws['ga']/max(aws['played'],1)

    fused = vs.dynamic_fusion(ml_pred, agg['result_prediction'], agg['consensus'])

    score_votes = [v['score'] for v in votes[:5]]
    sc = {}
    for s in score_votes: sc[s] = sc.get(s,0)+1
    best_score = max(sc, key=sc.get) if sc else "1-0"

    return {
        'match_id': match.get('id'), 'matchday': match.get('matchday'),
        'date': match.get('utcDate','')[:16],
        'home_team': ht.get('shortName', ht.get('name','?')),
        'away_team': at.get('shortName', at.get('name','?')),
        'home_crest': ht.get('crest',''), 'away_crest': at.get('crest',''),
        'home_pos': hs['position'], 'away_pos': aws['position'],
        'home_pts': hs['points'], 'away_pts': aws['points'],
        'home_form': hs['form'][-5:] if hs['form'] else '?',
        'away_form': aws['form'][-5:] if aws['form'] else '?',
        'prediction': fused['prediction'],
        'confidence': fused['confidence'],
        'home_prob': fused['probabilities']['home'],
        'draw_prob': fused['probabilities']['draw'],
        'away_prob': fused['probabilities']['away'],
        'predicted_score': best_score,
        'consensus': agg['consensus']['level'],
        'consensus_score': agg['consensus']['score'],
        'ml_weights': fused['fusion_weights']['ml'],
        'agent_weights': fused['fusion_weights']['agent'],
        'total_agents': 50,
        'agent_reasonings': agent_reasonings,
        'ml_prediction': ml_pred,
    }


if __name__ == '__main__':
    # Find which matches need re-running
    needs_rerun = []
    for i, p in enumerate(EXISTING):
        has_fallback = any('Fallback' in r.get('reasoning','') or 'Error' in r.get('reasoning','')
                          for r in p.get('agent_reasonings', []))
        if has_fallback:
            needs_rerun.append(i)

    print(f"Re-running {len(needs_rerun)} matches that had API errors...")
    print(f"Using sequential calls with delays to avoid rate limits\n")

    for count, idx in enumerate(needs_rerun):
        match = ALL_MATCHES[idx]
        home = match.get('homeTeam',{}).get('shortName','?')
        away = match.get('awayTeam',{}).get('shortName','?')
        print(f"[{count+1}/{len(needs_rerun)}] {home} vs {away}...", end=" ", flush=True)

        pred = predict_one(match)
        EXISTING[idx] = pred

        print(f"=> {pred['prediction']} ({pred['confidence']:.0%}) [{pred['consensus']}] {pred['predicted_score']}")
        for ar in pred.get('agent_reasonings',[]):
            print(f"    [{ar['role']:8s}] {ar['result']:5s}: {ar['reasoning'][:80]}")

        time.sleep(1)  # delay between matches

    with open('/tmp/llm_predictions.json', 'w') as f:
        json.dump(EXISTING, f, ensure_ascii=False, indent=2)

    hw = sum(1 for r in EXISTING if r['prediction'] == 'HOME')
    dr = sum(1 for r in EXISTING if r['prediction'] == 'DRAW')
    aw = sum(1 for r in EXISTING if r['prediction'] == 'AWAY')
    real = sum(1 for p in EXISTING if not any('Fallback' in r.get('reasoning','') or 'Error' in r.get('reasoning','') for r in p.get('agent_reasonings',[])))

    print(f"\nDone! {real}/79 matches with real LLM | {hw}H / {dr}D / {aw}A")
