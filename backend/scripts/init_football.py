#!/usr/bin/env python3
"""
足球预测系统初始化脚本
用法: python scripts/init_football.py [--seed-venues] [--sync-leagues]

步骤:
1. 验证配置
2. 测试数据库连接
3. 导入球场数据（可选）
4. 同步联赛信息（可选）
"""

import sys
import os
import argparse

# 确保可以导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import Config


def main():
    parser = argparse.ArgumentParser(description='MiroFish 足球模块初始化')
    parser.add_argument('--seed-venues', action='store_true', help='导入球场静态数据')
    parser.add_argument('--sync-leagues', action='store_true', help='同步联赛和球队数据')
    parser.add_argument('--full-sync', action='store_true', help='全量同步所有数据')
    parser.add_argument('--train', action='store_true', help='训练 ML 模型')
    parser.add_argument('--check', action='store_true', help='仅检查配置和连接')
    args = parser.parse_args()

    print("=" * 60)
    print("MiroFish 足球预测系统初始化")
    print("=" * 60)

    # 1. 验证配置
    print("\n[1] 检查配置...")
    warnings = Config.validate_football()
    if warnings:
        for w in warnings:
            print(f"  [WARN] {w}")
    else:
        print("  [OK] 所有配置已设置")

    print(f"  数据库: {Config.FOOTBALL_DB_HOST}:{Config.FOOTBALL_DB_PORT}/{Config.FOOTBALL_DB_NAME}")
    print(f"  支持联赛: {', '.join(Config.SUPPORTED_LEAGUES.keys())}")

    # 2. 测试数据库连接
    print("\n[2] 测试数据库连接...")
    try:
        from app.utils.db import init_db, check_health, close_db
        init_db(Config)
        health = check_health()
        if health.get('status') == 'ok':
            print("  [OK] PostgreSQL 连接成功")
        else:
            print(f"  [FAIL] {health}")
            if not args.check:
                sys.exit(1)
    except Exception as e:
        print(f"  [FAIL] 数据库连接失败: {e}")
        if not args.check:
            print("\n请确保 PostgreSQL 已启动并配置正确。")
            print("Docker 用户: docker compose up -d postgres")
            sys.exit(1)

    if args.check:
        print("\n配置检查完成。")
        return

    # 3. 导入球场数据
    if args.seed_venues or args.full_sync:
        print("\n[3] 导入球场静态数据...")
        try:
            from app.services.football.venue_data import seed_venues
            count = seed_venues()
            print(f"  [OK] 已导入 {count} 座球场")
        except Exception as e:
            print(f"  [FAIL] {e}")

    # 4. 同步联赛
    if args.sync_leagues or args.full_sync:
        print("\n[4] 同步联赛和球队数据...")
        try:
            from app.services.football.data_collector import FootballDataCollector
            collector = FootballDataCollector()

            if args.full_sync:
                results = collector.full_sync()
                print(f"  [OK] 全量同步完成: {results}")
            else:
                count = collector.sync_leagues()
                print(f"  [OK] 联赛同步: {count} 个联赛")
                for code in Config.SUPPORTED_LEAGUES:
                    tc = collector.sync_teams(code)
                    print(f"  [OK] {code}: {tc} 支球队")
        except Exception as e:
            print(f"  [FAIL] {e}")

    # 5. 训练模型
    if args.train:
        print("\n[5] 训练 ML 模型...")
        try:
            from app.services.football.feature_engineer import FeatureEngineer
            from app.services.football.ml_trainer import FootballMLTrainer

            engineer = FeatureEngineer()
            X, y_result, y_goals, y_over25, _ = engineer.build_feature_matrix()

            if X is None:
                print("  [SKIP] 训练数据不足，请先同步历史比赛数据")
            else:
                trainer = FootballMLTrainer()
                results = trainer.train_all(X, y_result, y_goals, y_over25)
                for model, info in results.items():
                    acc = info.get('accuracy_cv', 'N/A')
                    print(f"  [OK] {model}: CV accuracy = {acc}")
        except Exception as e:
            print(f"  [FAIL] {e}")

    # 清理
    try:
        close_db()
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("初始化完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
