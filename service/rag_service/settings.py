# services/rag_service/settings.py
import os
from decouple import Config, RepositoryEnv

# =============================================================================
# 0. 全局变量注入 (最优先级修复)
# =============================================================================
# 用户提供的有效 SiliconFlow 密钥
SF_KEY = "sk-nvfzirhgdkcpgmxhzrtpxcywpmlyrsrjhycowlirtfxjtokd"

# 强制注入到 os.environ，确保所有 SDK 都能默认读取到
# 这能解决部分 SDK 内部忽略显式传递的 api_key 而去读环境变量的问题
os.environ["SILICONFLOW_API_KEY"] = SF_KEY
# 同时清除可能导致干扰的全局 OpenAI 变量
INTERFERING_VARS = ['OPENAI_API_KEY', 'OPENAI_API_BASE', 'LLM_API_KEY', 'LLM_BASE_URL']
for var in INTERFERING_VARS:
    if var in os.environ:
        os.environ.pop(var)

# =============================================================================
# 1. 配置加载
# =============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, '.env')

if os.path.exists(ENV_PATH):
    config = Config(RepositoryEnv(ENV_PATH))
    print(f"--- [RAG System] 加载配置文件: {ENV_PATH} ---")
else:
    from decouple import config
    print("--- [RAG System] 未找到 .env，使用默认硬编码配置 ---")

def force_clean_key(v):
    """极致清洗：去空格、去引号、去回车"""
    if not v or str(v).strip() in ["", "EMPTY", "None", "none", "ollama"]: 
        return SF_KEY
    return str(v).strip().strip('"').strip("'").replace('\n', '').replace('\r', '')

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

# 打印调试信息
print(f"--- [RAG DEBUG START] ---")
print(f"PROVIDER: {LLM_PROVIDER}")
print(f"LLM: {llm_model_name} | KEY: {llm_api_key[:10]}...{llm_api_key[-5:]} (LEN: {len(llm_api_key)})")
print(f"EMBED: {embed_model_name} | KEY: {embed_api_key[:10]}...{embed_api_key[-5:]} (LEN: {len(embed_api_key)})")
print(f"--- [RAG DEBUG END] ---")
