"""
ML 模型训练与预测模块
四种预测目标：
1. 比赛结果 (H/D/A) - XGBoost 多分类
2. 精确比分 - Poisson 回归
3. 总进球 Over/Under 2.5 - 逻辑回归
4. 球员表现 - 梯度提升回归

不使用赔率数据，完全基于统计特征
"""

import logging
import os
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score, TimeSeriesSplit
from sklearn.metrics import accuracy_score, log_loss, mean_absolute_error
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from scipy.stats import poisson
import xgboost as xgb

from ...config import Config

logger = logging.getLogger('mirofish.football.ml')


class FootballMLTrainer:
    """足球预测 ML 模型训练器"""

    def __init__(self):
        self.model_dir = Config.ML_MODEL_DIR
        os.makedirs(self.model_dir, exist_ok=True)
        self.scaler = StandardScaler()
        self.models = {}

    # ============= 1. 比赛结果预测 (XGBoost) =============

    def train_match_result(self, X, y):
        """训练比赛结果预测模型 (0=H, 1=D, 2=A)

        Returns:
            dict: 训练结果 {accuracy, cv_scores, feature_importance}
        """
        logger.info(f"训练比赛结果模型: {X.shape[0]} 样本, {X.shape[1]} 特征")

        # 标准化
        X_scaled = self.scaler.fit_transform(X)

        # 时间序列交叉验证 (不能随机打乱)
        tscv = TimeSeriesSplit(n_splits=5)

        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='multi:softprob',
            num_class=3,
            eval_metric='mlogloss',
            random_state=42,
            n_jobs=-1,
        )

        # 交叉验证
        cv_scores = cross_val_score(model, X_scaled, y, cv=tscv, scoring='accuracy')
        logger.info(f"CV 准确率: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

        # 全量训练
        model.fit(X_scaled, y)

        # 特征重要性
        importance = dict(zip(X.columns, model.feature_importances_))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:15]

        self.models['match_result'] = model
        self._save_model('match_result', model)
        self._save_model('scaler', self.scaler)

        result = {
            'model': 'match_result',
            'algorithm': 'XGBoost',
            'accuracy_cv': round(float(cv_scores.mean()), 4),
            'accuracy_std': round(float(cv_scores.std()), 4),
            'n_samples': X.shape[0],
            'n_features': X.shape[1],
            'top_features': [(name, round(float(score), 4)) for name, score in top_features],
            'trained_at': datetime.utcnow().isoformat(),
        }

        logger.info(f"比赛结果模型训练完成: CV={result['accuracy_cv']}")
        self._save_metadata('match_result', result)
        return result

    def predict_match_result(self, features_dict):
        """预测比赛结果

        Args:
            features_dict: 特征字典

        Returns:
            dict: {prediction, probabilities: {home, draw, away}, confidence}
        """
        model = self._load_model('match_result')
        scaler = self._load_model('scaler')
        if model is None or scaler is None:
            return None

        X = pd.DataFrame([features_dict])
        X_scaled = scaler.transform(X)
        proba = model.predict_proba(X_scaled)[0]

        result_map = {0: 'HOME', 1: 'DRAW', 2: 'AWAY'}
        prediction = result_map[np.argmax(proba)]

        return {
            'prediction': prediction,
            'probabilities': {
                'home': round(float(proba[0]), 4),
                'draw': round(float(proba[1]), 4),
                'away': round(float(proba[2]), 4),
            },
            'confidence': round(float(np.max(proba)), 4),
        }

    # ============= 2. 精确比分预测 (Poisson) =============

    def train_score_prediction(self, X, y_home_goals, y_away_goals):
        """训练比分预测模型（双 Poisson 回归）"""
        logger.info("训练比分预测模型...")

        X_scaled = self.scaler.fit_transform(X) if not hasattr(self.scaler, 'mean_') else self.scaler.transform(X)

        # 主队进球 Poisson 回归
        home_model = xgb.XGBRegressor(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.05,
            objective='count:poisson',
            random_state=42,
            n_jobs=-1,
        )
        home_model.fit(X_scaled, y_home_goals)

        # 客队进球 Poisson 回归
        away_model = xgb.XGBRegressor(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.05,
            objective='count:poisson',
            random_state=42,
            n_jobs=-1,
        )
        away_model.fit(X_scaled, y_away_goals)

        # 评估
        home_pred = home_model.predict(X_scaled)
        away_pred = away_model.predict(X_scaled)
        home_mae = mean_absolute_error(y_home_goals, home_pred)
        away_mae = mean_absolute_error(y_away_goals, away_pred)

        self.models['score_home'] = home_model
        self.models['score_away'] = away_model
        self._save_model('score_home', home_model)
        self._save_model('score_away', away_model)

        result = {
            'model': 'score_prediction',
            'algorithm': 'XGBoost Poisson',
            'home_mae': round(float(home_mae), 4),
            'away_mae': round(float(away_mae), 4),
            'trained_at': datetime.utcnow().isoformat(),
        }
        self._save_metadata('score_prediction', result)
        logger.info(f"比分模型训练完成: MAE(H)={home_mae:.3f}, MAE(A)={away_mae:.3f}")
        return result

    def predict_score(self, features_dict):
        """预测比分"""
        home_model = self._load_model('score_home')
        away_model = self._load_model('score_away')
        scaler = self._load_model('scaler')
        if not all([home_model, away_model, scaler]):
            return None

        X = pd.DataFrame([features_dict])
        X_scaled = scaler.transform(X)

        home_lambda = float(home_model.predict(X_scaled)[0])
        away_lambda = float(away_model.predict(X_scaled)[0])

        # 生成比分概率矩阵 (0-5 球)
        max_goals = 6
        score_matrix = {}
        for h in range(max_goals):
            for a in range(max_goals):
                prob = poisson.pmf(h, home_lambda) * poisson.pmf(a, away_lambda)
                score_matrix[f"{h}-{a}"] = round(float(prob), 4)

        # 最可能比分
        most_likely = max(score_matrix.items(), key=lambda x: x[1])

        return {
            'most_likely_score': most_likely[0],
            'most_likely_prob': most_likely[1],
            'expected_home_goals': round(home_lambda, 2),
            'expected_away_goals': round(away_lambda, 2),
            'top_scores': sorted(score_matrix.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    # ============= 3. Over/Under 2.5 (逻辑回归) =============

    def train_over_under(self, X, y_over25):
        """训练总进球 Over/Under 2.5 模型"""
        logger.info("训练 Over/Under 2.5 模型...")

        X_scaled = self.scaler.fit_transform(X) if not hasattr(self.scaler, 'mean_') else self.scaler.transform(X)

        model = LogisticRegression(
            max_iter=1000,
            C=1.0,
            random_state=42,
        )

        tscv = TimeSeriesSplit(n_splits=5)
        cv_scores = cross_val_score(model, X_scaled, y_over25, cv=tscv, scoring='accuracy')

        model.fit(X_scaled, y_over25)

        self.models['over_under'] = model
        self._save_model('over_under', model)

        result = {
            'model': 'over_under_2.5',
            'algorithm': 'LogisticRegression',
            'accuracy_cv': round(float(cv_scores.mean()), 4),
            'accuracy_std': round(float(cv_scores.std()), 4),
            'trained_at': datetime.utcnow().isoformat(),
        }
        self._save_metadata('over_under', result)
        logger.info(f"Over/Under 模型训练完成: CV={result['accuracy_cv']}")
        return result

    def predict_over_under(self, features_dict):
        """预测 Over/Under 2.5"""
        model = self._load_model('over_under')
        scaler = self._load_model('scaler')
        if not all([model, scaler]):
            return None

        X = pd.DataFrame([features_dict])
        X_scaled = scaler.transform(X)
        proba = model.predict_proba(X_scaled)[0]

        return {
            'prediction': 'OVER' if proba[1] > 0.5 else 'UNDER',
            'over_probability': round(float(proba[1]), 4),
            'under_probability': round(float(proba[0]), 4),
            'confidence': round(float(max(proba)), 4),
        }

    # ============= 训练全部模型 =============

    def train_all(self, X, y_result, y_goals, y_over25):
        """训练全部 ML 模型

        Args:
            X: 特征矩阵
            y_result: 比赛结果标签 (0=H, 1=D, 2=A)
            y_goals: 总进球数
            y_over25: Over/Under 2.5 标签

        Returns:
            dict: 各模型训练结果
        """
        results = {}

        # 填充NaN
        X = X.fillna(0)

        # 1. 比赛结果
        results['match_result'] = self.train_match_result(X, y_result)

        # 2. 比分预测 (需要拆分主客队进球)
        # 从 y_goals 中无法直接得到主客队进球，需要从原始数据获取
        # 这里先跳过，在 prediction_engine 中处理

        # 3. Over/Under 2.5
        results['over_under'] = self.train_over_under(X, y_over25)

        logger.info("全部 ML 模型训练完成")
        return results

    # ============= 模型持久化 =============

    def _save_model(self, name, model):
        """保存模型到磁盘"""
        path = os.path.join(self.model_dir, f'{name}.pkl')
        with open(path, 'wb') as f:
            pickle.dump(model, f)
        logger.debug(f"模型已保存: {path}")

    def _load_model(self, name):
        """从磁盘加载模型"""
        if name in self.models:
            return self.models[name]

        path = os.path.join(self.model_dir, f'{name}.pkl')
        if not os.path.exists(path):
            logger.warning(f"模型文件不存在: {path}")
            return None

        with open(path, 'rb') as f:
            model = pickle.load(f)
        self.models[name] = model
        return model

    def _save_metadata(self, name, metadata):
        """保存训练元数据"""
        path = os.path.join(self.model_dir, f'{name}_metadata.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def get_model_status(self):
        """获取所有模型状态"""
        status = {}
        for model_name in ['match_result', 'score_home', 'score_away', 'over_under']:
            meta_path = os.path.join(self.model_dir, f'{model_name}_metadata.json')
            model_path = os.path.join(self.model_dir, f'{model_name}.pkl')

            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    status[model_name] = json.load(f)
                status[model_name]['file_exists'] = os.path.exists(model_path)
            else:
                status[model_name] = {'status': 'not_trained', 'file_exists': False}

        return status
