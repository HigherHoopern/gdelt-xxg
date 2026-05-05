import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
import requests
import urllib.request
import pandas as pd
import os
import logging
from sqlalchemy import text
from config import GDELT_URL, get_engine, setup_logging

def run_ingestor(data_dir):
    setup_logging()
    logging.info("Ingestor 采集进程启动...")
    engine = get_engine()
    last_url = ""
    os.makedirs(data_dir, exist_ok=True)

    while True:
        try:
            resp = requests.get(GDELT_URL, timeout=10)
            current_url = [line.split(" ")[-1] for line in resp.text.split("\n") if ".mentions.CSV.zip" in line][0]
            
            if current_url != last_url:
                logging.info(f"发现新包: {current_url.split('/')[-1]}")
                path = os.path.join(data_dir, current_url.split('/')[-1])
                urllib.request.urlretrieve(current_url, path)
                
                df = pd.read_csv(path, compression='zip', sep='\t', header=None, engine='python', on_bad_lines='skip')
                df.columns = ['GlobalEventID','EventTimeDate','MentionTimeDate','MentionType','MentionSourceName','MentionIdentifier','SentenceID','Actor1CharOffset','Actor2CharOffset','ActionCharOffset','InRawText','Confidence','MentionDocLen','MentionDocTone','MentionDocTranslationInfo','Extras']
                
                # 1. 内部去重
                df.drop_duplicates(subset=['MentionIdentifier'], inplace=True)
                
                # 2. 数据库查重 (URL级别)
                batch_urls = df['MentionIdentifier'].tolist()
                existing_urls = []
                # 分块查询，防止SQL过长
                for i in range(0, len(batch_urls), 500):
                    chunk = tuple(batch_urls[i:i+500])
                    check_sql = text("SELECT \"MentionIdentifier\" FROM mentions_original WHERE \"MentionIdentifier\" IN :urls")
                    with engine.connect() as conn:
                        res = conn.execute(check_sql, {"urls": chunk}).fetchall()
                        existing_urls.extend([r[0] for r in res])
                
                # 只保留数据库里没有的URL
                df_new = df[~df['MentionIdentifier'].isin(existing_urls)].copy()
                
                if not df_new.empty:
                    with engine.begin() as conn:
                        df_new.to_sql("mentions_original", conn, if_exists="append", index=False)
                    logging.info(f"✅ 入库 {len(df_new)} 条唯一原始数据 (过滤掉 {len(df)-len(df_new)} 条重复)")
                else:
                    logging.info("⏭️ 无新唯一新闻，跳过。")
                
                last_url = current_url
        except Exception as e:
            logging.error(f"采集报错: {e}")
        time.sleep(300)