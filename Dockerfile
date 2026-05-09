# 使用官方镜像，如果官方镜像慢，请检查网络或更换其他可用镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖（如果需要编译某些库）
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 拷贝依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目文件
COPY . .

# 设置环境变量路径
ENV PYTHONPATH=/app

# 默认不执行任何操作，由 docker-compose 指定启动命令
CMD ["python3", "main_service.py"]
