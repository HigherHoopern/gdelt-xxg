# llm.py
import logging
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
from llama_index.postprocessor.xinference_rerank import XinferenceRerank
from llama_index.core import Settings

try:
    from .settings import (
        LLM_PROVIDER, llm_model_name, llm_base_url, llm_api_key,
        embed_model_name, embed_base_url, embed_api_key,
        reranker_name, reranker_base_url, TOP_K, num_output
    )
except (ImportError, ValueError):
    from settings import (
        LLM_PROVIDER, llm_model_name, llm_base_url, llm_api_key,
        embed_model_name, embed_base_url, embed_api_key,
        reranker_name, reranker_base_url, TOP_K, num_output
    )

# 设置全局输出限制
Settings.num_output = num_output

def config_llm():
    """
    根据从 settings.py 导入的全局配置来初始化模型。
    """
    provider = LLM_PROVIDER.lower()

    logging.info(f"--- 正在配置模型，使用的提供商: {provider} ---")
    logging.info(f"LLM 模型: {llm_model_name} @ {llm_base_url}")
    logging.info(f"Embedding 模型: {embed_model_name}")
    logging.info(f"Reranker 模型: {reranker_name}")
    
    # 1. 初始化 LLM (通用 OpenAILike 适配)
    # 注意：SiliconFlow 和 Xinference 都兼容 OpenAI 协议
    llm = OpenAILike(
        model=llm_model_name,
        api_key=llm_api_key, 
        api_base=llm_base_url,
        max_tokens=num_output,
        temperature=0.0,
        is_chat_model=True,
        timeout=600
    )

    # 2. 根据 Provider 初始化 Embedding 和 Reranker
    if provider == 'xinf':
        emb = OpenAILikeEmbedding(
            model_name=embed_model_name,
            api_base=embed_base_url,
            api_key=embed_api_key,
        )
        reranker = XinferenceRerank(
            top_n=TOP_K,
            model=reranker_name,
            base_url=reranker_base_url,
        )

    elif provider == "openai-like":
        emb = OpenAILikeEmbedding(
            model_name=embed_model_name,
            api_base=embed_base_url,
            api_key=embed_api_key,
        )
        reranker = None

    elif provider == "siliconflow":
        # 动态导入 SiliconFlow 专有组件
        from llama_index.embeddings.siliconflow import SiliconFlowEmbedding
        from llama_index.postprocessor.siliconflow_rerank import SiliconFlowRerank
        
        # 使用 settings 中的配置，不再硬编码
        emb = SiliconFlowEmbedding(
            model=embed_model_name,
            api_key=embed_api_key,
        )

        reranker = SiliconFlowRerank(
            model=reranker_name,
            api_key=embed_api_key, # 通常 Embedding 和 Rerank 共用 key
            top_n=TOP_K,
        )

    else:
        raise ValueError(f"不支持的 provider: '{provider}'。请检查 .env 中的 LLM_PROVIDER 设置。")
    
    return llm, emb, reranker

if __name__ == "__main__":
    from llama_index.core import QueryBundle
    from llama_index.core.schema import NodeWithScore, TextNode

    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*50)
    print(f"🚀 开始进行 {LLM_PROVIDER} 模式功能测试")
    print("="*50)

    try:
        # 1. 初始化
        llm, emb, reranker = config_llm()
        
        # --- 测试 1: LLM ---
        print("\n[测试 1/3] LLM 生成测试...")
        llm_response = llm.complete("请用五个字以内形容江城。")
        print(f"✅ LLM 响应成功: {llm_response}")

        # --- 测试 2: Embedding ---
        print("\n[测试 2/3] Embedding 向量化测试...")
        test_text = "江城哈尼族彝族自治县"
        embed_result = emb.get_text_embedding(test_text)
        print(f"✅ Embedding 成功! 向量维度: {len(embed_result)}")

        # --- 测试 3: Reranker ---
        print("\n[测试 3/3] Reranker 重排测试...")
        if reranker:
            query = "江城的支柱产业是什么？"
            nodes = [
                NodeWithScore(node=TextNode(text="江城县的橡胶产业是当地的重要经济支柱。"), score=0.5),
                NodeWithScore(node=TextNode(text="今天江城的天气多云转晴。"), score=0.2),
            ]
            query_bundle = QueryBundle(query_str=query)
            ranked_nodes = reranker.postprocess_nodes(nodes, query_bundle)
            print(f"✅ Reranker 成功! 首位结果: {ranked_nodes[0].text}")
        else:
            print("⚠️ 未配置 Reranker，跳过测试")

        print("\n" + "="*50)
        print(f"🎉 {LLM_PROVIDER} 模式全链路测试通过！")
        print("="*50)

    except Exception as e:
        print("\n" + "!"*50)
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        print("!"*50)