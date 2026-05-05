# config/settings.py
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 1. 数据库配置
DB_CONFIG = {
    'url': os.getenv('DB_URL', 'postgresql+psycopg2://zhenxian:  vbn@127.0.0.1/dgelt'),
    'pool_size': int(os.getenv('DB_POOL_SIZE', 20))
}

# 2. GDELT 配置
GDELT_UPDATE_URL = os.getenv('GDELT_UPDATE_URL', "http://data.gdeltproject.org/gdeltv2/lastupdate.txt")

# 3. 南亚东南亚国家监控配置 (FIPS 10-4)
REGIONAL_COUNTRIES = {
    # 东南亚 (ASEAN + Timor-Leste)
    'BRUNEI': {'fips': 'BX', 'iso': 'BRN'},
    'CAMBODIA': {'fips': 'CB', 'iso': 'KHM'},
    'INDONESIA': {'fips': 'ID', 'iso': 'IDN'},
    'LAOS': {'fips': 'LA', 'iso': 'LAO'},
    'MALAYSIA': {'fips': 'MY', 'iso': 'MYS'},
    'MYANMAR': {'fips': 'BM', 'iso': 'MMR'},
    'PHILIPPINES': {'fips': 'RP', 'iso': 'PHL'},
    'SINGAPORE': {'fips': 'SN', 'iso': 'SGP'},
    'THAILAND': {'fips': 'TH', 'iso': 'THA'},
    'VIETNAM': {'fips': 'VM', 'iso': 'VNM'},
    'TIMOR_LESTE': {'fips': 'TT', 'iso': 'TLS'},
    # 南亚
    'INDIA': {'fips': 'IN', 'iso': 'IND'},
    'PAKISTAN': {'fips': 'PK', 'iso': 'PAK'},
    'BANGLADESH': {'fips': 'BG', 'iso': 'BGD'},
    'SRI_LANKA': {'fips': 'CE', 'iso': 'LKA'},
    'NEPAL': {'fips': 'NP', 'iso': 'NPL'},
    'BHUTAN': {'fips': 'BT', 'iso': 'BTN'}
}

# 4. 大模型配置 (符合 OpenAI 兼容格式)
LLM_CONFIG = {
    'provider': os.getenv('LLM_PROVIDER', 'siliconflow'),
    'model_name': os.getenv('LLM_MODEL_NAME', 'deepseek-ai/DeepSeek-V3'),
    'base_url': os.getenv('LLM_BASE_URL', 'https://api.siliconflow.cn/v1'),
    'api_key': os.getenv('LLM_API_KEY', '')
}

# 5. 系统调度配置 (秒)
SCHEDULE = {
    'ingest_interval': int(os.getenv('INGEST_INTERVAL', 900)),
    'process_interval': int(os.getenv('PROCESS_INTERVAL', 600)),
    'predict_interval': int(os.getenv('PREDICT_INTERVAL', 3600))
}
