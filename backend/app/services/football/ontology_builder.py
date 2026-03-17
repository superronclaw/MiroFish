"""
Zep Cloud 知识图谱构建器
将足球数据转换为 Zep 知识图谱实体和关系

实体类型 (10):
- Team, Player, Match, League, Venue, Referee, Season, Injury, Formation, Prediction

关系类型 (10):
- PLAYS_IN (Team->League), BELONGS_TO (Player->Team), HOME_TEAM/AWAY_TEAM (Team->Match),
- REFEREES (Referee->Match), HELD_AT (Match->Venue), HAS_INJURY (Player->Injury),
- USES_FORMATION (Team->Formation), PREDICTED_BY (Match->Prediction),
- HEAD_TO_HEAD (Team->Team), IN_SEASON (Match->Season)
"""

import logging
import json
from datetime import datetime

from ...config import Config
from ...utils.db import execute_query

logger = logging.getLogger('mirofish.football.ontology')


class FootballOntologyBuilder:
    """构建足球领域 Zep 知识图谱"""

    def __init__(self, zep_client=None):
        """
        Args:
            zep_client: Zep Cloud 客户端实例（从 MiroFish 主系统获取）
        """
        self.zep_client = zep_client
        self.graph_name = 'football_prediction'

    def build_ontology_text(self, league_code=None):
        """生成足球知识图谱的文本描述，用于 Zep 知识注入

        Zep 通过分析文本自动构建知识图谱，
        所以我们将结构化数据转换为自然语言描述

        Returns:
            list[str]: 知识文本段落列表
        """
        texts = []

        # 1. 联赛信息
        texts.extend(self._build_league_texts(league_code))

        # 2. 球队信息
        texts.extend(self._build_team_texts(league_code))

        # 3. 比赛信息（最近的比赛）
        texts.extend(self._build_match_texts(league_code, limit=50))

        # 4. 积分榜
        texts.extend(self._build_standings_texts(league_code))

        # 5. 球员信息
        texts.extend(self._build_player_texts(league_code))

        logger.info(f"生成 {len(texts)} 段知识文本")
        return texts

    def _build_league_texts(self, league_code=None):
        """联赛知识文本"""
        conditions = "WHERE fd_code = %s" if league_code else ""
        params = (league_code,) if league_code else None

        leagues = execute_query(
            f"SELECT * FROM leagues {conditions}", params, fetch_all=True
        )
        texts = []
        for league in (leagues or []):
            texts.append(
                f"The {league['name']} is a professional football league in {league['country']}. "
                f"Its code is {league['fd_code']}. "
                f"The current season started on {league.get('season_start')} and ends on {league.get('season_end')}."
            )
        return texts

    def _build_team_texts(self, league_code=None):
        """球队知识文本"""
        if league_code:
            teams = execute_query(
                """
                SELECT t.*, l.name AS league_name FROM teams t
                JOIN leagues l ON t.league_id = l.id
                WHERE l.fd_code = %s
                """,
                (league_code,),
                fetch_all=True,
            )
        else:
            teams = execute_query(
                "SELECT t.*, l.name AS league_name FROM teams t JOIN leagues l ON t.league_id = l.id",
                fetch_all=True,
            )

        texts = []
        for team in (teams or []):
            text = (
                f"{team['name']} (abbreviated {team.get('tla', 'N/A')}) plays in the {team.get('league_name', 'N/A')}. "
                f"Their home ground is {team.get('venue_name', 'unknown')}. "
            )
            if team.get('coach_name'):
                text += f"The team is managed by {team['coach_name']}. "
            if team.get('founded'):
                text += f"The club was founded in {team['founded']}. "
            texts.append(text)
        return texts

    def _build_match_texts(self, league_code=None, limit=50):
        """比赛知识文本"""
        conditions = ["m.status = 'FINISHED'"]
        params = []
        if league_code:
            conditions.append("l.fd_code = %s")
            params.append(league_code)

        matches = execute_query(
            f"""
            SELECT m.*, ht.name AS home_name, at.name AS away_name,
                   l.name AS league_name
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.id
            JOIN teams at ON m.away_team_id = at.id
            JOIN leagues l ON m.league_id = l.id
            WHERE {' AND '.join(conditions)}
            ORDER BY m.match_date DESC
            LIMIT %s
            """,
            params + [limit],
            fetch_all=True,
        )

        texts = []
        for m in (matches or []):
            hs = m.get('home_score_ft', '?')
            aws = m.get('away_score_ft', '?')
            date_str = str(m.get('match_date', 'unknown date'))[:10]

            text = (
                f"On {date_str}, {m['home_name']} played against {m['away_name']} "
                f"in the {m.get('league_name', '')} (matchday {m.get('matchday', '?')}). "
                f"The final score was {m['home_name']} {hs} - {aws} {m['away_name']}. "
            )
            if m.get('referee_name'):
                text += f"The match was refereed by {m['referee_name']}. "
            if m.get('weather_condition'):
                text += f"Weather conditions: {m['weather_condition']}, {m.get('temperature', '?')}°C. "

            texts.append(text)
        return texts

    def _build_standings_texts(self, league_code=None):
        """积分榜知识文本"""
        if league_code:
            stats = execute_query(
                """
                SELECT ts.*, t.name AS team_name, l.name AS league_name
                FROM team_season_stats ts
                JOIN teams t ON ts.team_id = t.id
                JOIN leagues l ON ts.league_id = l.id
                WHERE l.fd_code = %s
                ORDER BY ts.season DESC, ts.position
                """,
                (league_code,),
                fetch_all=True,
            )
        else:
            stats = execute_query(
                """
                SELECT ts.*, t.name AS team_name, l.name AS league_name
                FROM team_season_stats ts
                JOIN teams t ON ts.team_id = t.id
                JOIN leagues l ON ts.league_id = l.id
                ORDER BY ts.season DESC, l.name, ts.position
                """,
                fetch_all=True,
            )

        texts = []
        for s in (stats or []):
            played = s.get('played', 0) or 0
            texts.append(
                f"In the {s.get('league_name', '')} season {s.get('season', '')}, "
                f"{s['team_name']} is in position #{s.get('position', '?')} "
                f"with {s.get('points', 0)} points from {played} matches "
                f"({s.get('won', 0)}W {s.get('drawn', 0)}D {s.get('lost', 0)}L). "
                f"Goals: {s.get('goals_for', 0)} scored, {s.get('goals_against', 0)} conceded "
                f"(GD: {s.get('goal_difference', 0)})."
            )
        return texts

    def _build_player_texts(self, league_code=None):
        """球员知识文本"""
        if league_code:
            players = execute_query(
                """
                SELECT p.*, t.name AS team_name FROM players p
                JOIN teams t ON p.team_id = t.id
                JOIN leagues l ON t.league_id = l.id
                WHERE l.fd_code = %s
                ORDER BY p.name
                LIMIT 100
                """,
                (league_code,),
                fetch_all=True,
            )
        else:
            players = execute_query(
                """
                SELECT p.*, t.name AS team_name FROM players p
                JOIN teams t ON p.team_id = t.id
                ORDER BY p.name
                LIMIT 200
                """,
                fetch_all=True,
            )

        texts = []
        for p in (players or []):
            text = f"{p['name']} plays for {p.get('team_name', 'unknown')}. "
            if p.get('position'):
                text += f"Position: {p['position']}. "
            if p.get('nationality'):
                text += f"Nationality: {p['nationality']}. "
            texts.append(text)
        return texts

    async def inject_to_zep(self, league_code=None):
        """将知识注入 Zep Cloud 知识图谱

        Returns:
            dict: 注入结果
        """
        if not self.zep_client:
            logger.warning("Zep 客户端未配置")
            return {'status': 'error', 'message': 'Zep client not configured'}

        texts = self.build_ontology_text(league_code)

        success = 0
        errors = 0
        for i, text in enumerate(texts):
            try:
                await self.zep_client.graph.add(
                    data=text,
                    type="text",
                    group_id=self.graph_name,
                )
                success += 1
            except Exception as e:
                errors += 1
                logger.debug(f"Zep 知识注入失败 ({i}): {e}")

        result = {
            'status': 'ok',
            'total_texts': len(texts),
            'success': success,
            'errors': errors,
        }
        logger.info(f"Zep 知识注入完成: {success}/{len(texts)} 成功")
        return result
