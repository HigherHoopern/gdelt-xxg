# 基于AI和新闻数据的南亚东南亚地缘政治风险系统 (GRI-SA-SEA)

本项目是一个基于 GDELT 全球新闻大数据的实时监控与风险分析系统，专为中国企业境外投资提供**东盟 (ASEAN)** 地区的深度风险研判。

## 🌟 核心功能
1.  **全自动秒级采集**：每 15 分钟同步 GDELT v2 全球新闻事件。
2.  **AI 智能补全与翻译**：
    *   **自动抓取**：获取新闻全文正文。
    *   **AI 提炼**：若原标题/摘要缺失，DeepSeek-V3 会根据正文自动生成精华内容。
    *   **全量汉化**：标题、摘要、正文全部实现高质量中文翻译。
3.  **地缘风险指数 (GRI)**：基于多维公式量化 0-100 的实时风险得分。
4.  **高频波动监测**：支持 15 分钟级的风险波动曲线展示。
5.  **趋势研判与报告**：
    *   **未来预测**：通过时间序列模型预测未来 7 天风险。
    *   **专家研判**：AI 自动撰写中文投资建议报告。
6.  **可视化大屏**：Gradio + ECharts 驱动的动态地图与趋势深度预览（端口 8090）。


---

## 🚀 迁移与远程部署 (Migration & Deployment)

由于 4 月份的数据（1188 条深度处理记录）和历史 GRI 分值存储在本地数据库中，建议通过以下步骤完整迁移到远程服务器：

### 1. 导出本地数据
在本地项目根目录运行：
```bash
chmod +x scripts/dump_db.sh
./scripts/dump_db.sh
```
这将生成一个加密且压缩的 `gdelt_data_backup_YYYYMMDD.sql.gz` 文件。

### 2. 同步代码
使用 Git 将代码推送到您的 GitHub 私有仓库：
```bash
git add .
git commit -m "Final version for deployment"
git push origin main
```

### 3. 在远程服务器部署
在远程服务器上克隆代码并恢复数据：
1. **克隆代码**: `git clone git@github.com:HigherHoopern/gdelt-xxg.git`
2. **传输数据**: 将本地生成的 `.sql.gz` 文件通过 `scp` 传送到服务器。
3. **恢复数据库**:
   ```bash
   gunzip -c gdelt_data_backup_*.sql.gz | psql -U <username> -d <dbname>
   ```
4. **配置环境**: 创建 `.env` 文件并填入 API Key 和数据库连接信息。
5. **启动服务**:
   ```bash
   python3 main_service.py # 启动后台监控
   python3 run_web.py      # 启动前端界面
   ```

---

## 🛠️ 环境准备

### 1. 配置环境变量 (.env)
项目完全基于环境变量驱动。请确保已创建并配置 `.env` 文件：
```bash
cp .env.example .env
# 编辑 .env 填写数据库密码及 SiliconFlow API Key
```

### 2. 数据库
*   安装 **PostgreSQL** 并创建名为 `dgelt` 的数据库。
*   系统启动时会自动执行模式迁移（Migration），无需手动建表。

---

## 🚀 快速启动 (Dev 模式)

我们推荐使用 [**uv**](https://github.com/astral-sh/uv) 进行极速环境管理。

```bash
# 1. 创建并激活虚拟环境
uv venv gdelt-risk
source gdelt-risk/bin/activate  # macOS/Linux

# 2. 安装依赖
uv pip install -r requirements.txt

# 3. 启动后台总控 (新终端)
# 负责采集、深度翻译、风险计算
python3 main_service.py

# 4. 启动可视化大屏 (新终端)
# 访问地址: http://localhost:8090
python3 run_web.py
```

---

## 📦 生产部署 (Docker 模式)

使用加速镜像站（1ms.docker.run）实现一键部署：
```bash
docker-compose up --build -d
```
*   访问 `http://服务器IP:8090` 即可查看。

---

## 📜 历史数据补全

如果您需要查看过去（如 2026 年 4 月）的风险走势，请使用补全脚本：
```bash
# 用法: python3 scripts/backfill_history.py <开始日期YYYYMMDD> <结束日期YYYYMMDD>
python3 scripts/backfill_history.py 20260401 20260415
```

---

## 📊 风险指数 (GRI) 模型

$$GRI_c = \min \left( 100, \frac{\sum (W_j \times Impact_i \times \ln(Sources_i + 1) \times \text{ToneFactor}_i)}{\text{Sensitivity\_Factor}} \times 100 \right)$$

*   **$W_j$**: 类别权重（军事=1.5, 政治=1.3, 经济=1.2, 外交=1.0, 社会=0.8）。
*   **$Impact_i$**: 事件冲击强度 (`GoldsteinScale`)。
*   **Sensitivity_Factor**: 默认为 10.0 (敏感模式)。

---

## 📂 项目结构
```text
├── main_service.py         # 后台服务总控 (多线程)
├── run_web.py              # Web 仪表盘统一启动器
├── scripts/
│   └── backfill_history.py # 历史数据同步工具
├── web/app.py              # Gradio 前端代码
├── service/
│   ├── data_ingestor/      # GDELT 原始数据下载
│   ├── risk_engine/        # 核心逻辑：AI翻译、正文抓取、GRI计算
│   └── predictor/          # 趋势预测模块
├── common/
│   ├── models.py           # 数据库模型与自动迁移逻辑
│   └── logger.py           # 全中文按天滚动日志
└── logs/                   # YYYY-MM-DD.log 全系统详细日志
```

---
*Powered by GDELT & DeepSeek-V3 Intelligence*
