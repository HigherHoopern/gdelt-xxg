# main_service.py
import time
import threading
import logging
from service.data_ingestor.main import DataIngestor
from service.risk_engine.processor import RiskProcessor
from service.risk_engine.calculator import GRICalculator
from service.predictor.main import RiskPredictor
from config.settings import SCHEDULE
from common.logger import setup_logger

logger = setup_logger("后台总控服务")

def run_ingestor():
    logger.info("正在启动数据采集线程...")
    ingestor = DataIngestor()
    while True:
        try:
            urls = ingestor.fetch_latest_urls()
            for t, url in urls.items():
                ingestor.process_file(url, t)
        except Exception as e:
            logger.error(f"数据采集发生错误: {e}")
        time.sleep(SCHEDULE['ingest_interval'])

def run_processing_pipeline():
    logger.info("正在启动流水线处理线程...")
    processor = RiskProcessor()
    while True:
        try:
            logger.info("正在执行风险预处理任务...")
            processor.process_raw_to_business()
        except Exception as e:
            logger.error(f"业务处理流水线发生错误: {e}")
        time.sleep(SCHEDULE['process_interval'])

def run_calculator():
    logger.info("正在启动指数计算线程...")
    calculator = GRICalculator()
    while True:
        try:
            logger.info("正在执行地缘风险指数定期计算...")
            calculator.calculate_daily_index()
        except Exception as e:
            logger.error(f"指数计算器发生错误: {e}")
        # 固定每分钟计算一次，确保实时性
        time.sleep(60)

def run_predictor():
    logger.info("正在启动趋势预测线程...")
    predictor = RiskPredictor()
    while True:
        try:
            logger.info("正在更新风险指数趋势预测 (3天周期)...")
            predictor.predict_next_3_days()
        except Exception as e:
            logger.error(f"趋势预测发生错误: {e}")
        time.sleep(SCHEDULE['predict_interval'])

from common.models import init_db

if __name__ == "__main__":
    logger.info("=== XterAI全球地缘政治风险分析平台后台已启动 ===")
    
    logger.info("正在初始化数据库结构...")
    init_db()
    
    # 启动各后台线程
    threads = [
        threading.Thread(target=run_ingestor, name="数据采集器"),
        threading.Thread(target=run_processing_pipeline, name="流水线处理器"),
        threading.Thread(target=run_calculator, name="指数计算器"),
        threading.Thread(target=run_predictor, name="趋势预测器")
    ]
    
    for t in threads:
        t.daemon = True
        t.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("正在关闭系统...")
