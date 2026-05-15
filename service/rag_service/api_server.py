import logging
import os
import datetime
import pandas as pd
from sqlalchemy import text, create_engine
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from fastapi.responses import StreamingResponse

# LlamaIndex 核心
from llama_index.core import Document, VectorStoreIndex, Settings
# SiliconFlow 原生适配
from llama_index.llms.siliconflow import SiliconFlow
from llama_index.embeddings.siliconflow import SiliconFlowEmbedding
from llama_index.postprocessor.siliconflow_rerank import SiliconFlowRerank

# 导入独立配置
from config import SILICONFLOW_API_KEY, RAG_LLM_MODEL, RAG_EMBED_MODEL, RAG_RERANKER_MODEL, SF_BASE_URL, RAG_DB_URL

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAGService")

class RAGCore:
    def __init__(self):
        logger.info(f"--- [RAG CORE STARTUP] ---")
        
        # 强制设置环境变量以防 SDK 默认读取
        os.environ["SILICONFLOW_API_KEY"] = SILICONFLOW_API_KEY
        
        # 预检：直接测试 API
        self.test_raw_api()

        self.llm = SiliconFlow(model=RAG_LLM_MODEL, api_key=SILICONFLOW_API_KEY, max_tokens=2048)
        self.embed_model = SiliconFlowEmbedding(model_name=RAG_EMBED_MODEL, api_key=SILICONFLOW_API_KEY)
        self.reranker = SiliconFlowRerank(model=RAG_RERANKER_MODEL, api_key=SILICONFLOW_API_KEY, top_n=5)
        
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model
        
        self.index = None
        self.last_update = None
        self.engine = create_engine(RAG_DB_URL)
        logger.info(f"--- [RAG CORE READY] ---")

    def test_raw_api(self):
        import requests
        try:
            test_url = f"{SF_BASE_URL}/user/info"
            headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}"}
            resp = requests.get(test_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.info("✅ SiliconFlow API 鉴权测试成功！")
            else:
                # 打印详细指纹以供对比
                logger.error(f"❌ SiliconFlow API 鉴权失败！响应: {resp.text}")
                logger.error(f"当前使用的 Key 指纹: {SILICONFLOW_API_KEY[:6]}...{SILICONFLOW_API_KEY[-4:]} | 长度: {len(SILICONFLOW_API_KEY)}")
                logger.error("请检查您在 service/rag_service/config.py 中填写的 Key 是否完整（通常为 52 位）。")
        except Exception as e:
            logger.error(f"⚠️ 无法连接预检: {e}")

    def fetch_data(self):
        since_date = datetime.datetime.now() - datetime.timedelta(days=7)
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
