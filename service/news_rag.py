import requests
import logging

logger = logging.getLogger("NewsRAG")

class NewsRAGClient:
    def __init__(self, service_url="http://global_rag:8000"):
        self.url = f"{service_url}/query"

    def query(self, query_str):
        """调用远程 RAG 微服务 (支持流式模拟)"""
        try:
            # 这里的 response 是一个支持迭代的流
            response = requests.post(
                self.url, 
                json={"prompt": query_str}, 
                stream=True, 
                timeout=120
            )
            
            if response.status_code != 200:
                return type('obj', (object,), {'response_gen': iter([f"远程 RAG 服务报错: {response.text}"])})
            
            # 模拟 LlamaIndex 的 response 对象结构，以便前端无缝接入
            def token_generator():
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        yield chunk
            
            return type('obj', (object,), {'response_gen': token_generator()})
            
        except Exception as e:
            logger.error(f"RAG 服务连接失败: {e}")
            return type('obj', (object,), {'response_gen': iter([f"无法连接到智能问答微服务，请检查网络或后端状态。({str(e)})"])})

# 全局单例，指向 docker-compose 中的服务名
news_rag_service = NewsRAGClient()
