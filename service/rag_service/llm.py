# llm.py
import logging
import os
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
    全量使用 LlamaIndex + SiliconFlow 原生接口类。
    """
    provider = LLM_PROVIDER.lower()
    logging.info(f"--- RAG 模型初始化 (Provider: {provider}) ---")

    if provider == "siliconflow":
        # 1. 初始化 LLM (使用 SiliconFlow 专属类)
        from llama_index.llms.siliconflow import SiliconFlow
        llm = SiliconFlow(
            model=llm_model_name,
            api_key=llm_api_key,
            max_tokens=num_output,
            temperature=0.1,
            timeout=600,
        )

        # 2. 初始化 Embedding (使用 SiliconFlow 专属类)
        from llama_index.embeddings.siliconflow import SiliconFlowEmbedding
        emb = SiliconFlowEmbedding(
            model_name=embed_model_name,
            api_key=embed_api_key,
        )

        # 3. 初始化 Reranker (使用 SiliconFlow 专属类)
        from llama_index.postprocessor.siliconflow_rerank import SiliconFlowRerank
        reranker = SiliconFlowRerank(
            model=reranker_name,
            api_key=reranker_api_key,
            top_n=TOP_K,
        )

    else:
        # 非 siliconflow 模式下的逻辑
        from llama_index.llms.openai_like import OpenAILike
        from llama_index.embeddings.openai_like import OpenAILikeEmbedding
        
        llm = OpenAILike(model=llm_model_name, api_key=llm_api_key, api_base=llm_base_url, is_chat_model=True)
        emb = OpenAILikeEmbedding(model_name=embed_model_name, api_key=embed_api_key, api_base=embed_base_url)
        reranker = None

    return llm, emb, reranker
