"""
数据自动更新调度器
使用 APScheduler 实现定时数据采集与模型更新

调度策略:
- 常规: 每6小时同步一次比赛数据、积分榜
- 比赛日: 每30分钟增量同步
- 每周: 全量同步 + 模型重训练
"""

import logging
from datetime import datetime, date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from ...config import Config

logger = logging.getLogger('mirofish.football.scheduler')

_scheduler = None


def get_scheduler():
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            timezone='UTC',
            job_defaults={'coalesce': True, 'max_instances': 1},
        )
    return _scheduler


def init_scheduler():
    """初始化并启动所有定时任务"""
    scheduler = get_scheduler()

    if scheduler.running:
        logger.warning("调度器已在运行")
        return scheduler

    # 1. 常规数据同步 (每 N 小时)
    scheduler.add_job(
        _job_regular_sync,
        trigger=IntervalTrigger(hours=Config.DATA_UPDATE_INTERVAL_HOURS),
        id='regular_sync',
        name='常规数据同步',
        replace_existing=True,
    )

    # 2. 比赛日增量同步 (每 N 分钟, 只在赛季中执行)
    scheduler.add_job(
        _job_matchday_sync,
        trigger=IntervalTrigger(minutes=Config.MATCH_DAY_UPDATE_INTERVAL_MINUTES),
        id='matchday_sync',
        name='比赛日增量同步',
        replace_existing=True,
    )

    # 3. 每周全量同步 (周一凌晨3点 UTC)
    scheduler.add_job(
        _job_weekly_full_sync,
        trigger=CronTrigger(day_of_week='mon', hour=3, minute=0),
        id='weekly_full_sync',
        name='每周全量同步',
        replace_existing=True,
    )

    # 4. 天气数据更新 (每天2次)
    scheduler.add_job(
        _job_weather_sync,
        trigger=CronTrigger(hour='8,20', minute=0),
        id='weather_sync',
        name='天气数据更新',
        replace_existing=True,
    )

    # 5. 模型重训练 (每 N 天, 周三凌晨4点)
    scheduler.add_job(
        _job_retrain_models,
        trigger=CronTrigger(day_of_week='wed', hour=4, minute=0),
        id='retrain_models',
        name='模型重训练',
        replace_existing=True,
    )

    scheduler.start()
    logger.info("数据更新调度器已启动")
    _log_scheduled_jobs(scheduler)
    return scheduler


def shutdown_scheduler():
    """停止调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("调度器已停止")
    _scheduler = None


def _log_scheduled_jobs(scheduler):
    """打印所有已注册的任务"""
    for job in scheduler.get_jobs():
        logger.info(f"  任务: {job.name} | 下次执行: {job.next_run_time}")


# ============= 任务实现 =============

def _job_regular_sync():
    """常规数据同步"""
    logger.info("[定时任务] 开始常规数据同步...")
    try:
        from .data_collector import FootballDataCollector
        collector = FootballDataCollector()
        for code in Config.SUPPORTED_LEAGUES:
            collector.sync_matches(code)
            collector.sync_standings(code)
        logger.info("[定时任务] 常规同步完成")
    except Exception as e:
        logger.error(f"[定时任务] 常规同步失败: {e}")


def _job_matchday_sync():
    """比赛日增量同步 - 仅在有比赛时执行"""
    try:
        from ...utils.db import execute_query
        # 检查今天是否有比赛
        today_matches = execute_query(
            """
            SELECT COUNT(*) AS cnt FROM matches
            WHERE DATE(match_date) = CURRENT_DATE
              AND status IN ('SCHEDULED', 'IN_PLAY', 'PAUSED', 'LIVE')
            """,
            fetch_one=True,
        )
        if not today_matches or today_matches['cnt'] == 0:
            return  # 今天没有比赛，跳过

        logger.info(f"[定时任务] 比赛日增量同步 (今日 {today_matches['cnt']} 场比赛)")
        from .data_collector import FootballDataCollector
        collector = FootballDataCollector()
        collector.incremental_sync()
    except Exception as e:
        logger.error(f"[定时任务] 增量同步失败: {e}")


def _job_weekly_full_sync():
    """每周全量同步"""
    logger.info("[定时任务] 开始每周全量同步...")
    try:
        from .data_collector import FootballDataCollector
        collector = FootballDataCollector()
        collector.full_sync()
        logger.info("[定时任务] 每周全量同步完成")
    except Exception as e:
        logger.error(f"[定时任务] 全量同步失败: {e}")


def _job_weather_sync():
    """天气数据更新"""
    logger.info("[定时任务] 更新天气数据...")
    try:
        from .data_collector import FootballDataCollector
        collector = FootballDataCollector()
        collector.sync_weather_for_upcoming_matches(days_ahead=7)
    except Exception as e:
        logger.error(f"[定时任务] 天气数据更新失败: {e}")


def _job_retrain_models():
    """模型重训练"""
    logger.info("[定时任务] 开始模型重训练...")
    try:
        # TODO Phase 3: 集成 ML 训练器
        logger.info("[定时任务] ML 训练模块尚未实现")
    except Exception as e:
        logger.error(f"[定时任务] 模型训练失败: {e}")


def get_scheduler_status():
    """获取调度器状态"""
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': str(job.next_run_time) if job.next_run_time else None,
            'trigger': str(job.trigger),
        })
    return {
        'running': scheduler.running,
        'jobs': jobs,
    }
