import logging
import os
import datetime
import pandas as pd
from sqlalchemy import text
from common.models import SessionLocal

# LlamaIndex 核心
from llama_index.core import Document, VectorStoreIndex, Settings
# SiliconFlow 原生适配
from llama_index.llms.siliconflow import SiliconFlow
from llama_index.embeddings.siliconflow import SiliconFlowEmbedding
from llama_index.postprocessor.siliconflow_rerank import SiliconFlowRerank

logger = logging.getLogger("NewsRAG")

# =============================================================================
# 1. 强制硬编码配置 (唯一真相，避免任何环境变量干扰)
# =============================================================================
SF_KEY = "sk-nvfzirhgdkcpgmxhzrtpxcywpmlyrsrjhycowlirtfxjtokd"
LLM_MODEL = "deepseek-ai/DeepSeek-V3"
EMBED_MODEL = "BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

class NewsRAGService:
    def __init__(self):
        logger.info("🚀 正在初始化 RAG 系统 (Native SiliconFlow 模式)...")
        
        # 强制清理并注入环境变量
        os.environ["SILICONFLOW_API_KEY"] = SF_KEY
        
        # 1. 配置 LLM
        self.llm = SiliconFlow(
            model=LLM_MODEL,
            api_key=SF_KEY,
            max_tokens=2048,
            temperature=0.1,
            timeout=600
        )
        
        # 2. 配置 Embedding
        self.embed_model = SiliconFlowEmbedding(
            model_name=EMBED_MODEL,
            api_key=SF_KEY
        )
        
        # 3. 配置 Reranker
        self.reranker = SiliconFlowRerank(
            model=RERANKER_MODEL,
            api_key=SF_KEY,
            top_n=5
        )
        
        # 设置全局 Settings
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model
        
        self.index = None
        self.last_update = None
        
        # 启动自检
        self.test_connectivity()

    def test_connectivity(self):
        """预飞行检查：确保 API Key 在 SiliconFlow 侧有效"""
        try:
            logger.info(f"--- [RAG 连通性测试] ---")
            # 尝试一个极简生成
            self.llm.complete("Hi")
            logger.info("✅ LLM 鉴权成功！")
        except Exception as e:
            logger.error(f"❌ LLM 鉴权失败: {str(e)}")
            logger.error(f"请检查 API Key: {SF_KEY[:10]}...{SF_KEY[-5:]} 是否有效或有余额。")

    def fetch_last_7d_news(self):
        """从数据库获取过去 7 天的新闻"""
        session = SessionLocal()
        try:
            since_date = datetime.datetime.now() - datetime.timedelta(days=7)
            query = text("""
                SELECT country_code, category, title_zh, summary_zh, event_date 
                FROM risk_analysis_data 
                WHERE event_date >= :since
                AND (title_zh IS NOT NULL AND title_zh != '')
                ORDER BY event_date DESC
            """)
            df = pd.read_sql(query, session.bind, params={"since": since_date})
            return df
        finally:
            session.close()

    def rebuild_index(self):
        """构建/刷新内存索引"""
        df = self.fetch_last_7d_news()
        if df.empty:
            logger.warning("数据库中暂无过去 7 天的新闻。")
            return False

        documents = []
        for _, row in df.iterrows():
            content = (
                f"新闻日期: {row['event_date']}\n"
                f"涉及国家: {row['country_code']}\n"
                f"类别: {row['category']}\n"
                f"标题: {row['title_zh']}\n"
                f"摘要: {row['summary_zh']}"
            )
            doc = Document(text=content, metadata={"country": row['country_code']})
            documents.append(doc)

        self.index = VectorStoreIndex.from_documents(documents)
        self.last_update = datetime.datetime.now()
        logger.info(f"✅ RAG 索引已重建，包含 {len(documents)} 条新闻。")
        return True

    def query(self, query_str):
        """执行 RAG 查询 (支持流式输出)"""
        # 缓存逻辑：2 小时刷新一次
        if not self.index or (datetime.datetime.now() - self.last_update).total_seconds() > 7200:
            self.rebuild_index()

        if not self.index:
            # 返回一个模拟的流对象
            return type('obj', (object,), {'response_gen': iter(["抱歉，目前数据库中没有过去 7 天的新闻记录，无法回答。"])})

        query_engine = self.index.as_query_engine(
            similarity_top_k=8,
            node_postprocessors=[self.reranker],
            streaming=True
        )
        
        refined_query = f"基于过去 7 天的新闻报道，请回答：{query_str}。如果新闻中没有相关信息，请明确告知。"
        return query_engine.query(refined_query)

# 全局单例
news_rag_service = NewsRAGService()
