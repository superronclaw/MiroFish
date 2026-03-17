"""
群体智能投票系统单元测试
"""

import pytest
from app.services.football.voting_system import VotingSystem
from app.models.football_models import AgentRole


class TestVotingSystem:
    @pytest.fixture
    def voting(self):
        return VotingSystem()

    @pytest.fixture
    def sample_votes(self):
        """模拟 10 个 Agent 投票（简化版）"""
        return [
            # 5 Analysts vote HOME
            {'agent_id': 1, 'role': 'Analyst', 'result': 'HOME', 'confidence': 80, 'score': '2-1', 'over_under': 'OVER', 'reasoning': 'Strong home form'},
            {'agent_id': 2, 'role': 'Analyst', 'result': 'HOME', 'confidence': 75, 'score': '2-0', 'over_under': 'OVER', 'reasoning': 'Statistical advantage'},
            {'agent_id': 3, 'role': 'Analyst', 'result': 'HOME', 'confidence': 70, 'score': '1-0', 'over_under': 'UNDER', 'reasoning': 'Defensive strength'},
            {'agent_id': 4, 'role': 'Analyst', 'result': 'DRAW', 'confidence': 60, 'score': '1-1', 'over_under': 'UNDER', 'reasoning': 'Balanced teams'},
            {'agent_id': 5, 'role': 'Analyst', 'result': 'HOME', 'confidence': 85, 'score': '3-1', 'over_under': 'OVER', 'reasoning': 'xG dominance'},
            # 2 Fans vote HOME
            {'agent_id': 6, 'role': 'Fan', 'result': 'HOME', 'confidence': 90, 'score': '3-0', 'over_under': 'OVER', 'reasoning': 'Home crowd factor'},
            {'agent_id': 7, 'role': 'Fan', 'result': 'HOME', 'confidence': 85, 'score': '2-1', 'over_under': 'OVER', 'reasoning': 'Passionate support'},
            # 2 Insiders vote mixed
            {'agent_id': 8, 'role': 'Insider', 'result': 'HOME', 'confidence': 65, 'score': '1-0', 'over_under': 'UNDER', 'reasoning': 'Key player fit'},
            {'agent_id': 9, 'role': 'Insider', 'result': 'AWAY', 'confidence': 55, 'score': '0-1', 'over_under': 'UNDER', 'reasoning': 'Injury concerns'},
            # 1 Neutral
            {'agent_id': 10, 'role': 'Neutral', 'result': 'HOME', 'confidence': 60, 'score': '2-1', 'over_under': 'OVER', 'reasoning': 'Balanced assessment favors home'},
        ]

    def test_aggregate_basic(self, voting, sample_votes):
        result = voting.aggregate_votes(sample_votes)
        assert result is not None
        assert result['total_agents'] == 10
        assert result['valid_votes'] == 10

    def test_result_prediction(self, voting, sample_votes):
        result = voting.aggregate_votes(sample_votes)
        assert result['result_prediction']['prediction'] == 'HOME'

    def test_consensus_high(self, voting, sample_votes):
        result = voting.aggregate_votes(sample_votes)
        # 8 out of 10 vote HOME -> high consensus expected
        consensus = result['consensus']
        assert consensus['level'] in ('high', 'medium')
        assert consensus['score'] > 0.5

    def test_role_breakdown(self, voting, sample_votes):
        result = voting.aggregate_votes(sample_votes)
        breakdown = result['role_breakdown']
        assert 'Analyst' in breakdown
        assert 'Fan' in breakdown
        assert breakdown['Analyst']['count'] == 5
        assert breakdown['Fan']['count'] == 2

    def test_key_arguments(self, voting, sample_votes):
        result = voting.aggregate_votes(sample_votes)
        args = result['key_arguments']
        assert len(args) > 0
        assert len(args) <= 5
        # First argument should have highest score
        assert args[0]['score'] >= args[-1]['score']

    def test_empty_votes(self, voting):
        result = voting.aggregate_votes([])
        assert result is None


class TestDynamicFusion:
    @pytest.fixture
    def voting(self):
        return VotingSystem()

    def test_high_consensus_boosts_agent(self, voting):
        ml = {'probabilities': {'home': 0.5, 'draw': 0.3, 'away': 0.2}}
        agent = {'probabilities': {'HOME': 0.7, 'DRAW': 0.2, 'AWAY': 0.1}}
        consensus = {'level': 'high', 'score': 0.85}

        result = voting.dynamic_fusion(ml, agent, consensus)
        assert result['fusion_weights']['agent'] == 0.70
        assert result['fusion_weights']['ml'] == 0.30
        assert result['prediction'] == 'HOME'

    def test_low_consensus_boosts_ml(self, voting):
        ml = {'probabilities': {'home': 0.5, 'draw': 0.3, 'away': 0.2}}
        agent = {'probabilities': {'HOME': 0.4, 'DRAW': 0.35, 'AWAY': 0.25}}
        consensus = {'level': 'low', 'score': 0.35}

        result = voting.dynamic_fusion(ml, agent, consensus)
        assert result['fusion_weights']['ml'] == 0.55
        assert result['fusion_weights']['agent'] == 0.45

    def test_medium_consensus_default(self, voting):
        ml = {'probabilities': {'home': 0.45, 'draw': 0.30, 'away': 0.25}}
        agent = {'probabilities': {'HOME': 0.5, 'DRAW': 0.3, 'AWAY': 0.2}}
        consensus = {'level': 'medium', 'score': 0.55}

        result = voting.dynamic_fusion(ml, agent, consensus)
        assert result['fusion_weights']['ml'] == 0.4
        assert result['fusion_weights']['agent'] == 0.6

    def test_probabilities_sum_to_one(self, voting):
        ml = {'probabilities': {'home': 0.4, 'draw': 0.35, 'away': 0.25}}
        agent = {'probabilities': {'HOME': 0.6, 'DRAW': 0.25, 'AWAY': 0.15}}
        consensus = {'level': 'high', 'score': 0.75}

        result = voting.dynamic_fusion(ml, agent, consensus)
        total = sum(result['probabilities'].values())
        assert abs(total - 1.0) < 0.01
