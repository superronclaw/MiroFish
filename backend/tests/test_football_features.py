"""
特征工程与数据处理单元测试
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.services.football.data_processor import FootballDataProcessor, WeatherEncoder
from app.services.football.feature_engineer import FeatureEngineer


class TestWeatherEncoder:
    def test_clear(self):
        assert WeatherEncoder.encode('clear') == 1
        assert WeatherEncoder.encode('Clear') == 1

    def test_rain(self):
        assert WeatherEncoder.encode('rain') == 6
        assert WeatherEncoder.encode('light rain') == 5
        assert WeatherEncoder.encode('heavy rain') == 7

    def test_snow(self):
        assert WeatherEncoder.encode('snow') == 9

    def test_none(self):
        assert WeatherEncoder.encode(None) == 0
        assert WeatherEncoder.encode('') == 0

    def test_unknown(self):
        assert WeatherEncoder.encode('tornado') == 0


class TestDataProcessorClean:
    @pytest.fixture
    def sample_matches(self):
        return pd.DataFrame([
            {
                'id': 1, 'match_date': '2025-01-15 15:00:00',
                'home_team_id': 10, 'away_team_id': 20,
                'home_score_ft': 2, 'away_score_ft': 1,
                'weather_condition': 'clear', 'temperature': 12,
            },
            {
                'id': 2, 'match_date': '2025-01-16 20:00:00',
                'home_team_id': 30, 'away_team_id': 40,
                'home_score_ft': 0, 'away_score_ft': 0,
                'weather_condition': 'rain', 'temperature': 8,
            },
            {
                'id': 3, 'match_date': '2025-01-17 18:00:00',
                'home_team_id': 10, 'away_team_id': 30,
                'home_score_ft': 1, 'away_score_ft': 3,
                'weather_condition': None, 'temperature': None,
            },
        ])

    def test_result_labels(self, sample_matches):
        df = FootballDataProcessor.clean_matches(sample_matches)
        assert df.loc[0, 'result'] == 'H'
        assert df.loc[1, 'result'] == 'D'
        assert df.loc[2, 'result'] == 'A'

    def test_result_codes(self, sample_matches):
        df = FootballDataProcessor.clean_matches(sample_matches)
        assert df.loc[0, 'result_code'] == 0  # H
        assert df.loc[1, 'result_code'] == 1  # D
        assert df.loc[2, 'result_code'] == 2  # A

    def test_total_goals(self, sample_matches):
        df = FootballDataProcessor.clean_matches(sample_matches)
        assert df.loc[0, 'total_goals'] == 3
        assert df.loc[1, 'total_goals'] == 0
        assert df.loc[2, 'total_goals'] == 4

    def test_over_under(self, sample_matches):
        df = FootballDataProcessor.clean_matches(sample_matches)
        assert df.loc[0, 'over_2_5'] == 1  # 3 goals > 2.5
        assert df.loc[1, 'over_2_5'] == 0  # 0 goals < 2.5
        assert df.loc[2, 'over_2_5'] == 1  # 4 goals > 2.5

    def test_btts(self, sample_matches):
        df = FootballDataProcessor.clean_matches(sample_matches)
        assert df.loc[0, 'btts'] == 1  # 2-1
        assert df.loc[1, 'btts'] == 0  # 0-0
        assert df.loc[2, 'btts'] == 1  # 1-3


class TestRecentForm:
    @pytest.fixture
    def matches_df(self):
        # Team 10 played 5 matches: W, W, D, L, W
        data = []
        base_date = datetime(2025, 3, 1)
        results = [
            (10, 20, 2, 0),  # W
            (10, 30, 1, 1),  # D
            (40, 10, 0, 3),  # W (away)
            (10, 50, 0, 1),  # L
            (10, 60, 2, 1),  # W
        ]
        for i, (home, away, hs, aws) in enumerate(results):
            data.append({
                'id': i + 1,
                'match_date': base_date - timedelta(days=(i + 1) * 3),
                'home_team_id': home, 'away_team_id': away,
                'home_score_ft': hs, 'away_score_ft': aws,
            })
        df = pd.DataFrame(data)
        df['match_date'] = pd.to_datetime(df['match_date'])
        return df

    def test_form_points(self, matches_df):
        form = FootballDataProcessor.compute_recent_form(
            matches_df, team_id=10,
            before_date=datetime(2025, 3, 2),
            n_matches=5,
        )
        # W(3) + D(1) + W(3) + L(0) + W(3) = 10
        assert form['form_points'] == 10

    def test_form_goals(self, matches_df):
        form = FootballDataProcessor.compute_recent_form(
            matches_df, team_id=10,
            before_date=datetime(2025, 3, 2),
            n_matches=5,
        )
        # scored: 2+1+3+0+2 = 8
        assert form['form_goals_scored'] == 8
        # conceded: 0+1+0+1+1 = 3
        assert form['form_goals_conceded'] == 3


class TestHeadToHead:
    @pytest.fixture
    def h2h_df(self):
        data = [
            {'id': 1, 'match_date': datetime(2025, 1, 1), 'home_team_id': 10, 'away_team_id': 20, 'home_score_ft': 2, 'away_score_ft': 1},
            {'id': 2, 'match_date': datetime(2024, 10, 1), 'home_team_id': 20, 'away_team_id': 10, 'home_score_ft': 0, 'away_score_ft': 0},
            {'id': 3, 'match_date': datetime(2024, 5, 1), 'home_team_id': 10, 'away_team_id': 20, 'home_score_ft': 1, 'away_score_ft': 1},
        ]
        df = pd.DataFrame(data)
        df['match_date'] = pd.to_datetime(df['match_date'])
        return df

    def test_h2h_stats(self, h2h_df):
        h2h = FootballDataProcessor.compute_head_to_head(
            h2h_df, home_team_id=10, away_team_id=20,
            before_date=datetime(2025, 3, 1),
        )
        assert h2h['h2h_total'] == 3
        assert h2h['h2h_home_wins'] == 1  # team 10 wins
        assert h2h['h2h_away_wins'] == 0  # team 20 wins
        assert h2h['h2h_draws'] == 2


class TestFormationParser:
    def test_standard_formation(self):
        assert FeatureEngineer._count_formation_line('4-3-3', 0) == 4
        assert FeatureEngineer._count_formation_line('4-3-3', 1) == 3
        assert FeatureEngineer._count_formation_line('4-3-3', 2) == 3

    def test_five_back(self):
        assert FeatureEngineer._count_formation_line('5-3-2', 0) == 5
        assert FeatureEngineer._count_formation_line('5-3-2', 2) == 2

    def test_four_line(self):
        assert FeatureEngineer._count_formation_line('4-2-3-1', 0) == 4
        assert FeatureEngineer._count_formation_line('4-2-3-1', 1) == 2

    def test_attack_ratio(self):
        # 4-3-3: forwards=3, mids=3 -> (3 + 3*0.5) / 10 = 0.45
        ratio = FeatureEngineer._formation_attack_ratio('4-3-3')
        assert abs(ratio - 0.45) < 0.01

    def test_defensive_ratio(self):
        # 5-4-1: forwards=1, mids=4 -> (1 + 4*0.5) / 10 = 0.3
        ratio = FeatureEngineer._formation_attack_ratio('5-4-1')
        assert abs(ratio - 0.3) < 0.01
