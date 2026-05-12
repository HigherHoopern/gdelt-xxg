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

# 详细地理数据 (增加所属洲)
COUNTRY_GEO_DATA = {
    'BX': {'name': '文莱', 'iso': 'BRN', 'continent': 'Asia'},
    'CB': {'name': '柬埔寨', 'iso': 'KHM', 'continent': 'Asia'},
    'ID': {'name': '印度尼西亚', 'iso': 'IDN', 'continent': 'Asia'},
    'LA': {'name': '老挝', 'iso': 'LAO', 'continent': 'Asia'},
    'MY': {'name': '马来西亚', 'iso': 'MYS', 'continent': 'Asia'},
    'BM': {'name': '缅甸', 'iso': 'MMR', 'continent': 'Asia'},
    'RP': {'name': '菲律宾', 'iso': 'PHL', 'continent': 'Asia'},
    'SN': {'name': '新加坡', 'iso': 'SGP', 'continent': 'Asia'},
    'TH': {'name': '泰国', 'iso': 'THA', 'continent': 'Asia'},
    'VM': {'name': '越南', 'iso': 'VNM', 'continent': 'Asia'},
    'TT': {'name': '东帝汶', 'iso': 'TLS', 'continent': 'Asia'},
    'IN': {'name': '印度', 'iso': 'IND', 'continent': 'Asia'},
    'PK': {'name': '巴基斯坦', 'iso': 'PAK', 'continent': 'Asia'},
    'BG': {'name': '孟加拉国', 'iso': 'BGD', 'continent': 'Asia'},
    'CE': {'name': '斯里兰卡', 'iso': 'LKA', 'continent': 'Asia'},
    'NP': {'name': '尼泊尔', 'iso': 'NPL', 'continent': 'Asia'},
    'BT': {'name': '不丹', 'iso': 'BTN', 'continent': 'Asia'},
    # 中东国家 (Middle East)
    'IR': {'name': '伊朗', 'iso': 'IRN', 'continent': 'Middle East'},
    'IZ': {'name': '伊拉克', 'iso': 'IRQ', 'continent': 'Middle East'},
    'SA': {'name': '沙特', 'iso': 'SAU', 'continent': 'Middle East'},
    'IS': {'name': '以色列', 'iso': 'ISR', 'continent': 'Middle East'},
    'TU': {'name': '土耳其', 'iso': 'TUR', 'continent': 'Middle East'},
    'EG': {'name': '埃及', 'iso': 'EGY', 'continent': 'Middle East'},
    'AE': {'name': '阿联酋', 'iso': 'ARE', 'continent': 'Middle East'},
    'QA': {'name': '卡塔尔', 'iso': 'QAT', 'continent': 'Middle East'},
    'SY': {'name': '叙利亚', 'iso': 'SYR', 'continent': 'Middle East'},
    'JO': {'name': '约旦', 'iso': 'JOR', 'continent': 'Middle East'},
    'LE': {'name': '黎巴嫩', 'iso': 'LBN', 'continent': 'Middle East'},
    # 扩展全球大国
    'US': {'name': '美国', 'iso': 'USA', 'continent': 'North America'},
    'CH': {'name': '中国', 'iso': 'CHN', 'continent': 'Asia'},
    'RU': {'name': '俄罗斯', 'iso': 'RUS', 'continent': 'Europe'},
    'GB': {'name': '英国', 'iso': 'GBR', 'continent': 'Europe'},
    'FR': {'name': '法国', 'iso': 'FRA', 'continent': 'Europe'},
    'DE': {'name': '德国', 'iso': 'DEU', 'continent': 'Europe'},
    'JP': {'name': '日本', 'iso': 'JPN', 'continent': 'Asia'},
    'KR': {'name': '韩国', 'iso': 'KOR', 'continent': 'Asia'},
    'BR': {'name': '巴西', 'iso': 'BRA', 'continent': 'South America'},
    'AU': {'name': '澳大利亚', 'iso': 'AUS', 'continent': 'Oceania'}
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
    'Diplomacy': '外交纠纷', 'Social': '社会安全', 'General': '常规事务',
    'Health': '卫生防疫', 'Environment': '生态环境', 'Tech': '科技竞争'
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

# 全球 FIPS 10-4 到 ISO Alpha-3 映射表 (常用国家)
FIPS_TO_ISO = {
    'US': 'USA', 'CH': 'CHN', 'RU': 'RUS', 'IN': 'IND', 'ID': 'IDN', 'BR': 'BRA', 'PK': 'PAK', 'NG': 'NGA', 'BD': 'BGD', 'RU': 'RUS', 'MX': 'MEX', 'JP': 'JPN', 'ET': 'ETH', 'PH': 'PHL', 'RP': 'PHL', 'EG': 'EGY', 'VN': 'VNM', 'VM': 'VNM', 'CD': 'COD', 'TR': 'TUR', 'IR': 'IRN', 'DE': 'DEU', 'TH': 'THA', 'GB': 'GBR', 'FR': 'FRA', 'IT': 'ITA', 'ZA': 'ZAF', 'MM': 'MMR', 'BM': 'MMR', 'KR': 'KOR', 'CO': 'COL', 'ES': 'ESP', 'UA': 'UKR', 'AR': 'ARG', 'DZ': 'DZA', 'PL': 'POL', 'CA': 'CAN', 'SA': 'SAU', 'UZ': 'UZB', 'MY': 'MYS', 'IQ': 'IRQ', 'AF': 'AFG', 'AFG': 'AFG', 'CB': 'KHM', 'LA': 'LAO', 'SN': 'SGP', 'BX': 'BRN', 'TT': 'TLS', 'TT': 'TLS', 'CE': 'LKA', 'NP': 'NPL', 'BT': 'BTN', 'BG': 'BGD', 'PK': 'PAK', 'IN': 'IND'
}

def render_plotly_map():
    raw_df = fetch_history_data_unified()
    
    # 核心修复：手动构造最近 31 天的完整日期轴，确保包含当前最新日期
    today_dt = datetime.datetime.now()
    all_dates = [(today_dt - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(31)]
    all_dates = sorted(list(set(all_dates)))
    
    if raw_df.empty: return "<div style='height:500px; display:flex; align-items:center; justify-content:center;'>暂无风险数据</div>"
    
    # 全球化修改：从数据中提取所有出现的国家，而不是仅限于 ASEAN
    all_countries = list(raw_df['country_code'].unique())
    index_df = pd.MultiIndex.from_product([all_dates, all_countries], names=['date_str', 'country_code']).to_frame(index=False)
    df = pd.merge(index_df, raw_df[['date_str', 'country_code', 'risk_index']], on=['date_str', 'country_code'], how='left')
    df['risk_index'] = df['risk_index'].fillna(0)
    
    # 映射国家名称和 ISO 代码
    df['国家'] = df['country_code'].apply(lambda x: COUNTRY_GEO_DATA.get(x, {}).get('name', x))
    df['iso_alpha'] = df['country_code'].apply(lambda x: FIPS_TO_ISO.get(x, x)) # 优先从映射表找，找不到用原码
    df['风险等级'] = df['risk_index'].apply(lambda x: "低风险" if x <= 20 else "较低风险" if x <= 40 else "中等风险" if x <= 60 else "高风险" if x <= 80 else "极高风险")
    
    df = df.sort_values('date_str')
    
    fig = px.choropleth(
        df, locations="iso_alpha", color="risk_index", hover_name="国家", animation_frame="date_str", 
        hover_data={"iso_alpha": False, "risk_index": ":.2f", "date_str": True, "风险等级": True},
        color_continuous_scale=[(0, "#2ECC71"), (0.5, "#F1C40F"), (1.0, "#E74C3C")], 
        range_color=[0, 100], scope="world", # 修改为世界范围
        labels={'risk_index': '风险指数', 'date_str': '日期'}
    )
    
    # 采用自然地球投影，视觉效果更好
    fig.update_geos(
        visible=True, 
        projection_type="natural earth",
        showcountries=True, 
        countrycolor="RebeccaPurple"
    )
    
    fig.update_layout(
        title={'text': "全球风险指数动态", 'x': 0.95, 'y': 0.98, 'xanchor': 'right', 'font': {'size': 18}},
        margin={"r":20,"t":80,"l":10,"b":0}, height=500
    )
    
    for frame in fig.frames:
        frame.layout.coloraxis.cmin = 0
        frame.layout.coloraxis.cmax = 100
        
    return wrap_in_iframe(fig, height="500px", is_plotly=True)

def render_line(country_name="全部", continent_name="全部"):
    df = fetch_history_data_unified()
    if df.empty: return "<div style='height:572px; display:flex; align-items:center; justify-content:center;'>暂无历史走势数据</div>"
    
    # 逻辑调整：默认显示中东国家
    target_countries = []
    if country_name != "全部":
        code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), country_name)
        target_countries = [code]
    elif continent_name != "全部":
        continent_key = next((k for k, v in CONTINENT_MAPPING.items() if v == continent_name), None)
        target_countries = [k for k, v in COUNTRY_GEO_DATA.items() if v.get('continent') == continent_key]
    else:
        # 默认：中东
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
    
    line.set_global_opts(
        title_opts=opts.TitleOpts(title=f"{continent_name if continent_name != '全部' else '中东地区'} 30 天历史风险波动趋势", pos_right="5%"), 
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
        where_clause = ""
        if country_code:
            where_clause = f"AND country_code = '{country_code}'"
            
        query = text(f"""
            SELECT country_code, predicted_date as d, predicted_risk_index as val 
            FROM risk_predictions 
            WHERE predicted_date >= :today {where_clause}
            ORDER BY d ASC LIMIT 500
        """)
        df = pd.read_sql(query, session.bind, params={"today": today})
        if not df.empty: df['date_str'] = df['d'].dt.strftime('%m-%d')
        return df, today
    finally:
        session.close()

def render_prediction_chart(country_name="全部", continent_name="全部"):
    # 逻辑调整：默认显示中东国家
    target_countries = []
    if country_name != "全部":
        code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), country_name)
        target_countries = [code]
    elif continent_name != "全部":
        continent_key = next((k for k, v in CONTINENT_MAPPING.items() if v == continent_name), None)
        target_countries = [k for k, v in COUNTRY_GEO_DATA.items() if v.get('continent') == continent_key]
    else:
        target_countries = [k for k, v in COUNTRY_GEO_DATA.items() if v.get('continent') == 'Middle East']

    df, today = fetch_prediction_data_5d()
    if df.empty: return "<div style='height:500px; display:flex; align-items:center; justify-content:center;'>暂无预测数据</div>"
    
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

    line.set_global_opts(
        title_opts=opts.TitleOpts(title=f"{continent_name if continent_name != '全部' else '中东地区'} 未来 5 日风险趋势预测", pos_right="5%"), 
        tooltip_opts=opts.TooltipOpts(trigger="axis", formatter=JsCode("""
                function (params) { var res = ''; params.forEach(function (item) { if (item.value !== null && item.value !== undefined && item.value !== '') { res += item.marker + item.seriesName + ': ' + item.value + '<br/>'; } }); return res; }
            """)),
        legend_opts=opts.LegendOpts(pos_right="2%", pos_top="middle", orient="vertical"), 
        xaxis_opts=opts.AxisOpts(name="日期"), yaxis_opts=opts.AxisOpts(name="分值", min_=0, max_=100)
    )
    return wrap_in_iframe(line, height="500px")

def update_news(country_name="全部", continent_name="全部", search_keyword=""):
    search_keyword = search_keyword or ""
    logger.info(f"📰 更新实时新闻: {country_name}, {continent_name}, 搜索: {search_keyword}")
    
    code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), None) if country_name != "全部" else None
    session = SessionLocal()
    # 核心需求：过去 3 天的新闻 (根据用户最新要求恢复 3 天窗口)
    since_time = datetime.datetime.now() - datetime.timedelta(days=3)
    
    valid_filter = "(title_zh IS NOT NULL OR title IS NOT NULL) AND (summary_zh IS NOT NULL AND summary_zh != '') AND (title_zh NOT LIKE '%无法解析原文%')"
    search_clause = ""
    params = {"since": since_time}
    
    if search_keyword and search_keyword.strip():
        search_clause = f"AND (title_zh ILIKE :kw OR summary_zh ILIKE :kw OR title ILIKE :kw)"
        params["kw"] = f"%{search_keyword}%"
        
    geo_clause = ""
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

    query_news = text(f"""
        SELECT event_date, country_code, category, title, title_zh, summary_zh, url, image_url 
        FROM risk_analysis_data 
        WHERE event_date >= :since AND {valid_filter} {geo_clause} {search_clause}
        ORDER BY event_date DESC LIMIT 30
    """)
    
    news_df = pd.read_sql(query_news, session.bind, params=params)
    session.close()
    
    update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    news_html = f"""
    <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #666; font-size: 14px;">📅 数据同步时间: {update_time} (仅显示过去3天新闻)</span>
        <span style="background: {PRIMARY_COLOR}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">全球实时同步</span>
    </div>
    <div style="height:1080px; overflow-y:auto; border-radius:12px; box-shadow:0 4px 16px rgba(0,0,0,0.1); background:white;">
        <table style="width:100%; border-collapse:collapse; table-layout:fixed; font-family:sans-serif;">
            <thead>
                <tr style="background:{PRIMARY_COLOR}; color:white !important; text-align:left;">
                    <th style="width:90px; padding:15px; color:white !important;">时间</th>
                    <th style="width:40px; padding:15px; color:white !important;">国家</th>
                    <th style="width:45px; padding:15px; color:white !important;">类别</th>
                    <th style="width:12%; padding:15px; color:white !important;">标题</th>
                    <th style="width:30%; padding:15px; color:white !important;">内容摘要</th>
                    <th style="width:250px; padding:15px; text-align:center; color:white !important;">图片预览</th>
                    <th style="width:60px; padding:15px; text-align:center; color:white !important;">详情</th>
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
        summary_str = str(row['summary_zh'])[:300] + "..."
        
        # 尺寸再加倍：240x180
        img_url = row.get('image_url')
        if pd.notna(img_url) and img_url != '':
            img_html = f'<img src="{img_url}" style="width:240px; height:180px; object-fit:cover; border-radius:8px;" onerror="this.parentElement.innerHTML=\'<div style=width:240px;height:180px;background:#f0f0f0;display:flex;align-items:center;justify-content:center;color:#999;font-size:12px;>图片失效</div>\'">'
        else:
            img_html = '<div style="width:240px; height:180px; background:#f0f0f0; border-radius:8px; display:flex; align-items:center; justify-content:center; color:#999; font-size:12px;">暂无图片</div>'

        link_html = f'<a href="{row["url"]}" target="_blank" style="background:{PRIMARY_COLOR}; color:white; padding:8px 16px; border-radius:4px; text-decoration:none; font-size:13px; font-weight:bold;">阅读原文</a>'
        news_html += f"""
        <tr style="background:{bg}; border-bottom:1px solid #f0f3f5;">
            <td style="padding:16px 12px; color:#666; font-size:12px;">{time_str}</td>
            <td style="padding:16px 12px; font-size:12px;">{country_cn}</td>
            <td style="padding:16px 12px; font-size:12px;">{cat_cn}</td>
            <td style="padding:16px 12px; font-weight:600; font-size:13px; line-height:1.4;">{title_str}</td>
            <td style="padding:16px 12px; font-size:13px; color:#444; line-height:1.5;">{summary_str}</td>
            <td style="padding:12px; text-align:center;">{img_html}</td>
            <td style="padding:16px 12px; text-align:center;">{link_html}</td>
        </tr>"""
    news_html += "</tbody></table></div>"
    return news_html

def update_visualizations(country_name="全部", continent_name="全部"):
    logger.info(f"📊 更新图表可视化: {country_name}, {continent_name}")
    fig_map_html = render_plotly_map()
    line_html = render_line(country_name, continent_name)
    predict_html = render_prediction_chart(country_name, continent_name)
    return fig_map_html, line_html, predict_html

def update_dashboard(country_name="全部", continent_name="全部", search_keyword=""):
    # 兼容旧函数
    news_html = update_news(country_name, continent_name, search_keyword)
    fig_map_html, line_html, predict_html = update_visualizations(country_name, continent_name)
    return fig_map_html, line_html, predict_html, news_html

def generate_report(country_name):
    if country_name == "全部": yield "请先选择具体国家。"
    else:
        code = next((k for k, v in COUNTRY_GEO_DATA.items() if v['name'] == country_name), None)
        reporter = RiskReporter()
        for chunk in reporter.generate_country_report(code, country_name=country_name): yield chunk

# 加载外部 HTML/CSS 模板
html_path = os.path.join(os.path.dirname(__file__), "index.html")
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        HTML_TEMPLATE = f.read()
else:
    HTML_TEMPLATE = ""

# Gradio 界面 (回归 Gradio 原生 Tabs 架构)
with gr.Blocks(title="全球地缘风险分析平台") as demo:
    with gr.Row(variant="compact"):
        with gr.Column(scale=4): 
            gr.Markdown("# 🌍 全球地缘政治风险分析平台")
        with gr.Column(scale=1): 
            continent_selector = gr.Dropdown(choices=["全部"] + list(CONTINENT_MAPPING.values()), value="全部", label="🗺️ 按洲筛选", container=True)
        with gr.Column(scale=1): 
            country_selector = gr.Dropdown(choices=get_dynamic_country_choices(), value="全部", label="🌐 国家筛选", container=True)

    with gr.Tabs():
        with gr.TabItem("🗺️ 全球风险指数动态"):
            map_plot = gr.HTML(label="风险动态演变")
            
        with gr.TabItem("📈 未来 5 日风险预测"):
            predict_plot = gr.HTML(label="风险预测模型")
            
        with gr.TabItem("📉 历史风险波动趋势"):
            trend_box = gr.HTML(label="30日波动趋势")

        with gr.TabItem("📰 实时新闻"):
            with gr.Row():
                search_box = gr.Textbox(placeholder="🔍 输入关键词搜索过去 3 天的新闻...", label=None, show_label=False, container=False, scale=4)
                search_btn = gr.Button("搜索", variant="secondary", scale=1)
            news_html_box = gr.HTML()

        with gr.TabItem("🤖 AI 研判报告"):
            with gr.Column(elem_id="ai-report-container"):
                gr.Markdown("### 🤖 区域投资风险 AI 深度研判")
                report_btn = gr.Button("🚀 立即生成研判报告", variant="primary")
                with gr.Column(elem_id="ai-report-scroll-area"):
                    report_box = gr.Markdown("请在顶部选择国家后点击生成按钮。", elem_id="ai-report-box")

    # 定义 outputs 列表，供下方所有更新函数使用
    outputs = [map_plot, trend_box, predict_plot, news_html_box]

    # 1. 定义快速更新 (仅新闻)
    def fast_news_update(country, continent, keyword):
        return update_news(country, continent, keyword)

    # 2. 定义全量更新 (仪表盘 + 新闻)
    def full_dashboard_update(country, continent, keyword):
        return update_dashboard(country, continent, keyword)

    # 洲级联动
    def on_geo_change(continent):
        new_choices = get_dynamic_country_choices(continent)
        return gr.update(choices=new_choices, value="全部")

    continent_selector.change(on_geo_change, inputs=[continent_selector], outputs=[country_selector])
    
    # 统一仪表盘更新
    dashboard_inputs = [country_selector, continent_selector, search_box]
    demo.load(full_dashboard_update, inputs=dashboard_inputs, outputs=outputs)
    
    # 交互更新：国家或洲改变时，刷新全量数据
    country_selector.change(full_dashboard_update, inputs=dashboard_inputs, outputs=outputs)
    continent_selector.change(full_dashboard_update, inputs=dashboard_inputs, outputs=outputs)
    
    # 性能优化：搜索和定时器仅刷新“实时新闻”列表
    news_only_output = [news_html_box]
    search_btn.click(fast_news_update, inputs=dashboard_inputs, outputs=news_only_output)
    search_box.submit(fast_news_update, inputs=dashboard_inputs, outputs=news_only_output)
    gr.Timer(60).tick(fast_news_update, inputs=dashboard_inputs, outputs=news_only_output)

    report_btn.click(generate_report, inputs=[country_selector], outputs=[report_box])

if __name__ == "__main__":
    custom_theme = gr.themes.Default(primary_hue=gr.themes.Color(c50="#e6f0ff", c100="#cce0ff", c200="#99c2ff", c300="#66a3ff", c400="#3385ff", c500="#1467DF", c600="#1158c4", c700="#0d469b", c800="#0a3673", c900="#07264a", c950="#04152b"))
    demo.launch(server_name="0.0.0.0", server_port=8090, theme=custom_theme, head=HTML_TEMPLATE)
