"""
足球数据清洗与预处理
将原始API数据转换为ML可用格式

处理流程：
1. 数据验证与缺失值处理
2. 数据标准化与编码
3. 衍生指标计算
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from ...utils.db import execute_query

logger = logging.getLogger('mirofish.football.processor')


class FootballDataProcessor:
    """数据清洗与预处理"""

    # ============= 从数据库加载原始数据 =============

    @staticmethod
    def load_matches(league_code=None, season=None, status='FINISHED'):
        """从数据库加载比赛数据为 DataFrame"""
        conditions = []
        params = []

        if status:
            conditions.append("m.status = %s")
            params.append(status)
        if league_code:
            conditions.append("l.fd_code = %s")
            params.append(league_code)
        if season:
            conditions.append("m.season = %s")
            params.append(season)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        rows = execute_query(
            f"""
            SELECT
                m.id, m.fd_match_id, m.match_date, m.matchday, m.status, m.season,
                m.home_score_ft, m.away_score_ft, m.home_score_ht, m.away_score_ht,
                m.home_formation, m.away_formation,
                m.weather_condition, m.temperature, m.humidity, m.wind_speed,
                m.referee_name,
                l.fd_code AS league_code, l.name AS league_name,
                ht.id AS home_team_id, ht.name AS home_team_name,
                at.id AS away_team_id, at.name AS away_team_name
            FROM matches m
            JOIN leagues l ON m.league_id = l.id
            JOIN teams ht ON m.home_team_id = ht.id
            JOIN teams at ON m.away_team_id = at.id
            {where}
            ORDER BY m.match_date DESC
            """,
            params if params else None,
            fetch_all=True,
        )
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    @staticmethod
    def load_team_stats(league_code=None, season=None):
        """加载球队赛季统计"""
        conditions = []
        params = []
        if league_code:
            conditions.append("l.fd_code = %s")
            params.append(league_code)
        if season:
            conditions.append("ts.season = %s")
            params.append(season)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        rows = execute_query(
            f"""
            SELECT ts.*, t.name AS team_name, l.fd_code AS league_code
            FROM team_season_stats ts
            JOIN teams t ON ts.team_id = t.id
            JOIN leagues l ON ts.league_id = l.id
            {where}
            """,
            params if params else None,
            fetch_all=True,
        )
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ============= 数据清洗 =============

    @staticmethod
    def clean_matches(df):
        """清洗比赛数据"""
        if df.empty:
            return df

        # 确保日期格式
        df['match_date'] = pd.to_datetime(df['match_date'])

        # 计算比赛结果标签
        df['result'] = df.apply(
            lambda r: 'H' if (r['home_score_ft'] or 0) > (r['away_score_ft'] or 0)
            else ('A' if (r['home_score_ft'] or 0) < (r['away_score_ft'] or 0) else 'D'),
            axis=1,
        )

        # 结果编码（用于ML）: H=0, D=1, A=2
        result_map = {'H': 0, 'D': 1, 'A': 2}
        df['result_code'] = df['result'].map(result_map)

        # 总进球数
        df['total_goals'] = (df['home_score_ft'].fillna(0) + df['away_score_ft'].fillna(0)).astype(int)

        # Over/Under 2.5
        df['over_2_5'] = (df['total_goals'] > 2.5).astype(int)

        # BTTS (Both Teams To Score)
        df['btts'] = ((df['home_score_ft'].fillna(0) > 0) & (df['away_score_ft'].fillna(0) > 0)).astype(int)

        # 天气数值编码
        df['weather_code'] = df['weather_condition'].apply(
            lambda x: WeatherEncoder.encode(x) if pd.notna(x) else 0
        )

        # 温度标准化
        df['temp_normalized'] = df['temperature'].apply(
            lambda x: (x - 15) / 15 if pd.notna(x) else 0  # 以15度为中心标准化
        )

        return df

    # ============= 近期表现计算 =============

    @staticmethod
    def compute_recent_form(df, team_id, before_date, n_matches=5):
        """计算球队近 N 场比赛的表现指标

        Returns:
            dict with: form_points, form_goals_scored, form_goals_conceded,
                       form_win_rate, form_clean_sheets, form_scoring_first
        """
        team_matches = df[
            ((df['home_team_id'] == team_id) | (df['away_team_id'] == team_id))
            & (df['match_date'] < before_date)
        ].head(n_matches)

        if team_matches.empty:
            return {
                'form_points': 0, 'form_goals_scored': 0, 'form_goals_conceded': 0,
                'form_win_rate': 0, 'form_clean_sheets': 0, 'form_avg_goals': 0,
            }

        points = 0
        goals_scored = 0
        goals_conceded = 0
        clean_sheets = 0

        for _, m in team_matches.iterrows():
            is_home = m['home_team_id'] == team_id
            gs = m['home_score_ft'] if is_home else m['away_score_ft']
            gc = m['away_score_ft'] if is_home else m['home_score_ft']
            gs = gs or 0
            gc = gc or 0

            goals_scored += gs
            goals_conceded += gc
            if gc == 0:
                clean_sheets += 1
            if gs > gc:
                points += 3
            elif gs == gc:
                points += 1

        n = len(team_matches)
        return {
            'form_points': points,
            'form_goals_scored': goals_scored,
            'form_goals_conceded': goals_conceded,
            'form_win_rate': round(sum(
                1 for _, m in team_matches.iterrows()
                if (
                    ((m['home_score_ft'] or 0) > (m['away_score_ft'] or 0) and m['home_team_id'] == team_id)
                    or ((m['away_score_ft'] or 0) > (m['home_score_ft'] or 0) and m['away_team_id'] == team_id)
                )
            ) / n, 3) if n else 0,
            'form_clean_sheets': clean_sheets,
            'form_avg_goals': round(goals_scored / n, 2) if n else 0,
        }

    # ============= 历史交锋 =============

    @staticmethod
    def compute_head_to_head(df, home_team_id, away_team_id, before_date, n_matches=10):
        """计算两队历史交锋统计

        Returns:
            dict with: h2h_total, h2h_home_wins, h2h_away_wins, h2h_draws,
                       h2h_home_goals_avg, h2h_away_goals_avg, h2h_total_goals_avg
        """
        h2h = df[
            (
                ((df['home_team_id'] == home_team_id) & (df['away_team_id'] == away_team_id))
                | ((df['home_team_id'] == away_team_id) & (df['away_team_id'] == home_team_id))
            )
            & (df['match_date'] < before_date)
        ].head(n_matches)

        if h2h.empty:
            return {
                'h2h_total': 0, 'h2h_home_wins': 0, 'h2h_away_wins': 0, 'h2h_draws': 0,
                'h2h_home_goals_avg': 0, 'h2h_away_goals_avg': 0, 'h2h_total_goals_avg': 0,
            }

        home_wins = 0
        away_wins = 0
        draws = 0
        team1_goals = 0  # home_team_id 的进球
        team2_goals = 0  # away_team_id 的进球

        for _, m in h2h.iterrows():
            hs = m['home_score_ft'] or 0
            aws = m['away_score_ft'] or 0

            if m['home_team_id'] == home_team_id:
                team1_goals += hs
                team2_goals += aws
                if hs > aws:
                    home_wins += 1
                elif hs < aws:
                    away_wins += 1
                else:
                    draws += 1
            else:
                team1_goals += aws
                team2_goals += hs
                if aws > hs:
                    home_wins += 1
                elif aws < hs:
                    away_wins += 1
                else:
                    draws += 1

        n = len(h2h)
        return {
            'h2h_total': n,
            'h2h_home_wins': home_wins,
            'h2h_away_wins': away_wins,
            'h2h_draws': draws,
            'h2h_home_goals_avg': round(team1_goals / n, 2),
            'h2h_away_goals_avg': round(team2_goals / n, 2),
            'h2h_total_goals_avg': round((team1_goals + team2_goals) / n, 2),
        }


class WeatherEncoder:
    """天气条件编码（用于ML特征）"""

    WEATHER_MAP = {
        'clear': 1,
        'clouds': 2,
        'few clouds': 2,
        'scattered clouds': 2,
        'broken clouds': 3,
        'overcast clouds': 3,
        'drizzle': 4,
        'light rain': 5,
        'rain': 6,
        'heavy rain': 7,
        'thunderstorm': 8,
        'snow': 9,
        'mist': 3,
        'fog': 4,
    }

    @classmethod
    def encode(cls, condition):
        if not condition:
            return 0
        return cls.WEATHER_MAP.get(condition.lower().strip(), 0)
