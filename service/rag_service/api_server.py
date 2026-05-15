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
try:
    from rag_settings import SILICONFLOW_API_KEY, RAG_LLM_MODEL, RAG_EMBED_MODEL, RAG_RERANKER_MODEL, SF_BASE_URL, RAG_DB_URL
except ImportError:
    from service.rag_service.rag_settings import SILICONFLOW_API_KEY, RAG_LLM_MODEL, RAG_EMBED_MODEL, RAG_RERANKER_MODEL, SF_BASE_URL, RAG_DB_URL

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAGService")

class RAGCore:
    def __init__(self):
        # 强制清除环境变量干扰，并注入正确 Key
        os.environ["SILICONFLOW_API_KEY"] = SILICONFLOW_API_KEY
        
        logger.info(f"--- [RAG STARTUP DIAGNOSTIC] ---")
        logger.info(f"Using Key Fingerprint: {SILICONFLOW_API_KEY[:7]}...{SILICONFLOW_API_KEY[-4:]}")
        logger.info(f"Using Key Length: {len(SILICONFLOW_API_KEY)}")
        
        # 预检：直接测试 API
        self.test_raw_api()

        self.llm = SiliconFlow(model=RAG_LLM_MODEL, api_key=SILICONFLOW_API_KEY, max_tokens=2048)
        self.embed_model = SiliconFlowEmbedding(model_name=RAG_EMBED_MODEL, api_key=SILICONFLOW_API_KEY)
        self.reranker = SiliconFlowRerank(model=RAG_RERANKER_MODEL, api_key=SILICONFLOW_API_KEY, top_n=5)
        
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model
        Settings.chunk_size = 2048
        Settings.chunk_overlap = 50
        
        self.index = None
        self.last_update = None
        self.engine = create_engine(RAG_DB_URL)
        logger.info(f"--- [RAG CORE READY] ---")

    def test_raw_api(self):
        import requests
        try:
            # 尝试访问账号余额/信息接口作为最准的测试
            test_url = f"{SF_BASE_URL}/user/info"
            headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}"}
            resp = requests.get(test_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.info("✅ SiliconFlow API 鉴权测试成功！")
            else:
                logger.error(f"❌ SiliconFlow API 鉴权失败！响应: {resp.text}")
                logger.error(f"请检查 Key 是否有余额或权限: {SILICONFLOW_API_KEY}")
        except Exception as e:
            logger.error(f"⚠️ 预检连接超时: {e}")

    def fetch_data(self):
        try:
            since_date = datetime.datetime.now() - datetime.timedelta(days=7)
            logger.info(f"正在从数据库读取新闻数据 (从 {since_date} 至今)...")
            query = text("SELECT title_zh, summary_zh, event_date, country_code FROM risk_analysis_data WHERE event_date >= :since AND title_zh != ''")
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={"since": since_date})
                logger.info(f"数据库读取完成，共获取 {len(df)} 条新闻。")
                return df
        except Exception as e:
            logger.error(f"数据库读取异常: {e}")
            return pd.DataFrame()

    def refresh_index(self):
        try:
            logger.info("开始构建 RAG 向量索引...")
            df = self.fetch_data()
            if df.empty: 
                logger.warning("数据库中暂无过去7天的新闻，跳过索引构建。")
                return False
            
            docs = []
            for _, r in df.iterrows():
                # 将文本和元数据分离，以便后续引用
                text_content = f"标题:{r['title_zh']}\n内容:{r['summary_zh']}"
                metadata = {
                    "title": r['title_zh'],
                    "date": str(r['event_date']),
                    "country": r['country_code']
                }
                docs.append(Document(text=text_content, metadata=metadata))
            
            logger.info(f"正在调用 Embedding 接口进行向量化 (共 {len(docs)} 个文档)...")
            self.index = VectorStoreIndex.from_documents(docs)
            self.last_update = datetime.datetime.now()
            logger.info(f"✅ 索引已刷新: {len(docs)} 条资讯向量化完成")
            return True
        except Exception as e:
            logger.error(f"❌ 构建索引失败: {e}")
            return False

    def query_stream(self, prompt: str):
        # 如果索引为空，尝试同步刷新一次
        if not self.index:
            logger.info("索引为空，触发首次加载...")
            self.refresh_index()
            
        # 如果还是空（可能数据库没数据），直接返回
        if not self.index:
            return type('obj', (object,), {'response_gen': iter(["抱歉，RAG 暂无资讯数据可供参考。"])})

        # 检查是否需要后台更新（超过1小时）
        if (datetime.datetime.now() - self.last_update).total_seconds() > 3600:
            logger.info("索引已过期，将在下一次请求或后台刷新...")
            # 此处可以考虑异步刷新，暂保持同步
            self.refresh_index()
        
        # 启用流式查询
        query_engine = self.index.as_query_engine(
            similarity_top_k=10, 
            node_postprocessors=[self.reranker], 
            streaming=True
        )
        return query_engine.query(f"请基于过去7天的时政新闻，简洁专业地回答：{prompt}")

rag_core = RAGCore()
app = FastAPI(title="GDELT RAG Service")

class QueryRequest(BaseModel):
    prompt: str

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "index_ready": rag_core.index is not None,
        "last_update": str(rag_core.last_update) if rag_core.last_update else None
    }

@app.on_event("startup")
async def startup_event():
    # 启动时异步触发一次索引构建，避免阻塞
    import threading
    threading.Thread(target=rag_core.refresh_index).start()

@app.post("/query")
async def query(request: QueryRequest):
    try:
        response = rag_core.query_stream(request.prompt)
        def event_generator():
            # 1. 逐步输出回答内容
            for token in response.response_gen:
                yield token
            
            # 2. 回答结束后，输出引用的来源
            if hasattr(response, 'source_nodes') and response.source_nodes:
                yield "\n\n**🔍 引用来源：**\n"
                seen_sources = set()
                count = 1
                for node in response.source_nodes:
                    metadata = node.node.metadata
                    source_id = f"{metadata.get('date')} - {metadata.get('title')}"
                    if source_id not in seen_sources:
                        yield f"{count}. [{metadata.get('date')}] {metadata.get('title')}\n"
                        seen_sources.add(source_id)
                        count += 1
                        if count > 5: break # 最多展示5个来源
        
        return StreamingResponse(event_generator(), media_type="text/plain")
    except Exception as e:
        logger.error(f"查询请求遇到错误: {e}")
        return StreamingResponse(iter([f"[错误] 系统繁忙或鉴权失败: {str(e)}"]), media_type="text/plain")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
