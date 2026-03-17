"""
足球预测系统 API 路由
MiroFish Football Prediction Module - 完整实现
"""

import logging
from flask import Blueprint, jsonify, request

from ..config import Config
from ..utils.db import check_health as db_health, execute_query
from ..services.football.ml_trainer import FootballMLTrainer
from ..services.football.scheduler import get_scheduler_status

logger = logging.getLogger('mirofish.football.api')

football_bp = Blueprint('football', __name__)


# ============= 健康检查 =============

@football_bp.route('/health', methods=['GET'])
def health():
    """足球模块健康检查"""
    db_status = db_health()
    config_warnings = Config.validate_football()
    scheduler = get_scheduler_status()
    ml_trainer = FootballMLTrainer()

    return jsonify({
        'status': 'ok' if db_status.get('status') == 'ok' else 'degraded',
        'module': 'football',
        'database': db_status,
        'scheduler': scheduler,
        'models': ml_trainer.get_model_status(),
        'config_warnings': config_warnings,
        'supported_leagues': list(Config.SUPPORTED_LEAGUES.keys()),
    })


# ============= 联赛与球队 =============

@football_bp.route('/leagues', methods=['GET'])
def get_leagues():
    """获取支持的联赛列表"""
    return jsonify({
        'leagues': [
            {'code': code, **info}
            for code, info in Config.SUPPORTED_LEAGUES.items()
        ]
    })


@football_bp.route('/leagues/<league_code>/standings', methods=['GET'])
def get_standings(league_code):
    """获取联赛积分榜"""
    if league_code not in Config.SUPPORTED_LEAGUES:
        return jsonify({'error': f'不支持的联赛: {league_code}'}), 404

    standings = execute_query(
        """
        SELECT ts.position, ts.played, ts.won, ts.drawn, ts.lost,
               ts.goals_for, ts.goals_against, ts.goal_difference, ts.points,
               ts.home_won, ts.home_drawn, ts.home_lost,
               ts.away_won, ts.away_drawn, ts.away_lost,
               t.name AS team_name, t.tla, t.crest_url
        FROM team_season_stats ts
        JOIN teams t ON ts.team_id = t.id
        JOIN leagues l ON ts.league_id = l.id
        WHERE l.fd_code = %s
        ORDER BY ts.season DESC, ts.position
        """,
        (league_code,),
        fetch_all=True,
    )

    return jsonify({
        'league': league_code,
        'league_name': Config.SUPPORTED_LEAGUES[league_code]['name'],
        'standings': standings or [],
    })


@football_bp.route('/leagues/<league_code>/teams', methods=['GET'])
def get_teams(league_code):
    """获取联赛球队列表"""
    if league_code not in Config.SUPPORTED_LEAGUES:
        return jsonify({'error': f'不支持的联赛: {league_code}'}), 404

    teams = execute_query(
        """
        SELECT t.id, t.fd_team_id, t.name, t.short_name, t.tla,
               t.crest_url, t.venue_name, t.founded, t.colors, t.coach_name
        FROM teams t
        JOIN leagues l ON t.league_id = l.id
        WHERE l.fd_code = %s
        ORDER BY t.name
        """,
        (league_code,),
        fetch_all=True,
    )

    return jsonify({
        'league': league_code,
        'teams': teams or [],
    })


# ============= 比赛数据 =============

@football_bp.route('/matches', methods=['GET'])
def get_matches():
    """获取比赛列表（支持筛选）"""
    league = request.args.get('league')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)

    conditions = []
    params = []

    if league:
        conditions.append("l.fd_code = %s")
        params.append(league)
    if status:
        conditions.append("m.status = %s")
        params.append(status.upper())
    if date_from:
        conditions.append("m.match_date >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("m.match_date <= %s")
        params.append(date_to)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)

    matches = execute_query(
        f"""
        SELECT m.id, m.fd_match_id, m.match_date, m.matchday, m.status, m.season,
               m.home_score_ft, m.away_score_ft, m.home_score_ht, m.away_score_ht,
               m.home_formation, m.away_formation,
               m.weather_condition, m.temperature, m.referee_name,
               ht.name AS home_team, ht.tla AS home_tla, ht.crest_url AS home_crest,
               at.name AS away_team, at.tla AS away_tla, at.crest_url AS away_crest,
               l.fd_code AS league_code, l.name AS league_name
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.id
        JOIN teams at ON m.away_team_id = at.id
        JOIN leagues l ON m.league_id = l.id
        {where}
        ORDER BY m.match_date DESC
        LIMIT %s
        """,
        params,
        fetch_all=True,
    )

    return jsonify({
        'matches': matches or [],
        'filters': {'league': league, 'status': status, 'date_from': date_from, 'date_to': date_to},
        'count': len(matches or []),
    })


@football_bp.route('/matches/<int:match_id>', methods=['GET'])
def get_match_detail(match_id):
    """获取比赛详情"""
    match = execute_query(
        """
        SELECT m.*,
               ht.name AS home_team, ht.tla AS home_tla, ht.crest_url AS home_crest,
               at.name AS away_team, at.tla AS away_tla, at.crest_url AS away_crest,
               l.fd_code AS league_code, l.name AS league_name
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.id
        JOIN teams at ON m.away_team_id = at.id
        JOIN leagues l ON m.league_id = l.id
        WHERE m.id = %s
        """,
        (match_id,),
        fetch_one=True,
    )

    if not match:
        return jsonify({'error': f'比赛不存在: {match_id}'}), 404

    return jsonify({'match': match})


@football_bp.route('/matches/<int:match_id>/head-to-head', methods=['GET'])
def get_head_to_head(match_id):
    """获取两队历史交锋记录"""
    match = execute_query(
        "SELECT home_team_id, away_team_id FROM matches WHERE id = %s",
        (match_id,),
        fetch_one=True,
    )
    if not match:
        return jsonify({'error': f'比赛不存在: {match_id}'}), 404

    h2h = execute_query(
        """
        SELECT m.match_date, m.home_score_ft, m.away_score_ft, m.status,
               ht.name AS home_team, at.name AS away_team, l.name AS league_name
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.id
        JOIN teams at ON m.away_team_id = at.id
        JOIN leagues l ON m.league_id = l.id
        WHERE m.status = 'FINISHED'
          AND (
              (m.home_team_id = %s AND m.away_team_id = %s)
              OR (m.home_team_id = %s AND m.away_team_id = %s)
          )
        ORDER BY m.match_date DESC
        LIMIT 20
        """,
        (match['home_team_id'], match['away_team_id'],
         match['away_team_id'], match['home_team_id']),
        fetch_all=True,
    )

    return jsonify({
        'match_id': match_id,
        'head_to_head': h2h or [],
        'total': len(h2h or []),
    })


# ============= 预测 =============

@football_bp.route('/predictions/match/<int:match_id>', methods=['GET'])
def get_prediction(match_id):
    """获取单场比赛预测结果"""
    prediction = execute_query(
        """
        SELECT p.*, m.match_date,
               ht.name AS home_team, at.name AS away_team,
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

    if not prediction:
        return jsonify({
            'match_id': match_id,
            'prediction': None,
            'message': '尚无预测结果，请先触发预测',
        })

    return jsonify({'prediction': prediction})


@football_bp.route('/predictions/upcoming', methods=['GET'])
def get_upcoming_predictions():
    """获取未来比赛预测列表"""
    league = request.args.get('league')
    days = request.args.get('days', 7, type=int)

    conditions = [
        "m.status = 'SCHEDULED'",
        "m.match_date BETWEEN NOW() AND NOW() + INTERVAL '%s days'",
    ]
    params = [days]

    if league:
        conditions.append("l.fd_code = %s")
        params.append(league)

    results = execute_query(
        f"""
        SELECT m.id AS match_id, m.match_date, m.matchday,
               ht.name AS home_team, ht.tla AS home_tla,
               at.name AS away_team, at.tla AS away_tla,
               l.fd_code AS league_code, l.name AS league_name,
               p.predicted_result, p.confidence, p.consensus_level,
               p.combined_home_prob, p.combined_draw_prob, p.combined_away_prob,
               p.predicted_score
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.id
        JOIN teams at ON m.away_team_id = at.id
        JOIN leagues l ON m.league_id = l.id
        LEFT JOIN predictions p ON p.match_id = m.id
        WHERE {' AND '.join(conditions)}
        ORDER BY m.match_date
        """,
        params,
        fetch_all=True,
    )

    return jsonify({
        'predictions': results or [],
        'filters': {'league': league, 'days': days},
        'count': len(results or []),
    })


@football_bp.route('/predictions/match/<int:match_id>/simulate', methods=['POST'])
def trigger_simulation(match_id):
    """触发双层预测（ML + 群体智能投票）"""
    try:
        from ..services.football.prediction_engine import PredictionEngine
        engine = PredictionEngine()
        result = engine.predict_match(match_id)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify({
            'status': 'completed',
            'prediction': result,
        })
    except Exception as e:
        logger.error(f"预测触发失败: {e}")
        return jsonify({'error': str(e)}), 500


# ============= 球员 =============

@football_bp.route('/players/<int:player_id>/stats', methods=['GET'])
def get_player_stats(player_id):
    """获取球员赛季统计"""
    player = execute_query(
        """
        SELECT p.*, t.name AS team_name
        FROM players p
        LEFT JOIN teams t ON p.team_id = t.id
        WHERE p.id = %s
        """,
        (player_id,),
        fetch_one=True,
    )

    if not player:
        return jsonify({'error': f'球员不存在: {player_id}'}), 404

    match_stats = execute_query(
        """
        SELECT SUM(goals) AS total_goals, SUM(assists) AS total_assists,
               AVG(rating) AS avg_rating, COUNT(*) AS appearances,
               SUM(minutes_played) AS total_minutes,
               SUM(yellow_cards) AS yellow_cards, SUM(red_cards) AS red_cards
        FROM player_match_stats
        WHERE player_id = %s
        """,
        (player_id,),
        fetch_one=True,
    )

    return jsonify({
        'player': player,
        'stats': match_stats,
    })


# ============= 数据管理 =============

@football_bp.route('/data/status', methods=['GET'])
def data_status():
    """数据采集状态"""
    stats = {}
    for table in ['leagues', 'teams', 'matches', 'players', 'venues', 'predictions']:
        result = execute_query(f"SELECT COUNT(*) AS cnt FROM {table}", fetch_one=True)
        stats[table] = result['cnt'] if result else 0

    return jsonify({
        'database': db_health(),
        'table_counts': stats,
        'scheduler': get_scheduler_status(),
        'data_sources': {
            'football_data_org': {
                'configured': bool(Config.FOOTBALL_DATA_API_KEY),
            },
            'api_football': {
                'configured': bool(Config.API_FOOTBALL_KEY),
            },
            'openweathermap': {
                'configured': bool(Config.OPENWEATHER_API_KEY),
            },
        },
    })


@football_bp.route('/data/sync', methods=['POST'])
def trigger_sync():
    """手动触发数据同步"""
    body = request.get_json(silent=True) or {}
    source = body.get('source', 'all')
    league = body.get('league')

    try:
        from ..services.football.data_collector import FootballDataCollector
        collector = FootballDataCollector()

        if source == 'all':
            result = collector.full_sync(league)
        elif source == 'matches':
            result = collector.sync_matches(league) if league else 'league parameter required'
        elif source == 'teams':
            result = collector.sync_teams(league) if league else 'league parameter required'
        elif source == 'standings':
            result = collector.sync_standings(league) if league else 'league parameter required'
        elif source == 'weather':
            result = collector.sync_weather_for_upcoming_matches()
        else:
            return jsonify({'error': f'未知的数据源: {source}'}), 400

        return jsonify({'status': 'completed', 'result': str(result)})

    except Exception as e:
        logger.error(f"数据同步失败: {e}")
        return jsonify({'error': str(e)}), 500


# ============= 模型管理 =============

@football_bp.route('/models/status', methods=['GET'])
def model_status():
    """ML 模型状态"""
    trainer = FootballMLTrainer()
    return jsonify({'models': trainer.get_model_status()})


@football_bp.route('/models/train', methods=['POST'])
def trigger_training():
    """触发模型训练"""
    body = request.get_json(silent=True) or {}
    league_code = body.get('league')

    try:
        from ..services.football.feature_engineer import FeatureEngineer
        engineer = FeatureEngineer()
        X, y_result, y_goals, y_over25, match_ids = engineer.build_feature_matrix(league_code=league_code)

        if X is None:
            return jsonify({'error': '没有足够的训练数据'}), 400

        trainer = FootballMLTrainer()
        results = trainer.train_all(X, y_result, y_goals, y_over25)

        return jsonify({'status': 'completed', 'results': results})

    except Exception as e:
        logger.error(f"模型训练失败: {e}")
        return jsonify({'error': str(e)}), 500


# ============= 调度器管理 =============

@football_bp.route('/scheduler/status', methods=['GET'])
def scheduler_status():
    """调度器状态"""
    return jsonify(get_scheduler_status())


@football_bp.route('/scheduler/start', methods=['POST'])
def start_scheduler():
    """启动调度器"""
    try:
        from ..services.football.scheduler import init_scheduler
        init_scheduler()
        return jsonify({'status': 'started', 'scheduler': get_scheduler_status()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
