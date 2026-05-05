import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

def setup_logger(name):
    log_dir = "./logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 避免重复添加 handler
    if not logger.handlers:
        # 格式化
        formatter = logging.Formatter('%(asctime)s - [%(name)s] - [%(levelname)s] - %(message)s')

        # 按天滚动的日志处理器
        # filename 设为基础名，但在实际生成时我们会通过 suffix 来体现日期
        log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        
        file_handler = TimedRotatingFileHandler(
            log_file, 
            when="midnight", 
            interval=1, 
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 同时输出到控制台
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
