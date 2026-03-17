#!/usr/bin/env python3
"""
MiroFish - 英超全部比賽預測
Dual-Layer: ML Features + 50-Agent Swarm Intelligence
"""

import sys, os, json, random, time
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.football.voting_system import VotingSystem
from app.services.football.agent_profile_generator import generate_agent_profiles
from app.utils.weather_client import WeatherClient

# Load data
with open('/tmp/pl_matches.json') as f:
    ALL_MATCHES = json.load(f)
with open('/tmp/pl_standings.json') as f:
    RAW_STANDINGS = json.load(f)
with open('/tmp/pl_teams.json') as f:
    ALL_TEAMS = json.load(f)

# Build lookup tables
STANDINGS = {}
table = RAW_STANDINGS if isinstance(RAW_STANDINGS, list) else RAW_STANDINGS.get('standings', [])
if isinstance(table, list) and table:
    entries = table[0].get('table', []) if isinstance(table[0], dict) else table
    for entry in entries:
        team = entry.get('team', {})
        STANDINGS[team.get('id')] = entry

TEAM_MAP = {}
for t in ALL_TEAMS:
    TEAM_MAP[t.get('id')] = t


def get_team_stats(team_id):
    s = STANDINGS.get(team_id, {})
    return {
        'position': s.get('position', 10),
        'points': s.get('points', 0),
        'played': s.get('playedGames', 0),
        'won': s.get('won', 0),
        'drawn': s.get('draw', 0),
        'lost': s.get('lost', 0),
        'goals_for': s.get('goalsFor', 0),
        'goals_against': s.get('goalsAgainst', 0),
        'gd': s.get('goalDifference', 0),
        'form': s.get('form', ''),
    }


def form_to_points(form_str):
    if not form_str:
        return 7
    pts = 0
    for ch in form_str[-5:]:
        if ch == 'W': pts += 3
        elif ch == 'D': pts += 1
    return pts


def predict_match(match):
    home_team = match.get('homeTeam', {})
    away_team = match.get('awayTeam', {})
    home_id = home_team.get('id')
    away_id = away_team.get('id')

    hs = get_team_stats(home_id)
    aws = get_team_stats(away_id)

    home_form = form_to_points(hs['form'])
    away_form = form_to_points(aws['form'])

    # === ML LAYER ===
    # Position advantage
    pos_diff = aws['position'] - hs['position']  # positive = home ranked higher
    # Form advantage
    form_diff = home_form - away_form
    # Goal difference per game
    home_gd_pg = hs['gd'] / max(hs['played'], 1)
    away_gd_pg = aws['gd'] / max(aws['played'], 1)
    gd_diff = home_gd_pg - away_gd_pg

    # Base probabilities with home advantage
    home_base = 0.42
    draw_base = 0.27
    away_base = 0.31

    # Adjustments
    home_adj = pos_diff * 0.012 + form_diff * 0.015 + gd_diff * 0.04
    home_prob = max(0.08, min(0.75, home_base + home_adj))
    away_prob = max(0.08, min(0.75, away_base - home_adj))
    draw_prob = max(0.12, 1.0 - home_prob - away_prob)

    total = home_prob + draw_prob + away_prob
    home_prob /= total
    draw_prob /= total
    away_prob /= total

    # Score prediction (Poisson-like)
    home_attack = hs['goals_for'] / max(hs['played'], 1)
    away_attack = aws['goals_for'] / max(aws['played'], 1)
    home_defense = hs['goals_against'] / max(hs['played'], 1)
    away_defense = aws['goals_against'] / max(aws['played'], 1)

    home_lambda = max(0.5, (home_attack + away_defense) / 2 * 1.05)  # slight home boost
    away_lambda = max(0.3, (away_attack + home_defense) / 2 * 0.95)

    ml_prediction = {
        'probabilities': {'home': round(home_prob, 4), 'draw': round(draw_prob, 4), 'away': round(away_prob, 4)},
        'home_goals': round(home_lambda, 2),
        'away_goals': round(away_lambda, 2),
    }

    # === AGENT LAYER ===
    profiles = generate_agent_profiles()
    votes = []
    for profile in profiles:
        vote = simulate_agent_vote(profile['role'], hs, aws, ml_prediction, home_form, away_form)
        vote.update({'agent_id': profile['agent_id'], 'name': profile['name'], 'role': profile['role']})
        votes.append(vote)

    vs = VotingSystem()
    agg = vs.aggregate_votes(votes)
    fused = vs.dynamic_fusion(ml_prediction, agg['result_prediction'], agg['consensus'])

    # Most likely score
    h_goals = round(home_lambda)
    a_goals = round(away_lambda)
    if fused['prediction'] == 'HOME' and h_goals <= a_goals:
        h_goals = a_goals + 1
    elif fused['prediction'] == 'AWAY' and a_goals <= h_goals:
        a_goals = h_goals + 1
    elif fused['prediction'] == 'DRAW':
        a_goals = h_goals = min(h_goals, a_goals)

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
        'predicted_score': f"{h_goals}-{a_goals}",
        'consensus': agg['consensus']['level'],
        'consensus_score': agg['consensus']['score'],
        'ml_weights': fused['fusion_weights']['ml'],
        'agent_weights': fused['fusion_weights']['agent'],
        'ml_prediction': ml_prediction,
        'total_agents': 50,
    }


def simulate_agent_vote(role, home_stats, away_stats, ml_pred, home_form, away_form):
    ml_probs = ml_pred['probabilities']

    if role == 'Fan':
        boost = random.uniform(0.04, 0.12)
        probs = {'HOME': ml_probs['home'] + boost, 'DRAW': ml_probs['draw'] - boost * 0.3, 'AWAY': ml_probs['away'] - boost * 0.7}
        confidence = random.randint(60, 88)
    elif role == 'Analyst':
        noise = random.uniform(-0.04, 0.04)
        probs = {'HOME': ml_probs['home'] + noise, 'DRAW': ml_probs['draw'], 'AWAY': ml_probs['away'] - noise}
        confidence = random.randint(55, 82)
    elif role == 'Media':
        shift = random.choice([-0.06, 0, 0.04, 0.08])
        probs = {'HOME': ml_probs['home'] + shift, 'DRAW': ml_probs['draw'] + random.uniform(-0.04, 0.06), 'AWAY': ml_probs['away'] - shift}
        confidence = random.randint(48, 75)
    elif role == 'Insider':
        factor = random.uniform(-0.03, 0.03)
        probs = {'HOME': ml_probs['home'] + factor, 'DRAW': ml_probs['draw'], 'AWAY': ml_probs['away'] - factor}
        confidence = random.randint(62, 88)
    else:  # Neutral
        noise = random.uniform(-0.03, 0.03)
        probs = {'HOME': ml_probs['home'] + noise, 'DRAW': ml_probs['draw'] + random.uniform(-0.02, 0.04), 'AWAY': ml_probs['away'] - noise}
        confidence = random.randint(50, 72)

    total = sum(max(0.05, v) for v in probs.values())
    probs = {k: max(0.05, v) / total for k, v in probs.items()}
    result = random.choices(list(probs.keys()), weights=list(probs.values()), k=1)[0]

    return {'result': result, 'confidence': confidence, 'score': '1-0', 'over_under': 'OVER', 'reasoning': f'{role} analysis.'}


if __name__ == '__main__':
    print(f"Running predictions for {len(ALL_MATCHES)} matches...")
    random.seed(42)
    np.random.seed(42)

    results = []
    for i, match in enumerate(ALL_MATCHES):
        pred = predict_match(match)
        results.append(pred)
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(ALL_MATCHES)} done...")

    # Save results
    with open('/tmp/predictions.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nAll {len(results)} predictions complete!")
    print(f"Saved to /tmp/predictions.json")

    # Quick summary
    home_wins = sum(1 for r in results if r['prediction'] == 'HOME')
    draws = sum(1 for r in results if r['prediction'] == 'DRAW')
    away_wins = sum(1 for r in results if r['prediction'] == 'AWAY')
    avg_conf = np.mean([r['confidence'] for r in results])
    high_cons = sum(1 for r in results if r['consensus'] == 'high')
    print(f"\nSummary: {home_wins}H / {draws}D / {away_wins}A")
    print(f"Average confidence: {avg_conf:.1%}")
    print(f"High consensus: {high_cons}/{len(results)}")
