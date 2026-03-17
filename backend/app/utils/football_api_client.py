"""
Football Data API Client
支持 football-data.org (主) 和 API-Football (備選)

主數據源: https://api.football-data.org/v4/
備選數據源: https://v3.football.api-sports.io/
"""

import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date

import requests

logger = logging.getLogger('mirofish.football_api')


class FootballDataClient:
    """football-data.org API Client (免費層: 10 requests/min)"""

    BASE_URL = "https://api.football-data.org/v4"

    # 五大聯賽代碼
    LEAGUE_CODES = {
        'PL': 'Premier League',
        'PD': 'La Liga',
        'SA': 'Serie A',
        'BL1': 'Bundesliga',
        'FL1': 'Ligue 1',
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-Auth-Token': api_key,
            'Content-Type': 'application/json'
        })
        self._last_request_time = 0
        self._min_interval = 6.5  # ~10 requests per minute

    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request with rate limiting"""
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                logger.warning("Rate limit hit, waiting 60s...")
                time.sleep(60)
                return self._get(endpoint, params)
            logger.error(f"HTTP error {response.status_code}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    # =================== 聯賽 ===================

    def get_competitions(self) -> List[Dict]:
        """獲取所有可用聯賽"""
        data = self._get("/competitions")
        return data.get('competitions', [])

    def get_competition(self, code: str) -> Dict:
        """獲取指定聯賽信息"""
        return self._get(f"/competitions/{code}")

    def get_standings(self, code: str) -> Dict:
        """獲取聯賽積分榜"""
        return self._get(f"/competitions/{code}/standings")

    def get_top_scorers(self, code: str, limit: int = 20) -> Dict:
        """獲取射手榜"""
        return self._get(f"/competitions/{code}/scorers", params={'limit': limit})

    # =================== 球隊 ===================

    def get_teams(self, competition_code: str) -> List[Dict]:
        """獲取聯賽所有球隊"""
        data = self._get(f"/competitions/{competition_code}/teams")
        return data.get('teams', [])

    def get_team(self, team_id: int) -> Dict:
        """獲取球隊詳情"""
        return self._get(f"/teams/{team_id}")

    def get_team_matches(
        self,
        team_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """獲取球隊比賽列表"""
        params = {'limit': limit}
        if date_from:
            params['dateFrom'] = date_from
        if date_to:
            params['dateTo'] = date_to
        if status:
            params['status'] = status
        data = self._get(f"/teams/{team_id}/matches", params=params)
        return data.get('matches', [])

    # =================== 比賽 ===================

    def get_matches(
        self,
        competition_code: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        matchday: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """獲取比賽列表"""
        params = {}
        if date_from:
            params['dateFrom'] = date_from
        if date_to:
            params['dateTo'] = date_to
        if matchday:
            params['matchday'] = matchday
        if status:
            params['status'] = status
        data = self._get(f"/competitions/{competition_code}/matches", params=params)
        return data.get('matches', [])

    def get_match(self, match_id: int) -> Dict:
        """獲取比賽詳情（包括陣容、裁判等）"""
        return self._get(f"/matches/{match_id}")

    def get_head_to_head(self, match_id: int, limit: int = 10) -> Dict:
        """獲取歷史交鋒記錄"""
        return self._get(f"/matches/{match_id}/head2head", params={'limit': limit})

    # =================== 球員 ===================

    def get_person(self, person_id: int) -> Dict:
        """獲取球員/教練詳情"""
        return self._get(f"/persons/{person_id}")

    # =================== 工具方法 ===================

    def get_upcoming_matches(self, competition_code: str, days: int = 7) -> List[Dict]:
        """獲取未來 N 天的比賽"""
        today = date.today().isoformat()
        from datetime import timedelta
        future = (date.today() + timedelta(days=days)).isoformat()
        return self.get_matches(
            competition_code,
            date_from=today,
            date_to=future,
            status='SCHEDULED'
        )

    def get_recent_results(self, competition_code: str, days: int = 7) -> List[Dict]:
        """獲取最近 N 天的比賽結果"""
        from datetime import timedelta
        today = date.today().isoformat()
        past = (date.today() - timedelta(days=days)).isoformat()
        return self.get_matches(
            competition_code,
            date_from=past,
            date_to=today,
            status='FINISHED'
        )

    def get_all_league_data(self, competition_code: str) -> Dict[str, Any]:
        """一次性獲取聯賽完整數據（球隊、積分榜、射手榜）"""
        logger.info(f"Fetching full league data for {competition_code}...")
        teams = self.get_teams(competition_code)
        standings = self.get_standings(competition_code)
        scorers = self.get_top_scorers(competition_code)
        return {
            'teams': teams,
            'standings': standings,
            'scorers': scorers,
            'competition_code': competition_code
        }


class APIFootballClient:
    """API-Football Client (備選, 免費層: 100 requests/day)"""

    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'x-rapidapi-key': api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        })
        self._daily_count = 0

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request"""
        if self._daily_count >= 95:
            logger.warning("Approaching daily API limit (100), skipping request")
            return {'response': []}

        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            self._daily_count += 1
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API-Football request failed: {e}")
            raise

    def get_injuries(self, league_id: int, season: int) -> List[Dict]:
        """獲取傷病名單"""
        data = self._get("/injuries", params={
            'league': league_id,
            'season': season
        })
        return data.get('response', [])

    def get_top_scorers(self, league_id: int, season: int) -> List[Dict]:
        """獲取射手榜"""
        data = self._get("/players/topscorers", params={
            'league': league_id,
            'season': season
        })
        return data.get('response', [])

    def get_top_assists(self, league_id: int, season: int) -> List[Dict]:
        """獲取助攻榜"""
        data = self._get("/players/topassists", params={
            'league': league_id,
            'season': season
        })
        return data.get('response', [])

    def get_fixture_statistics(self, fixture_id: int) -> List[Dict]:
        """獲取比賽統計"""
        data = self._get("/fixtures/statistics", params={
            'fixture': fixture_id
        })
        return data.get('response', [])

    def get_predictions(self, fixture_id: int) -> Dict:
        """獲取比賽預測和陣容預測"""
        data = self._get("/predictions", params={
            'fixture': fixture_id
        })
        responses = data.get('response', [])
        return responses[0] if responses else {}

    def get_lineups(self, fixture_id: int) -> List[Dict]:
        """獲取預測陣容"""
        data = self._get("/fixtures/lineups", params={
            'fixture': fixture_id
        })
        return data.get('response', [])

    def get_player_season_stats(self, player_id: int, season: int) -> Dict:
        """獲取球員賽季統計"""
        data = self._get("/players", params={
            'id': player_id,
            'season': season
        })
        responses = data.get('response', [])
        return responses[0] if responses else {}
