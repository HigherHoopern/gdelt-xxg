# service/rag_service/rag_settings.py
import os
from decouple import Config, RepositoryEnv

# 基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, '.env')

if os.path.exists(ENV_PATH):
    config = Config(RepositoryEnv(ENV_PATH))
else:
    from decouple import config

# =============================================================================
# RAG 服务独立配置 (最终加固版)
# =============================================================================

# 1. 替换为用户提供的全新 Key
DEFAULT_KEY = "sk-srcpejudpayelxblupyevmcgblzwewipehpwpdsylcroctdh"

# 逻辑：优先读取 RAG 专用变量，再读取通用变量，最后使用硬编码
SILICONFLOW_API_KEY = config("RAG_LLM_API_KEY", default=config("LLM_API_KEY", default=DEFAULT_KEY)).strip().strip('"').strip("'")

# 如果读取出来的 Key 被翻译模块干扰变成了 "ollama" 或为空，强制重置为 DEFAULT_KEY
if SILICONFLOW_API_KEY.lower() in ["ollama", "empty", "none", ""]:
    SILICONFLOW_API_KEY = DEFAULT_KEY

# 模型配置
RAG_LLM_MODEL = config("RAG_LLM_MODEL_NAME", default="deepseek-ai/DeepSeek-V3")
RAG_EMBED_MODEL = config("RAG_EMBED_MODEL_NAME", default="BAAI/bge-m3")
RAG_RERANKER_MODEL = config("RAG_RERANKER_NAME", default="BAAI/bge-reranker-v2-m3")

# 基础 URL
SF_BASE_URL = "https://api.siliconflow.cn/v1"

# 数据库配置
RAG_DB_URL = config("DB_URL", default="postgresql+psycopg2://zhenxian:15821828225Lzx!@global_db/dgelt")
