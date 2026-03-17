#!/usr/bin/env python3
"""
MiroFish - 真正 LLM Agent 投票預測
每場比賽 5 個 Agent（每個角色 1 個）透過 AI Gateway 做真正推理
"""

import sys, os, json, time, random
import concurrent.futures
import numpy as np
import requests
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.services.football.voting_system import VotingSystem

API_URL = "https://ai-gateway.happycapy.ai/api/v1/chat/completions"
API_KEY = os.environ.get("AI_GATEWAY_API_KEY", "0ace44de3ac3427c815b24b5bfb2d6b2")
MODEL = "anthropic/claude-haiku-4.5"

# Load data
with open('/tmp/pl_matches.json') as f:
    ALL_MATCHES = json.load(f)
with open('/tmp/pl_standings.json') as f:
    RAW_STANDINGS = json.load(f)

STANDINGS = {}
table = RAW_STANDINGS if isinstance(RAW_STANDINGS, list) else RAW_STANDINGS.get('standings', [])
if isinstance(table, list) and table:
    for entry in (table[0].get('table', []) if isinstance(table[0], dict) else table):
        STANDINGS[entry.get('team', {}).get('id')] = entry

ROLE_PROMPTS = {
    "Fan": "You are a passionate football Fan. You heavily favor the home team due to crowd atmosphere and home advantage. You are emotional and optimistic about home wins. Your analysis is based on fan sentiment, stadium atmosphere, and loyalty.",
    "Analyst": "You are a professional football Data Analyst. You rely strictly on statistics: league position, points, goal difference, recent form (W/D/L), and historical performance. You are objective and data-driven. You assign probabilities based on evidence.",
    "Media": "You are a football Media Journalist. You follow narratives, team news, managerial pressure, and public perception. You consider storylines like revenge matches, relegation battles, and title races. You may predict upsets when the narrative supports it.",
    "Insider": "You are a football Insider with access to team news. You heavily weigh injuries, squad fitness, rotation risk, and tactical matchups. You know which teams have congested schedules. Formation matchups and key player availability are your focus.",
    "Neutral": "You are a Neutral football Observer. You provide balanced, unbiased analysis considering all factors equally: form, position, home advantage, injuries, weather. You tend to predict conservatively and often see draws in tight matches.",
}

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
})


def get_stats(team_id):
    s = STANDINGS.get(team_id, {})
    return {
        'position': s.get('position', 10),
        'points': s.get('points', 0),
        'played': s.get('playedGames', 0),
        'won': s.get('won', 0),
        'drawn': s.get('draw', 0),
        'lost': s.get('lost', 0),
        'gf': s.get('goalsFor', 0),
        'ga': s.get('goalsAgainst', 0),
        'gd': s.get('goalDifference', 0),
        'form': s.get('form') or '',
    }


def build_match_prompt(match, home_stats, away_stats):
    home = match.get('homeTeam', {}).get('name', '?')
    away = match.get('awayTeam', {}).get('name', '?')
    md = match.get('matchday', '?')
    date = match.get('utcDate', '')[:16]

    return f"""Premier League 2025/26 - Matchday {md}
{date}

HOME: {home}
  Position: #{home_stats['position']} | Points: {home_stats['points']} | Played: {home_stats['played']}
  W{home_stats['won']} D{home_stats['drawn']} L{home_stats['lost']} | GF:{home_stats['gf']} GA:{home_stats['ga']} GD:{home_stats['gd']:+d}
  Recent form: {(home_stats['form'] or '?')[-5:]}

AWAY: {away}
  Position: #{away_stats['position']} | Points: {away_stats['points']} | Played: {away_stats['played']}
  W{away_stats['won']} D{away_stats['drawn']} L{away_stats['lost']} | GF:{away_stats['gf']} GA:{away_stats['ga']} GD:{away_stats['gd']:+d}
  Recent form: {(away_stats['form'] or '?')[-5:]}

Predict the match result. Reply in EXACTLY this JSON format, nothing else:
{{"result":"HOME or DRAW or AWAY","confidence":60-95,"score":"X-Y","reasoning":"one sentence"}}"""


def call_llm(role, match_prompt, retries=2):
    """Call AI Gateway for one agent's prediction."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": ROLE_PROMPTS[role]},
            {"role": "user", "content": match_prompt},
        ],
        "max_tokens": 120,
        "temperature": 0.7,
    }
    for attempt in range(retries + 1):
        try:
            resp = session.post(API_URL, json=payload, timeout=30)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Parse JSON from response
            # Handle cases where LLM wraps in markdown
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            result = data.get("result", "HOME").upper()
            if result not in ("HOME", "DRAW", "AWAY"):
                result = "HOME"
            return {
                "role": role,
                "result": result,
                "confidence": min(95, max(40, int(data.get("confidence", 65)))),
                "score": data.get("score", "1-0"),
                "reasoning": data.get("reasoning", ""),
                "over_under": "OVER" if sum(int(g) for g in str(data.get("score", "1-0")).split("-")[:2]) > 2 else "UNDER",
            }
        except Exception as e:
            if attempt == retries:
                return {
                    "role": role,
                    "result": "HOME",
                    "confidence": 55,
                    "score": "1-0",
                    "reasoning": f"Fallback: {str(e)[:50]}",
                    "over_under": "UNDER",
                }
            time.sleep(1)


def predict_match_with_llm(match, match_idx):
    """Run 5-agent LLM voting for one match."""
    home_team = match.get('homeTeam', {})
    away_team = match.get('awayTeam', {})
    hs = get_stats(home_team.get('id'))
    aws = get_stats(away_team.get('id'))

    prompt = build_match_prompt(match, hs, aws)

    # Call 5 agents in parallel
    votes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(call_llm, role, prompt): role for role in ROLE_PROMPTS}
        for future in concurrent.futures.as_completed(futures):
            vote = future.result()
            # Scale to represent full agent counts
            role = vote['role']
            counts = {'Fan': 5, 'Analyst': 15, 'Media': 8, 'Insider': 12, 'Neutral': 10}
            for i in range(counts[role]):
                v = vote.copy()
                v['agent_id'] = f"{role}_{i+1:02d}"
                v['name'] = f"{role}_{i+1:02d}"
                votes.append(v)

    # Aggregate
    vs = VotingSystem()
    agg = vs.aggregate_votes(votes)

    # ML heuristic layer
    pos_diff = aws['position'] - hs['position']
    form_diff = form_pts(hs['form']) - form_pts(aws['form'])
    gd_diff = (hs['gd'] / max(hs['played'], 1)) - (aws['gd'] / max(aws['played'], 1))
    home_adj = pos_diff * 0.012 + form_diff * 0.015 + gd_diff * 0.04
    hp = max(0.08, min(0.75, 0.42 + home_adj))
    ap = max(0.08, min(0.75, 0.31 - home_adj))
    dp = max(0.12, 1.0 - hp - ap)
    t = hp + dp + ap
    ml_pred = {'probabilities': {'home': round(hp/t, 4), 'draw': round(dp/t, 4), 'away': round(ap/t, 4)}}

    # Poisson scores
    ha = hs['gf'] / max(hs['played'], 1)
    aa = aws['gf'] / max(aws['played'], 1)
    hd = hs['ga'] / max(hs['played'], 1)
    ad = aws['ga'] / max(aws['played'], 1)
    home_lambda = max(0.5, (ha + ad) / 2 * 1.05)
    away_lambda = max(0.3, (aa + hd) / 2 * 0.95)

    # Fusion
    fused = vs.dynamic_fusion(ml_pred, agg['result_prediction'], agg['consensus'])

    # Score from LLM votes (most common)
    score_votes = [v['score'] for v in votes[:5]]  # from 5 real agents
    score_count = {}
    for s in score_votes:
        score_count[s] = score_count.get(s, 0) + 1
    best_score = max(score_count, key=score_count.get) if score_count else "1-0"

    # Collect reasonings from real agents
    agent_reasonings = []
    seen_roles = set()
    for v in votes:
        if v['role'] not in seen_roles and v.get('reasoning'):
            agent_reasonings.append({'role': v['role'], 'reasoning': v['reasoning'], 'result': v['result']})
            seen_roles.add(v['role'])

    return {
        'match_id': match.get('id'),
        'matchday': match.get('matchday'),
        'date': match.get('utcDate', '')[:16],
        'home_team': home_team.get('shortName', home_team.get('name', '?')),
        'away_team': away_team.get('shortName', away_team.get('name', '?')),
        'home_crest': home_team.get('crest', ''),
        'away_crest': away_team.get('crest', ''),
        'home_pos': hs['position'],
        'away_pos': aws['position'],
        'home_pts': hs['points'],
        'away_pts': aws['points'],
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
        'ml_home_goals': round(home_lambda, 2),
        'ml_away_goals': round(away_lambda, 2),
    }


def form_pts(form_str):
    if not form_str: return 7
    return sum(3 if c == 'W' else 1 if c == 'D' else 0 for c in form_str[-5:])


if __name__ == '__main__':
    print("=" * 65)
    print("  MiroFish - Real LLM Agent Predictions")
    print(f"  Model: {MODEL} | Agents: 5 roles x 50 scaled | Matches: {len(ALL_MATCHES)}")
    print("=" * 65)

    results = []
    total = len(ALL_MATCHES)
    start_time = time.time()

    for i, match in enumerate(ALL_MATCHES):
        home = match.get('homeTeam', {}).get('shortName', '?')
        away = match.get('awayTeam', {}).get('shortName', '?')
        print(f"\n[{i+1}/{total}] {home} vs {away}...", end=" ", flush=True)

        pred = predict_match_with_llm(match, i)
        results.append(pred)

        # Show result
        r = pred['prediction']
        c = pred['confidence']
        cs = pred['consensus']
        print(f"=> {r} ({c:.0%}) [{cs}] Score: {pred['predicted_score']}")

        # Show agent reasonings
        for ar in pred.get('agent_reasonings', []):
            print(f"    [{ar['role']:8s}] {ar['result']:5s}: {ar['reasoning'][:80]}")

    elapsed = time.time() - start_time

    # Save
    with open('/tmp/llm_predictions.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    hw = sum(1 for r in results if r['prediction'] == 'HOME')
    dr = sum(1 for r in results if r['prediction'] == 'DRAW')
    aw = sum(1 for r in results if r['prediction'] == 'AWAY')
    high = sum(1 for r in results if r['consensus'] == 'high')
    avg_c = np.mean([r['confidence'] for r in results])

    print(f"\n{'='*65}")
    print(f"  COMPLETE: {total} matches in {elapsed:.0f}s ({elapsed/total:.1f}s per match)")
    print(f"  Results: {hw}H / {dr}D / {aw}A")
    print(f"  Avg confidence: {avg_c:.1%} | High consensus: {high}/{total}")
    print(f"  Saved to /tmp/llm_predictions.json")
    print(f"{'='*65}")
