"""
Football Prediction Service Module
MiroFish 足球預測系統 - 整合群體智能投票機制與 ML 預測

雙層預測架構:
  Layer 1: ML 模型 (XGBoost, Poisson, Logistic) - 40% 權重
  Layer 2: 群體智能投票 (50 agents, 5 角色, 18 輪) - 60% 權重

核心組件:
- data_collector: 多數據源數據收集 (football-data.org, API-Football, OpenWeatherMap)
- data_processor: 數據清洗與處理
- feature_engineer: 8 大類 ~82 維特徵工程
- ml_trainer: ML 模型訓練與預測
- prediction_engine: 雙層融合預測引擎
- agent_profile_generator: 50 個 Agent 角色生成
- voting_system: 加權投票與共識分析
- ontology_builder: Zep Cloud 知識圖譜構建
- venue_data: 五大聯賽球場靜態數據
- scheduler: APScheduler 定時數據更新
"""


def __getattr__(name):
    """Lazy imports to avoid loading heavy modules on package import."""
    _imports = {
        'FootballDataCollector': '.data_collector',
        'FootballDataProcessor': '.data_processor',
        'FeatureEngineer': '.feature_engineer',
        'FootballMLTrainer': '.ml_trainer',
        'PredictionEngine': '.prediction_engine',
        'VotingSystem': '.voting_system',
        'generate_agent_profiles': '.agent_profile_generator',
        'FootballOntologyBuilder': '.ontology_builder',
        'seed_venues': '.venue_data',
        'init_scheduler': '.scheduler',
        'shutdown_scheduler': '.scheduler',
        'get_scheduler_status': '.scheduler',
    }
    if name in _imports:
        import importlib
        module = importlib.import_module(_imports[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'FootballDataCollector',
    'FootballDataProcessor',
    'FeatureEngineer',
    'FootballMLTrainer',
    'PredictionEngine',
    'VotingSystem',
    'generate_agent_profiles',
    'FootballOntologyBuilder',
    'seed_venues',
    'init_scheduler',
    'shutdown_scheduler',
    'get_scheduler_status',
]
