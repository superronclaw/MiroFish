"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    # ============= 足球预测系统配置 =============

    # Football-Data.org API (主要数据源, 免费 10 req/min)
    FOOTBALL_DATA_API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY', '')
    FOOTBALL_DATA_BASE_URL = 'https://api.football-data.org/v4'

    # API-Football (备用数据源, 免费 100 req/day)
    API_FOOTBALL_KEY = os.environ.get('API_FOOTBALL_KEY', '')
    API_FOOTBALL_BASE_URL = 'https://v3.football.api-sports.io'

    # OpenWeatherMap API (天气数据)
    OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '')

    # PostgreSQL 数据库 (足球结构化数据)
    FOOTBALL_DB_HOST = os.environ.get('FOOTBALL_DB_HOST', 'localhost')
    FOOTBALL_DB_PORT = int(os.environ.get('FOOTBALL_DB_PORT', '5432'))
    FOOTBALL_DB_NAME = os.environ.get('FOOTBALL_DB_NAME', 'mirofish_football')
    FOOTBALL_DB_USER = os.environ.get('FOOTBALL_DB_USER', 'mirofish')
    FOOTBALL_DB_PASSWORD = os.environ.get('FOOTBALL_DB_PASSWORD', '')

    @property
    def FOOTBALL_DB_URI(self):
        return (
            f"postgresql://{self.FOOTBALL_DB_USER}:{self.FOOTBALL_DB_PASSWORD}"
            f"@{self.FOOTBALL_DB_HOST}:{self.FOOTBALL_DB_PORT}/{self.FOOTBALL_DB_NAME}"
        )

    # 支持的联赛 (欧洲五大联赛)
    SUPPORTED_LEAGUES = {
        'PL': {'name': 'Premier League', 'country': 'England', 'fd_code': 'PL', 'api_football_id': 39},
        'PD': {'name': 'La Liga', 'country': 'Spain', 'fd_code': 'PD', 'api_football_id': 140},
        'SA': {'name': 'Serie A', 'country': 'Italy', 'fd_code': 'SA', 'api_football_id': 135},
        'BL1': {'name': 'Bundesliga', 'country': 'Germany', 'fd_code': 'BL1', 'api_football_id': 78},
        'FL1': {'name': 'Ligue 1', 'country': 'France', 'fd_code': 'FL1', 'api_football_id': 61},
    }

    # 数据更新调度配置
    DATA_UPDATE_INTERVAL_HOURS = int(os.environ.get('DATA_UPDATE_INTERVAL_HOURS', '6'))
    MATCH_DAY_UPDATE_INTERVAL_MINUTES = int(os.environ.get('MATCH_DAY_UPDATE_INTERVAL_MINUTES', '30'))

    # ML 模型配置
    ML_MODEL_DIR = os.path.join(os.path.dirname(__file__), '../data/models')
    ML_RETRAIN_INTERVAL_DAYS = int(os.environ.get('ML_RETRAIN_INTERVAL_DAYS', '7'))

    # 群体智能投票配置
    SWARM_TOTAL_AGENTS = 50
    SWARM_SIMULATION_ROUNDS = 18
    SWARM_AGENT_ROLES = {
        'fan': {'count': 5, 'weight': 0.10},
        'analyst': {'count': 15, 'weight': 0.30},
        'media': {'count': 8, 'weight': 0.15},
        'insider': {'count': 12, 'weight': 0.25},
        'neutral': {'count': 10, 'weight': 0.20},
    }

    # 双层预测融合权重
    ML_PREDICTION_WEIGHT = float(os.environ.get('ML_PREDICTION_WEIGHT', '0.4'))
    AGENT_PREDICTION_WEIGHT = float(os.environ.get('AGENT_PREDICTION_WEIGHT', '0.6'))

    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        return errors

    @classmethod
    def validate_football(cls):
        """验证足球模块配置"""
        warnings_list = []
        if not cls.FOOTBALL_DATA_API_KEY:
            warnings_list.append("FOOTBALL_DATA_API_KEY 未配置（主要数据源不可用）")
        if not cls.API_FOOTBALL_KEY:
            warnings_list.append("API_FOOTBALL_KEY 未配置（备用数据源不可用）")
        if not cls.OPENWEATHER_API_KEY:
            warnings_list.append("OPENWEATHER_API_KEY 未配置（天气数据不可用）")
        if not cls.FOOTBALL_DB_PASSWORD:
            warnings_list.append("FOOTBALL_DB_PASSWORD 未配置")
        return warnings_list

