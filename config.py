# config.py
import os
import logging
import warnings
from datetime import datetime
from sqlalchemy import create_engine

DB_URL = "postgresql+psycopg2://zhenxian:  vbn@127.0.0.1/News"
DATA_DIR = "./GDELT_data/"
LOG_DIR = "./logs/main"
GDELT_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# 伪装浏览器请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    # 忽略时区警告
    warnings.filterwarnings("ignore", category=UserWarning, module='dateutil')
    
    log_file = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - [%(processName)s] - %(levelname)s - %(message)s')
    
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(formatter)
    root_logger.addHandler(fh)
    
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)

    # 【关键】屏蔽三方库的噪音日志
    logging.getLogger("newspaper").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("jieba").setLevel(logging.ERROR)

def get_engine():
    return create_engine(DB_URL, pool_size=10, max_overflow=20)