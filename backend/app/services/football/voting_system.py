"""
群体智能投票系统
整合 50 个 Agent 的预测结果，通过加权投票产生最终群体预测

投票流程:
1. 收集所有 Agent 投票
2. 按角色权重加权汇总
3. 计算共识度 (consensus level)
4. 根据共识度动态调整 ML/Agent 融合权重
5. 输出最终预测

共识度计算:
- 高共识 (>70%): Agent 权重提升至 70%
- 中共识 (40-70%): 维持默认 60%
- 低共识 (<40%): ML 权重提升至 55%
"""

import logging
import json
from collections import Counter

from ...config import Config
from ...models.football_models import AgentRole, AGENT_WEIGHTS

logger = logging.getLogger('mirofish.football.voting')


class VotingSystem:
    """群体智能投票汇总系统"""

    def __init__(self):
        self.ml_base_weight = Config.ML_PREDICTION_WEIGHT  # 0.4
        self.agent_base_weight = Config.AGENT_PREDICTION_WEIGHT  # 0.6

    def aggregate_votes(self, agent_votes):
        """汇总 Agent 投票结果

        Args:
            agent_votes: list[dict] - 每个 Agent 的投票
                [{
                    'agent_id': 1,
                    'role': 'Analyst',
                    'weight': 0.02,
                    'result': 'HOME',
                    'confidence': 75,
                    'score': '2-1',
                    'over_under': 'OVER',
                    'reasoning': '...',
                }]

        Returns:
            dict: 汇总结果
        """
        if not agent_votes:
            return None

        # 1. 按结果加权投票
        result_votes = self._weighted_vote(agent_votes, 'result')

        # 2. 比分投票
        score_votes = self._weighted_vote(agent_votes, 'score')

        # 3. Over/Under 投票
        ou_votes = self._weighted_vote(agent_votes, 'over_under')

        # 4. 计算共识度
        consensus = self._calculate_consensus(agent_votes)

        # 5. 按角色分组统计
        role_breakdown = self._role_breakdown(agent_votes)

        # 6. 关键论点提取
        key_arguments = self._extract_key_arguments(agent_votes)

        return {
            'result_prediction': result_votes,
            'score_prediction': score_votes,
            'over_under_prediction': ou_votes,
            'consensus': consensus,
            'role_breakdown': role_breakdown,
            'key_arguments': key_arguments,
            'total_agents': len(agent_votes),
            'valid_votes': sum(1 for v in agent_votes if v.get('result')),
        }

    def _weighted_vote(self, votes, field):
        """加权投票统计

        Returns:
            dict: {prediction, probabilities: {option: weight_sum}, margin}
        """
        weighted_counts = {}
        total_weight = 0

        for vote in votes:
            value = vote.get(field)
            if not value:
                continue

            role = vote.get('role', 'Neutral')
            # 使用角色权重 * 个人信心
            role_weight = AGENT_WEIGHTS.get(AgentRole(role), 0.02)
            confidence = vote.get('confidence', 50) / 100
            weight = role_weight * confidence

            weighted_counts[value] = weighted_counts.get(value, 0) + weight
            total_weight += weight

        if not weighted_counts or total_weight == 0:
            return {'prediction': None, 'probabilities': {}, 'margin': 0}

        # 归一化
        probabilities = {k: round(v / total_weight, 4) for k, v in weighted_counts.items()}

        # 排序
        sorted_options = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        prediction = sorted_options[0][0]
        margin = sorted_options[0][1] - (sorted_options[1][1] if len(sorted_options) > 1 else 0)

        return {
            'prediction': prediction,
            'probabilities': dict(sorted_options[:5]),  # top 5
            'margin': round(margin, 4),
        }

    def _calculate_consensus(self, votes):
        """计算共识度

        共识度 = 最多票选项的加权占比
        Returns:
            dict: {level: 'high'|'medium'|'low', score: float, description: str}
        """
        result_counts = {}
        total_weight = 0

        for vote in votes:
            result = vote.get('result')
            if not result:
                continue

            role = vote.get('role', 'Neutral')
            weight = AGENT_WEIGHTS.get(AgentRole(role), 0.02)
            result_counts[result] = result_counts.get(result, 0) + weight
            total_weight += weight

        if total_weight == 0:
            return {'level': 'low', 'score': 0, 'description': '无有效投票'}

        max_share = max(result_counts.values()) / total_weight

        if max_share > 0.70:
            level = 'high'
            desc = f'高度共识 ({max_share:.0%} 一致)'
        elif max_share > 0.40:
            level = 'medium'
            desc = f'中度共识 ({max_share:.0%} 多数)'
        else:
            level = 'low'
            desc = f'低共识/分歧 ({max_share:.0%})'

        return {
            'level': level,
            'score': round(max_share, 4),
            'description': desc,
        }

    def _role_breakdown(self, votes):
        """按角色分组统计"""
        breakdown = {}
        for role in AgentRole:
            role_votes = [v for v in votes if v.get('role') == role.value]
            if not role_votes:
                continue

            result_counts = Counter(v.get('result') for v in role_votes if v.get('result'))
            avg_confidence = sum(v.get('confidence', 50) for v in role_votes) / len(role_votes)

            most_common = result_counts.most_common(1)
            breakdown[role.value] = {
                'count': len(role_votes),
                'weight': AGENT_WEIGHTS.get(role, 0),
                'majority_prediction': most_common[0][0] if most_common else None,
                'vote_distribution': dict(result_counts),
                'avg_confidence': round(avg_confidence, 1),
            }

        return breakdown

    def _extract_key_arguments(self, votes, top_n=5):
        """提取关键论点（按角色权重和信心排序）"""
        scored_args = []
        for vote in votes:
            reasoning = vote.get('reasoning', '').strip()
            if not reasoning:
                continue

            role = vote.get('role', 'Neutral')
            weight = AGENT_WEIGHTS.get(AgentRole(role), 0.02)
            confidence = vote.get('confidence', 50) / 100
            score = weight * confidence

            scored_args.append({
                'agent': vote.get('name', f"Agent_{vote.get('agent_id')}"),
                'role': role,
                'prediction': vote.get('result'),
                'reasoning': reasoning,
                'score': round(score, 4),
            })

        # 按得分排序取 top N
        scored_args.sort(key=lambda x: x['score'], reverse=True)
        return scored_args[:top_n]

    def dynamic_fusion(self, ml_prediction, agent_prediction, consensus):
        """动态权重融合 - 根据共识度调整 ML/Agent 权重

        Args:
            ml_prediction: ML 模型预测 {probabilities: {home, draw, away}}
            agent_prediction: Agent 投票结果 {probabilities: {HOME, DRAW, AWAY}}
            consensus: 共识度 {level, score}

        Returns:
            dict: 融合预测结果
        """
        # 根据共识度动态调整权重
        consensus_level = consensus.get('level', 'medium')
        consensus_score = consensus.get('score', 0.5)

        if consensus_level == 'high':
            ml_weight = 0.30
            agent_weight = 0.70
        elif consensus_level == 'low':
            ml_weight = 0.55
            agent_weight = 0.45
        else:
            ml_weight = self.ml_base_weight
            agent_weight = self.agent_base_weight

        # 归一化 Agent 概率到 ML 的 key 格式
        agent_probs = agent_prediction.get('probabilities', {})
        agent_normalized = {
            'home': agent_probs.get('HOME', 0),
            'draw': agent_probs.get('DRAW', 0),
            'away': agent_probs.get('AWAY', 0),
        }

        # 确保概率和为1
        agent_total = sum(agent_normalized.values())
        if agent_total > 0:
            agent_normalized = {k: v / agent_total for k, v in agent_normalized.items()}

        ml_probs = ml_prediction.get('probabilities', {'home': 0.33, 'draw': 0.33, 'away': 0.34})

        # 加权融合
        fused = {}
        for key in ['home', 'draw', 'away']:
            fused[key] = round(
                ml_weight * ml_probs.get(key, 0.33) + agent_weight * agent_normalized.get(key, 0.33),
                4,
            )

        # 归一化
        total = sum(fused.values())
        if total > 0:
            fused = {k: round(v / total, 4) for k, v in fused.items()}

        prediction_map = {'home': 'HOME', 'draw': 'DRAW', 'away': 'AWAY'}
        final_prediction = prediction_map[max(fused, key=fused.get)]

        return {
            'prediction': final_prediction,
            'probabilities': fused,
            'confidence': round(max(fused.values()), 4),
            'fusion_weights': {
                'ml': ml_weight,
                'agent': agent_weight,
            },
            'consensus_level': consensus_level,
            'consensus_score': consensus_score,
        }
