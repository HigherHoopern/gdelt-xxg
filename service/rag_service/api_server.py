import logging
import os
import datetime
import pandas as pd
from sqlalchemy import text
from sqlalchemy import create_engine
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from fastapi.responses import StreamingResponse

# LlamaIndex 核心
from llama_index.core import Document, VectorStoreIndex, Settings
# SiliconFlow 原生适配
from llama_index.llms.siliconflow import SiliconFlow
from llama_index.embeddings.siliconflow import SiliconFlowEmbedding
from llama_index.postprocessor.siliconflow_rerank import SiliconFlowRerank

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAGService")

# =============================================================================
# 1. 核心配置 (从环境变量读取，优先适配 Docker 环境)
# =============================================================================
SF_KEY = os.getenv("RAG_LLM_API_KEY", "sk-nvfzirhgdkcpgmxhzrtpxcywpmlyrsrjhycowlirtfxjtokd")
LLM_MODEL = os.getenv("RAG_LLM_MODEL_NAME", "deepseek-ai/DeepSeek-V3")
EMBED_MODEL = os.getenv("RAG_EMBED_MODEL_NAME", "BAAI/bge-m3")
RERANKER_MODEL = os.getenv("RAG_RERANKER_NAME", "BAAI/bge-reranker-v2-m3")

# 核心修复：DB_URL 必须指向 global_db 容器名，而不是 127.0.0.1
DEFAULT_DB_URL = "postgresql+psycopg2://zhenxian:15821828225Lzx!@global_db/dgelt"
DB_URL = os.getenv("DB_URL", DEFAULT_DB_URL)

class RAGCore:
    def __init__(self):
        logger.info(f"🚀 初始化 RAG 引擎: {LLM_MODEL}")
        logger.info(f"🔗 正在连接数据库: {DB_URL.split('@')[-1]}") # 掩码打印 DB 地址
        
        self.llm = SiliconFlow(model=LLM_MODEL, api_key=SF_KEY, max_tokens=2048)
        self.embed_model = SiliconFlowEmbedding(model_name=EMBED_MODEL, api_key=SF_KEY)
        self.reranker = SiliconFlowRerank(model=RERANKER_MODEL, api_key=SF_KEY, top_n=5)
        
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model
        
        self.index = None
        self.last_update = None
        self.engine = create_engine(DB_URL)

    def fetch_data(self):
        since_date = datetime.datetime.now() - datetime.timedelta(days=7)
        # 使用 SQLAlchemy text 对象以获得更好的兼容性
        query = text("SELECT title_zh, summary_zh, event_date, country_code FROM risk_analysis_data WHERE event_date >= :since AND title_zh != ''")
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params={"since": since_date})

    def refresh_index(self):
        df = self.fetch_data()
        if df.empty: return False
        docs = [Document(text=f"日期:{r['event_date']} 国家:{r['country_code']} 标题:{r['title_zh']} 内容:{r['summary_zh']}") for _, r in df.iterrows()]
        self.index = VectorStoreIndex.from_documents(docs)
        self.last_update = datetime.datetime.now()
        logger.info(f"索引已刷新: {len(docs)} 条资讯")
        return True

    def query_stream(self, prompt: str):
        if not self.index or (datetime.datetime.now() - self.last_update).total_seconds() > 3600:
            self.refresh_index()
        
        query_engine = self.index.as_query_engine(similarity_top_k=10, node_postprocessors=[self.reranker], streaming=True)
        return query_engine.query(f"基于过去7天新闻回答：{prompt}")

rag_core = RAGCore()
app = FastAPI(title="GDELT RAG Service")

class QueryRequest(BaseModel):
    prompt: str

@app.post("/query")
async def query(request: QueryRequest):
    try:
        response = rag_core.query_stream(request.prompt)
        def event_generator():
            for token in response.response_gen:
                yield token
        return StreamingResponse(event_generator(), media_type="text/plain")
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
