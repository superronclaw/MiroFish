"""
特征工程模块
将原始数据转换为 80-100 维 ML 特征向量

8大特征类别：
1. 场地因素 (8 features)
2. 天气/环境 (6 features)
3. 阵容/阵型 (10 features)
4. 球员个人统计 (12 features)
5. 近期表现趋势 (16 features)
6. 历史交锋 (10 features)
7. 联赛排名/积分 (12 features)
8. 裁判因素 (8 features)

总计: ~82 维特征
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from .data_processor import FootballDataProcessor, WeatherEncoder
from ...utils.db import execute_query

logger = logging.getLogger('mirofish.football.features')


class FeatureEngineer:
    """特征工程 - 构建 ML 特征矩阵"""

    # 特征名称列表（保持顺序一致）
    FEATURE_NAMES = []

    def __init__(self):
        self.processor = FootballDataProcessor()

    def build_feature_matrix(self, league_code=None, season=None):
        """构建完整特征矩阵，用于模型训练

        Returns:
            X: pd.DataFrame (特征矩阵)
            y_result: pd.Series (比赛结果: 0=H, 1=D, 2=A)
            y_goals: pd.Series (总进球数)
            y_over25: pd.Series (大于2.5球: 0/1)
            match_ids: pd.Series (比赛ID)
        """
        # 加载历史比赛
        df = self.processor.load_matches(league_code=league_code, season=season, status='FINISHED')
        if df.empty:
            logger.warning("没有可用的比赛数据")
            return None, None, None, None, None

        df = self.processor.clean_matches(df)
        all_matches_df = self.processor.load_matches(league_code=league_code, status='FINISHED')
        all_matches_df = self.processor.clean_matches(all_matches_df)

        features_list = []
        valid_indices = []

        for idx, match in df.iterrows():
            try:
                features = self._extract_features(match, all_matches_df)
                if features:
                    features_list.append(features)
                    valid_indices.append(idx)
            except Exception as e:
                logger.debug(f"特征提取失败 (match_id={match.get('id')}): {e}")

        if not features_list:
            logger.warning("未能提取任何有效特征")
            return None, None, None, None, None

        X = pd.DataFrame(features_list)
        valid_df = df.loc[valid_indices].reset_index(drop=True)

        FeatureEngineer.FEATURE_NAMES = list(X.columns)
        logger.info(f"特征矩阵构建完成: {X.shape[0]} 场比赛, {X.shape[1]} 维特征")

        return (
            X,
            valid_df['result_code'],
            valid_df['total_goals'],
            valid_df['over_2_5'],
            valid_df['id'],
        )

    def extract_prediction_features(self, match_id):
        """为单场比赛提取预测特征

        Args:
            match_id: 比赛数据库ID

        Returns:
            dict: 特征字典
        """
        match = execute_query(
            """
            SELECT m.*, l.fd_code AS league_code,
                   ht.name AS home_team_name, at.name AS away_team_name
            FROM matches m
            JOIN leagues l ON m.league_id = l.id
            JOIN teams ht ON m.home_team_id = ht.id
            JOIN teams at ON m.away_team_id = at.id
            WHERE m.id = %s
            """,
            (match_id,),
            fetch_one=True,
        )
        if not match:
            return None

        # 加载所有历史比赛用于计算
        all_df = self.processor.load_matches(league_code=match['league_code'], status='FINISHED')
        all_df = self.processor.clean_matches(all_df)

        return self._extract_features(match, all_df)

    def _extract_features(self, match, all_matches_df):
        """从单场比赛提取全部特征"""
        features = {}
        match_date = pd.to_datetime(match.get('match_date'))
        home_id = match.get('home_team_id')
        away_id = match.get('away_team_id')

        # 1. 场地因素 (8 features)
        features.update(self._venue_features(home_id))

        # 2. 天气/环境 (6 features)
        features.update(self._weather_features(match))

        # 3. 阵容/阵型 (10 features)
        features.update(self._formation_features(match))

        # 4. 球员个人统计 (12 features)
        features.update(self._player_features(home_id, away_id))

        # 5. 近期表现趋势 (16 features)
        features.update(self._form_features(all_matches_df, home_id, away_id, match_date))

        # 6. 历史交锋 (10 features)
        features.update(self._h2h_features(all_matches_df, home_id, away_id, match_date))

        # 7. 联赛排名/积分 (12 features)
        features.update(self._standings_features(home_id, away_id, match.get('league_code')))

        # 8. 裁判因素 (8 features)
        features.update(self._referee_features(match.get('referee_name')))

        return features

    # ============= 1. 场地因素 =============

    def _venue_features(self, home_team_id):
        """场地特征: 容量、海拔、草地类型、主场优势等"""
        venue = execute_query(
            """
            SELECT v.* FROM venues v
            JOIN teams t ON t.venue_name = v.name
            WHERE t.id = %s
            """,
            (home_team_id,),
            fetch_one=True,
        )

        if venue:
            return {
                'venue_capacity': venue.get('capacity', 0) or 0,
                'venue_capacity_log': np.log1p(venue.get('capacity', 0) or 0),
                'venue_altitude': venue.get('altitude', 0) or 0,
                'venue_surface_natural': 1 if (venue.get('surface') or '').lower() == 'grass' else 0,
                'venue_latitude': venue.get('latitude', 0) or 0,
                'venue_longitude': venue.get('longitude', 0) or 0,
                'venue_roof': 1 if venue.get('roof') else 0,
                'venue_built_year': venue.get('built_year', 2000) or 2000,
            }
        return {
            'venue_capacity': 0, 'venue_capacity_log': 0, 'venue_altitude': 0,
            'venue_surface_natural': 1, 'venue_latitude': 0, 'venue_longitude': 0,
            'venue_roof': 0, 'venue_built_year': 2000,
        }

    # ============= 2. 天气/环境 =============

    def _weather_features(self, match):
        """天气特征: 温度、湿度、风速、天气类型编码"""
        temp = match.get('temperature') or 15
        humidity = match.get('humidity') or 50
        wind = match.get('wind_speed') or 0
        condition = match.get('weather_condition') or ''

        # 天气影响得分
        impact = 0
        if temp < 5 or temp > 32:
            impact += 0.3
        if wind > 30:
            impact += 0.3
        if humidity > 85:
            impact += 0.2
        if 'rain' in condition.lower() or 'snow' in condition.lower():
            impact += 0.2

        return {
            'weather_temp': temp,
            'weather_temp_normalized': (temp - 15) / 15,
            'weather_humidity': humidity / 100,
            'weather_wind': wind,
            'weather_code': WeatherEncoder.encode(condition),
            'weather_impact': min(impact, 1.0),
        }

    # ============= 3. 阵容/阵型 =============

    def _formation_features(self, match):
        """阵型特征: 阵型编码、攻击性/防守性指标"""
        home_f = match.get('home_formation') or '4-4-2'
        away_f = match.get('away_formation') or '4-4-2'

        return {
            'home_defenders': self._count_formation_line(home_f, 0),
            'home_midfielders': self._count_formation_line(home_f, 1),
            'home_forwards': self._count_formation_line(home_f, 2),
            'away_defenders': self._count_formation_line(away_f, 0),
            'away_midfielders': self._count_formation_line(away_f, 1),
            'away_forwards': self._count_formation_line(away_f, 2),
            'home_attack_ratio': self._formation_attack_ratio(home_f),
            'away_attack_ratio': self._formation_attack_ratio(away_f),
            'formation_diff_attack': self._formation_attack_ratio(home_f) - self._formation_attack_ratio(away_f),
            'formation_diff_defense': self._count_formation_line(home_f, 0) - self._count_formation_line(away_f, 0),
        }

    @staticmethod
    def _count_formation_line(formation, line_index):
        """解析阵型字符串 (e.g. '4-3-3') 返回指定线球员数"""
        try:
            parts = [int(p) for p in formation.split('-')]
            if line_index < len(parts):
                return parts[line_index]
        except (ValueError, AttributeError):
            pass
        return 4  # 默认值

    @staticmethod
    def _formation_attack_ratio(formation):
        """计算阵型攻击性指标 (前锋+中场攻击型) / 总数"""
        try:
            parts = [int(p) for p in formation.split('-')]
            total = sum(parts)
            if total == 0:
                return 0.5
            # 前锋 + 一半中场视为攻击力
            forwards = parts[-1] if len(parts) > 0 else 0
            mids = parts[1] if len(parts) > 2 else 0
            return round((forwards + mids * 0.5) / total, 3)
        except (ValueError, AttributeError):
            return 0.5

    # ============= 4. 球员个人统计 =============

    def _player_features(self, home_team_id, away_team_id):
        """球员汇总特征: 队内总进球、助攻、关键球员缺阵数等"""
        home_stats = self._get_team_player_stats(home_team_id)
        away_stats = self._get_team_player_stats(away_team_id)
        home_injuries = self._count_injuries(home_team_id)
        away_injuries = self._count_injuries(away_team_id)

        return {
            'home_squad_goals': home_stats.get('total_goals', 0),
            'home_squad_assists': home_stats.get('total_assists', 0),
            'home_squad_avg_rating': home_stats.get('avg_rating', 0),
            'home_injuries_count': home_injuries,
            'home_key_player_missing': 1 if home_injuries >= 3 else 0,
            'away_squad_goals': away_stats.get('total_goals', 0),
            'away_squad_assists': away_stats.get('total_assists', 0),
            'away_squad_avg_rating': away_stats.get('avg_rating', 0),
            'away_injuries_count': away_injuries,
            'away_key_player_missing': 1 if away_injuries >= 3 else 0,
            'squad_goals_diff': home_stats.get('total_goals', 0) - away_stats.get('total_goals', 0),
            'injuries_diff': home_injuries - away_injuries,
        }

    def _get_team_player_stats(self, team_id):
        """获取球队球员汇总统计"""
        result = execute_query(
            """
            SELECT
                COALESCE(SUM(pms.goals), 0) AS total_goals,
                COALESCE(SUM(pms.assists), 0) AS total_assists,
                COALESCE(AVG(pms.rating), 0) AS avg_rating
            FROM player_match_stats pms
            JOIN players p ON pms.player_id = p.id
            WHERE p.team_id = %s
            """,
            (team_id,),
            fetch_one=True,
        )
        return result if result else {'total_goals': 0, 'total_assists': 0, 'avg_rating': 0}

    def _count_injuries(self, team_id):
        """统计球队当前伤病球员数"""
        result = execute_query(
            """
            SELECT COUNT(*) AS cnt FROM injuries i
            JOIN players p ON i.player_id = p.id
            WHERE p.team_id = %s AND i.status = 'active'
            """,
            (team_id,),
            fetch_one=True,
        )
        return result['cnt'] if result else 0

    # ============= 5. 近期表现趋势 =============

    def _form_features(self, all_df, home_id, away_id, match_date):
        """近期表现: 近5场、近10场表现指标"""
        home_5 = self.processor.compute_recent_form(all_df, home_id, match_date, n_matches=5)
        home_10 = self.processor.compute_recent_form(all_df, home_id, match_date, n_matches=10)
        away_5 = self.processor.compute_recent_form(all_df, away_id, match_date, n_matches=5)
        away_10 = self.processor.compute_recent_form(all_df, away_id, match_date, n_matches=10)

        return {
            'home_form5_points': home_5['form_points'],
            'home_form5_goals': home_5['form_goals_scored'],
            'home_form5_conceded': home_5['form_goals_conceded'],
            'home_form5_winrate': home_5['form_win_rate'],
            'home_form10_points': home_10['form_points'],
            'home_form10_goals': home_10['form_goals_scored'],
            'home_form10_avg_goals': home_10['form_avg_goals'],
            'home_form10_clean_sheets': home_10['form_clean_sheets'],
            'away_form5_points': away_5['form_points'],
            'away_form5_goals': away_5['form_goals_scored'],
            'away_form5_conceded': away_5['form_goals_conceded'],
            'away_form5_winrate': away_5['form_win_rate'],
            'away_form10_points': away_10['form_points'],
            'away_form10_goals': away_10['form_goals_scored'],
            'away_form10_avg_goals': away_10['form_avg_goals'],
            'away_form10_clean_sheets': away_10['form_clean_sheets'],
        }

    # ============= 6. 历史交锋 =============

    def _h2h_features(self, all_df, home_id, away_id, match_date):
        """历史交锋特征"""
        h2h = self.processor.compute_head_to_head(all_df, home_id, away_id, match_date)

        total = max(h2h['h2h_total'], 1)
        return {
            'h2h_total_matches': h2h['h2h_total'],
            'h2h_home_wins': h2h['h2h_home_wins'],
            'h2h_away_wins': h2h['h2h_away_wins'],
            'h2h_draws': h2h['h2h_draws'],
            'h2h_home_win_rate': round(h2h['h2h_home_wins'] / total, 3),
            'h2h_away_win_rate': round(h2h['h2h_away_wins'] / total, 3),
            'h2h_home_goals_avg': h2h['h2h_home_goals_avg'],
            'h2h_away_goals_avg': h2h['h2h_away_goals_avg'],
            'h2h_total_goals_avg': h2h['h2h_total_goals_avg'],
            'h2h_dominance': round((h2h['h2h_home_wins'] - h2h['h2h_away_wins']) / total, 3),
        }

    # ============= 7. 联赛排名/积分 =============

    def _standings_features(self, home_id, away_id, league_code):
        """联赛排名与积分差特征"""
        home_stats = execute_query(
            """
            SELECT * FROM team_season_stats
            WHERE team_id = %s
            ORDER BY season DESC LIMIT 1
            """,
            (home_id,),
            fetch_one=True,
        )
        away_stats = execute_query(
            """
            SELECT * FROM team_season_stats
            WHERE team_id = %s
            ORDER BY season DESC LIMIT 1
            """,
            (away_id,),
            fetch_one=True,
        )

        h = home_stats or {}
        a = away_stats or {}

        h_played = max(h.get('played', 0) or 0, 1)
        a_played = max(a.get('played', 0) or 0, 1)

        return {
            'home_position': h.get('position', 10) or 10,
            'away_position': a.get('position', 10) or 10,
            'position_diff': (h.get('position', 10) or 10) - (a.get('position', 10) or 10),
            'home_points': h.get('points', 0) or 0,
            'away_points': a.get('points', 0) or 0,
            'points_diff': (h.get('points', 0) or 0) - (a.get('points', 0) or 0),
            'home_goal_diff': h.get('goal_difference', 0) or 0,
            'away_goal_diff': a.get('goal_difference', 0) or 0,
            'home_ppg': round((h.get('points', 0) or 0) / h_played, 2),
            'away_ppg': round((a.get('points', 0) or 0) / a_played, 2),
            'home_gf_per_match': round((h.get('goals_for', 0) or 0) / h_played, 2),
            'away_gf_per_match': round((a.get('goals_for', 0) or 0) / a_played, 2),
        }

    # ============= 8. 裁判因素 =============

    def _referee_features(self, referee_name):
        """裁判特征: 平均黄牌、红牌、点球、主场偏向等"""
        if not referee_name:
            return {
                'ref_avg_yellows': 0, 'ref_avg_reds': 0, 'ref_avg_penalties': 0,
                'ref_home_win_rate': 0.46, 'ref_total_matches': 0,
                'ref_avg_fouls': 0, 'ref_card_strictness': 0, 'ref_experience': 0,
            }

        ref_stats = execute_query(
            """
            SELECT
                COUNT(*) AS total_matches,
                COALESCE(AVG(yellow_cards), 0) AS avg_yellows,
                COALESCE(AVG(red_cards), 0) AS avg_reds,
                COALESCE(AVG(penalties_awarded), 0) AS avg_penalties,
                COALESCE(AVG(fouls), 0) AS avg_fouls,
                COALESCE(
                    SUM(CASE WHEN home_win THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0),
                    0.46
                ) AS home_win_rate
            FROM referee_match_records r
            JOIN referees ref ON r.referee_id = ref.id
            WHERE ref.name = %s
            """,
            (referee_name,),
            fetch_one=True,
        )

        if not ref_stats or ref_stats['total_matches'] == 0:
            return {
                'ref_avg_yellows': 0, 'ref_avg_reds': 0, 'ref_avg_penalties': 0,
                'ref_home_win_rate': 0.46, 'ref_total_matches': 0,
                'ref_avg_fouls': 0, 'ref_card_strictness': 0, 'ref_experience': 0,
            }

        total = ref_stats['total_matches']
        return {
            'ref_avg_yellows': round(float(ref_stats['avg_yellows']), 2),
            'ref_avg_reds': round(float(ref_stats['avg_reds']), 3),
            'ref_avg_penalties': round(float(ref_stats['avg_penalties']), 3),
            'ref_home_win_rate': round(float(ref_stats['home_win_rate']), 3),
            'ref_total_matches': total,
            'ref_avg_fouls': round(float(ref_stats['avg_fouls']), 1),
            'ref_card_strictness': round(
                (float(ref_stats['avg_yellows']) + float(ref_stats['avg_reds']) * 3) / 10, 3
            ),
            'ref_experience': min(total / 100, 1.0),  # 归一化到 0-1
        }
