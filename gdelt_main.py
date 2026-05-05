import multiprocessing
import time
import logging
import sys
import os
from datetime import datetime
from sqlalchemy import text

# 从自定义模块导入逻辑
from config import DB_URL, DATA_DIR, get_engine, setup_logging
from ingestor import run_ingestor
from worker import run_worker

# ==========================================
# 1. 数据库初始化 (建表与索引)
# ==========================================
def init_db():
    """在程序启动前，确保数据库结构完整"""
    # 初始化主进程日志
    setup_logging()
    logging.info("------------------------------------------")
    logging.info("正在执行数据库结构初始化检查...")
    engine = get_engine()
    
    # 1.1 原始数据表 (GDELT Mentions 16个原始字段)
    sql_orig = """
    CREATE TABLE IF NOT EXISTS public.mentions_original (
        id SERIAL PRIMARY KEY,
        "GlobalEventID" BIGINT,
        "EventTimeDate" BIGINT,
        "MentionTimeDate" BIGINT,
        "MentionType" INTEGER,
        "MentionSourceName" TEXT,
        "MentionIdentifier" TEXT,
        "SentenceID" INTEGER,
        "Actor1CharOffset" INTEGER,
        "Actor2CharOffset" INTEGER,
        "ActionCharOffset" INTEGER,
        "InRawText" INTEGER,
        "Confidence" INTEGER,
        "MentionDocLen" INTEGER,
        "MentionDocTone" NUMERIC,
        "MentionDocTranslationInfo" TEXT,
        "Extras" TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    # 1.2 翻译后的数据表
    sql_processed = """
    CREATE TABLE IF NOT EXISTS public.mentions (
        id SERIAL PRIMARY KEY,
        "GlobalEventID" BIGINT,
        "标题" TEXT,
        "摘要" TEXT,
        "内容" TEXT,
        "时间" TIMESTAMP,
        "url" TEXT,
        "url_image" TEXT,
        "SourceName" TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    # 1.3 索引（对增量查重和Worker提速至关重要）
    sql_index = """
    CREATE INDEX IF NOT EXISTS idx_orig_eventid ON mentions_original ("GlobalEventID");
    CREATE INDEX IF NOT EXISTS idx_orig_url ON mentions_original ("MentionIdentifier");
    CREATE INDEX IF NOT EXISTS idx_mentions_eventid ON mentions ("GlobalEventID");
    CREATE INDEX IF NOT EXISTS idx_mentions_url ON mentions ("url");
    """

    try:
        with engine.begin() as conn:
            conn.execute(text(sql_orig))
            conn.execute(text(sql_processed))
            conn.execute(text(sql_index))
        logging.info("数据库初始化：表结构与索引检查完成。")
    except Exception as e:
        logging.error(f"数据库初始化失败，请检查数据库服务是否开启: {e}")
        sys.exit(1)

# ==========================================
# 2. 主监控逻辑
# ==========================================
if __name__ == '__main__':
    # 【针对 Mac 系统的关键修复】
    # 强制使用 spawn 模式启动进程，防止 macOS 上的 BrokenPipeError 和资源竞争
    if sys.platform == 'darwin':
        multiprocessing.set_start_method('spawn', force=True)

    # 第一步：初始化数据库
    init_db()

    # 第二步：定义子进程任务
    # 采集进程：负责下载 GDELT 并去重入库原始表
    p_ingest = multiprocessing.Process(
        target=run_ingestor, 
        args=(DATA_DIR,), 
        name="Ingestor"
    )

    # 翻译进程：负责从原始表提数、抓取、翻译、存入结果表
    # 设置 batch_size 为 50，你可以根据翻译 API 速度调整
    p_work = multiprocessing.Process(
        target=run_worker, 
        args=(50,), 
        name="Worker"
    )

    # 第三步：启动进程
    logging.info("系统全量开启：采集任务与翻译任务正在并行运行。")
    p_ingest.start()
    p_work.start()

    logging.info(f"子进程启动详情：Ingestor(PID:{p_ingest.pid}), Worker(PID:{p_work.pid})")

    try:
        # 第四步：健康检查循环
        while True:
            time.sleep(15) # 每 15 秒检查一次进程存活状态
            
            if not p_ingest.is_alive():
                logging.error("Ingestor 采集进程意外退出，正在重新拉起...")
                p_ingest = multiprocessing.Process(target=run_ingestor, args=(DATA_DIR,), name="Ingestor")
                p_ingest.start()
            
            if not p_work.is_alive():
                logging.error("Worker 翻译进程意外退出，正在重新拉起...")
                p_work = multiprocessing.Process(target=run_worker, args=(50,), name="Worker")
                p_work.start()
                
    except KeyboardInterrupt:
        # 第五步：优雅退出
        logging.info("接收到退出指令 (Ctrl+C)，正在安全关闭系统...")
        p_ingest.terminate()
        p_work.terminate()
        p_ingest.join()
        p_work.join()
        logging.info("系统已完全安全关闭。")