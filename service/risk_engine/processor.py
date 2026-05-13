import pandas as pd
import datetime
import os
import sys
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from common.models import SessionLocal, RiskAnalysisData, init_db
from newspaper import Article, Config
from common.logger import setup_logger
from openai import OpenAI
from config.settings import LLM_CONFIG

logger = setup_logger("风险预处理器")

# 爬虫伪装配置
crawler_config = Config()
crawler_config.browser_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
crawler_config.request_timeout = 15

CATEGORY_MAPPING = {
    'Military': {'weight': 1.5, 'event_prefixes': ['18', '19', '20']},
    'Political': {'weight': 1.3, 'event_prefixes': ['11', '12', '13', '14', '15', '16', '17']},
    'Economic': {'weight': 1.2, 'themes': ['ECON_', 'TRADE_', 'FINANCE_']},
    'Diplomacy': {'weight': 1.0, 'event_prefixes': ['01', '02', '03', '04', '05']},
    'Social': {'weight': 0.8, 'themes': ['SOCIETY', 'PROTEST', 'STRIKE']},
}

import random

# User-Agent 池
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
]

class RiskProcessor:
    def __init__(self):
        # 初始化 OpenAI 兼容客户端用于翻译与补全 (SiliconFlow)
        self.client = OpenAI(
            api_key=LLM_CONFIG['api_key'],
            base_url=LLM_CONFIG['base_url']
        )

    def get_category(self, event_code, themes):
        event_code = str(event_code).zfill(2)
        themes = themes or ""
        for cat, rules in CATEGORY_MAPPING.items():
            if 'event_prefixes' in rules:
                for prefix in rules['event_prefixes']:
                    if event_code.startswith(prefix):
                        return cat, rules['weight']
            if 'themes' in rules:
                for theme in rules['themes']:
                    if theme in themes:
                        return cat, rules['weight']
        return 'General', 0.5

    def ai_generate(self, system_prompt, user_content):
        if not user_content or len(user_content) < 5: return ""
        try:
            response = self.client.chat.completions.create(
                model=LLM_CONFIG['model_name'],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3
            )
            # 核心修复：增加 choices 存在性检查，防止 index out of range
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                logger.warning("AI 响应成功但未返回有效内容 (choices 为空)。")
                return ""
        except Exception as e:
            logger.error(f"AI 生成失败: {e}")
            return ""

    def scrape_full_content(self, url):
        try:
            config = Config()
            config.browser_user_agent = random.choice(USER_AGENTS)
            config.request_timeout = 20
            article = Article(url, config=config)
            article.download()
            article.parse()
            return article.title or "", article.summary or "", article.text or ""
        except Exception as e:
            logger.warning(f"解析 URL 失败: {url}, 错误: {e}")
            return "", "", ""

    def process_raw_to_business(self):
        main_session = SessionLocal()
        try:
            # 扩展处理窗口到 7 天，确保能够处理积压数据并填充图表
            now = datetime.datetime.now()
            min_date_dt = now - datetime.timedelta(days=7)
            min_date = min_date_dt.strftime('%Y%m%d%H%M%S')
            logger.info(f"🔍 正在扫描 {min_date} 之后的新闻任务...")
            
            query = text(f"""
                SELECT * FROM (
                    SELECT DISTINCT ON (e."SOURCEURL")
                        e."GlobalEventID", e."SOURCEURL", e."ActionGeo_CountryCode", 
                        e."EventCode", e."GoldsteinScale", e."NumSources", e."AvgTone", e."DATEADDED",
                        g."Themes", g."SharingImage", r.title_zh as current_status
                    FROM export e
                    LEFT JOIN gkg g ON e."SOURCEURL" = g."DocumentIdentifier"
                    LEFT JOIN risk_analysis_data r ON e."SOURCEURL" = r.url
                    WHERE e."DATEADDED" >= '{min_date}'
                      AND (r.url IS NULL 
                           OR r.title_zh IS NULL 
                           OR r.title_zh = '' 
                           OR r.title_zh LIKE '[RETRY_%]')
                    ORDER BY e."SOURCEURL", e."DATEADDED" DESC
                ) sub
                ORDER BY "DATEADDED" DESC
                LIMIT 50
            """)
            tasks = main_session.execute(query).fetchall()
        finally:
            main_session.close()

        if not tasks:
            return

        total = len(tasks)
        logger.info(f"🚀 开始处理批次任务，共计 {total} 条。")

        for idx, task in enumerate(tasks, 1):
            url = task[1]
            status = task[10] or ""
            p_log = f"[{idx}/{total}]"
            
            # 解析重试次数
            retry_count = 0
            if "[RETRY_" in status:
                try:
                    retry_count = int(status.split("_")[1].split("]")[0])
                except: retry_count = 0

            try:
                # 步骤 A: 网页解析
                logger.info(f"{p_log} 正在解析 URL: {url[:50]}...")
                category, weight = self.get_category(task[3], task[8])
                raw_title, raw_summary, raw_content = self.scrape_full_content(url)
                
                if not raw_content:
                    if retry_count < 3:
                        logger.warning(f"{p_log} 内容解析失败，标记为重试 ({retry_count + 1}/3)")
                        t_zh, s_zh, c_zh = f"[RETRY_{retry_count + 1}]", "", ""
                    else:
                        logger.error(f"{p_log} 达到最大重试次数，标记为解析失败。")
                        t_zh, s_zh, c_zh = "[无法解析原文]", "[该链接已失效或被拦截]", ""
                else:
                    # 步骤 B: AI 处理 (略过已有的逻辑...)
                    t_zh = self.ai_generate("翻译标题为中文。直接输出。", raw_title) if raw_title else self.ai_generate("根据正文总结一个20字以内的中文标题。", raw_content[:300])
                    s_zh = self.ai_generate("翻译摘要为中文。直接输出。", raw_summary) if raw_summary else self.ai_generate("根据正文撰写100字以内的中文摘要。", raw_content[:2000])
                    c_zh = self.ai_generate("将新闻全文翻译成中文。直接输出。", raw_content[:2000])

                if not t_zh or not s_zh:
                    # AI 失败但不更新状态，让它下一轮重试
                    continue

                # 步骤 E: 数据库写入
                logger.info(f"{p_log} 正在执行数据库同步 (Upsert)...")
                stmt = insert(RiskAnalysisData).values(
                    global_event_id=task[0],
                    event_date=datetime.datetime.strptime(str(task[7]), '%Y%m%d%H%M%S') if len(str(task[7])) >= 14 else datetime.datetime.now(),
                    country_code=task[2],
                    category=category,
                    weight=weight,
                    impact_score=abs(float(task[4])),
                    num_sources=task[5],
                    avg_tone=float(task[6]),
                    url=url,
                    title=raw_title,
                    title_zh=t_zh,
                    summary=raw_summary,
                    summary_zh=s_zh,
                    content=raw_content,
                    content_zh=c_zh,
                    image_url=task[9],
                    created_at=datetime.datetime.now()
                )
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=['url'],
                    set_={
                        "title_zh": stmt.excluded.title_zh,
                        "summary_zh": stmt.excluded.summary_zh,
                        "content_zh": stmt.excluded.content_zh,
                        "title": stmt.excluded.title,
                        "summary": stmt.excluded.summary,
                        "content": stmt.excluded.content,
                        "event_date": stmt.excluded.event_date,
                        "category": stmt.excluded.category,
                        "weight": stmt.excluded.weight,
                        "impact_score": stmt.excluded.impact_score
                    }
                )
                
                with SessionLocal() as session:
                    session.execute(stmt)
                    session.commit()
                logger.info(f"✅ {p_log} 任务处理成功。")

            except Exception as e:
                logger.error(f"❌ {p_log} 处理失败: {e}")

if __name__ == "__main__":
    processor = RiskProcessor()
    processor.process_raw_to_business()
