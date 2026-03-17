"""
Football Data Models
數據模型層 - 用於數據庫操作和數據傳輸
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum


class MatchStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"


class PredictionType(str, Enum):
    FULL = "full"           # ML + 群體智能
    ML_ONLY = "ml_only"     # 僅 ML
    QUICK = "quick"         # 快速預測


class SimulationStatus(str, Enum):
    CREATED = "CREATED"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentRole(str, Enum):
    FAN = "Fan"
    ANALYST = "Analyst"
    MEDIA = "Media"
    INSIDER = "Insider"
    NEUTRAL = "Neutral"


# 智能體投票權重
AGENT_WEIGHTS = {
    AgentRole.FAN: 0.10,
    AgentRole.ANALYST: 0.30,
    AgentRole.MEDIA: 0.15,
    AgentRole.INSIDER: 0.25,
    AgentRole.NEUTRAL: 0.20,
}


@dataclass
class League:
    league_id: Optional[int] = None
    name: str = ""
    country: str = ""
    season: str = ""
    api_league_id: Optional[int] = None
    logo_url: Optional[str] = None


@dataclass
class Venue:
    venue_id: Optional[int] = None
    name: str = ""
    city: str = ""
    country: str = ""
    capacity: int = 0
    altitude_meters: int = 0
    pitch_type: str = "natural"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    atmosphere_rating: float = 5.0


@dataclass
class Team:
    team_id: Optional[int] = None
    name: str = ""
    short_name: str = ""
    league_id: Optional[int] = None
    venue_id: Optional[int] = None
    api_team_id: Optional[int] = None
    logo_url: Optional[str] = None
    founded: Optional[int] = None
    coach_name: Optional[str] = None


@dataclass
class Player:
    player_id: Optional[int] = None
    name: str = ""
    team_id: Optional[int] = None
    api_player_id: Optional[int] = None
    position: str = ""
    nationality: str = ""
    date_of_birth: Optional[date] = None
    market_value: int = 0
    preferred_foot: str = "right"
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    shirt_number: Optional[int] = None


@dataclass
class Referee:
    referee_id: Optional[int] = None
    name: str = ""
    nationality: str = ""
    total_matches: int = 0
    avg_yellow_cards: float = 0.0
    avg_red_cards: float = 0.0
    avg_fouls: float = 0.0
    avg_penalties: float = 0.0
    strictness_rating: float = 5.0
    controversy_index: float = 0.0


@dataclass
class Match:
    match_id: Optional[int] = None
    league_id: Optional[int] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    venue_id: Optional[int] = None
    referee_id: Optional[int] = None
    match_date: Optional[datetime] = None
    matchday: Optional[int] = None
    status: MatchStatus = MatchStatus.SCHEDULED
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_ht_score: Optional[int] = None
    away_ht_score: Optional[int] = None
    api_match_id: Optional[int] = None
    # 天氣
    weather_condition: Optional[str] = None
    temperature_celsius: Optional[float] = None
    humidity_percent: Optional[int] = None
    wind_speed_ms: Optional[float] = None
    # 陣型
    home_formation: Optional[str] = None
    away_formation: Optional[str] = None


@dataclass
class TeamSeasonStats:
    team_id: int = 0
    league_id: int = 0
    season: str = ""
    position: int = 0
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    points: int = 0
    home_won: int = 0
    home_drawn: int = 0
    home_lost: int = 0
    away_won: int = 0
    away_drawn: int = 0
    away_lost: int = 0
    clean_sheets: int = 0

    @property
    def win_rate(self) -> float:
        return self.won / max(self.played, 1)

    @property
    def home_win_rate(self) -> float:
        home_played = self.home_won + self.home_drawn + self.home_lost
        return self.home_won / max(home_played, 1)

    @property
    def away_win_rate(self) -> float:
        away_played = self.away_won + self.away_drawn + self.away_lost
        return self.away_won / max(away_played, 1)

    @property
    def goals_per_match(self) -> float:
        return self.goals_for / max(self.played, 1)

    @property
    def conceded_per_match(self) -> float:
        return self.goals_against / max(self.played, 1)


@dataclass
class Injury:
    injury_id: Optional[int] = None
    player_id: int = 0
    team_id: int = 0
    injury_type: str = ""
    severity: str = "moderate"
    start_date: Optional[date] = None
    expected_return: Optional[date] = None
    status: str = "injured"


@dataclass
class MatchPrediction:
    """綜合預測結果"""
    match_id: int = 0
    prediction_type: PredictionType = PredictionType.FULL
    # ML 預測
    ml_home_win_prob: float = 0.0
    ml_draw_prob: float = 0.0
    ml_away_win_prob: float = 0.0
    ml_predicted_home_goals: float = 0.0
    ml_predicted_away_goals: float = 0.0
    ml_over_2_5_prob: float = 0.0
    ml_confidence: float = 0.0
    # 智能體預測
    agent_home_win_prob: float = 0.0
    agent_draw_prob: float = 0.0
    agent_away_win_prob: float = 0.0
    agent_consensus_level: str = "moderate"
    agent_total_agents: int = 0
    agent_voting_details: Dict = field(default_factory=dict)
    agent_key_arguments: List = field(default_factory=list)
    # 綜合預測
    combined_home_win_prob: float = 0.0
    combined_draw_prob: float = 0.0
    combined_away_win_prob: float = 0.0
    combined_predicted_score: str = ""
    combined_confidence: float = 0.0
    prediction_narrative: str = ""

    @property
    def final_result(self) -> str:
        """返回最終預測結果"""
        probs = {
            'home_win': self.combined_home_win_prob,
            'draw': self.combined_draw_prob,
            'away_win': self.combined_away_win_prob,
        }
        return max(probs, key=probs.get)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'match_id': self.match_id,
            'prediction_type': self.prediction_type.value,
            'ml_prediction': {
                'home_win': round(self.ml_home_win_prob, 4),
                'draw': round(self.ml_draw_prob, 4),
                'away_win': round(self.ml_away_win_prob, 4),
                'predicted_home_goals': round(self.ml_predicted_home_goals, 2),
                'predicted_away_goals': round(self.ml_predicted_away_goals, 2),
                'over_2_5': round(self.ml_over_2_5_prob, 4),
                'confidence': round(self.ml_confidence, 4),
            },
            'agent_prediction': {
                'home_win': round(self.agent_home_win_prob, 4),
                'draw': round(self.agent_draw_prob, 4),
                'away_win': round(self.agent_away_win_prob, 4),
                'consensus_level': self.agent_consensus_level,
                'total_agents': self.agent_total_agents,
                'voting_details': self.agent_voting_details,
                'key_arguments': self.agent_key_arguments,
            },
            'combined_prediction': {
                'home_win': round(self.combined_home_win_prob, 4),
                'draw': round(self.combined_draw_prob, 4),
                'away_win': round(self.combined_away_win_prob, 4),
                'predicted_score': self.combined_predicted_score,
                'final_result': self.final_result,
                'confidence': round(self.combined_confidence, 4),
            },
            'narrative': self.prediction_narrative,
        }


@dataclass
class AgentProfile:
    """智能體人設"""
    agent_id: str = ""
    role: AgentRole = AgentRole.NEUTRAL
    name: str = ""
    team_support: Optional[str] = None
    personality: str = "balanced"
    bias_level: float = 0.0
    knowledge_level: str = "medium"
    emotional_factor: float = 0.5
    key_concerns: List[str] = field(default_factory=list)
    background: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'role': self.role.value,
            'name': self.name,
            'team_support': self.team_support,
            'personality': self.personality,
            'bias_level': self.bias_level,
            'knowledge_level': self.knowledge_level,
            'emotional_factor': self.emotional_factor,
            'key_concerns': self.key_concerns,
            'background': self.background,
        }
