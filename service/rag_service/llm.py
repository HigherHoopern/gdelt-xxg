# llm.py
import logging
import os
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.postprocessor.siliconflow_rerank import SiliconFlowRerank
from llama_index.core import Settings

# --- 直接从 settings.py 导入配置 ---
try:
    from .settings import (
        LLM_PROVIDER, llm_model_name, llm_base_url, llm_api_key,
        embed_model_name, embed_base_url, embed_api_key,
        reranker_name, reranker_api_key, TOP_K, num_output
    )
except (ImportError, ValueError):
    from settings import (
        LLM_PROVIDER, llm_model_name, llm_base_url, llm_api_key,
        embed_model_name, embed_base_url, embed_api_key,
        reranker_name, reranker_api_key, TOP_K, num_output
    )

# 设置全局输出限制
Settings.num_output = num_output

def config_llm():
    """
    根据从 settings.py 导入的全局配置来初始化模型。
    针对 SiliconFlow 优化：直接使用标准 OpenAI 类以获得最大稳定性。
    """
    provider = LLM_PROVIDER.lower()
    logging.info(f"--- RAG 模型初始化 (Provider: {provider}) ---")

    if provider == "siliconflow":
        # 1. 初始化 LLM
        # 直接使用 OpenAI 类，但在 api_base 中指定 SiliconFlow 地址
        # 这种方式比 OpenAILike 更能强制 API Key 的传递
        llm = OpenAI(
            model=llm_model_name,
            api_key=llm_api_key,
            api_base=llm_base_url,
            max_tokens=num_output,
            temperature=0.1,
            timeout=600,
            reuse_client=False # 强制每次创建新客户端，避免干扰
        )

        # 2. 初始化 Embedding
        # 同样使用标准 OpenAIEmbedding 配合自定义 api_base
        emb = OpenAIEmbedding(
            model=embed_model_name,
            api_key=embed_api_key,
            api_base=embed_base_url,
            timeout=600,
        )

        # 3. 初始化 Reranker
        reranker = SiliconFlowRerank(
            model=reranker_name,
            api_key=reranker_api_key,
            top_n=TOP_K,
        )

    else:
        # 非 siliconflow 模式下的逻辑（保持基本兼容）
        from llama_index.llms.openai_like import OpenAILike
        from llama_index.embeddings.openai_like import OpenAILikeEmbedding
        
        llm = OpenAILike(model=llm_model_name, api_key=llm_api_key, api_base=llm_base_url, is_chat_model=True)
        emb = OpenAILikeEmbedding(model_name=embed_model_name, api_key=embed_api_key, api_base=embed_base_url)
        reranker = None

    return llm, emb, reranker
