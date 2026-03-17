"""
足球数据模型单元测试
"""

import pytest
from app.models.football_models import (
    AgentRole, MatchStatus, PredictionType, SimulationStatus,
    AGENT_WEIGHTS, League, Venue, Team, Match, TeamSeasonStats,
    MatchPrediction, AgentProfile,
)


class TestEnums:
    def test_agent_roles(self):
        assert AgentRole.FAN.value == 'Fan'
        assert AgentRole.ANALYST.value == 'Analyst'
        assert AgentRole.MEDIA.value == 'Media'
        assert AgentRole.INSIDER.value == 'Insider'
        assert AgentRole.NEUTRAL.value == 'Neutral'
        assert len(AgentRole) == 5

    def test_match_status(self):
        assert MatchStatus.SCHEDULED.value == 'SCHEDULED'
        assert MatchStatus.FINISHED.value == 'FINISHED'
        assert MatchStatus.LIVE.value == 'LIVE'
        assert MatchStatus.POSTPONED.value == 'POSTPONED'
        assert MatchStatus.CANCELLED.value == 'CANCELLED'

    def test_prediction_type(self):
        assert PredictionType.FULL.value == 'full'
        assert PredictionType.ML_ONLY.value == 'ml_only'
        assert PredictionType.QUICK.value == 'quick'


class TestAgentWeights:
    def test_weights_sum_to_one(self):
        total = sum(AGENT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_analyst_highest(self):
        assert AGENT_WEIGHTS[AgentRole.ANALYST] == 0.30
        assert AGENT_WEIGHTS[AgentRole.ANALYST] >= max(
            v for k, v in AGENT_WEIGHTS.items() if k != AgentRole.ANALYST
        )

    def test_fan_lowest(self):
        assert AGENT_WEIGHTS[AgentRole.FAN] == 0.10


class TestTeamSeasonStats:
    def test_win_rate(self):
        stats = TeamSeasonStats(
            team_id=1, league_id=1, season=2025, position=1,
            played=10, won=7, drawn=2, lost=1,
            goals_for=20, goals_against=5, goal_difference=15, points=23,
        )
        assert stats.win_rate == 0.7

    def test_goals_per_match(self):
        stats = TeamSeasonStats(
            team_id=1, league_id=1, season=2025, position=1,
            played=10, won=5, drawn=3, lost=2,
            goals_for=15, goals_against=8, goal_difference=7, points=18,
        )
        assert stats.goals_per_match == 1.5

    def test_zero_played(self):
        stats = TeamSeasonStats(
            team_id=1, league_id=1, season=2025, position=1,
            played=0, won=0, drawn=0, lost=0,
            goals_for=0, goals_against=0, goal_difference=0, points=0,
        )
        assert stats.win_rate == 0
        assert stats.goals_per_match == 0


class TestMatchPrediction:
    def test_to_dict(self):
        pred = MatchPrediction(
            match_id=1,
            ml_home_win_prob=0.5, ml_draw_prob=0.3, ml_away_win_prob=0.2,
            ml_confidence=0.72,
            agent_home_win_prob=0.6, agent_draw_prob=0.25, agent_away_win_prob=0.15,
            agent_consensus_level='high',
            agent_total_agents=50,
            combined_home_win_prob=0.55, combined_draw_prob=0.275, combined_away_win_prob=0.175,
            combined_confidence=0.55,
        )
        d = pred.to_dict()
        assert d['match_id'] == 1
        assert d['ml_prediction']['home_win'] == 0.5
        assert d['ml_prediction']['draw'] == 0.3
        assert d['agent_prediction']['home_win'] == 0.6
        assert d['agent_prediction']['consensus_level'] == 'high'
        assert d['combined_prediction']['home_win'] == 0.55
        assert d['combined_prediction']['confidence'] == 0.55
        assert pred.final_result == 'home_win'

    def test_final_result(self):
        pred = MatchPrediction(
            match_id=2,
            combined_home_win_prob=0.2, combined_draw_prob=0.5, combined_away_win_prob=0.3,
        )
        assert pred.final_result == 'draw'
