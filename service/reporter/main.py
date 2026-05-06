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
        生成地缘政治风险周度研判报告，支持流式输出。
        """
        session = SessionLocal()
        display_name = country_name if country_name else country_code
        try:
            # 1. 获取过去一周风险指数平均值及变化趋势
            one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
            latest_idx = session.query(DailyRiskIndex).filter(
                DailyRiskIndex.country_code == country_code
            ).order_by(DailyRiskIndex.calculation_date.desc()).first()

            if not latest_idx: 
                yield f"暂无 {display_name} 的风险数据。"
                return

            # 2. 获取过去一周核心新闻
            news_items = session.query(RiskAnalysisData).filter(
                RiskAnalysisData.country_code == country_code,
                RiskAnalysisData.event_date >= one_week_ago
            ).order_by(RiskAnalysisData.event_date.desc()).limit(10).all()

            news_text = "\n".join([f"- [{i.category}] {i.title_zh if i.title_zh else i.title}: {i.summary_zh if i.summary_zh else i.summary}" for i in news_items])

            # 3. 构造提示词 - 聚焦地缘政治风险研判，明确日期，强制 Markdown
            today_str = datetime.datetime.now().strftime('%Y年%m月%d日')
            prompt = f"""
            你是一位资深的地缘政治风险分析专家。请根据以下数据，生成一份《{display_name}地缘政治风险周度研判报告》。

            报告基准日期: {today_str}
            目标国家: {display_name}
            当前风险指数: {latest_idx.risk_index} (等级: {latest_idx.risk_level})

            过去一周核心情报摘要:
            {news_text}

            请严格按照以下 Markdown 格式生成，排版要求非常紧凑，不要有冗余的空行：
            ### 📋 {display_name}地缘政治风险周度研判 ({today_str})
            **1. 周期性局势回顾**：[简要结合风险指数波动和重大事件进行描述，不换行直接写]
            **2. 核心冲突/风险点识别**：[识别主权纠纷、内政动荡或外交博弈等关键点]
            **3. 未来短期趋势预测**：[基于当前情报的演变推演]

            要求：
            - 禁止提供任何“投资建议”或“中国企业建议”。
            - 必须使用 Markdown 加粗和列表语法，但段落之间不要留多余空行。
            - 全文必须使用该国的正式中文全称（{display_name}）。
            - 报告日期必须严格锁定为：{today_str}。
            - 语言专业、中立、极其简练，总字数控制在 400-500 字。
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
                # 核心修复：检查 choices 是否为空，防止 list index out of range
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        content = delta.content
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
