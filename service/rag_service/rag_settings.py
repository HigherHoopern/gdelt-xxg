# service/rag_service/config.py
import os

# =============================================================================
# RAG 服务独立配置文件
# =============================================================================

# 请在此处填入您从 SiliconFlow 官网获取的完整 API Key
# 提示：通常 SiliconFlow 的 Key 长度为 52 位（包含 sk- 前缀）
SILICONFLOW_API_KEY = "sk-nvfzirhgdkcpgmxhzrtpxcywpmlyrsrjhycowlirtfxjtokd"

# 模型配置
RAG_LLM_MODEL = "deepseek-ai/DeepSeek-V3"
RAG_EMBED_MODEL = "BAAI/bge-m3"
RAG_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# 基础 URL
SF_BASE_URL = "https://api.siliconflow.cn/v1"

# 数据库配置 (适配 Docker 网络)
RAG_DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://zhenxian:15821828225Lzx!@global_db/dgelt")
