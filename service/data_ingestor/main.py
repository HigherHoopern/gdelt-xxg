import os
import requests
import pandas as pd
import zipfile
import io
import time
import sys

# 自动定位项目根目录并加入搜索路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy import text
from common.models import SessionLocal, init_db, GdeltExport, GdeltMention, GdeltGKG
from config.settings import GDELT_UPDATE_URL, REGIONAL_COUNTRIES
from common.logger import setup_logger

logger = setup_logger("数据采集器")

class DataIngestor:
    def __init__(self):
        self.last_processed_url = {"export": "", "mentions": "", "gkg": ""}
        self.asean_fips = [v['fips'] for v in REGIONAL_COUNTRIES.values()]

    def fetch_latest_urls(self):
        try:
            resp = requests.get(GDELT_UPDATE_URL, timeout=10)
            lines = resp.text.strip().split('\n')
            urls = {}
            for line in lines:
                parts = line.split()
                if len(parts) < 3: continue
                url = parts[2]
                if '.export.CSV.zip' in url: urls['export'] = url
                elif '.mentions.CSV.zip' in url: urls['mentions'] = url
                elif '.gkg.csv.zip' in url: urls['gkg'] = url
            return urls
        except Exception as e:
            logger.error(f"获取最新更新列表失败: {e}")
            return {}

    def process_file(self, url, table_type):
        if url == self.last_processed_url[table_type]:
            return
        
        logger.info(f"正在下载 {table_type} 数据包: {url}")
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                logger.error(f"下载失败 ({r.status_code}): {url}")
                return

            # 验证内容是否为 ZIP (GDELT 有时会返回错误 HTML 页面)
            content = r.content
            if not content.startswith(b'PK'):
                logger.error(f"文件格式错误，不是有效的 ZIP 文件: {url}")
                return

            z = zipfile.ZipFile(io.BytesIO(content))
            file_name = z.namelist()[0]
            
            # GKG 使用制表符，Export/Mentions 也使用制表符
            # 增加 encoding_errors='replace' 以解决部分 GDELT 文件中非 UTF-8 字符导致的解码失败问题
            df = pd.read_csv(
                z.open(file_name), 
                sep='\t', 
                header=None, 
                engine='python', 
                on_bad_lines='skip',
                encoding='utf-8',
                encoding_errors='replace'
            )
            
            if table_type == 'export':
                self.ingest_export(df)
            elif table_type == 'mentions':
                self.ingest_mentions(df)
            elif table_type == 'gkg':
                self.ingest_gkg(df)
                
            self.last_processed_url[table_type] = url
        except Exception as e:
            logger.error(f"处理 {table_type} 文件失败: {e}")

    def ingest_export(self, df):
        # 映射 Export 的 61 列中的关键列
        df = df.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7, 15, 16, 17, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 51, 52, 53, 54, 56, 57, 58, 59, 60]]
        df.columns = [
            'GlobalEventID', 'Day', 'MonthYear', 'Year', 'FractionDate', 
            'Actor1Code', 'Actor1Name', 'Actor1CountryCode',
            'Actor2Code', 'Actor2Name', 'Actor2CountryCode',
            'IsRootEvent', 'EventCode', 'EventBaseCode', 'EventRootCode', 'QuadClass', 
            'GoldsteinScale', 'NumMentions', 'NumSources', 'NumArticles', 'AvgTone',
            'ActionGeo_Type', 'ActionGeo_FullName', 'ActionGeo_CountryCode', 'ActionGeo_ADM1Code',
            'ActionGeo_Lat', 'ActionGeo_Long', 'ActionGeo_FeatureID', 'DATEADDED', 'SOURCEURL'
        ]
        
        # 全球化修改：不再过滤特定国家，收集全球数据
        df_global = df
        if not df_global.empty:
            from sqlalchemy.dialects.postgresql import insert
            from common.models import GdeltExport
            
            with SessionLocal() as session:
                for _, row in df_global.iterrows():
                    data = row.to_dict()
                    stmt = insert(GdeltExport).values(**data).on_conflict_do_nothing(index_elements=['GlobalEventID'])
                    session.execute(stmt)
                session.commit()
            logger.info(f"成功入库 {len(df_global)} 条唯一全球出口 (Export) 记录。")

    def ingest_mentions(self, df):
        df = df.iloc[:, [0, 1, 2, 3, 4, 5, 6, 11, 12]]
        df.columns = [
            'GlobalEventID', 'EventTimeDate', 'MentionTimeDate', 'MentionType', 
            'MentionSourceName', 'MentionIdentifier', 'SentenceID', 'Confidence', 'MentionDocTone'
        ]
        from sqlalchemy.dialects.postgresql import insert
        from common.models import GdeltMention
        
        with SessionLocal() as session:
            # 批量 Upsert 优化性能
            for _, row in df.iterrows():
                data = row.to_dict()
                stmt = insert(GdeltMention).values(**data).on_conflict_do_nothing(index_elements=['GlobalEventID', 'MentionIdentifier'])
                session.execute(stmt)
            session.commit()
        logger.info(f"成功入库 {len(df)} 条唯一提及 (Mentions) 记录。")

    def ingest_gkg(self, df):
        df = df.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 25]]
        df.columns = [
            'GKGRECORDID', 'DATE', 'SourceCollectionIdentifier', 'SourceCommonName', 'DocumentIdentifier',
            'Counts', 'V2Counts', 'Themes', 'V2Themes', 'Locations', 'V2Locations', 
            'Persons', 'V2Persons', 'Organizations', 'V2Organizations', 'V2Tone', 'SharingImage', 'TranslationInfo'
        ]
        from sqlalchemy.dialects.postgresql import insert
        from common.models import GdeltGKG
        
        with SessionLocal() as session:
            for _, row in df.iterrows():
                data = row.to_dict()
                stmt = insert(GdeltGKG).values(**data).on_conflict_do_nothing(index_elements=['GKGRECORDID'])
                session.execute(stmt)
            session.commit()
        logger.info(f"成功入库 {len(df)} 条唯一知识图谱 (GKG) 记录。")

    def run(self):
        logger.info("数据采集服务已启动。")
        while True:
            urls = self.fetch_latest_urls()
            for t, url in urls.items():
                self.process_file(url, t)
            time.sleep(300)

if __name__ == "__main__":
    ingestor = DataIngestor()
    ingestor.run()
