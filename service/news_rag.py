import logging
from llama_index.core import Document, VectorStoreIndex, Settings
from sqlalchemy import text
from common.models import SessionLocal
import datetime
from service.rag_service.llm import config_llm
from service.rag_service.prompt import QA_PROMPT_TMPL # 如果有预定义的 prompt
import pandas as pd

logger = logging.getLogger("NewsRAG")

class NewsRAGService:
    def __init__(self):
        # 1. 配置 LLM, Embedding, Reranker
        llm, emb, reranker = config_llm()
        Settings.llm = llm
        Settings.embed_model = emb
        self.reranker = reranker
        self.index = None
        self.last_update = None

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
        """重新构建内存索引"""
        df = self.fetch_last_7d_news()
        if df.empty:
            logger.warning("No news data found for the last 7 days.")
            return False

        documents = []
        for _, row in df.iterrows():
            content = f"时间: {row['event_date']}\n国家: {row['country_code']}\n类别: {row['category']}\n标题: {row['title_zh']}\n摘要: {row['summary_zh']}"
            doc = Document(
                text=content,
                metadata={
                    "country": row['country_code'],
                    "date": str(row['event_date']),
                    "category": row['category']
                }
            )
            documents.append(doc)

        self.index = VectorStoreIndex.from_documents(documents)
        self.last_update = datetime.datetime.now()
        logger.info(f"RAG index rebuilt with {len(documents)} documents.")
        return True

    def query(self, query_str):
        """执行 RAG 查询"""
        # 如果索引不存在或超过 1 小时未更新，则重建（简单缓存策略）
        if not self.index or (datetime.datetime.now() - self.last_update).total_seconds() > 3600:
            self.rebuild_index()

        if not self.index:
            return "数据库中暂无过去 7 天的相关新闻数据。"

        # 配置查询引擎
        node_postprocessors = [self.reranker] if self.reranker else []
        query_engine = self.index.as_query_engine(
            similarity_top_k=10,
            node_postprocessors=node_postprocessors,
            streaming=True
        )
        
        response = query_engine.query(query_str)
        return response

# 全局单例
news_rag_service = NewsRAGService()
