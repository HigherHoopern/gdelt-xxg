import gradio as gr
import pandas as pd
import plotly.express as px
import os
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

# 洲映射表
CONTINENT_MAPPING = {
    'Middle East': '中东',
    'Asia': '亚洲',
    'Europe': '欧洲',
    'Africa': '非洲',
    'North America': '北美洲',
    'South America': '南美洲',
    'Oceania': '大洋洲'
}

# 详细地理数据 (包含洲信息和坐标)
COUNTRY_GEO_DATA = {
    'BX': {'name': '文莱', 'iso': 'BRN', 'continent': 'Asia', 'lat': 4.5, 'lon': 114.7},
    'CB': {'name': '柬埔寨', 'iso': 'KHM', 'continent': 'Asia', 'lat': 12.5, 'lon': 105.0},
    'ID': {'name': '印度尼西亚', 'iso': 'IDN', 'continent': 'Asia', 'lat': -0.78, 'lon': 113.9},
    'LA': {'name': '老挝', 'iso': 'LAO', 'continent': 'Asia', 'lat': 18.0, 'lon': 105.0},
    'MY': {'name': '马来西亚', 'iso': 'MYS', 'continent': 'Asia', 'lat': 4.2, 'lon': 101.9},
    'BM': {'name': '缅甸', 'iso': 'MMR', 'continent': 'Asia', 'lat': 21.9, 'lon': 95.9},
    'RP': {'name': '菲律宾', 'iso': 'PHL', 'continent': 'Asia', 'lat': 12.8, 'lon': 121.7},
    'SN': {'name': '新加坡', 'iso': 'SGP', 'continent': 'Asia', 'lat': 1.3, 'lon': 103.8},
    'TH': {'name': '泰国', 'iso': 'THA', 'continent': 'Asia', 'lat': 15.8, 'lon': 100.9},
    'VM': {'name': '越南', 'iso': 'VNM', 'continent': 'Asia', 'lat': 14.0, 'lon': 108.2},
    'TT': {'name': '东帝汶', 'iso': 'TLS', 'continent': 'Asia', 'lat': -8.8, 'lon': 125.7},
    'IN': {'name': '印度', 'iso': 'IND', 'continent': 'Asia', 'lat': 20.5, 'lon': 78.9},
    'PK': {'name': '巴基斯坦', 'iso': 'PAK', 'continent': 'Asia', 'lat': 30.3, 'lon': 69.3},
    'BG': {'name': '孟加拉国', 'iso': 'BGD', 'continent': 'Asia', 'lat': 23.6, 'lon': 90.3},
    'CE': {'name': '斯里兰卡', 'iso': 'LKA', 'continent': 'Asia', 'lat': 7.8, 'lon': 80.7},
    'NP': {'name': '尼泊尔', 'iso': 'NPL', 'continent': 'Asia', 'lat': 28.3, 'lon': 84.1},
    'BT': {'name': '不丹', 'iso': 'BTN', 'continent': 'Asia', 'lat': 27.5, 'lon': 90.4},
    # 中东国家 (Middle East)
    'IR': {'name': '伊朗', 'iso': 'IRN', 'continent': 'Middle East', 'lat': 32.4, 'lon': 53.6},
    'IZ': {'name': '伊拉克', 'iso': 'IRQ', 'continent': 'Middle East', 'lat': 33.2, 'lon': 43.6},
    'SA': {'name': '沙特', 'iso': 'SAU', 'continent': 'Middle East', 'lat': 23.8, 'lon': 45.0},
    'IS': {'name': '以色列', 'iso': 'ISR', 'continent': 'Middle East', 'lat': 31.0, 'lon': 34.8},
    'TU': {'name': '土耳其', 'iso': 'TUR', 'continent': 'Middle East', 'lat': 38.9, 'lon': 35.2},
    'EG': {'name': '埃及', 'iso': 'EGY', 'continent': 'Middle East', 'lat': 26.8, 'lon': 30.8},
    'AE': {'name': '阿联酋', 'iso': 'ARE', 'continent': 'Middle East', 'lat': 23.4, 'lon': 53.8},
    'QA': {'name': '卡塔尔', 'iso': 'QAT', 'continent': 'Middle East', 'lat': 25.3, 'lon': 51.1},
    'SY': {'name': '叙利亚', 'iso': 'SYR', 'continent': 'Middle East', 'lat': 34.8, 'lon': 38.9},
    'JO': {'name': '约旦', 'iso': 'JOR', 'continent': 'Middle East', 'lat': 31.2, 'lon': 36.5},
    'LE': {'name': '黎巴嫩', 'iso': 'LBN', 'continent': 'Middle East', 'lat': 33.8, 'lon': 35.8},
    # 扩展全球大国
    'US': {'name': '美国', 'iso': 'USA', 'continent': 'North America', 'lat': 37.0, 'lon': -95.7},
    'CH': {'name': '中国', 'iso': 'CHN', 'continent': 'Asia', 'lat': 35.8, 'lon': 104.1},
    'RU': {'name': '俄罗斯', 'iso': 'RUS', 'continent': 'Europe', 'lat': 61.5, 'lon': 105.3},
    'GB': {'name': '英国', 'iso': 'GBR', 'continent': 'Europe', 'lat': 55.3, 'lon': -3.4},
    'FR': {'name': '法国', 'iso': 'FRA', 'continent': 'Europe', 'lat': 46.2, 'lon': 2.2},
    'DE': {'name': '德国', 'iso': 'DEU', 'continent': 'Europe', 'lat': 51.1, 'lon': 10.4},
    'JP': {'name': '日本', 'iso': 'JPN', 'continent': 'Asia', 'lat': 36.2, 'lon': 138.2},
    'KR': {'name': '韩国', 'iso': 'KOR', 'continent': 'Asia', 'lat': 35.9, 'lon': 127.7},
    'BR': {'name': '巴西', 'iso': 'BRA', 'continent': 'South America', 'lat': -14.2, 'lon': -51.9},
    'AU': {'name': '澳大利亚', 'iso': 'AUS', 'continent': 'Oceania', 'lat': -25.2, 'lon': 133.7}
}

def get_dynamic_country_choices(continent_name="全部"):
    """动态获取数据库中所有有数据的国家名称，支持按洲筛选"""
    session = SessionLocal()
    try:
        query = text("SELECT DISTINCT country_code FROM risk_index_history")
        codes = [r[0] for r in session.execute(query).fetchall() if r[0]]
        choices = ["全部"]
        
        continent_key = next((k for k, v in CONTINENT_MAPPING.items() if v == continent_name), None)
        
        for code in sorted(codes):
            data = COUNTRY_GEO_DATA.get(code, {})
            name = data.get('name', code)
            
            if continent_key and data.get('continent') != continent_key:
                continue
                
            choices.append(name)
        return choices
    except:
        return ["全部"]
    finally:
        session.close()

CATEGORY_TRANSLATION = {
    'Military': '军事冲突', 'Political': '政治动荡', 'Economic': '经济制裁',
    'Diplomacy': '外交纠纷', 'Social': '社会安全', 'General': '常规事务'
}

def wrap_in_iframe(chart_obj, height="500px", is_plotly=False):
    if is_plotly:
        full_html = chart_obj.to_html(include_plotlyjs='cdn', full_html=True)
    else:
        full_html = chart_obj.render_embed()
    b64_html = base64.b64encode(full_html.encode('utf-8')).decode('utf-8')
    return f'<iframe src="data:text/html;base64,{b64_html}" width="100%" height="{height}" frameborder="0" style="border-radius:12px; background:white;"></iframe>'

def fetch_history_data_unified():
    """
    统一获取过去 30 天的历史数据，确保地图和趋势图同步。
    """
    session = SessionLocal()
    try:
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
        raw_df['date_str'] = (raw_df['d'] + datetime.timedelta(hours=8)).dt.strftime('%Y-%m-%d')
        return raw_df
    finally:
        session.close()

def render_plotly_map(country_name="全部", continent_name="全部"):
    raw_df = fetch_history_data_unified()
    
    today_dt = datetime.datetime.now()
    all_dates = [(today_dt - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(31)]
    all_dates = sorted(list(set(all_dates)))
    
    if raw_df.empty: return "<div style='height:500px; display:flex; align-items:center; justify-content:center;'>暂无风险数据</div>"
    
    all_countries = list(COUNTRY_GEO_DATA.keys())
    index_df = pd.MultiIndex.from_product([all_dates, all_countries], names=['date_str', 'country_code']).to_frame(index=False)
    df = pd.merge(index_df, raw_df[['date_str', 'country_code', 'risk_index']], on=['date_str', 'country_code'], how='left')
    df['risk_index'] = df['risk_index'].fillna(0)
    
    df['国家'] = df['country_code'].apply(lambda x: COUNTRY_GEO_DATA.get(x, {}).get('name', '未知'))
    df['iso_alpha'] = df['country_code'].apply(lambda x: COUNTRY_GEO_DATA.get(x, {}).get('iso', ''))
    df['风险等级'] = df['risk_index'].apply(lambda x: "低风险" if x <= 20 else "较低风险" if x <= 40 else "中等风险" if x <= 60 else "高风险" if x <= 80 else "极高风险")
    df['continent_cn'] = df['country_code'].apply(lambda x: CONTINENT_MAPPING.get(COUNTRY_GEO_DATA.get(x, {}).get('continent', ''), ''))

    # 根据筛选器过滤地图显示范围 (但保持数据全量用于动画)
    scope = "world"
    if continent_name == "亚洲" or continent_name == "中东":
        scope = "asia"
    elif continent_name == "欧洲":
        scope = "europe"
    elif continent_name == "非洲":
        scope = "africa"
    elif continent_name == "北美洲":
        scope = "north america"
    elif continent_name == "南美洲":
        scope = "south america"

    df = df.sort_values('date_str')
    
    fig = px.choropleth(
        df, locations="iso_alpha", color="risk_index", hover_name="国家", animation_frame="date_str", 
        hover_data={"iso_alpha": False, "risk_index": ":.2f", "date_str": True, "风险等级": True},
        color_continuous_scale=[(0, "#2ECC71"), (0.5, "#F1C40F"), (1.0, "#E74C3C")], 
        range_color=[0, 100], scope=scope,
        labels={'risk_index': '风险指数', 'date_str': '日期'}
    )
    
    fig.update_geos(fitbounds="locations" if continent_name != "全部" else None, visible=False, projection_type="mercator")
    
    fig.update_layout(
        title={'text': "全球风险指数动态演变", 'x': 0.5, 'y': 0.98, 'xanchor': 'center', 'font': {'size': 18}},
        margin={"r":0,"t":50,"l":0,"b":0}, height=850
    )
    
    label_df = pd.DataFrame([{'name': v['name'], 'lat': v['lat'], 'lon': v['lon']} for v in COUNTRY_GEO_DATA.values()])
    fig.add_scattergeo(
        lat=label_df['lat'], lon=label_df['lon'], text=label_df['name'], mode='text', 
        textfont={"color": "#333", "size": 10}, showlegend=False
    )
    
    for frame in fig.frames:
        frame.layout.coloraxis.cmin = 0
        frame.layout.coloraxis.cmax = 100
        
    return wrap_in_iframe(fig, height="850px", is_plotly=True)

def render_line(country_name="全部", continent_name="全部"):
    df = fetch_history_data_unified()
    if df.empty: return "<div style='height:572px; display:flex; align-items:center; justify-content:center;'>暂无历史走势数据</div>"
    
    # 筛选逻辑
    target_countries = []
    if country_name != "全部":
        code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), None)
        target_countries = [code] if code else []
    elif continent_name != "全部":
        continent_key = next((k for k, v in CONTINENT_MAPPING.items() if v == continent_name), None)
        target_countries = [k for k, v in COUNTRY_GEO_DATA.items() if v.get('continent') == continent_key]
    else:
        # 默认显示中东地区
        target_countries = [k for k, v in COUNTRY_GEO_DATA.items() if v.get('continent') == 'Middle East']

    dates = sorted(df['date_str'].unique().tolist())
    line = Line(init_opts=opts.InitOpts(width="100%", height="528px"))
    line.add_xaxis(dates)
    
    active_codes = df['country_code'].unique()
    for code in target_countries:
        if code not in active_codes: continue
        name = COUNTRY_GEO_DATA.get(code, {}).get('name', code)
        country_df = df[df['country_code'] == code]
        data_map = dict(zip(country_df['date_str'], country_df['risk_index']))
        y_data = [round(float(data_map.get(d, 0)), 2) for d in dates]
        line.add_yaxis(name, y_data, is_smooth=True, symbol_size=4, linestyle_opts=opts.LineStyleOpts(width=1.5))
    
    title_prefix = country_name if country_name != "全部" else (continent_name if continent_name != "全部" else "中东地区")
    line.set_global_opts(
        title_opts=opts.TitleOpts(title=f"{title_prefix} 30 天历史风险波动趋势", pos_right="5%"), 
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
        legend_opts=opts.LegendOpts(pos_right="2%", pos_top="middle", orient="vertical"), 
        xaxis_opts=opts.AxisOpts(name="日期"), 
        yaxis_opts=opts.AxisOpts(name="分值"), 
        datazoom_opts=[opts.DataZoomOpts()]
    )
    return wrap_in_iframe(line, height="572px")

def fetch_prediction_data_5d():
    session = SessionLocal()
    try:
        today = datetime.datetime.now().date()
        query = text(f"""
            SELECT country_code, predicted_date as d, predicted_risk_index as val 
            FROM risk_predictions 
            WHERE predicted_date >= :today
            ORDER BY d ASC LIMIT 500
        """)
        df = pd.read_sql(query, session.bind, params={"today": today})
        if not df.empty: df['date_str'] = df['d'].dt.strftime('%m-%d')
        return df, today
    finally:
        session.close()

def render_prediction_chart(country_name="全部", continent_name="全部"):
    df, today = fetch_prediction_data_5d()
    if df.empty: return "<div style='height:500px; display:flex; align-items:center; justify-content:center;'>暂无预测数据</div>"
    
    # 筛选逻辑
    target_countries = []
    if country_name != "全部":
        code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), None)
        target_countries = [code] if code else []
    elif continent_name != "全部":
        continent_key = next((k for k, v in CONTINENT_MAPPING.items() if v == continent_name), None)
        target_countries = [k for k, v in COUNTRY_GEO_DATA.items() if v.get('continent') == continent_key]
    else:
        # 默认显示中东地区
        target_countries = [k for k, v in COUNTRY_GEO_DATA.items() if v.get('continent') == 'Middle East']

    dates_list = [(today + datetime.timedelta(days=i)).strftime('%m-%d') for i in range(6)]
    line = Line(init_opts=opts.InitOpts(width="100%", height="500px"))
    line.add_xaxis(dates_list)
    
    active_codes = df['country_code'].unique()
    for code in target_countries:
        if code not in active_codes: continue
        name = COUNTRY_GEO_DATA.get(code, {}).get('name', code)
        country_df = df[df['country_code'] == code]
        data_map = dict(zip(country_df['date_str'], country_df['val']))
        y_data = [round(float(data_map.get(d, 0)), 2) if d in data_map else None for d in dates_list]
        line.add_yaxis(name, y_data, is_smooth=True, symbol_size=4, linestyle_opts=opts.LineStyleOpts(width=2.25, type_="dashed"), label_opts=opts.LabelOpts(is_show=False))

    title_prefix = country_name if country_name != "全部" else (continent_name if continent_name != "全部" else "中东地区")
    line.set_global_opts(
        title_opts=opts.TitleOpts(title=f"{title_prefix} 未来 5 日风险趋势预测", pos_right="5%"), 
        tooltip_opts=opts.TooltipOpts(trigger="axis", formatter=JsCode("""
                function (params) { var res = ''; params.forEach(function (item) { if (item.value !== null && item.value !== undefined && item.value !== '') { res += item.marker + item.seriesName + ': ' + item.value + '<br/>'; } }); return res; }
            """)),
        legend_opts=opts.LegendOpts(pos_right="2%", pos_top="middle", orient="vertical"), 
        xaxis_opts=opts.AxisOpts(name="日期"), yaxis_opts=opts.AxisOpts(name="分值", min_=0, max_=100)
    )
    return wrap_in_iframe(line, height="500px")

def update_news(country_name="全部", continent_name="全部"):
    logger.info(f"📰 更新实时新闻: {country_name}, {continent_name}")
    code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), None) if country_name != "全部" else None
    
    session = SessionLocal()
    valid_filter = "(title_zh IS NOT NULL OR title IS NOT NULL) AND (summary_zh IS NOT NULL AND summary_zh != '') AND (title_zh NOT LIKE '%无法解析原文%')"
    
    geo_clause = ""
    params = {}
    if code:
        geo_clause = "AND country_code = :code"
        params["code"] = code
    elif continent_name != "全部":
        continent_key = next((k for k, v in CONTINENT_MAPPING.items() if v == continent_name), None)
        continent_countries = [k for k, v in COUNTRY_GEO_DATA.items() if v.get('continent') == continent_key]
        if continent_countries:
            geo_clause = f"AND country_code IN :continent_countries"
            params["continent_countries"] = tuple(continent_countries)
        else:
            geo_clause = "AND 1=0"

    query_news = text(f"SELECT event_date, country_code, category, title, title_zh, summary_zh, url, image_url FROM risk_analysis_data WHERE {valid_filter} {geo_clause} ORDER BY event_date DESC LIMIT 50")
    news_df = pd.read_sql(query_news, session.bind, params=params)
    session.close()
    
    update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    news_html = f"""
    <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #666; font-size: 14px;">📅 数据最后同步时间: {update_time}</span>
        <span style="background: {PRIMARY_COLOR}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">实时同步中</span>
    </div>
    <div style="height:1080px; overflow-y:auto; border-radius:12px; box-shadow:0 4px 16px rgba(0,0,0,0.1); background:white;">
        <table style="width:100%; border-collapse:collapse; table-layout:fixed; font-family:sans-serif;">
            <thead>
                <tr style="background:{PRIMARY_COLOR}; color:white !important; text-align:left;">
                    <th style="width:110px; padding:15px; color:white !important;">时间</th>
                    <th style="width:90px; padding:15px; color:white !important;">国家</th>
                    <th style="width:100px; padding:15px; color:white !important;">类别</th>
                    <th style="width:25%; padding:15px; color:white !important;">标题</th>
                    <th style="width:30%; padding:15px; color:white !important;">内容摘要</th>
                    <th style="width:150px; padding:15px; text-align:center; color:white !important;">图片预览</th>
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
        
        img_url = row.get('image_url')
        if pd.notna(img_url) and img_url != '':
            img_html = f'<img src="{img_url}" style="width:120px; height:90px; object-fit:cover; border-radius:8px;" onerror="this.style.display=\'none\'">'
        else:
            img_html = '<div style="width:120px; height:90px; background:#f0f0f0; border-radius:8px; display:flex; align-items:center; justify-content:center; color:#999; font-size:12px;">暂无图片</div>'

        link_html = f'<a href="{row["url"]}" target="_blank" style="background:{PRIMARY_COLOR}; color:white; padding:4px 10px; border-radius:4px; text-decoration:none; font-size:12px; font-weight:bold;">阅读</a>'
        news_html += f"""<tr style="background:{bg}; border-bottom:1px solid #f0f3f5;"><td style="padding:16px 12px; color:#666; font-size:13px;">{time_str}</td><td style="padding:16px 12px;">{country_cn}</td><td style="padding:16px 12px;">{cat_cn}</td><td style="padding:16px 12px; font-weight:600;">{title_str}</td><td style="padding:16px 12px; font-size:14px;">{summary_str}</td><td style="padding:12px; text-align:center;">{img_html}</td><td style="padding:16px 12px; text-align:center;">{link_html}</td></tr>"""
    news_html += "</tbody></table></div>"
    return news_html

def update_dashboard(country_name, continent_name):
    logger.info(f"🔄 更新仪表盘: {country_name}, {continent_name}")
    fig_map_html = render_plotly_map(country_name, continent_name)
    line_html = render_line(country_name, continent_name)
    predict_html = render_prediction_chart(country_name, continent_name)
    news_html = update_news(country_name, continent_name)
    return fig_map_html, line_html, predict_html, news_html

def generate_report(country_name):
    if country_name == "全部": yield "请先选择具体国家。"
    else:
        code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), None)
        reporter = RiskReporter()
        for chunk in reporter.generate_country_report(code, country_name=country_name): yield chunk

# Gradio 界面
with gr.Blocks(title="全球地缘政治风险分析平台") as demo:
    with gr.Row(variant="compact"):
        with gr.Column(scale=3): 
            gr.Markdown("# 🌍 全球地缘政治风险分析平台")
        with gr.Column(scale=1): 
            continent_selector = gr.Dropdown(choices=["全部"] + list(CONTINENT_MAPPING.values()), value="全部", label="🗺️ 区域筛选")
        with gr.Column(scale=1): 
            country_selector = gr.Dropdown(choices=get_dynamic_country_choices(), value="全部", label="🌐 国家筛选")

    with gr.Tabs():
        with gr.TabItem("🗺️ 风险动态地图"):
            map_plot = gr.HTML()
        
        with gr.TabItem("📈 风险趋势预测"):
            predict_plot = gr.HTML()
            
        with gr.TabItem("📉 历史波动分析"):
            trend_box = gr.HTML()

        with gr.TabItem("📰 实时新闻"):
            news_html_box = gr.HTML()

        with gr.TabItem("🤖 AI 研判报告"):
            with gr.Column(elem_id="ai-report-container"):
                gr.Markdown("### 🤖 区域投资风险 AI 深度研判")
                report_btn = gr.Button("🚀 立即生成研判报告", variant="primary")
                with gr.Column(elem_id="ai-report-scroll-area"):
                    report_box = gr.Markdown("请在顶部选择国家后点击生成按钮。", elem_id="ai-report-box")

    # 洲级联动
    def on_continent_change(continent):
        new_choices = get_dynamic_country_choices(continent)
        return gr.update(choices=new_choices, value="全部")

    continent_selector.change(on_continent_change, inputs=[continent_selector], outputs=[country_selector])

    outputs = [map_plot, trend_box, predict_plot, news_html_box]
    dashboard_inputs = [country_selector, continent_selector]
    
    demo.load(update_dashboard, inputs=dashboard_inputs, outputs=outputs)
    country_selector.change(update_dashboard, inputs=dashboard_inputs, outputs=outputs)
    continent_selector.change(update_dashboard, inputs=dashboard_inputs, outputs=outputs)
    
    gr.Timer(60).tick(update_dashboard, inputs=dashboard_inputs, outputs=outputs)
    report_btn.click(generate_report, inputs=[country_selector], outputs=[report_box])

if __name__ == "__main__":
    custom_theme = gr.themes.Default(primary_hue=gr.themes.Color(c50="#e6f0ff", c100="#cce0ff", c200="#99c2ff", c300="#66a3ff", c400="#3385ff", c500="#1467DF", c600="#1158c4", c700="#0d469b", c800="#0a3673", c900="#07264a", c950="#04152b"))
    demo.launch(server_name="0.0.0.0", server_port=8090, theme=custom_theme, 
        css=f"""
        .gradio-container {{max-width: 98% !important; background-color: #f4f7f9 !important;}}
        footer {{display: none !important;}}
        button.primary, .gr-button-primary {{ background-color: {PRIMARY_COLOR} !important; border-color: {PRIMARY_COLOR} !important; color: white !important; }}
        .tabs .tabitem.selected {{ border-color: {PRIMARY_COLOR} !important; }}
        #ai-report-container {{ height: 1000px !important; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; background: #ffffff; box-shadow: 0 2px 12px rgba(0,0,0,0.08); display: flex !important; flex-direction: column !important; }}
        #ai-report-scroll-area {{ flex-grow: 1 !important; height: 850px !important; overflow-y: auto !important; border-top: 1px solid #eee; margin-top: 10px; padding-top: 10px; }}
        #ai-report-box {{ min-height: 100%; font-family: sans-serif; line-height: 1.5; color: #2c3e50; }}
        """)
