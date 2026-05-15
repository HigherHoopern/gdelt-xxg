# services/rag_service/settings.py
import os
from decouple import Config, RepositoryEnv, UndefinedValueError

# =============================================================================
# 0. 强制跨目录读取根目录的 .env 文件
# =============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, '.env')

if os.path.exists(ENV_PATH):
    config = Config(RepositoryEnv(ENV_PATH))
    print(f"--- [Config] 成功加载配置文件: {ENV_PATH} ---")
else:
    from decouple import config
    print("--- [Config] 未找到 .env，使用系统环境变量 ---")

def cast_to_none_or_int(value):
    if isinstance(value, str) and value.strip().lower() == 'none':
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

# =============================================================================
# 基础配置
# =============================================================================
DEBUG = config('DEBUG', default=False, cast=bool)

# RAG 核心参数
# 针对 RAG 使用专门的 Provider 变量，避免与翻译用的 OLLAMA 冲突
LLM_PROVIDER = config("RAG_LLM_PROVIDER", default='siliconflow')
CHUNK_SIZE = config("CHUNK_SIZE", default=1024, cast=int)
VEC_STORE = config("VEC_STORE", default="milvus") 
STREAM = config("STREAM", default=True, cast=bool) 
TOP_K = config("TOP_K", default=5, cast=int)
REBUILD_INDEX = config("REBUILD_INDEX", default=False, cast=bool)

KB_FOLDER_DIR = config("KB_FOLDER_DIR", default='./kb_md')
LOCAL_VECTOR_DB_PATH = config("LOCAL_VECTOR_DB_PATH", default="./vector_store")

try:
    # =============================================================================
    # MinIO 配置 (修改默认值为 localhost)
    # =============================================================================
    minio_endpoint = config("MINIO_ENDPOINT", default="localhost:9000")
    minio_access_key = config("MINIO_ACCESS_KEY", default="minioadmin")
    minio_secret_key = config("MINIO_SECRET_KEY", default="minioadmin")
    minio_bucket = config("MINIO_BUCKET_NAME", default="xterai-kb")
    minio_secure = config("MINIO_SECURE", default=False, cast=bool)

    # =============================================================================
    # Milvus 配置 (修改变量名对齐 .env 并修改默认地址)
    # =============================================================================
    # ！！！注意：这里改为读取 .env 中的 MILVUS 变量
    MILVUS = config("MILVUS", default=False, cast=bool)
    milvus_uri = config("MILVUS_URI", default="http://localhost:19530")
    milvus_token = config("MILVUS_TOKEN", default='')
    MILVUS_COLLECTION_NAME = config("MILVUS_COLLECTION_NAME", default="jiangcheng_vec")
    
    # =============================================================================
    # LLM (大语言模型) 配置
    # =============================================================================
    SILICONFLOW_KEY = "sk-nvfzirhgdkcpgmxhzrtpxcywpmlyrsrjhycowlirtfxjtokd"

    llm_model_name = config("LLM_MODEL_NAME", default="deepseek-ai/DeepSeek-V3")
    llm_base_url = config("LLM_BASE_URL", default="https://api.siliconflow.cn/v1")

    # 强制逻辑：如果环境变量为空或为 EMPTY，则回退到 SiliconFlow Key
    # 彻底杜绝引号干扰：直接替换掉所有引号
    def clean_key(v):
        if not v or v == "EMPTY": return SILICONFLOW_KEY
        return str(v).strip().replace('"', '').replace("'", "")

    llm_api_key = clean_key(config("LLM_API_KEY", default=SILICONFLOW_KEY))
    embed_api_key = clean_key(config('EMBED_API_KEY', default=SILICONFLOW_KEY))
    reranker_api_key = clean_key(config('RERANKER_API_KEY', default=SILICONFLOW_KEY))

    context_window_size = config("CONTEXT_WINDOW_SIZE", default=32768, cast=int)
    num_output = config("NUM_OUTPUT", default=2048, cast=int)

    # =============================================================================
    # Embedding (嵌入模型) 配置
    # =============================================================================
    embed_model_name = config('EMBED_MODEL_NAME', default="BAAI/bge-m3")
    embed_base_url = config('EMBED_BASE_URL', default="https://api.siliconflow.cn/v1")

    # =============================================================================
    # Reranker (重排序模型) 配置
    # =============================================================================
    reranker_name = config('RERANKER_NAME', default='BAAI/bge-reranker-v2-m3')
    reranker_base_url = config('RERANKER_BASE_URL', default='https://api.siliconflow.cn/v1')

    # 打印掩码后的 Key 以供调试
    print(f"--- [RAG Config] LLM Key: {llm_api_key[:6]}...{llm_api_key[-4:]} (len: {len(llm_api_key)}) ---")
    print(f"--- [RAG Config] Embed Key: {embed_api_key[:6]}...{embed_api_key[-4:]} (len: {len(embed_api_key)}) ---")
    
    # =============================================================================
    # Redis 配置 (修改默认值为 localhost)
    # =============================================================================
    use_redis = config("USE_REDIS", default=True, cast=bool)
    redis_host = config("REDIS_HOST", default="localhost")
    redis_port = config("REDIS_PORT", default=6379, cast=int)

    # --- 新增：鉴权配置 ---
    auth_secret_key = config("AUTH_SECRET_KEY", default="xterai_jiangcheng_super_secret_key_2026")
    auth_algorithm = config("ALGORITHM", default="HS256")

except UndefinedValueError as e:
    import sys
    print(f"\n{'='*50}\n!!! [配置错误] 缺少关键环境变量: {e}\n{'='*50}\n")
    raise SystemExit(1)