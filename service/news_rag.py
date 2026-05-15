import logging
from llama_index.core import Document, VectorStoreIndex, Settings, StorageContext, load_index_from_storage
from sqlalchemy import text
from common.models import SessionLocal
import datetime
import os
from service.rag_service.llm import config_llm
import pandas as pd

logger = logging.getLogger("NewsRAG")

# 持久化索引保存路径
PERSIST_DIR = "./storage/news_index"

class NewsRAGService:
    def __init__(self):
        # 1. 配置 LLM, Embedding, Reranker
        llm, emb, reranker = config_llm()
        Settings.llm = llm
        Settings.embed_model = emb
        self.reranker = reranker
        self.index = None
        self.last_update = None
        
        # 确保存储目录存在
        if not os.path.exists(PERSIST_DIR):
            os.makedirs(PERSIST_DIR, exist_ok=True)

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
        """构建/刷新索引。采用方案：每次加载 7 天数据在内存中构建，简单且能保证时效性"""
        df = self.fetch_last_7d_news()
        if df.empty:
            logger.warning("No news data found for the last 7 days.")
            return False

        documents = []
        for _, row in df.iterrows():
            # 强化上下文信息，帮助 LLM 更好理解新闻背景
            content = (
                f"新闻日期: {row['event_date']}\n"
                f"涉及国家: {row['country_code']}\n"
                f"新闻类别: {row['category']}\n"
                f"新闻标题: {row['title_zh']}\n"
                f"详细内容: {row['summary_zh']}"
            )
            doc = Document(
                text=content,
                metadata={
                    "country": row['country_code'],
                    "date": str(row['event_date']),
                    "category": row['category']
                }
            )
            documents.append(doc)

        # 在内存中创建索引。由于只有 7 天数据，规模通常在几千条以内，内存构建非常快。
        self.index = VectorStoreIndex.from_documents(documents)
        self.last_update = datetime.datetime.now()
        logger.info(f"✅ RAG 索引已重建，包含过去 7 天的 {len(documents)} 条新闻。")
        return True

    def query(self, query_str):
        """执行 RAG 查询"""
        # 如果索引不存在或超过 2 小时未更新，则重建
        if not self.index or (datetime.datetime.now() - self.last_update).total_seconds() > 7200:
            self.rebuild_index()

        if not self.index:
            return type('obj', (object,), {'response_gen': iter(["数据库中暂无过去 7 天的新闻数据，请稍后再试。"])})

        # 配置查询引擎
        node_postprocessors = [self.reranker] if self.reranker else []
        query_engine = self.index.as_query_engine(
            similarity_top_k=8,
            node_postprocessors=node_postprocessors,
            streaming=True
        )
        
        # 自动在 query 中注入“最近 7 天”的背景提示
        refined_query = f"基于过去 7 天的新闻报道，请回答：{query_str}。如果新闻中没有相关信息，请明确告知。"
        
        response = query_engine.query(refined_query)
        return response

# 全局单例
news_rag_service = NewsRAGService()
