"""
足球数据采集服务
从 football-data.org 和 API-Football 采集五大联赛数据
写入 PostgreSQL 数据库

数据覆盖范围：2024-2026赛季
8大数据类别：场地、天气、阵容、球员统计、近期表现、历史交锋、联赛排名、裁判因素
"""

import logging
import json
from datetime import datetime, date, timedelta

from ...config import Config
from ...utils.football_api_client import FootballDataClient, APIFootballClient
from ...utils.weather_client import WeatherClient
from ...utils.db import execute_query, execute_many

logger = logging.getLogger('mirofish.football.collector')


class FootballDataCollector:
    """足球数据采集器 - 整合多数据源"""

    def __init__(self):
        self.fd_client = FootballDataClient(Config.FOOTBALL_DATA_API_KEY)
        self.af_client = APIFootballClient(Config.API_FOOTBALL_KEY)
        self.weather_client = WeatherClient(Config.OPENWEATHER_API_KEY)
        self.leagues = Config.SUPPORTED_LEAGUES

    # ============= 联赛与球队 =============

    def sync_leagues(self):
        """同步五大联赛信息到数据库"""
        logger.info("开始同步联赛信息...")
        count = 0
        for code, info in self.leagues.items():
            try:
                competition = self.fd_client.get_competition(code)
                if not competition:
                    continue

                season = competition.get('currentSeason', {})
                execute_query(
                    """
                    INSERT INTO leagues (fd_code, api_football_id, name, country, current_season, season_start, season_end)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (fd_code) DO UPDATE SET
                        name = EXCLUDED.name,
                        current_season = EXCLUDED.current_season,
                        season_start = EXCLUDED.season_start,
                        season_end = EXCLUDED.season_end,
                        updated_at = NOW()
                    """,
                    (
                        code,
                        info['api_football_id'],
                        info['name'],
                        info['country'],
                        season.get('id'),
                        season.get('startDate'),
                        season.get('endDate'),
                    ),
                )
                count += 1
                logger.info(f"  [OK] {info['name']}")
            except Exception as e:
                logger.error(f"  [FAIL] {info['name']}: {e}")
        logger.info(f"联赛同步完成: {count}/{len(self.leagues)}")
        return count

    def sync_teams(self, league_code):
        """同步指定联赛的球队信息"""
        logger.info(f"开始同步球队: {league_code}")
        teams_data = self.fd_client.get_teams(league_code)
        if not teams_data or 'teams' not in teams_data:
            logger.warning(f"未获取到 {league_code} 球队数据")
            return 0

        # 获取联赛ID
        league = execute_query(
            "SELECT id FROM leagues WHERE fd_code = %s", (league_code,), fetch_one=True
        )
        if not league:
            logger.error(f"联赛 {league_code} 不在数据库中，请先执行 sync_leagues")
            return 0
        league_id = league['id']

        params_list = []
        for team in teams_data['teams']:
            params_list.append((
                team.get('id'),
                league_id,
                team.get('name'),
                team.get('shortName'),
                team.get('tla'),
                team.get('crest'),
                team.get('venue'),
                team.get('founded'),
                team.get('clubColors'),
                team.get('coach', {}).get('name') if team.get('coach') else None,
            ))

        execute_many(
            """
            INSERT INTO teams (fd_team_id, league_id, name, short_name, tla, crest_url, venue_name, founded, colors, coach_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fd_team_id) DO UPDATE SET
                name = EXCLUDED.name,
                short_name = EXCLUDED.short_name,
                crest_url = EXCLUDED.crest_url,
                venue_name = EXCLUDED.venue_name,
                coach_name = EXCLUDED.coach_name,
                updated_at = NOW()
            """,
            params_list,
        )
        logger.info(f"球队同步完成: {league_code} - {len(params_list)} 支球队")
        return len(params_list)

    # ============= 比赛数据 =============

    def sync_matches(self, league_code, season=None, date_from=None, date_to=None):
        """同步比赛数据（含比分、阵型）"""
        logger.info(f"开始同步比赛: {league_code}")

        params = {}
        if season:
            params['season'] = season
        if date_from:
            params['dateFrom'] = date_from
        if date_to:
            params['dateTo'] = date_to

        matches_data = self.fd_client.get_matches(league_code, **params)
        if not matches_data or 'matches' not in matches_data:
            logger.warning(f"未获取到 {league_code} 比赛数据")
            return 0

        count = 0
        for match in matches_data['matches']:
            try:
                self._upsert_match(match, league_code)
                count += 1
            except Exception as e:
                logger.error(f"比赛写入失败 (id={match.get('id')}): {e}")

        logger.info(f"比赛同步完成: {league_code} - {count} 场")
        return count

    def _upsert_match(self, match, league_code):
        """插入或更新单场比赛"""
        home_team = match.get('homeTeam', {})
        away_team = match.get('awayTeam', {})
        score = match.get('score', {})
        full_time = score.get('fullTime', {})
        half_time = score.get('halfTime', {})
        referees = match.get('referees', [])
        referee_name = referees[0].get('name') if referees else None

        # 查找主队和客队内部ID
        home = execute_query(
            "SELECT id FROM teams WHERE fd_team_id = %s", (home_team.get('id'),), fetch_one=True
        )
        away = execute_query(
            "SELECT id FROM teams WHERE fd_team_id = %s", (away_team.get('id'),), fetch_one=True
        )
        league = execute_query(
            "SELECT id FROM leagues WHERE fd_code = %s", (league_code,), fetch_one=True
        )

        if not home or not away or not league:
            logger.warning(f"球队或联赛ID缺失，跳过比赛 {match.get('id')}")
            return

        execute_query(
            """
            INSERT INTO matches (
                fd_match_id, league_id, home_team_id, away_team_id,
                match_date, status, matchday, stage,
                home_score_ft, away_score_ft, home_score_ht, away_score_ht,
                referee_name, season
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fd_match_id) DO UPDATE SET
                status = EXCLUDED.status,
                home_score_ft = EXCLUDED.home_score_ft,
                away_score_ft = EXCLUDED.away_score_ft,
                home_score_ht = EXCLUDED.home_score_ht,
                away_score_ht = EXCLUDED.away_score_ht,
                referee_name = EXCLUDED.referee_name,
                updated_at = NOW()
            """,
            (
                match.get('id'),
                league['id'],
                home['id'],
                away['id'],
                match.get('utcDate'),
                match.get('status'),
                match.get('matchday'),
                match.get('stage'),
                full_time.get('home'),
                full_time.get('away'),
                half_time.get('home'),
                half_time.get('away'),
                referee_name,
                match.get('season', {}).get('id'),
            ),
        )

    # ============= 积分榜 =============

    def sync_standings(self, league_code, season=None):
        """同步联赛积分榜 -> team_season_stats"""
        logger.info(f"开始同步积分榜: {league_code}")
        standings_data = self.fd_client.get_standings(league_code, season=season)
        if not standings_data or 'standings' not in standings_data:
            logger.warning(f"未获取到 {league_code} 积分榜")
            return 0

        league = execute_query(
            "SELECT id FROM leagues WHERE fd_code = %s", (league_code,), fetch_one=True
        )
        if not league:
            return 0

        season_year = standings_data.get('season', {}).get('id', date.today().year)
        total_type = standings_data['standings'][0] if standings_data['standings'] else None
        if not total_type or total_type.get('type') != 'TOTAL':
            # 尝试找 TOTAL 类型
            for s in standings_data['standings']:
                if s.get('type') == 'TOTAL':
                    total_type = s
                    break

        if not total_type:
            logger.warning("未找到 TOTAL 类型积分榜")
            return 0

        count = 0
        for entry in total_type.get('table', []):
            team_fd_id = entry.get('team', {}).get('id')
            team = execute_query(
                "SELECT id FROM teams WHERE fd_team_id = %s", (team_fd_id,), fetch_one=True
            )
            if not team:
                continue

            execute_query(
                """
                INSERT INTO team_season_stats (
                    team_id, league_id, season, position,
                    played, won, drawn, lost,
                    goals_for, goals_against, goal_difference, points,
                    home_played, home_won, home_drawn, home_lost,
                    away_played, away_won, away_drawn, away_lost
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (team_id, league_id, season) DO UPDATE SET
                    position = EXCLUDED.position,
                    played = EXCLUDED.played,
                    won = EXCLUDED.won,
                    drawn = EXCLUDED.drawn,
                    lost = EXCLUDED.lost,
                    goals_for = EXCLUDED.goals_for,
                    goals_against = EXCLUDED.goals_against,
                    goal_difference = EXCLUDED.goal_difference,
                    points = EXCLUDED.points,
                    home_played = EXCLUDED.home_played,
                    home_won = EXCLUDED.home_won,
                    home_drawn = EXCLUDED.home_drawn,
                    home_lost = EXCLUDED.home_lost,
                    away_played = EXCLUDED.away_played,
                    away_won = EXCLUDED.away_won,
                    away_drawn = EXCLUDED.away_drawn,
                    away_lost = EXCLUDED.away_lost,
                    updated_at = NOW()
                """,
                (
                    team['id'], league['id'], season_year,
                    entry.get('position'),
                    entry.get('playedGames'), entry.get('won'), entry.get('draw'), entry.get('lost'),
                    entry.get('goalsFor'), entry.get('goalsAgainst'),
                    entry.get('goalDifference'), entry.get('points'),
                    # home/away 需要从分类积分榜获取，暂用 None
                    None, None, None, None,
                    None, None, None, None,
                ),
            )
            count += 1

        # 尝试补充 home/away 数据
        self._sync_home_away_standings(standings_data, league['id'], season_year)

        logger.info(f"积分榜同步完成: {league_code} - {count} 支球队")
        return count

    def _sync_home_away_standings(self, standings_data, league_id, season_year):
        """补充主/客场积分榜数据"""
        for standings_group in standings_data.get('standings', []):
            stype = standings_group.get('type')
            if stype not in ('HOME', 'AWAY'):
                continue

            prefix = 'home' if stype == 'HOME' else 'away'
            for entry in standings_group.get('table', []):
                team_fd_id = entry.get('team', {}).get('id')
                team = execute_query(
                    "SELECT id FROM teams WHERE fd_team_id = %s", (team_fd_id,), fetch_one=True
                )
                if not team:
                    continue

                execute_query(
                    f"""
                    UPDATE team_season_stats SET
                        {prefix}_played = %s,
                        {prefix}_won = %s,
                        {prefix}_drawn = %s,
                        {prefix}_lost = %s,
                        updated_at = NOW()
                    WHERE team_id = %s AND league_id = %s AND season = %s
                    """,
                    (
                        entry.get('playedGames'),
                        entry.get('won'),
                        entry.get('draw'),
                        entry.get('lost'),
                        team['id'], league_id, season_year,
                    ),
                )

    # ============= 球员数据（API-Football） =============

    def sync_top_scorers(self, league_code, season=None):
        """同步联赛射手榜（从 API-Football）"""
        af_league_id = self.leagues[league_code]['api_football_id']
        season = season or date.today().year
        logger.info(f"开始同步射手榜: {league_code} ({season})")

        scorers = self.af_client.get_top_scorers(af_league_id, season)
        if not scorers or 'response' not in scorers:
            return 0

        count = 0
        for item in scorers.get('response', [])[:30]:  # top 30
            player = item.get('player', {})
            stats_list = item.get('statistics', [])
            if not stats_list:
                continue
            stats = stats_list[0]
            games = stats.get('games', {})
            goals_data = stats.get('goals', {})
            passes_data = stats.get('passes', {})
            shots_data = stats.get('shots', {})

            try:
                # 先确保球员存在
                self._upsert_player(player, stats.get('team', {}))

                # 更新球员赛季统计（存到 player_match_stats 汇总字段或独立查询）
                count += 1
            except Exception as e:
                logger.error(f"射手榜球员处理失败 {player.get('name')}: {e}")

        logger.info(f"射手榜同步完成: {count} 名球员")
        return count

    def _upsert_player(self, player_data, team_data):
        """插入或更新球员"""
        # 查找球队
        team = None
        if team_data.get('name'):
            team = execute_query(
                "SELECT id FROM teams WHERE name ILIKE %s LIMIT 1",
                (f"%{team_data['name']}%",),
                fetch_one=True,
            )

        execute_query(
            """
            INSERT INTO players (api_football_id, name, nationality, position, date_of_birth, team_id, photo_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (api_football_id) DO UPDATE SET
                name = EXCLUDED.name,
                team_id = COALESCE(EXCLUDED.team_id, players.team_id),
                photo_url = EXCLUDED.photo_url,
                updated_at = NOW()
            """,
            (
                player_data.get('id'),
                player_data.get('name'),
                player_data.get('nationality'),
                player_data.get('position') or player_data.get('type'),
                player_data.get('birth', {}).get('date') if isinstance(player_data.get('birth'), dict) else None,
                team['id'] if team else None,
                player_data.get('photo'),
            ),
        )

    # ============= 天气数据 =============

    def sync_weather_for_upcoming_matches(self, days_ahead=7):
        """为未来 N 天的比赛获取天气预报"""
        logger.info(f"开始采集未来 {days_ahead} 天比赛天气数据...")

        upcoming = execute_query(
            """
            SELECT m.id, m.match_date, v.city, v.latitude, v.longitude
            FROM matches m
            LEFT JOIN teams t ON m.home_team_id = t.id
            LEFT JOIN venues v ON t.venue_name = v.name
            WHERE m.status = 'SCHEDULED'
              AND m.match_date BETWEEN NOW() AND NOW() + INTERVAL '%s days'
              AND m.weather_condition IS NULL
            """,
            (days_ahead,),
            fetch_all=True,
        )

        if not upcoming:
            logger.info("没有需要更新天气的比赛")
            return 0

        count = 0
        for match in upcoming:
            try:
                weather = None
                if match.get('latitude') and match.get('longitude'):
                    weather = self.weather_client.get_weather_for_match(
                        match['latitude'], match['longitude'],
                        match['match_date'],
                    )
                elif match.get('city'):
                    weather = self.weather_client.get_weather_by_city(match['city'])

                if weather:
                    execute_query(
                        """
                        UPDATE matches SET
                            weather_condition = %s,
                            temperature = %s,
                            humidity = %s,
                            wind_speed = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            weather.get('condition'),
                            weather.get('temperature'),
                            weather.get('humidity'),
                            weather.get('wind_speed'),
                            match['id'],
                        ),
                    )
                    count += 1
            except Exception as e:
                logger.error(f"天气数据采集失败 (match_id={match['id']}): {e}")

        logger.info(f"天气数据更新完成: {count}/{len(upcoming)}")
        return count

    # ============= 伤病数据（API-Football） =============

    def sync_injuries(self, league_code, season=None):
        """同步伤病数据"""
        af_league_id = self.leagues[league_code]['api_football_id']
        season = season or date.today().year
        logger.info(f"开始同步伤病数据: {league_code}")

        injuries_data = self.af_client.get_injuries(af_league_id, season)
        if not injuries_data or 'response' not in injuries_data:
            return 0

        count = 0
        for item in injuries_data.get('response', []):
            player = item.get('player', {})
            team = item.get('team', {})
            fixture = item.get('fixture', {})

            try:
                # 找到球员
                db_player = execute_query(
                    "SELECT id FROM players WHERE api_football_id = %s",
                    (player.get('id'),),
                    fetch_one=True,
                )
                if not db_player:
                    continue

                execute_query(
                    """
                    INSERT INTO injuries (player_id, injury_type, severity, start_date, expected_return, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        db_player['id'],
                        player.get('reason'),
                        'unknown',
                        fixture.get('date'),
                        None,
                        'active',
                    ),
                )
                count += 1
            except Exception as e:
                logger.error(f"伤病数据处理失败: {e}")

        logger.info(f"伤病数据同步完成: {count} 条记录")
        return count

    # ============= 全量同步 =============

    def full_sync(self, league_code=None):
        """全量同步指定联赛或所有联赛"""
        leagues_to_sync = [league_code] if league_code else list(self.leagues.keys())
        results = {}

        # 1. 联赛基础信息
        self.sync_leagues()

        for code in leagues_to_sync:
            logger.info(f"\n{'='*50}")
            logger.info(f"全量同步: {self.leagues[code]['name']}")
            logger.info(f"{'='*50}")

            result = {}

            # 2. 球队
            result['teams'] = self.sync_teams(code)

            # 3. 比赛（当前赛季）
            result['matches'] = self.sync_matches(code)

            # 4. 积分榜
            result['standings'] = self.sync_standings(code)

            # 5. 射手榜
            result['top_scorers'] = self.sync_top_scorers(code)

            # 6. 伤病
            result['injuries'] = self.sync_injuries(code)

            results[code] = result

        # 7. 天气（所有联赛一起）
        results['weather'] = self.sync_weather_for_upcoming_matches()

        logger.info("\n全量同步完成:")
        for code, res in results.items():
            if isinstance(res, dict):
                logger.info(f"  {code}: {res}")
            else:
                logger.info(f"  {code}: {res}")

        return results

    def incremental_sync(self):
        """增量同步（比赛日频繁调用）"""
        logger.info("开始增量同步...")

        # 只同步最近和未来的比赛
        today = date.today()
        date_from = (today - timedelta(days=3)).isoformat()
        date_to = (today + timedelta(days=7)).isoformat()

        total = 0
        for code in self.leagues:
            total += self.sync_matches(code, date_from=date_from, date_to=date_to)

        # 更新积分榜
        for code in self.leagues:
            self.sync_standings(code)

        # 更新天气
        self.sync_weather_for_upcoming_matches(days_ahead=3)

        logger.info(f"增量同步完成: {total} 场比赛更新")
        return total
