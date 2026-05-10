import math
import datetime
import os
import sys

# 自动定位项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy import text
from common.models import SessionLocal, DailyRiskIndex, RiskIndexHistory, init_db
from config.settings import REGIONAL_COUNTRIES
from common.logger import setup_logger

logger = setup_logger("风险指数计算器")

# 核心优化：提高基准值到 100，给分值留出 10 倍的波动空间
NORMALIZATION_FACTOR = 100.0 

class GRICalculator:
    def __init__(self):
        pass

    def get_risk_level(self, score):
        if score <= 20: return "低风险"
        if score <= 40: return "较低风险"
        if score <= 60: return "中等风险"
        if score <= 80: return "高风险"
        return "极高风险"

    def calculate_daily_index(self, lookback_hours=24, base_time=None):
        """
        计算风险指数。
        :param lookback_hours: 缩短为 24 小时以增强日级波动感
        """
        session = SessionLocal()
        try:
            # 性能优化：截断到分钟，防止微秒级重复
            now_dt = datetime.datetime.now()
            calc_now = base_time if base_time else now_dt.replace(second=0, microsecond=0)
            start_time = calc_now - datetime.timedelta(hours=lookback_hours)
            
            # 1. 获取最新处理过的数据
            query = text("""
                SELECT 
                    country_code,
                    SUM(weight * impact_score * LN(num_sources + 1) * ((100 - avg_tone) / 100)) as raw_score,
                    COUNT(*) as event_count
                FROM risk_analysis_data
                WHERE event_date >= :start_time AND event_date <= :end_time
                GROUP BY country_code
            """)
            
            results = session.execute(query, {
                "start_time": start_time,
                "end_time": calc_now
            }).fetchall()
            
            # 获取所有国家列表，用于衰减计算
            all_country_codes = [v['fips'] for v in REGIONAL_COUNTRIES.values()]
            results_map = {row[0]: row for row in results if row[0]}

            for country_code in all_country_codes:
                row = results_map.get(country_code)
                
                if row:
                    _, raw_score, event_count = row
                    gri_score = min(100.0, (float(raw_score) / NORMALIZATION_FACTOR) * 100.0)
                else:
                    # 核心优化：衰减逻辑。如果没有新数据，参考上一条历史记录并衰减 10%
                    # 这保证了风险曲线的连续性，不会突降到 0
                    last_hist = session.query(RiskIndexHistory).filter(
                        RiskIndexHistory.country_code == country_code
                    ).order_by(RiskIndexHistory.calculation_date.desc()).first()
                    
                    if last_hist and last_hist.risk_index > 5:
                        gri_score = float(last_hist.risk_index) * 0.9  # 衰减 10%
                        event_count = 0
                    else:
                        gri_score = 0.0
                        event_count = 0
                
                risk_level = self.get_risk_level(gri_score)
                
                # 3. 保存至历史记录表 (Upsert 逻辑)
                existing_hist = session.query(RiskIndexHistory).filter(
                    RiskIndexHistory.country_code == country_code,
                    RiskIndexHistory.calculation_date == calc_now
                ).first()
                
                if existing_hist:
                    existing_hist.risk_index = gri_score
                else:
                    history_entry = RiskIndexHistory(
                        country_code=country_code,
                        risk_index=gri_score,
                        calculation_date=calc_now
                    )
                    session.add(history_entry)
                
                # 4. 更新日聚合记录 (仅在非回补模式下)
                if not base_time:
                    today_start = datetime.datetime.combine(calc_now.date(), datetime.time.min)
                    existing_daily = session.query(DailyRiskIndex).filter(
                        DailyRiskIndex.country_code == country_code,
                        DailyRiskIndex.calculation_date >= today_start
                    ).first()
                    
                    if existing_daily:
                        existing_daily.risk_index = gri_score
                        existing_daily.risk_level = risk_level
                        existing_daily.event_count = event_count
                        existing_daily.calculation_date = calc_now
                    else:
                        new_index = DailyRiskIndex(
                            country_code=country_code,
                            risk_index=gri_score,
                            risk_level=risk_level,
                            event_count=event_count,
                            calculation_date=calc_now
                        )
                        session.add(new_index)
            
            session.commit()
        except Exception as e:
            logger.error(f"指数计算错误: {e}")
            session.rollback()
        finally:
            session.close()

if __name__ == "__main__":
    calculator = GRICalculator()
    calculator.calculate_daily_index()
