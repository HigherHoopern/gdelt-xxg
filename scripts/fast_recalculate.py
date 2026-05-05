import datetime
import os
import sys
from sqlalchemy import text

# 自动定位项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from common.models import SessionLocal, RiskAnalysisData
from service.risk_engine.calculator import GRICalculator
from common.logger import setup_logger

logger = setup_logger("极速历史计算")

class FastRecalculator:
    def __init__(self):
        self.calculator = GRICalculator()

    def sync_metadata_only(self):
        """
        核心逻辑：直接从原始表抽取计算 GRI 所需的元数据到业务表。
        完全跳过爬虫和 AI 翻译，实现秒级同步。
        """
        logger.info("正在执行 SQL 级元数据同步 (跳过 AI 翻译)...")
        session = SessionLocal()
        try:
            # 使用 INSERT INTO ... SELECT ... ON CONFLICT DO NOTHING
            # 这样已经翻译好的数据不会被覆盖，没入库的数据会被快速填入元数据
            sync_sql = text("""
                INSERT INTO risk_analysis_data (
                    global_event_id, event_date, country_code, category, weight, 
                    impact_score, num_sources, avg_tone, url, created_at
                )
                SELECT DISTINCT ON (e."SOURCEURL")
                    e."GlobalEventID", 
                    to_timestamp(e."Day"::text, 'YYYYMMDD'), 
                    e."ActionGeo_CountryCode",
                    CASE 
                        WHEN e."EventCode" LIKE '18%' OR e."EventCode" LIKE '19%' OR e."EventCode" LIKE '20%' THEN 'Military'
                        WHEN e."EventCode" LIKE '11%' OR e."EventCode" LIKE '12%' OR e."EventCode" LIKE '13%' THEN 'Political'
                        ELSE 'General'
                    END,
                    CASE 
                        WHEN e."EventCode" LIKE '18%' THEN 1.5
                        WHEN e."EventCode" LIKE '11%' THEN 1.3
                        ELSE 0.5
                    END,
                    ABS(e."GoldsteinScale"),
                    e."NumSources",
                    e."AvgTone",
                    e."SOURCEURL",
                    NOW()
                FROM export e
                WHERE e."Day" >= 20260401 AND e."Day" <= 20260430
                ON CONFLICT (url) DO NOTHING;
            """)
            result = session.execute(sync_sql)
            session.commit()
            logger.info(f"成功快速同步了大量历史元数据。")
        except Exception as e:
            logger.error(f"同步失败: {e}")
            session.rollback()
        finally:
            session.close()

    def run_daily_points(self):
        """
        循环处理 4 月份的每一天，生成 GRI 记录
        """
        start_date = datetime.date(2026, 4, 1)
        end_date = datetime.date(2026, 4, 30)
        current = start_date
        
        logger.info("开始按日回溯计算 GRI 风险打点...")
        
        while current <= end_date:
            # 模拟在那一天的 23:59:59 执行计算
            calc_time = datetime.datetime.combine(current, datetime.time(23, 59, 59))
            logger.info(f"正在计算日期: {current} ...")
            
            # 调用计算器，改为回溯 24 小时计算当天的独立分值
            self.calculator.calculate_daily_index(lookback_hours=24, base_time=calc_time)
            current += datetime.timedelta(days=1)
            
        logger.info("✅ 4 月份所有风险指数打点已完成！")

if __name__ == "__main__":
    recalc = FastRecalculator()
    # 1. 先把基础数据填入业务表（不翻译，只填数）
    recalc.sync_metadata_only()
    # 2. 批量产生 30 个分值点
    recalc.run_daily_points()
    print("\n🚀 处理完成！现在请刷新网页，您将看到完整的 4 月份曲线。")
    print("后台服务 main_service.py 将在稍后自动为您补全这些新闻的中文翻译。")
