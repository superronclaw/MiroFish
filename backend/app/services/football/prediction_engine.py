"""
双层预测引擎
Layer 1: ML 模型预测 (XGBoost, Poisson, Logistic)
Layer 2: 群体智能投票 (50 agents, 18 rounds, OASIS)
融合: 动态权重 (共识度自适应)

完整预测流程:
1. 特征提取
2. ML 模型预测 (Layer 1)
3. 生成 Agent 上下文
4. OASIS 模拟投票 (Layer 2)
5. 投票汇总
6. 动态权重融合
7. 存储预测结果
"""

import logging
import json
from datetime import datetime

from ...config import Config
from ...utils.db import execute_query
from ...utils.llm_client import LLMClient
from .feature_engineer import FeatureEngineer
from .ml_trainer import FootballMLTrainer
from .agent_profile_generator import generate_agent_profiles, generate_match_context_prompt
from .voting_system import VotingSystem

logger = logging.getLogger('mirofish.football.prediction')


class PredictionEngine:
    """双层预测引擎 - ML + 群体智能"""

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.ml_trainer = FootballMLTrainer()
        self.voting_system = VotingSystem()
        self.llm_client = LLMClient()
        self.agent_profiles = generate_agent_profiles()

    def predict_match(self, match_id):
        """完整预测流程

        Args:
            match_id: 比赛数据库 ID

        Returns:
            dict: 完整预测结果
        """
        logger.info(f"开始预测比赛: match_id={match_id}")

        # 获取比赛信息
        match = self._get_match_info(match_id)
        if not match:
            return {'error': f'比赛不存在: {match_id}'}

        # 1. 特征提取
        features = self.feature_engineer.extract_prediction_features(match_id)
        if not features:
            return {'error': '特征提取失败'}

        # 2. ML 模型预测 (Layer 1)
        ml_result = self._ml_predict(features)

        # 3. 群体智能投票 (Layer 2)
        agent_result = self._agent_predict(match, features, ml_result)

        # 4. 动态权重融合
        if ml_result and agent_result:
            consensus = agent_result.get('consensus', {'level': 'medium', 'score': 0.5})
            final = self.voting_system.dynamic_fusion(
                ml_result.get('match_result', {}),
                agent_result.get('result_prediction', {}),
                consensus,
            )
        elif ml_result:
            final = {
                'prediction': ml_result.get('match_result', {}).get('prediction'),
                'probabilities': ml_result.get('match_result', {}).get('probabilities', {}),
                'confidence': ml_result.get('match_result', {}).get('confidence', 0),
                'fusion_weights': {'ml': 1.0, 'agent': 0.0},
                'consensus_level': 'n/a',
            }
        else:
            final = {
                'prediction': agent_result.get('result_prediction', {}).get('prediction') if agent_result else None,
                'probabilities': {},
                'confidence': 0,
                'fusion_weights': {'ml': 0.0, 'agent': 1.0},
            }

        # 5. 组装完整预测
        prediction = {
            'match_id': match_id,
            'match': {
                'home_team': match.get('home_team_name'),
                'away_team': match.get('away_team_name'),
                'league': match.get('league_code'),
                'date': str(match.get('match_date')),
            },
            'ml_prediction': ml_result,
            'agent_prediction': agent_result,
            'combined_prediction': final,
            'predicted_at': datetime.utcnow().isoformat(),
        }

        # 6. 存储预测结果
        self._save_prediction(match_id, prediction)

        logger.info(
            f"预测完成: {match.get('home_team_name')} vs {match.get('away_team_name')} "
            f"-> {final.get('prediction')} (conf={final.get('confidence', 0):.2%})"
        )

        return prediction

    def _get_match_info(self, match_id):
        """获取比赛详细信息"""
        return execute_query(
            """
            SELECT m.*,
                   l.fd_code AS league_code, l.name AS league_name,
                   ht.name AS home_team_name, at.name AS away_team_name,
                   ht.venue_name
            FROM matches m
            JOIN leagues l ON m.league_id = l.id
            JOIN teams ht ON m.home_team_id = ht.id
            JOIN teams at ON m.away_team_id = at.id
            WHERE m.id = %s
            """,
            (match_id,),
            fetch_one=True,
        )

    def _ml_predict(self, features):
        """Layer 1: ML 模型预测"""
        try:
            result = {}

            # 比赛结果
            match_result = self.ml_trainer.predict_match_result(features)
            if match_result:
                result['match_result'] = match_result

            # 比分预测
            score = self.ml_trainer.predict_score(features)
            if score:
                result['score'] = score

            # Over/Under
            ou = self.ml_trainer.predict_over_under(features)
            if ou:
                result['over_under'] = ou

            return result if result else None

        except Exception as e:
            logger.error(f"ML 预测失败: {e}")
            return None

    def _agent_predict(self, match, features, ml_prediction=None):
        """Layer 2: 群体智能投票预测

        使用 LLM 让每个 Agent 根据其角色和上下文进行预测
        """
        try:
            # 生成比赛上下文
            context = generate_match_context_prompt(
                match, features,
                ml_prediction.get('match_result') if ml_prediction else None,
            )

            # 收集所有 Agent 投票
            agent_votes = []
            for profile in self.agent_profiles:
                try:
                    vote = self._get_agent_vote(profile, context)
                    if vote:
                        vote['agent_id'] = profile['agent_id']
                        vote['name'] = profile['name']
                        vote['role'] = profile['role']
                        vote['weight'] = profile['weight']
                        agent_votes.append(vote)
                except Exception as e:
                    logger.debug(f"Agent {profile['name']} 投票失败: {e}")

            if not agent_votes:
                logger.warning("没有收集到有效的 Agent 投票")
                return None

            logger.info(f"收集到 {len(agent_votes)}/{len(self.agent_profiles)} 个 Agent 投票")

            # 汇总投票
            return self.voting_system.aggregate_votes(agent_votes)

        except Exception as e:
            logger.error(f"群体智能预测失败: {e}")
            return None

    def _get_agent_vote(self, profile, context):
        """获取单个 Agent 的投票

        Args:
            profile: Agent profile dict
            context: 比赛上下文提示词

        Returns:
            dict: {result, confidence, score, over_under, reasoning}
        """
        system_prompt = profile['system_prompt']
        user_prompt = context

        response = self.llm_client.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
        )

        if not response:
            return None

        # 解析响应
        try:
            if isinstance(response, str):
                vote = json.loads(response)
            else:
                vote = response

            # 标准化结果
            result = vote.get('result', '').upper()
            if result not in ('HOME', 'DRAW', 'AWAY'):
                return None

            return {
                'result': result,
                'confidence': min(max(int(vote.get('confidence', 50)), 0), 100),
                'score': vote.get('score', ''),
                'over_under': vote.get('over_under', '').upper(),
                'reasoning': vote.get('reasoning', ''),
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.debug(f"Agent 响应解析失败: {e}")
            return None

    def _save_prediction(self, match_id, prediction):
        """存储预测结果到数据库"""
        try:
            combined = prediction.get('combined_prediction', {})
            ml_pred = prediction.get('ml_prediction', {})
            agent_pred = prediction.get('agent_prediction', {})

            execute_query(
                """
                INSERT INTO predictions (
                    match_id, prediction_type,
                    ml_home_prob, ml_draw_prob, ml_away_prob,
                    ml_predicted_home_goals, ml_predicted_away_goals,
                    agent_home_prob, agent_draw_prob, agent_away_prob,
                    combined_home_prob, combined_draw_prob, combined_away_prob,
                    predicted_result, predicted_score,
                    confidence, consensus_level,
                    ml_weight, agent_weight,
                    agent_voting_details, agent_key_arguments
                ) VALUES (
                    %s, 'full',
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s
                )
                ON CONFLICT (match_id, prediction_type) DO UPDATE SET
                    ml_home_prob = EXCLUDED.ml_home_prob,
                    ml_draw_prob = EXCLUDED.ml_draw_prob,
                    ml_away_prob = EXCLUDED.ml_away_prob,
                    agent_home_prob = EXCLUDED.agent_home_prob,
                    agent_draw_prob = EXCLUDED.agent_draw_prob,
                    agent_away_prob = EXCLUDED.agent_away_prob,
                    combined_home_prob = EXCLUDED.combined_home_prob,
                    combined_draw_prob = EXCLUDED.combined_draw_prob,
                    combined_away_prob = EXCLUDED.combined_away_prob,
                    predicted_result = EXCLUDED.predicted_result,
                    predicted_score = EXCLUDED.predicted_score,
                    confidence = EXCLUDED.confidence,
                    consensus_level = EXCLUDED.consensus_level,
                    ml_weight = EXCLUDED.ml_weight,
                    agent_weight = EXCLUDED.agent_weight,
                    agent_voting_details = EXCLUDED.agent_voting_details,
                    agent_key_arguments = EXCLUDED.agent_key_arguments,
                    updated_at = NOW()
                """,
                (
                    match_id,
                    # ML probabilities
                    ml_pred.get('match_result', {}).get('probabilities', {}).get('home'),
                    ml_pred.get('match_result', {}).get('probabilities', {}).get('draw'),
                    ml_pred.get('match_result', {}).get('probabilities', {}).get('away'),
                    # ML score prediction
                    ml_pred.get('score', {}).get('expected_home_goals'),
                    ml_pred.get('score', {}).get('expected_away_goals'),
                    # Agent probabilities
                    agent_pred.get('result_prediction', {}).get('probabilities', {}).get('HOME') if agent_pred else None,
                    agent_pred.get('result_prediction', {}).get('probabilities', {}).get('DRAW') if agent_pred else None,
                    agent_pred.get('result_prediction', {}).get('probabilities', {}).get('AWAY') if agent_pred else None,
                    # Combined
                    combined.get('probabilities', {}).get('home'),
                    combined.get('probabilities', {}).get('draw'),
                    combined.get('probabilities', {}).get('away'),
                    combined.get('prediction'),
                    ml_pred.get('score', {}).get('most_likely_score'),
                    combined.get('confidence'),
                    combined.get('consensus_level'),
                    combined.get('fusion_weights', {}).get('ml'),
                    combined.get('fusion_weights', {}).get('agent'),
                    # JSON details
                    json.dumps(agent_pred.get('role_breakdown', {}), ensure_ascii=False) if agent_pred else None,
                    json.dumps(agent_pred.get('key_arguments', []), ensure_ascii=False) if agent_pred else None,
                ),
            )
            logger.debug(f"预测结果已存储: match_id={match_id}")

        except Exception as e:
            logger.error(f"预测结果存储失败: {e}")

    def get_prediction(self, match_id):
        """获取已有的预测结果"""
        return execute_query(
            """
            SELECT p.*, m.match_date,
                   ht.name AS home_team_name, at.name AS away_team_name,
                   l.fd_code AS league_code
            FROM predictions p
            JOIN matches m ON p.match_id = m.id
            JOIN teams ht ON m.home_team_id = ht.id
            JOIN teams at ON m.away_team_id = at.id
            JOIN leagues l ON m.league_id = l.id
            WHERE p.match_id = %s
            ORDER BY p.updated_at DESC
            LIMIT 1
            """,
            (match_id,),
            fetch_one=True,
        )

    def batch_predict(self, league_code=None, days_ahead=7):
        """批量预测未来比赛

        Args:
            league_code: 联赛代码 (可选)
            days_ahead: 预测未来天数

        Returns:
            list[dict]: 预测结果列表
        """
        conditions = [
            "m.status = 'SCHEDULED'",
            "m.match_date BETWEEN NOW() AND NOW() + INTERVAL '%s days'",
        ]
        params = [days_ahead]

        if league_code:
            conditions.append("l.fd_code = %s")
            params.append(league_code)

        upcoming = execute_query(
            f"""
            SELECT m.id FROM matches m
            JOIN leagues l ON m.league_id = l.id
            WHERE {' AND '.join(conditions)}
            ORDER BY m.match_date
            """,
            params,
            fetch_all=True,
        )

        if not upcoming:
            logger.info("没有未来比赛需要预测")
            return []

        results = []
        for match in upcoming:
            try:
                prediction = self.predict_match(match['id'])
                results.append(prediction)
            except Exception as e:
                logger.error(f"批量预测失败 (match_id={match['id']}): {e}")

        logger.info(f"批量预测完成: {len(results)}/{len(upcoming)} 场")
        return results
