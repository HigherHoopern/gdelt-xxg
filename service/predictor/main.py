import numpy as np
import pandas as pd
import datetime
import os
import sys

# 自动定位项目根目录并加入搜索路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from sklearn.linear_model import LinearRegression
from common.models import SessionLocal, DailyRiskIndex, RiskPrediction, init_db
from sqlalchemy import text
from common.logger import setup_logger

logger = setup_logger("风险预测器")

class RiskPredictor:
    def __init__(self):
        pass

    def predict_next_3_days(self):
        session = SessionLocal()
        try:
            # 获取所有有数据的国家
            countries = [r[0] for r in session.execute(text("SELECT DISTINCT country_code FROM daily_risk_index")).fetchall()]
            
            if not countries:
                logger.warning("尚无历史风险数据，跳过预测生成。")
                return

            for country in countries:
                # 1. 核心改进：使用最近 30 天的每日聚合数据 (daily_risk_index)
                # 这样预测的是基于日均水平的长趋势，更加稳健
                start_training = datetime.datetime.now() - datetime.timedelta(days=30)
                df = pd.read_sql(
                    text(f"SELECT calculation_date, risk_index FROM daily_risk_index WHERE country_code = '{country}' AND calculation_date >= :start ORDER BY calculation_date ASC"),
                    session.bind,
                    params={"start": start_training}
                )
                
                # 如果日表数据不足，尝试从 15 分钟表回补
                if len(df) < 3:
                    df = pd.read_sql(
                        text(f"SELECT calculation_date, risk_index FROM risk_index_history WHERE country_code = '{country}' ORDER BY calculation_date ASC"),
                        session.bind
                    )
                
                if len(df) < 2:
                    logger.info(f"国家 {country} 样本不足，跳过预测。")
                    continue
                
                logger.info(f"正在为国家 {country} 生成未来 3 天预测 (基于 30 天历史趋势)...")
                
                # 2. 准备特征
                df['days_from_start'] = (df['calculation_date'] - df['calculation_date'].min()).dt.days
                X = df[['days_from_start']].values
                y = df['risk_index'].values.astype(float)
                
                # 3. 线性回归模型
                model = LinearRegression()
                model.fit(X, y)
                
                # 4. 预测未来 7 天 (前 4 天实线区，后 3 天虚线区)
                last_day = df['days_from_start'].max()
                last_date = df['calculation_date'].max()
                
                for i in range(1, 8): # 循环 7 次
                    future_day = last_day + i
                    pred_score = float(model.predict([[future_day]])[0])
                    pred_score = max(0.0, min(100.0, pred_score))
                    
                    pred_date = last_date + datetime.timedelta(days=i)
                    pred_date = datetime.datetime.combine(pred_date.date(), datetime.time.min)
                    
                    # 5. 保存或更新预测
                    existing = session.query(RiskPrediction).filter(
                        RiskPrediction.country_code == country,
                        RiskPrediction.predicted_date == pred_date
                    ).first()
                    
                    if existing:
                        existing.predicted_risk_index = pred_score
                    else:
                        new_pred = RiskPrediction(
                            country_code=country,
                            predicted_date=pred_date,
                            predicted_risk_index=pred_score,
                            model_version="月度趋势线性拟合-v7d"
                        )
                        session.add(new_pred)
                
            session.commit()
            logger.info("未来 7 天的风险趋势预测已更新完成。")
        except Exception as e:
            logger.error(f"趋势预测过程中发生错误: {e}")
            session.rollback()
        finally:
            session.close()

if __name__ == "__main__":
    predictor = RiskPredictor()
    predictor.predict_next_3_days()
