"""
足球预测系统集成测试
测试模块间协作：数据处理 -> 特征工程 -> ML 预测 -> 投票 -> 融合
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.models.football_models import (
    AgentRole, AGENT_WEIGHTS, MatchPrediction, PredictionType,
)
from app.services.football.data_processor import FootballDataProcessor, WeatherEncoder
from app.services.football.feature_engineer import FeatureEngineer
from app.services.football.voting_system import VotingSystem
from app.services.football.agent_profile_generator import (
    generate_agent_profiles, generate_match_context_prompt, ROLE_TEMPLATES,
)


# ============= Test Fixtures =============

@pytest.fixture
def sample_matches_df():
    """Create a realistic matches DataFrame for testing pipeline."""
    base_date = datetime(2025, 1, 1)
    rows = []
    for i in range(20):
        home_score = np.random.randint(0, 4)
        away_score = np.random.randint(0, 3)
        rows.append({
            'match_id': i + 1,
            'home_team_id': 101 if i % 2 == 0 else 102,
            'away_team_id': 102 if i % 2 == 0 else 101,
            'match_date': base_date + timedelta(days=i * 7),
            'home_score_ft': home_score,
            'away_score_ft': away_score,
            'home_score_ht': home_score // 2,
            'away_score_ht': away_score // 2,
            'status': 'FINISHED',
            'matchday': i + 1,
            'league_id': 1,
            'venue_id': 1,
            'weather_condition': np.random.choice(['Clear', 'Rain', 'Clouds']),
            'temperature': np.random.uniform(5, 25),
            'humidity': np.random.randint(40, 90),
            'wind_speed': np.random.uniform(0, 15),
            'referee_name': 'Michael Oliver',
            'home_formation': '4-3-3',
            'away_formation': '4-4-2',
        })
    return pd.DataFrame(rows)


@pytest.fixture
def sample_agent_votes():
    """Create realistic agent votes for a match."""
    votes = []
    # Fan votes (5 agents)
    for i in range(5):
        votes.append({
            'agent_id': i + 1,
            'name': f'Fan_{i+1:02d}',
            'role': 'Fan',
            'weight': 0.02,
            'result': np.random.choice(['HOME', 'DRAW', 'AWAY'], p=[0.5, 0.2, 0.3]),
            'confidence': np.random.randint(60, 90),
            'score': '2-1',
            'over_under': 'OVER',
            'reasoning': f'Fan analysis {i}: Home team has strong support.',
        })
    # Analyst votes (15 agents)
    for i in range(15):
        votes.append({
            'agent_id': 6 + i,
            'name': f'Analyst_{i+1:02d}',
            'role': 'Analyst',
            'weight': 0.02,
            'result': np.random.choice(['HOME', 'DRAW', 'AWAY'], p=[0.6, 0.25, 0.15]),
            'confidence': np.random.randint(55, 85),
            'score': '2-1',
            'over_under': 'OVER',
            'reasoning': f'Statistical analysis {i}: xG favors home team.',
        })
    # Media votes (8 agents)
    for i in range(8):
        votes.append({
            'agent_id': 21 + i,
            'name': f'Media_{i+1:02d}',
            'role': 'Media',
            'weight': 0.01875,
            'result': np.random.choice(['HOME', 'DRAW', 'AWAY'], p=[0.4, 0.3, 0.3]),
            'confidence': np.random.randint(50, 80),
            'score': '1-1',
            'over_under': 'UNDER',
            'reasoning': f'Media narrative {i}: Both teams cautious.',
        })
    # Insider votes (12 agents)
    for i in range(12):
        votes.append({
            'agent_id': 29 + i,
            'name': f'Insider_{i+1:02d}',
            'role': 'Insider',
            'weight': 0.02083,
            'result': np.random.choice(['HOME', 'DRAW', 'AWAY'], p=[0.55, 0.25, 0.2]),
            'confidence': np.random.randint(65, 90),
            'score': '2-0',
            'over_under': 'OVER',
            'reasoning': f'Insider intel {i}: Home team fitness is excellent.',
        })
    # Neutral votes (10 agents)
    for i in range(10):
        votes.append({
            'agent_id': 41 + i,
            'name': f'Neutral_{i+1:02d}',
            'role': 'Neutral',
            'weight': 0.02,
            'result': np.random.choice(['HOME', 'DRAW', 'AWAY'], p=[0.45, 0.3, 0.25]),
            'confidence': np.random.randint(50, 75),
            'score': '1-0',
            'over_under': 'UNDER',
            'reasoning': f'Balanced view {i}: Slight edge to home.',
        })
    return votes


# ============= Pipeline Integration Tests =============

class TestDataProcessingPipeline:
    """Test data flows correctly through processing stages."""

    def test_clean_then_form_computation(self, sample_matches_df):
        """Clean data, then compute recent form - end to end."""
        cleaned = FootballDataProcessor.clean_matches(sample_matches_df)

        # Verify cleaning added required columns
        assert 'result' in cleaned.columns
        assert 'result_code' in cleaned.columns
        assert 'total_goals' in cleaned.columns
        assert 'over_2_5' in cleaned.columns

        # Compute form for team 101
        form = FootballDataProcessor.compute_recent_form(
            cleaned, team_id=101,
            before_date=datetime(2025, 6, 1),
            n_matches=5,
        )
        assert 'form_points' in form
        assert 0 <= form['form_points'] <= 15  # max 5 wins = 15 points
        assert form['form_goals_scored'] >= 0
        assert form['form_goals_conceded'] >= 0
        assert 0 <= form['form_win_rate'] <= 1

    def test_clean_then_h2h(self, sample_matches_df):
        """Clean data, then compute head-to-head stats."""
        cleaned = FootballDataProcessor.clean_matches(sample_matches_df)

        h2h = FootballDataProcessor.compute_head_to_head(
            cleaned,
            home_team_id=101, away_team_id=102,
            before_date=datetime(2025, 6, 1),
            n_matches=10,
        )
        assert h2h['h2h_total'] > 0
        assert h2h['h2h_home_wins'] + h2h['h2h_away_wins'] + h2h['h2h_draws'] == h2h['h2h_total']
        assert h2h['h2h_home_goals_avg'] >= 0
        assert h2h['h2h_away_goals_avg'] >= 0


class TestVotingToFusionPipeline:
    """Test voting aggregation flows into dynamic fusion."""

    def test_vote_then_fuse(self, sample_agent_votes):
        """Aggregate votes, then fuse with ML prediction."""
        vs = VotingSystem()

        # Step 1: Aggregate
        agg = vs.aggregate_votes(sample_agent_votes)
        assert agg is not None
        assert agg['total_agents'] == 50
        assert agg['consensus'] is not None
        assert agg['result_prediction']['prediction'] in ('HOME', 'DRAW', 'AWAY')

        # Step 2: Create mock ML prediction
        ml_prediction = {
            'probabilities': {'home': 0.45, 'draw': 0.30, 'away': 0.25},
        }

        # Step 3: Fuse
        fused = vs.dynamic_fusion(
            ml_prediction=ml_prediction,
            agent_prediction=agg['result_prediction'],
            consensus=agg['consensus'],
        )

        assert fused['prediction'] in ('HOME', 'DRAW', 'AWAY')
        probs = fused['probabilities']
        assert abs(sum(probs.values()) - 1.0) < 0.01
        assert fused['fusion_weights']['ml'] + fused['fusion_weights']['agent'] == 1.0
        assert fused['consensus_level'] in ('high', 'medium', 'low')

    def test_high_consensus_shifts_weights(self):
        """When all agents agree, agent weight should increase."""
        vs = VotingSystem()

        # Create unanimous votes (all HOME)
        votes = []
        for role in AgentRole:
            for i in range(5):
                votes.append({
                    'agent_id': len(votes) + 1,
                    'role': role.value,
                    'result': 'HOME',
                    'confidence': 80,
                    'reasoning': 'Strong home advantage.',
                })

        agg = vs.aggregate_votes(votes)
        consensus = agg['consensus']
        assert consensus['level'] == 'high'
        assert consensus['score'] > 0.70

        ml_pred = {'probabilities': {'home': 0.35, 'draw': 0.35, 'away': 0.30}}
        fused = vs.dynamic_fusion(ml_pred, agg['result_prediction'], consensus)

        # Agent weight should be 0.70 (high consensus)
        assert fused['fusion_weights']['agent'] == 0.70
        assert fused['fusion_weights']['ml'] == 0.30
        # Final prediction should favor HOME (agents all said HOME)
        assert fused['prediction'] == 'HOME'


class TestAgentProfileGeneration:
    """Test agent profile generation and match context."""

    def test_generates_correct_count(self):
        """Should generate exactly 50 agents."""
        profiles = generate_agent_profiles()
        assert len(profiles) == 50

    def test_role_distribution(self):
        """Verify correct number of agents per role."""
        profiles = generate_agent_profiles()
        role_counts = {}
        for p in profiles:
            role_counts[p['role']] = role_counts.get(p['role'], 0) + 1

        assert role_counts.get('Fan', 0) == 5
        assert role_counts.get('Analyst', 0) == 15
        assert role_counts.get('Media', 0) == 8
        assert role_counts.get('Insider', 0) == 12
        assert role_counts.get('Neutral', 0) == 10

    def test_unique_system_prompts(self):
        """Each agent should have a unique system prompt."""
        profiles = generate_agent_profiles()
        prompts = [p['system_prompt'] for p in profiles]
        # Not all unique due to random sampling, but most should differ
        unique_count = len(set(prompts))
        assert unique_count >= 30  # At least 60% unique

    def test_match_context_prompt(self):
        """Match context prompt should include all key data."""
        match_data = {
            'home_team_name': 'Manchester United',
            'away_team_name': 'Liverpool',
            'league_name': 'Premier League',
            'match_date': '2025-03-15',
            'venue': 'Old Trafford',
            'weather_condition': 'Rain',
            'temperature': 8,
            'wind_speed': 15,
            'referee_name': 'Michael Oliver',
        }
        features = {
            'home_position': 3,
            'away_position': 1,
            'home_points': 55,
            'away_points': 70,
            'home_form5_points': 12,
            'away_form5_points': 15,
            'h2h_total_matches': 10,
            'h2h_home_wins': 4,
            'h2h_draws': 3,
            'h2h_away_wins': 3,
        }
        prompt = generate_match_context_prompt(match_data, features)

        assert 'Manchester United' in prompt
        assert 'Liverpool' in prompt
        assert 'Premier League' in prompt
        assert 'Rain' in prompt
        assert 'Michael Oliver' in prompt
        assert 'HOME WIN / DRAW / AWAY WIN' in prompt
        assert 'JSON' in prompt

    def test_match_context_with_ml_prediction(self):
        """ML prediction section should be included when provided."""
        match_data = {'home_team_name': 'A', 'away_team_name': 'B'}
        features = {}
        ml_pred = {
            'prediction': 'HOME',
            'probabilities': {'home': 0.5, 'draw': 0.3, 'away': 0.2},
        }
        prompt = generate_match_context_prompt(match_data, features, ml_pred)
        assert 'ML MODEL PREDICTION' in prompt


class TestRoleTemplatesIntegrity:
    """Test that role templates are well-formed."""

    def test_all_roles_have_templates(self):
        """Every AgentRole should have a corresponding template."""
        for role in AgentRole:
            assert role in ROLE_TEMPLATES, f"Missing template for {role}"

    def test_templates_have_required_fields(self):
        """Templates should have all required fields."""
        required = [
            'personality_traits', 'knowledge_focus', 'bias_description',
            'analysis_style', 'system_prompt_template',
        ]
        for role, template in ROLE_TEMPLATES.items():
            for field in required:
                assert field in template, f"Missing {field} in {role} template"

    def test_templates_have_enough_traits(self):
        """Each role should have at least 5 personality traits."""
        for role, template in ROLE_TEMPLATES.items():
            assert len(template['personality_traits']) >= 5, (
                f"{role} has too few personality traits"
            )

    def test_system_prompt_has_placeholders(self):
        """System prompt templates should have {traits} and {focus}."""
        for role, template in ROLE_TEMPLATES.items():
            tpl = template['system_prompt_template']
            assert '{traits}' in tpl, f"{role} template missing {{traits}}"
            assert '{focus}' in tpl, f"{role} template missing {{focus}}"


class TestMatchPredictionModel:
    """Test MatchPrediction model integration."""

    def test_full_prediction_workflow(self):
        """Create a prediction, populate all fields, convert to dict."""
        pred = MatchPrediction(
            match_id=42,
            prediction_type=PredictionType.FULL,
            # ML layer
            ml_home_win_prob=0.45,
            ml_draw_prob=0.30,
            ml_away_win_prob=0.25,
            ml_predicted_home_goals=1.6,
            ml_predicted_away_goals=1.1,
            ml_over_2_5_prob=0.55,
            ml_confidence=0.72,
            # Agent layer
            agent_home_win_prob=0.50,
            agent_draw_prob=0.28,
            agent_away_win_prob=0.22,
            agent_consensus_level='medium',
            agent_total_agents=50,
            agent_voting_details={'home_votes': 25, 'draw_votes': 14, 'away_votes': 11},
            agent_key_arguments=[{'role': 'Analyst', 'reasoning': 'xG favors home'}],
            # Combined
            combined_home_win_prob=0.48,
            combined_draw_prob=0.29,
            combined_away_win_prob=0.23,
            combined_predicted_score='2-1',
            combined_confidence=0.70,
            prediction_narrative='Home team expected to win narrowly.',
        )

        d = pred.to_dict()

        # Verify structure
        assert 'ml_prediction' in d
        assert 'agent_prediction' in d
        assert 'combined_prediction' in d
        assert 'narrative' in d

        # ML layer
        assert d['ml_prediction']['home_win'] == 0.45
        assert d['ml_prediction']['predicted_home_goals'] == 1.6
        assert d['ml_prediction']['over_2_5'] == 0.55

        # Agent layer
        assert d['agent_prediction']['total_agents'] == 50
        assert d['agent_prediction']['consensus_level'] == 'medium'
        assert len(d['agent_prediction']['key_arguments']) == 1

        # Combined
        assert d['combined_prediction']['final_result'] == 'home_win'
        assert d['combined_prediction']['predicted_score'] == '2-1'

        # Narrative
        assert 'Home team' in d['narrative']


class TestWeatherIntegration:
    """Test weather encoding integrates with feature pipeline."""

    def test_weather_encoding_consistency(self):
        """Weather encoding should be deterministic."""
        conditions = ['Clear', 'Rain', 'Snow', 'Clouds', 'Drizzle', 'Thunderstorm']
        for cond in conditions:
            enc1 = WeatherEncoder.encode(cond)
            enc2 = WeatherEncoder.encode(cond)
            assert enc1 == enc2, f"Inconsistent encoding for {cond}"

    def test_weather_severity_ordering(self):
        """Severe weather should have higher codes than mild."""
        clear = WeatherEncoder.encode('Clear')
        rain = WeatherEncoder.encode('Rain')
        snow = WeatherEncoder.encode('Snow')
        # Snow and rain should have higher impact than clear
        assert snow > clear
        assert rain > clear
