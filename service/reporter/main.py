import os
import datetime
from openai import OpenAI
from sqlalchemy import text
from common.models import SessionLocal, RiskReport, DailyRiskIndex, RiskAnalysisData, init_db
from config.settings import LLM_CONFIG
from common.logger import setup_logger

logger = setup_logger("风险分析报告专家")

class RiskReporter:
    def __init__(self):
        # 初始化 OpenAI 兼容客户端 (SiliconFlow)
        self.client = OpenAI(
            api_key=LLM_CONFIG['api_key'],
            base_url=LLM_CONFIG['base_url']
        )

    def generate_country_report(self, country_code, country_name=None):
        """
        生成投资研判报告，支持流式输出。
        """
        session = SessionLocal()
        display_name = country_name if country_name else country_code
        try:
            # 1. 获取最新风险指数
            latest_idx = session.query(DailyRiskIndex).filter(
                DailyRiskIndex.country_code == country_code
            ).order_by(DailyRiskIndex.calculation_date.desc()).first()
            
            if not latest_idx: 
                yield f"暂无 {display_name} 的风险数据。"
                return

            # 2. 获取最新核心新闻
            news_items = session.query(RiskAnalysisData).filter(
                RiskAnalysisData.country_code == country_code
            ).order_by(RiskAnalysisData.event_date.desc()).limit(5).all()
            
            news_text = "\n".join([f"- [{i.category}] {i.title_zh if i.title_zh else i.title}: {i.summary_zh if i.summary_zh else i.summary}" for i in news_items])

            # 3. 构造提示词 - 核心修复：使用中文全称
            prompt = f"""
            你是一位专业的地缘政治风险分析师，专注于为中国企业提供东盟及南亚国家投资建议。
            
            当前目标国家: {display_name}
            实时风险指数: {latest_idx.risk_index} (等级: {latest_idx.risk_level})
            
            最新核心新闻事件摘要:
            {news_text}
            
            请根据以上数据生成一份投资研判报告，包含：
            1. 局势简评 (根据风险指数和新闻)
            2. 核心风险点识别
            3. 给中国投资者的具体建议 (如：增加库存、审慎签约、关注汇率等)
            
            要求：
            - 请在报告全文中使用该国的正式中文全称（{display_name}），不要使用国家代码或缩写。
            - 语言专业且简洁，字数在 500 字以内。
            """
            
            # 4. 调用 OpenAI 兼容 API 并开启流式输出 (DeepSeek-V3)
            response = self.client.chat.completions.create(
                model=LLM_CONFIG['model_name'],
                messages=[
                    {"role": "system", "content": "你是一个资深的地缘政治风险分析专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=True
            )
            
            full_report = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_report += content
                    yield full_report # 实时产出已生成的内容

            # 5. 生成结束后保存报告
            new_report = RiskReport(
                country_code=country_code,
                report_content=full_report,
                report_date=datetime.datetime.now()
            )
            session.add(new_report)
            session.commit()
            logger.info(f"成功为 {country_code} 生成并保存了流式报告。")
            
        except Exception as e:
            logger.error(f"为 {country_code} 生成报告时出错: {e}")
            session.rollback()
            yield f"生成报告失败: {e}"
        finally:
            session.close()

if __name__ == "__main__":
    reporter = RiskReporter()
    for chunk in reporter.generate_country_report("VM"):
        print(chunk, end="", flush=True)
