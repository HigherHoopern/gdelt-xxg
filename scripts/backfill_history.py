import requests
import datetime
import logging
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 自动将项目根目录添加到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from service.data_ingestor.main import DataIngestor
from service.risk_engine.processor import RiskProcessor
from service.risk_engine.calculator import GRICalculator
from common.logger import setup_logger

# 统一日志配置
logger = setup_logger("历史数据并发补全")

GDELT_MASTER_LIST = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"

class ConcurrentBackfill:
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.ingestor = DataIngestor()
        self.processor = RiskProcessor()
        self.calculator = GRICalculator()

    def get_historical_urls(self, start_date_str, end_date_str):
        logger.info(f"正在从 GDELT 获取历史文件列表...")
        try:
            resp = requests.get(GDELT_MASTER_LIST, timeout=30)
            lines = resp.text.strip().split('\n')
        except Exception as e:
            logger.error(f"无法获取主列表: {e}")
            return []

        filtered_urls = []
        for line in lines:
            parts = line.split()
            if len(parts) < 3: continue
            url = parts[2]
            file_name = url.split('/')[-1]
            file_date = file_name[:8]
            if start_date_str <= file_date <= end_date_str:
                filtered_urls.append(url)
        
        logger.info(f"在区间 {start_date_str} 至 {end_date_str} 内发现 {len(filtered_urls)} 个数据文件。")
        return filtered_urls

    def process_time_slot_batch(self, timestamp, group_urls):
        """线程工作函数：处理单个 15 分钟时间片"""
        t_prefix = f"<{timestamp}>"
        try:
            # 1. 采集
            for url in group_urls:
                table_type = ""
                if '.export.' in url: table_type = 'export'
                elif '.mentions.' in url: table_type = 'mentions'
                elif '.gkg.' in url: table_type = 'gkg'
                if table_type:
                    self.ingestor.process_file(url, table_type)
            
            # 2. 深度处理
            self.processor.process_raw_to_business()
            
            # 3. 核心修复：在该时间点立即执行一次计算，并将计算结果记录到该历史时刻
            # 解析时间戳为 datetime 对象
            slot_time = datetime.datetime.strptime(timestamp, '%Y%m%d%H%M%S')
            self.calculator.calculate_daily_index(lookback_hours=72, base_time=slot_time)
            
            return True, timestamp
        except Exception as e:
            return False, f"{timestamp} 出错: {e}"

    def run_backfill(self, start_date, end_date):
        urls = self.get_historical_urls(start_date, end_date)
        if not urls: return

        # 组织时间片
        time_slots = {}
        for url in urls:
            timestamp = url.split('/')[-1][:14]
            if timestamp not in time_slots: time_slots[timestamp] = []
            time_slots[timestamp].append(url)

        sorted_timestamps = sorted(time_slots.keys())
        total_slots = len(sorted_timestamps)
        logger.info(f"🚀 开始并发补全任务：共计 {total_slots} 个时间片，并发窗口: {self.max_workers}")

        # 使用线程池加速
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_slot = {
                executor.submit(self.process_time_slot_batch, ts, time_slots[ts]): ts 
                for ts in sorted_timestamps
            }
            
            completed = 0
            for future in as_completed(future_to_slot):
                success, info = future.result()
                completed += 1
                status_icon = "✅" if success else "❌"
                if completed % 5 == 0:
                    logger.info(f"{status_icon} 总体进度: {completed}/{total_slots} | 时间片 {info} 及其分值已入库")

        logger.info("历史数据及 30 天趋势分值补全任务圆满完成！")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python3 scripts/backfill_history.py <开始日期YYYYMMDD> <结束日期YYYYMMDD>")
        sys.exit(1)

    start, end = sys.argv[1], sys.argv[2]
    
    print(f"🚀 将补全 {start} 到 {end} 的数据及【历史风险指数曲线】。")
    confirm = input("确认开始执行吗？(y/n): ")
    if confirm.lower() != 'y': sys.exit(0)

    backfill = ConcurrentBackfill(max_workers=5)
    backfill.run_backfill(start, end)
