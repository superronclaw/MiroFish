"""
PostgreSQL 数据库连接管理
MiroFish 足球预测系统 - 结构化数据存储
"""

import logging
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool, extras

logger = logging.getLogger('mirofish.football.db')

# 全局连接池
_connection_pool = None


def init_db(config):
    """初始化数据库连接池

    Args:
        config: Flask Config 对象，包含 FOOTBALL_DB_* 配置
    """
    global _connection_pool

    if _connection_pool is not None:
        logger.warning("数据库连接池已存在，跳过重复初始化")
        return

    try:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=config.FOOTBALL_DB_HOST,
            port=config.FOOTBALL_DB_PORT,
            database=config.FOOTBALL_DB_NAME,
            user=config.FOOTBALL_DB_USER,
            password=config.FOOTBALL_DB_PASSWORD,
        )
        logger.info(
            f"PostgreSQL 连接池已初始化: "
            f"{config.FOOTBALL_DB_HOST}:{config.FOOTBALL_DB_PORT}/{config.FOOTBALL_DB_NAME}"
        )
    except psycopg2.Error as e:
        logger.error(f"数据库连接池初始化失败: {e}")
        _connection_pool = None
        raise


def get_pool():
    """获取连接池实例"""
    if _connection_pool is None:
        raise RuntimeError("数据库连接池未初始化，请先调用 init_db()")
    return _connection_pool


@contextmanager
def get_connection():
    """获取数据库连接（上下文管理器，自动归还连接池）

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    p = get_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


@contextmanager
def get_cursor(cursor_factory=None):
    """获取游标（上下文管理器，自动提交 / 回滚）

    Args:
        cursor_factory: 游标工厂，如 psycopg2.extras.RealDictCursor

    Usage:
        with get_cursor(RealDictCursor) as cur:
            cur.execute("SELECT * FROM teams")
            rows = cur.fetchall()
    """
    with get_connection() as conn:
        factory = cursor_factory or extras.RealDictCursor
        cur = conn.cursor(cursor_factory=factory)
        try:
            yield cur
        finally:
            cur.close()


def execute_query(sql, params=None, fetch_one=False, fetch_all=False):
    """执行 SQL 查询的便捷方法

    Args:
        sql: SQL 语句
        params: 参数元组或字典
        fetch_one: 返回单条记录
        fetch_all: 返回所有记录

    Returns:
        查询结果（dict 或 list[dict]）或受影响行数
    """
    with get_cursor() as cur:
        cur.execute(sql, params)
        if fetch_one:
            return cur.fetchone()
        if fetch_all:
            return cur.fetchall()
        return cur.rowcount


def execute_many(sql, params_list):
    """批量执行 SQL（INSERT / UPDATE）

    Args:
        sql: SQL 语句
        params_list: 参数列表
    """
    with get_cursor() as cur:
        extras.execute_batch(cur, sql, params_list, page_size=100)
        return cur.rowcount


def close_db():
    """关闭数据库连接池"""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("PostgreSQL 连接池已关闭")


def check_health():
    """数据库健康检查"""
    try:
        result = execute_query("SELECT 1 AS ok", fetch_one=True)
        return {'status': 'ok', 'database': 'connected'} if result else {'status': 'error'}
    except Exception as e:
        return {'status': 'error', 'database': str(e)}
