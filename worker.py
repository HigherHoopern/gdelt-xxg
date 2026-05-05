# worker.py
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# worker.py
import time
import logging
import pandas as pd
import requests
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text
from newspaper import Article
from deep_translator import GoogleTranslator
from config import get_engine, setup_logging, HEADERS

# 更丰富的 User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

def _scrape_item(url):
    """带诊断信息的抓取函数"""
    headers = HEADERS.copy()
    headers['User-Agent'] = random.choice(USER_AGENTS)
    
    try:
        # 1. 发送请求
        resp = requests.get(url, headers=headers, timeout=12, verify=False)
        
        if resp.status_code != 200:
            return {"error": f"HTTP_{resp.status_code}"}

        # 2. 解析内容
        a = Article(url)
        a.set_html(resp.text)
        a.parse()
        
        content = a.text.strip()
        
        # 3. 诊断过滤
        if not content:
            return {"error": "Empty_Content"}
        
        if len(content) < 80: # 降低门槛到 80 字
            return {"error": f"Too_Short({len(content)})"}
        
        if "Access Denied" in content or "enable JS" in content.lower():
            return {"error": "Firewall_Blocked"}
            
        return {
            'content': content, 
            'title': a.title or "No Title", 
            'summary': a.summary or "", 
            'url_image': a.top_image or "", 
            'publish_date': a.publish_date or datetime.now(), 
            'url': url
        }
    except requests.exceptions.Timeout:
        return {"error": "Timeout"}
    except Exception as e:
        return {"error": f"Error_{type(e).__name__}"}

def run_worker(batch_size):
    setup_logging()
    logging.info("Worker 翻译处理器已启动...")
    engine = get_engine()
    translator = GoogleTranslator(source='auto', target='zh-CN')

    while True:
        try:
            # 1. 捞取任务
            query = text("""
                SELECT o."GlobalEventID", o."MentionIdentifier", o."MentionSourceName"
                FROM mentions_original o
                LEFT JOIN mentions m ON o."GlobalEventID" = m."GlobalEventID"
                WHERE m."GlobalEventID" IS NULL
                ORDER BY o."MentionTimeDate" DESC LIMIT :limit
            """)
            with engine.connect() as conn:
                df_tasks = pd.read_sql(query, conn, params={"limit": batch_size})

            if df_tasks.empty:
                time.sleep(30); continue

            # 2. 并行抓取
            total_tasks = len(df_tasks)
            logging.info(f">>> 正在处理批次: {total_tasks} 条任务")
            
            scraped_results = []
            # 统计各种错误原因
            stats = {}

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(_scrape_item, row['MentionIdentifier']): row for _, row in df_tasks.iterrows()}
                for f in as_completed(futures):
                    row = futures[f]
                    res = f.result()
                    
                    data = {
                        'GlobalEventID': row['GlobalEventID'],
                        'SourceName': row['MentionSourceName'],
                        'url': row['MentionIdentifier']
                    }
                    
                    if isinstance(res, dict) and "content" in res:
                        data.update(res)
                        data['status'] = 'success'
                    else:
                        # 记录错误原因统计
                        err_reason = res.get("error", "Unknown") if res else "None"
                        stats[err_reason] = stats.get(err_reason, 0) + 1
                        
                        data.update({
                            'content': 'EMPTY', 'title': f'[Failed_{err_reason}]', 
                            'summary': '', 'url_image': '', 'status': 'failed',
                            'publish_date': datetime.now()
                        })
                    scraped_results.append(data)

            # 3. 翻译成功项
            success_items = [i for i in scraped_results if i['status'] == 'success']
            total_success = len(success_items)
            
            if total_success > 0:
                logging.info(f"✨ 抓取成功 {total_success} 条，开始翻译...")
                for idx, item in enumerate(success_items):
                    try:
                        item['标题'] = translator.translate(item['title'])[:500]
                        item['摘要'] = translator.translate(item['summary'] or " ")[:1000]
                        item['内容'] = translator.translate(item['content'][:2500])
                        dt = item['publish_date']
                        item['时间'] = (dt + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S') if isinstance(dt, datetime) else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        logging.error(f"翻译失败: {e}")
                        item['status'] = 'failed'
            
            # 4. 入库
            final_to_db = []
            for item in scraped_results:
                if item['status'] == 'success':
                    final_to_db.append(item)
                else:
                    # 失败占位
                    item.update({
                        '标题': item.get('title', '抓取失败'), '摘要': '', '内容': 'EMPTY', 
                        '时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'url_image': ''
                    })
                    final_to_db.append(item)

            if final_to_db:
                df_final = pd.DataFrame(final_to_db)
                db_cols = ['GlobalEventID', '标题', '摘要', '内容', '时间', 'url', 'url_image', 'SourceName']
                with engine.begin() as conn:
                    df_final[db_cols].fillna('').to_sql("mentions", conn, if_exists="append", index=False)
                
                # 打印诊断报告
                report = ", ".join([f"{k}:{v}" for k, v in stats.items()])
                logging.info(f"✅ 批次完成! 成功: {total_success} | 失败详情: {report}")

        except Exception as e:
            logging.error(f"Worker 异常: {e}")
            time.sleep(30)