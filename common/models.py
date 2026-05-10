from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Text, Numeric, DateTime, Index, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
from config.settings import DB_CONFIG

Base = declarative_base()

class GdeltExport(Base):
    __tablename__ = 'export'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    GlobalEventID = Column(BigInteger, index=True, unique=True)
    Day = Column(Integer)
    MonthYear = Column(Integer)
    Year = Column(Integer)
    FractionDate = Column(Numeric)
    Actor1Code = Column(String(50))
    Actor1Name = Column(String(255))
    Actor1CountryCode = Column(String(10))
    Actor2Code = Column(String(50))
    Actor2Name = Column(String(255))
    Actor2CountryCode = Column(String(10))
    IsRootEvent = Column(Integer)
    EventCode = Column(String(10), index=True)
    EventBaseCode = Column(String(10))
    EventRootCode = Column(String(10))
    QuadClass = Column(Integer)
    GoldsteinScale = Column(Numeric)
    NumMentions = Column(Integer)
    NumSources = Column(Integer)
    NumArticles = Column(Integer)
    AvgTone = Column(Numeric)
    ActionGeo_Type = Column(Integer)
    ActionGeo_FullName = Column(Text)
    ActionGeo_CountryCode = Column(String(10), index=True)
    ActionGeo_ADM1Code = Column(String(20))
    ActionGeo_Lat = Column(Numeric)
    ActionGeo_Long = Column(Numeric)
    ActionGeo_FeatureID = Column(String(50))
    DATEADDED = Column(BigInteger)
    SOURCEURL = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

class GdeltMention(Base):
    __tablename__ = 'mentions'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    GlobalEventID = Column(BigInteger, index=True)
    EventTimeDate = Column(BigInteger)
    MentionTimeDate = Column(BigInteger)
    MentionType = Column(Integer)
    MentionSourceName = Column(String(255))
    MentionIdentifier = Column(Text, index=True)
    SentenceID = Column(Integer)
    Confidence = Column(Integer)
    MentionDocLen = Column(Integer)
    MentionDocTone = Column(Numeric)
    created_at = Column(DateTime, default=datetime.datetime.now)
    __table_args__ = (Index('idx_mention_unique', "GlobalEventID", "MentionIdentifier", unique=True),)

class GdeltGKG(Base):
    __tablename__ = 'gkg'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    GKGRECORDID = Column(Text, index=True, unique=True) # 改为 TEXT
    DATE = Column(BigInteger)
    SourceCollectionIdentifier = Column(Integer)
    SourceCommonName = Column(Text) # 改为 TEXT
    DocumentIdentifier = Column(Text, index=True)
    Counts = Column(Text)
    V2Counts = Column(Text)
    Themes = Column(Text)
    V2Themes = Column(Text)
    Locations = Column(Text)
    V2Locations = Column(Text)
    Persons = Column(Text)
    V2Persons = Column(Text)
    Organizations = Column(Text)
    V2Organizations = Column(Text)
    V2Tone = Column(Text)
    SharingImage = Column(Text)
    TranslationInfo = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

class RiskAnalysisData(Base):
    __tablename__ = 'risk_analysis_data'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    global_event_id = Column(BigInteger, index=True)
    event_date = Column(DateTime, index=True)
    country_code = Column(String(10), index=True)
    category = Column(String(50), index=True)
    weight = Column(Numeric)
    impact_score = Column(Numeric)
    num_sources = Column(Integer)
    avg_tone = Column(Numeric)
    url = Column(Text, unique=True)
    title = Column(Text)
    title_zh = Column(Text)
    summary = Column(Text)
    summary_zh = Column(Text)
    content = Column(Text)
    content_zh = Column(Text)
    image_url = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

class DailyRiskIndex(Base):
    __tablename__ = 'daily_risk_index'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    country_code = Column(String(10), index=True)
    risk_index = Column(Numeric)
    risk_level = Column(String(20))
    event_count = Column(Integer)
    calculation_date = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.datetime.now)

class RiskIndexHistory(Base):
    __tablename__ = 'risk_index_history'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    country_code = Column(String(10), index=True)
    risk_index = Column(Numeric)
    calculation_date = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.datetime.now)

class RiskPrediction(Base):
    __tablename__ = 'risk_predictions'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    country_code = Column(String(10), index=True)
    predicted_date = Column(DateTime, index=True)
    predicted_risk_index = Column(Numeric)
    model_version = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)

class RiskReport(Base):
    __tablename__ = 'risk_reports'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    country_code = Column(String(10), index=True)
    report_content = Column(Text)
    report_date = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.datetime.now)

engine = create_engine(DB_CONFIG['url'], pool_size=DB_CONFIG['pool_size'], max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        # 1. 补全列
        for col_name in ['title_zh', 'summary_zh', 'content', 'content_zh']:
            res = conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='risk_analysis_data' AND column_name='{col_name}'"))
            if not res.fetchone():
                try:
                    conn.execute(text(f"ALTER TABLE risk_analysis_data ADD COLUMN {col_name} TEXT"))
                    conn.commit()
                except: pass
        # 2. 升级 GKG 字段长度
        try:
            conn.execute(text("ALTER TABLE gkg ALTER COLUMN \"GKGRECORDID\" TYPE TEXT"))
            conn.execute(text("ALTER TABLE gkg ALTER COLUMN \"SourceCommonName\" TYPE TEXT"))
            conn.commit()
        except: pass
