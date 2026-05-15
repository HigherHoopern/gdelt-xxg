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

# 关键修复：显式使用绝对导入新的配置名
try:
    from rag_settings import SILICONFLOW_API_KEY, RAG_LLM_MODEL, RAG_EMBED_MODEL, RAG_RERANKER_MODEL, SF_BASE_URL, RAG_DB_URL
except ImportError:
    from service.rag_service.rag_settings import SILICONFLOW_API_KEY, RAG_LLM_MODEL, RAG_EMBED_MODEL, RAG_RERANKER_MODEL, SF_BASE_URL, RAG_DB_URL

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAGService")

class RAGCore:
    def __init__(self):
        # 性能与安全性清洗
        self.clean_key = str(SILICONFLOW_API_KEY).strip().strip('"').strip("'").replace('\n', '').replace('\r', '')
        
        logger.info(f"--- [RAG STARTUP DIAGNOSTIC] ---")
        logger.info(f"Key Fingerprint: {self.clean_key[:7]}...{self.clean_key[-4:]}")
        logger.info(f"Key Length: {len(self.clean_key)}")
        
        if len(self.clean_key) < 51:
            logger.warning("⚠️ 警告：检测到 API Key 长度异常（通常应为 51-52 位），请核对复制是否完整。")

        # 强制设置环境变量以防 SDK 内部逻辑绕过显式传递
        os.environ["SILICONFLOW_API_KEY"] = self.clean_key
        
        # 预检
        self.test_raw_api()

        self.llm = SiliconFlow(model=RAG_LLM_MODEL, api_key=self.clean_key, max_tokens=2048)
        self.embed_model = SiliconFlowEmbedding(model_name=RAG_EMBED_MODEL, api_key=self.clean_key)
        self.reranker = SiliconFlowRerank(model=RAG_RERANKER_MODEL, api_key=self.clean_key, top_n=5)
        
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
            headers = {"Authorization": f"Bearer {self.clean_key}"}
            resp = requests.get(test_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.info("✅ SiliconFlow 原生鉴权测试成功！")
            else:
                logger.error(f"❌ SiliconFlow 原生鉴权失败！状态码: {resp.status_code} | 响应: {resp.text}")
        except Exception as e:
            logger.error(f"⚠️ 预检连接超时: {e}")

    def fetch_data(self):
        since_date = datetime.datetime.now() - datetime.timedelta(days=7)
        query = text("SELECT title_zh, summary_zh, event_date, country_code FROM risk_analysis_data WHERE event_date >= :since AND title_zh != ''")
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params={"since": since_date})

    def refresh_index(self):
        df = self.fetch_data()
        if df.empty: 
            logger.warning("数据库中暂无过去7天的新闻。")
            return False
        docs = [Document(text=f"日期:{r['event_date']} 国家:{r['country_code']} 标题:{r['title_zh']} 内容:{r['summary_zh']}") for _, r in df.iterrows()]
        self.index = VectorStoreIndex.from_documents(docs)
        self.last_update = datetime.datetime.now()
        logger.info(f"索引已刷新: {len(docs)} 条资讯")
        return True

    def query_stream(self, prompt: str):
        if not self.index or (datetime.datetime.now() - self.last_update).total_seconds() > 3600:
            self.refresh_index()
        if not self.index:
            return type('obj', (object,), {'response_gen': iter(["目前没有足够的新闻数据来回答该问题。"])})
        
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
        # 如果是 Api key is invalid，直接返回这个具体的错误
        err_msg = str(e)
        if "Api key is invalid" in err_msg:
            return StreamingResponse(iter(["[错误] SiliconFlow API Key 校验失败，请检查 RAG 服务配置。"]), media_type="text/plain")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
