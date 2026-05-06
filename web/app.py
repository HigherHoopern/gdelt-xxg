import gradio as gr
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from common.models import SessionLocal, DailyRiskIndex, RiskAnalysisData, RiskPrediction, RiskReport, RiskIndexHistory
from config.settings import REGIONAL_COUNTRIES
from service.reporter.main import RiskReporter
import datetime
import base64
from common.logger import setup_logger

# ECharts 相关导入
from pyecharts import options as opts
from pyecharts.charts import Line
from pyecharts.globals import CurrentConfig
from pyecharts.commons.utils import JsCode

# 配置 ECharts 资源
CurrentConfig.ONLINE_HOST = "https://assets.pyecharts.org/assets/"

logger = setup_logger("WebDashboard")

# 全局品牌主色调
PRIMARY_COLOR = "#1467DF"

# 详细地理数据
COUNTRY_GEO_DATA = {
    'BX': {'name': '文莱', 'iso': 'BRN', 'en': 'Brunei', 'lat': 4.5, 'lon': 114.7},
    'CB': {'name': '柬埔寨', 'iso': 'KHM', 'en': 'Cambodia', 'lat': 12.5, 'lon': 105.0},
    'ID': {'name': '印度尼西亚', 'iso': 'IDN', 'en': 'Indonesia', 'lat': -0.78, 'lon': 113.9},
    'LA': {'name': '老挝', 'iso': 'LAO', 'en': 'Laos', 'lat': 18.0, 'lon': 105.0},
    'MY': {'name': '马来西亚', 'iso': 'MYS', 'en': 'Malaysia', 'lat': 4.2, 'lon': 101.9},
    'BM': {'name': '缅甸', 'iso': 'MMR', 'en': 'Myanmar', 'lat': 21.9, 'lon': 95.9},
    'RP': {'name': '菲律宾', 'iso': 'PHL', 'en': 'Philippines', 'lat': 12.8, 'lon': 121.7},
    'SN': {'name': '新加坡', 'iso': 'SGP', 'en': 'Singapore', 'lat': 1.3, 'lon': 103.8},
    'TH': {'name': '泰国', 'iso': 'THA', 'en': 'Thailand', 'lat': 15.8, 'lon': 100.9},
    'VM': {'name': '越南', 'iso': 'VNM', 'en': 'Vietnam', 'lat': 14.0, 'lon': 108.2},
    'TT': {'name': '东帝汶', 'iso': 'TLS', 'en': 'Timor-Leste', 'lat': -8.8, 'lon': 125.7},
    'IN': {'name': '印度', 'iso': 'IND', 'en': 'India', 'lat': 20.5, 'lon': 78.9},
    'PK': {'name': '巴基斯坦', 'iso': 'PAK', 'en': 'Pakistan', 'lat': 30.3, 'lon': 69.3},
    'BG': {'name': '孟加拉国', 'iso': 'BGD', 'en': 'Bangladesh', 'lat': 23.6, 'lon': 90.3},
    'CE': {'name': '斯里兰卡', 'iso': 'LKA', 'en': 'Sri Lanka', 'lat': 7.8, 'lon': 80.7},
    'NP': {'name': '尼泊尔', 'iso': 'NPL', 'en': 'Nepal', 'lat': 28.3, 'lon': 84.1},
    'BT': {'name': '不丹', 'iso': 'BTN', 'en': 'Bhutan', 'lat': 27.5, 'lon': 90.4}
}

CATEGORY_TRANSLATION = {
    'Military': '军事冲突', 'Political': '政治动荡', 'Economic': '经济制裁',
    'Diplomacy': '外交纠纷', 'Social': '社会安全', 'General': '常规事务'
}

def wrap_in_iframe(chart_obj, height="440px", is_plotly=False):
    if is_plotly:
        full_html = chart_obj.to_html(include_plotlyjs='cdn', full_html=True)
    else:
        full_html = chart_obj.render_embed()
    b64_html = base64.b64encode(full_html.encode('utf-8')).decode('utf-8')
    return f'<iframe src="data:text/html;base64,{b64_html}" width="100%" height="{height}" frameborder="0" style="border-radius:10px;"></iframe>'

def fetch_history_data_unified():
    """
    统一获取过去 30 天的历史数据，确保地图和趋势图同步。
    """
    session = SessionLocal()
    try:
        # 获取当前时间点，向前回溯 30 天
        # 注意：使用 calculation_date 的最大值作为基准，或者直接使用 now()
        now = datetime.datetime.now()
        start_time = now - datetime.timedelta(days=30)
        
        query = text("""
            SELECT country_code, AVG(risk_index) as risk_index, date_trunc('day', calculation_date) as d
            FROM risk_index_history 
            WHERE calculation_date >= :start
            GROUP BY country_code, date_trunc('day', calculation_date)
            ORDER BY d ASC
        """)
        raw_df = pd.read_sql(query, session.bind, params={"start": start_time})
        if raw_df.empty: return raw_df

        # 统一日期格式化逻辑
        raw_df['date_str'] = (raw_df['d'] + datetime.timedelta(hours=8)).dt.strftime('%Y-%m-%d')
        return raw_df
    finally:
        session.close()

def render_plotly_map():
    raw_df = fetch_history_data_unified()
    if raw_df.empty: return "<div style='height:500px; display:flex; align-items:center; justify-content:center;'>暂无风险数据</div>"
    
    # 构造完整的日期-国家矩阵，确保动画滑块包含所有日期
    all_dates = sorted(raw_df['date_str'].unique().tolist())
    all_countries = list(COUNTRY_GEO_DATA.keys())
    
    index_df = pd.MultiIndex.from_product([all_dates, all_countries], names=['date_str', 'country_code']).to_frame(index=False)
    df = pd.merge(index_df, raw_df[['date_str', 'country_code', 'risk_index']], on=['date_str', 'country_code'], how='left')
    df['risk_index'] = df['risk_index'].fillna(0)
    
    df['国家'] = df['country_code'].apply(lambda x: COUNTRY_GEO_DATA.get(x, {}).get('name', '未知'))
    df['iso_alpha'] = df['country_code'].apply(lambda x: COUNTRY_GEO_DATA.get(x, {}).get('iso', ''))
    df['风险等级'] = df['risk_index'].apply(lambda x: "低风险" if x <= 20 else "较高风险" if x <= 40 else "中等风险" if x <= 60 else "高风险" if x <= 80 else "极高风险")
    
    df = df.sort_values('date_str')
    
    fig = px.choropleth(
        df, locations="iso_alpha", color="risk_index", hover_name="国家", animation_frame="date_str", 
        hover_data={"iso_alpha": False, "risk_index": ":.2f", "date_str": True, "风险等级": True},
        color_continuous_scale=[(0, "#2ECC71"), (0.5, "#F1C40F"), (1.0, "#E74C3C")], 
        range_color=[0, 100], scope="asia",
        labels={'risk_index': '风险指数', 'date_str': '日期'}
    )
    
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=500)
    
    label_df = pd.DataFrame([{'name': v['name'], 'lat': v['lat'], 'lon': v['lon']} for v in COUNTRY_GEO_DATA.values()])
    fig.add_scattergeo(
        lat=label_df['lat'], lon=label_df['lon'], text=label_df['name'], mode='text', 
        textfont={"color": "#333", "size": 10, "family": "Arial Black"}, showlegend=False
    )
    
    for frame in fig.frames:
        frame.layout.coloraxis.cmin = 0
        frame.layout.coloraxis.cmax = 100
        
    return wrap_in_iframe(fig, height="500px", is_plotly=True)

def render_line(country_code=None):
    df = fetch_history_data_unified()
    if df.empty: return "<div style='height:572px; display:flex; align-items:center; justify-content:center;'>暂无历史走势数据</div>"
    
    dates = sorted(df['date_str'].unique().tolist())
    line = Line(init_opts=opts.InitOpts(width="100%", height="528px"))
    line.add_xaxis(dates)
    
    target_countries = [country_code] if country_code else df['country_code'].unique()
    for code in target_countries:
        name = COUNTRY_GEO_DATA.get(code, {}).get('name', code)
        country_df = df[df['country_code'] == code]
        if country_df.empty: continue
        data_map = dict(zip(country_df['date_str'], country_df['risk_index']))
        y_data = [round(float(data_map.get(d, 0)), 2) for d in dates]
        line.add_yaxis(name, y_data, is_smooth=True, symbol_size=4, linestyle_opts=opts.LineStyleOpts(width=1.5))
    
    line.set_global_opts(
        title_opts=opts.TitleOpts(title="30 天历史风险波动趋势"), 
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
        legend_opts=opts.LegendOpts(pos_right="2%", pos_top="middle", orient="vertical"), 
        xaxis_opts=opts.AxisOpts(name="日期"), 
        yaxis_opts=opts.AxisOpts(name="分值"), 
        datazoom_opts=[opts.DataZoomOpts()]
    )
    return wrap_in_iframe(line, height="572px")

def fetch_prediction_data_5d(country_code=None):
    session = SessionLocal()
    try:
        today = datetime.datetime.now().date()
        where_clause = f"AND country_code = '{country_code}'" if country_code else ""
        query = text(f"""
            SELECT country_code, predicted_date as d, predicted_risk_index as val 
            FROM risk_predictions 
            WHERE predicted_date >= :today {where_clause}
            ORDER BY d ASC LIMIT 100
        """)
        df = pd.read_sql(query, session.bind, params={"today": today})
        if not df.empty: df['date_str'] = df['d'].dt.strftime('%m-%d')
        return df, today
    finally:
        session.close()

def render_prediction_chart(country_code=None):
    df, today = fetch_prediction_data_5d(country_code)
    if df.empty: return "<div style='height:500px; display:flex; align-items:center; justify-content:center;'>暂无预测数据</div>"
    
    dates_list = [(today + datetime.timedelta(days=i)).strftime('%m-%d') for i in range(6)]
    line = Line(init_opts=opts.InitOpts(width="100%", height="500px"))
    line.add_xaxis(dates_list)
    
    target_countries = [country_code] if country_code else df['country_code'].unique()
    for code in target_countries:
        name = COUNTRY_GEO_DATA.get(code, {}).get('name', code)
        country_df = df[df['country_code'] == code]
        if country_df.empty: continue
        data_map = dict(zip(country_df['date_str'], country_df['val']))
        y_data = [round(float(data_map.get(d, 0)), 2) if d in data_map else None for d in dates_list]
        line.add_yaxis(name, y_data, is_smooth=True, symbol_size=4, linestyle_opts=opts.LineStyleOpts(width=2.25, type_="dashed"), label_opts=opts.LabelOpts(is_show=False))

    line.set_global_opts(
        title_opts=opts.TitleOpts(title="未来 5 日风险趋势预测"), 
        tooltip_opts=opts.TooltipOpts(trigger="axis", formatter=JsCode("""
                function (params) { var res = ''; params.forEach(function (item) { if (item.value !== null && item.value !== undefined && item.value !== '') { res += item.marker + item.seriesName + ': ' + item.value + '<br/>'; } }); return res; }
            """)),
        legend_opts=opts.LegendOpts(pos_right="2%", pos_top="middle", orient="vertical"), 
        xaxis_opts=opts.AxisOpts(name="日期"), yaxis_opts=opts.AxisOpts(name="分值", min_=0, max_=100)
    )
    return wrap_in_iframe(line, height="500px")

def update_dashboard(country_name):
    logger.info(f"🔄 更新仪表盘: {country_name}")
    code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), None)
    
    # 修复：先获取统一数据
    fig_map_html = render_plotly_map()
    line_html = render_line(code)
    predict_html = render_prediction_chart(code)
    
    session = SessionLocal()
    # 核心过滤逻辑：排除标题/摘要缺失、无法解析或失效的干扰信息
    valid_filter = """
        (title_zh IS NOT NULL OR title IS NOT NULL) 
        AND (summary_zh IS NOT NULL AND summary_zh != '')
        AND (title_zh NOT LIKE '%无法解析原文%')
        AND (summary_zh NOT LIKE '%无法解析原文%')
        AND (summary_zh NOT LIKE '%该链接已失效或被拦截%')
    """
    where_clause = f"WHERE country_code = :code AND {valid_filter}" if code else f"WHERE {valid_filter}"
    query_news = text(f"SELECT event_date, country_code, category, title, title_zh, summary_zh, url FROM risk_analysis_data {where_clause} ORDER BY event_date DESC LIMIT 20")
    news_df = pd.read_sql(query_news, session.bind, params={"code": code} if code else {})
    session.close()
    
    news_html = f"""
    <div style="height:1080px; overflow-y:auto; border-radius:12px; box-shadow:0 4px 16px rgba(0,0,0,0.1); background:white;">
        <table style="width:100%; border-collapse:collapse; table-layout:fixed; font-family:sans-serif;">
            <thead>
                <tr style="background:{PRIMARY_COLOR}; color:white !important; text-align:left;">
                    <th style="width:110px; padding:15px; color:white !important;">时间</th>
                    <th style="width:90px; padding:15px; color:white !important;">国家</th>
                    <th style="width:100px; padding:15px; color:white !important;">类别</th>
                    <th style="width:30%; padding:15px; color:white !important;">标题</th>
                    <th style="width:40%; padding:15px; color:white !important;">内容摘要</th>
                    <th style="width:80px; padding:15px; text-align:center; color:white !important;">详情</th>
                </tr>
            </thead>
            <tbody>
    """
    for i, row in news_df.iterrows():
        bg = "#fafbfc" if i % 2 == 0 else "#ffffff"
        time_str = (row['event_date'] + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
        country_cn = COUNTRY_GEO_DATA.get(row['country_code'], {}).get('name', row['country_code'])
        cat_cn = CATEGORY_TRANSLATION.get(row['category'], row['category'])
        title_str = str(row['title_zh']) if pd.notna(row['title_zh']) and row['title_zh'] != '' else str(row['title'])
        if title_str.lower() == 'nan': continue
        summary_str = str(row['summary_zh'])[:250] + "..."
        link_html = f'<a href="{row["url"]}" target="_blank" style="background:{PRIMARY_COLOR}; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">阅读</a>'
        news_html += f"""<tr style="background:{bg}; border-bottom:1px solid #f0f3f5;"><td style="padding:16px 12px; color:#666; font-size:13px;">{time_str}</td><td style="padding:16px 12px;">{country_cn}</td><td style="padding:16px 12px;">{cat_cn}</td><td style="padding:16px 12px; font-weight:600;">{title_str}</td><td style="padding:16px 12px; font-size:14px;">{summary_str}</td><td style="padding:16px 12px; text-align:center;">{link_html}</td></tr>"""
    news_html += "</tbody></table></div>"
    
    return fig_map_html, line_html, predict_html, news_html

def generate_report(country_name):
    if country_name == "全部": yield "请先选择具体国家。"
    else:
        code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), None)
        reporter = RiskReporter()
        for chunk in reporter.generate_country_report(code, country_name=country_name): yield chunk

# Gradio 界面
with gr.Blocks(title="南亚东南亚地缘风险分析平台") as demo:
    with gr.Row(variant="compact"):
        with gr.Column(scale=5): 
            gr.Markdown("# 南亚东南亚地缘政治风险分析平台")
        with gr.Column(scale=1): 
            country_selector = gr.Dropdown(choices=["全部"] + [v['name'] for v in COUNTRY_GEO_DATA.values()], value="全部", label="🌐 全局筛选", container=False)

    with gr.Tabs():
        with gr.TabItem("📊 风险监测面板"):
            with gr.Row():
                with gr.Column(scale=1): map_plot = gr.HTML(label="风险动态演变")
                with gr.Column(scale=1): predict_plot = gr.HTML(label="未来 5 日风险预测")
            with gr.Row(): trend_box = gr.HTML(label="风险趋势分析")

        with gr.TabItem("📰 实时新闻"):
            news_html_box = gr.HTML()

        with gr.TabItem("🤖 AI 研判报告"):
            with gr.Column(elem_id="ai-report-container"):
                gr.Markdown("### 🤖 区域投资风险 AI 深度研判")
                report_btn = gr.Button("🚀 立即生成研判报告", variant="primary")
                with gr.Column(elem_id="ai-report-scroll-area"):
                    report_box = gr.Markdown("请在顶部选择国家后点击生成按钮。", elem_id="ai-report-box")

    outputs = [map_plot, trend_box, predict_plot, news_html_box]
    demo.load(update_dashboard, inputs=[country_selector], outputs=outputs)
    country_selector.change(update_dashboard, inputs=[country_selector], outputs=outputs)
    gr.Timer(900).tick(update_dashboard, inputs=[country_selector], outputs=outputs)
    report_btn.click(generate_report, inputs=[country_selector], outputs=[report_box])

if __name__ == "__main__":
    custom_theme = gr.themes.Default(primary_hue=gr.themes.Color(c50="#e6f0ff", c100="#cce0ff", c200="#99c2ff", c300="#66a3ff", c400="#3385ff", c500="#1467DF", c600="#1158c4", c700="#0d469b", c800="#0a3673", c900="#07264a", c950="#04152b"))
    demo.launch(server_name="0.0.0.0", server_port=8090, theme=custom_theme, 
        css=f"""
        .gradio-container {{max-width: 98% !important; background-color: #f4f7f9 !important;}}
        button.primary, .gr-button-primary {{ background-color: {PRIMARY_COLOR} !important; border-color: {PRIMARY_COLOR} !important; color: white !important; }}
        .tabs .tabitem.selected {{ border-color: {PRIMARY_COLOR} !important; }}
        #ai-report-container {{ height: 1000px !important; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; background: #ffffff; box-shadow: 0 2px 12px rgba(0,0,0,0.08); display: flex !important; flex-direction: column !important; }}
        #ai-report-scroll-area {{ flex-grow: 1 !important; height: 850px !important; overflow-y: auto !important; border-top: 1px solid #eee; margin-top: 10px; padding-top: 10px; }}

        #ai-report-box {{ min-height: 100%; font-family: sans-serif; }}
        #news-table-wrapper {{ height: 1100px !important; max-height: 1100px !important; min-height: 1100px !important; display: block !important; }}
        """)
