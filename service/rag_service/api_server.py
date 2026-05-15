# services/rag_service/api_server.py
import os
import sys
import shutil
import traceback
import warnings
import logging
import asyncio
import uvicorn
import json
import datetime
import time
import re
import uuid
from typing import AsyncGenerator, Dict, Optional, List, Any
from contextlib import asynccontextmanager
from io import BytesIO

# --- 核心逻辑依赖 ---
import redis
import fitz  # PyMuPDF
import docx2txt
from minio import Minio
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError

from llama_index.core import (
    Settings, 
    SimpleDirectoryReader, 
    VectorStoreIndex, 
    StorageContext
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle, Document
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterCondition

from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.llms import ChatMessage
from llama_index.vector_stores.milvus import MilvusVectorStore

# --- 本地模块导入 ---
from settings import (
    DEBUG, CHUNK_SIZE, STREAM, KB_FOLDER_DIR, TOP_K,
    redis_host, redis_port, use_redis,
    MILVUS, milvus_uri, milvus_token, MILVUS_COLLECTION_NAME, REBUILD_INDEX,
    minio_endpoint, minio_access_key, minio_secret_key, minio_bucket, minio_secure,
    context_window_size, num_output,
    auth_secret_key, auth_algorithm
)
from llm import config_llm
from prompt import get_system_prompt, get_condense_prompt, get_context_prompt_template

# ==============================================================================
# 0. 基础配置与日志
# ==============================================================================
SECRET_KEY = auth_secret_key
ALGORITHM = auth_algorithm

warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.makedirs(KB_FOLDER_DIR, exist_ok=True)
TEMP_DIR = "./temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

LOG_DIR = './logs/main'
os.makedirs(LOG_DIR, exist_ok=True)
current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
log_filename = os.path.join(LOG_DIR, f"{current_date_str}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'), 
        logging.StreamHandler() 
    ]
)

try:
    minio_client = Minio(minio_endpoint, access_key=minio_access_key, secret_key=minio_secret_key, secure=minio_secure)
except Exception as e:
    logging.error(f"MinIO 连接警告: {e}")
    minio_client = None

# ==============================================================================
# 1. 权限与工具类
# ==============================================================================
def get_user_info(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供有效的认证 Token")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "user_id": int(payload.get("user_id")),
            "role": payload.get("role"),
            "dept_id": int(payload.get("dept_id")),
            "username": payload.get("sub")
        }
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

def build_permission_filters(user: dict) -> Optional[MetadataFilters]:
    if user["role"] == "super_admin":
        return None
    dept_id_val = int(user["dept_id"])
    if not MILVUS:
        return MetadataFilters(filters=[MetadataFilter(key="dept_id", value=dept_id_val)], condition=FilterCondition.AND)

    if user["role"] == "normal_user":
        u_filter = MetadataFilter(key="uploader_id", value=int(user["user_id"]))
        g_filter = MetadataFilter(key="is_general", value=1)
        inner_or = MetadataFilters(filters=[u_filter, g_filter], condition=FilterCondition.OR)
        return MetadataFilters(filters=[MetadataFilter(key="dept_id", value=dept_id_val), inner_or], condition=FilterCondition.AND)
    
    return MetadataFilters(filters=[MetadataFilter(key="dept_id", value=dept_id_val)], condition=FilterCondition.AND)

class LoggableRetriever(BaseRetriever):
    def __init__(self, original_retriever: BaseRetriever):
        self._original_retriever = original_retriever
        super().__init__()
    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        t_start = time.time()
        nodes = self._original_retriever.retrieve(query_bundle)
        logging.info(f">>> [Retriever] 检索耗时: {time.time() - t_start:.4f}s | 命中片段: {len(nodes)}")
        return nodes

class LoggableReranker(BaseNodePostprocessor):
    def __init__(self, original_reranker):
        super().__init__()
        self._original_reranker = original_reranker
    def _postprocess_nodes(self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None) -> List[NodeWithScore]:
        t_start = time.time()
        reranked_nodes = self._original_reranker.postprocess_nodes(nodes, query_bundle)
        logging.info(f">>> [Reranker] 重排耗时: {time.time() - t_start:.4f}s | 最终保留: {len(reranked_nodes)}")
        return reranked_nodes

class LlamaIndexRAG:
    def __init__(self, vector_store=None):
        self.vector_store = vector_store
        self._memory_index = None 
    def get_index(self):
        if self.vector_store:
            storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
            return VectorStoreIndex.from_vector_store(self.vector_store, storage_context=storage_context)
        else:
            if self._memory_index is None:
                self._memory_index = VectorStoreIndex([])
            return self._memory_index

# ==============================================================================
# 2. 核心初始化 (🔥 移出异步作用域，强行单线程同步启动)
# ==============================================================================
def initialize_components():
    logging.info("--- 开始同步初始化 RAG 核心组件 ---")
    llm, emb, reranker = config_llm()
    
    Settings.llm = llm
    Settings.embed_model = emb
    Settings.context_window = context_window_size
    Settings.num_output = min(num_output, 2048) 
    
    vector_store = None
    if MILVUS:
        final_uri = milvus_uri if milvus_uri.startswith("http") else f"http://{milvus_uri}"
        logging.info(f"正在配置 Milvus: {final_uri}")
        try:
            # =================================================================
            # 🚀 终极黑科技：正确修补 pymilvus 类的底层隔离 Bug
            # 拦截 _fetch_handler 抛出的 ConnectionNotExistException 并强行自愈
            # =================================================================
            from pymilvus.orm.connections import Connections # 核心修复：导入 Class 而不是 Module
            
            # 确保只打一次补丁，防止重复覆盖
            if not hasattr(Connections, '_is_patched'):
                original_fetch_handler = Connections._fetch_handler
                
                # 重写底层的获取连接方法
                def safe_fetch_handler(self, alias="default"):
                    try:
                        # 尝试用原始方法获取连接
                        return original_fetch_handler(self, alias)
                    except Exception:
                        # 拦截到报错！说明 SDK 内部丢了别名，我们强行给它连上！
                        logging.warning(f"⚠️ 拦截到 SDK 丢失别名 '{alias}'，正在强制补全底层连接...")
                        
                        uri_cleaned = final_uri.replace("http://", "").replace("https://", "")
                        h, p = uri_cleaned.split(":") if ":" in uri_cleaned else (uri_cleaned, "19530")
                        
                        # self 就是全局连接池对象，强行通过底层 ORM 注册这个丢失的别名
                        self.connect(alias=alias, host=h, port=p, token=milvus_token)
                        
                        # 连好之后再返回给 LlamaIndex
                        return original_fetch_handler(self, alias)
                
                # 覆盖类的底层方法，让 LlamaIndex 乖乖听话
                Connections._fetch_handler = safe_fetch_handler
                Connections._is_patched = True
            # =================================================================
            
            # 现在放心大胆地实例化，不管它内部怎么乱连，我们的补丁都会兜底
            vector_store = MilvusVectorStore(
                uri=final_uri, 
                token=milvus_token, 
                collection_name=MILVUS_COLLECTION_NAME,
                dim=1024,
                enable_dynamic_field=True,
                overwrite=REBUILD_INDEX
            )
            logging.info("✅[Milvus] VectorStore 实例化成功 (底层自愈补丁生效)")
            
        except Exception as e:
            logging.error(f"❌ Milvus 实例化异常: {str(e)}")
            logging.error(traceback.format_exc())
            vector_store = None
    else:
        logging.info("--- MILVUS 已禁用 ---")
    
    rag_engine = LlamaIndexRAG(vector_store)
    postprocessors =[LoggableReranker(reranker)] if reranker else[]
    
    return rag_engine, llm, postprocessors

# --- 关键动作：在 FastAPI 启动前，全局单线程就完成连接 ---
app_state = {}
try:
    _rag_engine, _llm, _postprocessors = initialize_components()
    app_state["rag"] = _rag_engine
    app_state["llm"] = _llm
    app_state["postprocessors"] = _postprocessors
except Exception as init_err:
    logging.error(f"全局初始化崩溃: {init_err}")

# ==============================================================================
# 3. Redis 记忆管理
# ==============================================================================
def load_history_from_redis(session_id: str) -> List[ChatMessage]:
    client = app_state.get("redis_client")
    if not client: return[]
    try:
        data = client.get(f"chat_history:{session_id}")
        if data:
            msgs = json.loads(data)
            return[ChatMessage(role=m["role"].replace("MessageRole.", "").lower(), content=m["content"]) for m in msgs]
    except Exception as e:
        logging.error(f"Redis 读取失败: {e}")
    return []

def save_history_to_redis(session_id: str, history: List[ChatMessage]):
    client = app_state.get("redis_client")
    if not client: return
    try:
        serializable =[{"role": m.role.value if hasattr(m.role, 'value') else str(m.role).lower(), "content": m.content} for m in history[-10:]]
        client.set(f"chat_history:{session_id}", json.dumps(serializable, ensure_ascii=False), ex=604800)
    except Exception as e:
        logging.error(f"Redis 保存失败: {e}")

# ==============================================================================
# 4. FastAPI 实例
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("---[API STARTUP] FastAPI 服务正式启动 ---")
    if use_redis:
        try:
            app_state["redis_client"] = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            app_state["redis_client"].ping()
            logging.info("✅ Redis 记忆模块连接成功")
        except:
            app_state["redis_client"] = None
    yield
    if app_state.get("redis_client"): app_state["redis_client"].close()

app = FastAPI(title="XterAI Jiangcheng RAG API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

# ==============================================================================
# 5. 业务接口
# ==============================================================================
@app.post("/upload")
async def upload_document(file: UploadFile = File(...), is_general: bool = Form(False), user: dict = Depends(get_user_info)):
    temp_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}_{file.filename}")
    try:
        content = await file.read()
        with open(temp_path, "wb") as f: f.write(content)
        if minio_client:
            storage_path = f"dept_{user['dept_id']}/user_{user['user_id']}/{file.filename}"
            minio_client.put_object(minio_bucket, storage_path, data=BytesIO(content), length=len(content))
        
        ext = os.path.splitext(file.filename)[1].lower()
        if ext == ".pdf":
            with fitz.open(temp_path) as pdf:
                text_data = "\n".join([page.get_text() for page in pdf])
        elif ext == ".docx":
            text_data = docx2txt.process(temp_path)
        else:
            text_data = content.decode("utf-8", errors="ignore")

        if not text_data.strip(): raise ValueError("未提取到有效文本")

        doc = Document(
            text=text_data,
            metadata={"file_name": file.filename, "uploader_id": int(user["user_id"]), "dept_id": int(user["dept_id"]), "is_general": 1 if is_general else 0}
        )
        
        index = app_state["rag"].get_index()
        index.insert_nodes(Settings.node_parser.get_nodes_from_documents([doc]))
        logging.info(f"✅ 文件 {file.filename} 索引完成")
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        logging.error(f"❌ 上传失败: {traceback.format_exc()}")
        return {"status": "error", "msg": str(e)}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

async def sse_generator(question: str, session_id: str, user: dict) -> AsyncGenerator:
    yield f"data: {json.dumps({'type': 'session_info', 'data': {'session_id': session_id}})}\n\n"

    filters = build_permission_filters(user)
    index = app_state["rag"].get_index()
    
    retriever = LoggableRetriever(index.as_retriever(similarity_top_k=TOP_K, filters=filters))
    memory = ChatMemoryBuffer.from_defaults(token_limit=4000, chat_history=load_history_from_redis(session_id))

    chat_engine = CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        node_postprocessors=app_state["postprocessors"],
        llm=app_state["llm"],
        memory=memory,
        system_prompt=get_system_prompt(),
        condense_prompt=get_condense_prompt()
    )

    try:
        response_gen = chat_engine.stream_chat(question).response_gen
        full_answer = ""
        for token in response_gen:
            if token:
                full_answer += token
                yield f"data: {json.dumps({'type': 'answer_chunk', 'data': token}, ensure_ascii=False)}\n\n"
        
        if not full_answer.strip():
            fallback_msg = "好的，我是您的智慧政务助手小艾。目前知识库中没有关于此问题的记录，请问有什么我可以帮您的吗？"
            yield f"data: {json.dumps({'type': 'answer_chunk', 'data': fallback_msg}, ensure_ascii=False)}\n\n"

        if app_state.get("redis_client"):
            save_history_to_redis(session_id, memory.get_all())
    except Exception as e:
        logging.error(f"Chat Error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
    finally:
        yield f"data: {json.dumps({'type': 'stream_end', 'data': {}})}\n\n"

@app.post("/chat")
async def handle_chat(request: QueryRequest, user: dict = Depends(get_user_info)):
    return StreamingResponse(sse_generator(request.question, request.session_id or str(uuid.uuid4()), user), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8070)