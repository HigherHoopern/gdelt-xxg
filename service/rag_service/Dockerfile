FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
# 修改这里
COPY ./services/rag_service .
EXPOSE 8070
CMD ["python", "api_server.py"]