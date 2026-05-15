# services/rag_service/settings.py
import os
from decouple import Config, RepositoryEnv

# =============================================================================
# 0. 基础路径与环境清理
# =============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, '.env')

# 关键修复：清除可能导致干扰的全局环境变量
# 如果这些变量存在且指向 ollama，会导致 OpenAI 客户端报错 401
INTERFERING_VARS = ['OPENAI_API_KEY', 'OPENAI_API_BASE', 'LLM_API_KEY', 'LLM_BASE_URL']
for var in INTERFERING_VARS:
    if var in os.environ:
        os.environ.pop(var)

if os.path.exists(ENV_PATH):
    config = Config(RepositoryEnv(ENV_PATH))
    print(f"--- [RAG System] 加载配置文件: {ENV_PATH} ---")
else:
    from decouple import config
    print("--- [RAG System] 未找到 .env，使用默认硬编码配置 ---")

# =============================================================================
# RAG 专用模型配置 (强制使用 SiliconFlow)
# =============================================================================

# 1. 用户提供的 SiliconFlow 密钥 (这是唯一真理)
SF_KEY = "sk-nvfzirhgdkcpgmxhzrtpxcywpmlyrsrjhycowlirtfxjtokd"

def force_clean_key(v):
    """极致清洗：去空格、去引号、如果是占位符则返回 SF_KEY"""
    if not v or str(v).strip() in ["", "EMPTY", "None", "none", "ollama"]: 
        return SF_KEY
    return str(v).strip().strip('"').strip("'")

# RAG 专用 Provider
LLM_PROVIDER = config("RAG_LLM_PROVIDER", default='siliconflow')

# LLM 配置
llm_model_name = config("RAG_LLM_MODEL_NAME", default="deepseek-ai/DeepSeek-V3")
llm_base_url = config("RAG_LLM_BASE_URL", default="https://api.siliconflow.cn/v1")
llm_api_key = force_clean_key(config("RAG_LLM_API_KEY", default=SF_KEY))

# Embedding 配置
embed_model_name = config('RAG_EMBED_MODEL_NAME', default="BAAI/bge-m3")
embed_base_url = config('RAG_EMBED_BASE_URL', default="https://api.siliconflow.cn/v1")
embed_api_key = force_clean_key(config('RAG_EMBED_API_KEY', default=SF_KEY))

# Reranker 配置
reranker_name = config('RAG_RERANKER_NAME', default='BAAI/bge-reranker-v2-m3')
reranker_base_url = config('RAG_RERANKER_BASE_URL', default='https://api.siliconflow.cn/v1')
reranker_api_key = force_clean_key(config('RAG_RERANKER_API_KEY', default=SF_KEY))

# 其他参数
TOP_K = config("TOP_K", default=5, cast=int)
CHUNK_SIZE = config("CHUNK_SIZE", default=1024, cast=int)
num_output = config("NUM_OUTPUT", default=2048, cast=int)

# 打印调试信息（启动容器时务必查看 docker logs）
print(f"--- [RAG DEBUG START] ---")
print(f"PROVIDER: {LLM_PROVIDER}")
print(f"LLM: {llm_model_name} | URL: {llm_base_url} | KEY: {llm_api_key[:10]}...{llm_api_key[-5:]}")
print(f"EMBED: {embed_model_name} | URL: {embed_base_url} | KEY: {embed_api_key[:10]}...{embed_api_key[-5:]}")
print(f"--- [RAG DEBUG END] ---")
