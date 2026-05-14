import gradio as gr
import pandas as pd
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
    'AU': {'name': '澳大利亚', 'iso': 'AUS', 'continent': 'Oceania', 'lat': -25.2, 'lon': 133.7},
    # 额外补充 GDELT 常见代码
    'CH': {'name': '中国', 'iso': 'CHN', 'continent': 'Asia', 'lat': 35.8, 'lon': 104.1},
    'TW': {'name': '中国台湾', 'iso': 'TWN', 'continent': 'Asia', 'lat': 23.6, 'lon': 121.0},
    'HK': {'name': '中国香港', 'iso': 'HKG', 'continent': 'Asia', 'lat': 22.3, 'lon': 114.1},
    'KS': {'name': '韩国', 'iso': 'KOR', 'continent': 'Asia', 'lat': 35.9, 'lon': 127.7},
    'JA': {'name': '日本', 'iso': 'JPN', 'continent': 'Asia', 'lat': 36.2, 'lon': 138.2},
    'RS': {'name': '俄罗斯', 'iso': 'RUS', 'continent': 'Europe', 'lat': 61.5, 'lon': 105.3},
    'UK': {'name': '英国', 'iso': 'GBR', 'continent': 'Europe', 'lat': 55.3, 'lon': -3.4},
    'GM': {'name': '德国', 'iso': 'DEU', 'continent': 'Europe', 'lat': 51.1, 'lon': 10.4},
    'FR': {'name': '法国', 'iso': 'FRA', 'continent': 'Europe', 'lat': 46.2, 'lon': 2.2},
    'IT': {'name': '意大利', 'iso': 'ITA', 'continent': 'Europe', 'lat': 41.8, 'lon': 12.5},
    'SP': {'name': '西班牙', 'iso': 'ESP', 'continent': 'Europe', 'lat': 40.4, 'lon': -3.7},
    'CA': {'name': '加拿大', 'iso': 'CAN', 'continent': 'North America', 'lat': 56.1, 'lon': -106.3},
    'MX': {'name': '墨西哥', 'iso': 'MEX', 'continent': 'North America', 'lat': 23.6, 'lon': -102.5},
    'SF': {'name': '南非', 'iso': 'ZAF', 'continent': 'Africa', 'lat': -30.5, 'lon': 22.9},
    'SG': {'name': '塞内加尔', 'iso': 'SEN', 'continent': 'Africa', 'lat': 14.5, 'lon': -14.4},
    'NI': {'name': '尼日利亚', 'iso': 'NGA', 'continent': 'Africa', 'lat': 9.1, 'lon': 8.7},
    'IZ': {'name': '伊拉克', 'iso': 'IRQ', 'continent': 'Middle East', 'lat': 33.2, 'lon': 43.6},
    'IR': {'name': '伊朗', 'iso': 'IRN', 'continent': 'Middle East', 'lat': 32.4, 'lon': 53.6},
    'TU': {'name': '土耳其', 'iso': 'TUR', 'continent': 'Middle East', 'lat': 38.9, 'lon': 35.2},
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
        # 针对 pyecharts 的增强包装，确保在 Base64 环境下也能正确加载地图
        inner_html = chart_obj.render_embed()
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script type="text/javascript" src="https://assets.pyecharts.org/assets/echarts.min.js"></script>
            <script type="text/javascript" src="https://assets.pyecharts.org/assets/maps/world.js"></script>
            <style>
                body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background-color: transparent; }}
                /* 隐藏 pyecharts 默认生成的容器边距 */
                .chart-container {{ margin: 0 !important; border: none !important; }}
            </style>
        </head>
        <body>
            {inner_html}
        </body>
        </html>
        """
    b64_html = base64.b64encode(full_html.encode('utf-8')).decode('utf-8')
    return f'<iframe src="data:text/html;base64,{b64_html}" width="100%" height="{height}" frameborder="0" style="border-radius:12px; background:white; border:none;"></iframe>'

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

# PyEcharts 世界地图国家名称映射 (用于显示中文)
WORLD_NAME_MAP = {
    "Afghanistan": "阿富汗", "Angola": "安哥拉", "Albania": "阿尔巴尼亚", "United Arab Emirates": "阿联酋", "Argentina": "阿根廷",
    "Armenia": "亚美尼亚", "Australia": "澳大利亚", "Austria": "奥地利", "Azerbaijan": "亚塞拜然", "Burundi": "布隆迪",
    "Belgium": "比利时", "Benin": "贝宁", "Burkina Faso": "布基纳法索", "Bangladesh": "孟加拉国", "Bulgaria": "保加利亚",
    "Bahamas": "巴哈马", "Bosnia and Herz.": "波斯尼亚和黑塞哥维那", "Belarus": "白俄罗斯", "Belize": "伯利兹", "Bermuda": "百慕大",
    "Bolivia": "玻利维亚", "Brazil": "巴西", "Brunei": "文莱", "Bhutan": "不丹", "Botswana": "博茨瓦纳",
    "Central African Rep.": "中非共和国", "Canada": "加拿大", "Switzerland": "瑞士", "Chile": "智利", "China": "中国",
    "Ivory Coast": "科特迪瓦", "Cameroon": "喀麦隆", "Dem. Rep. Congo": "刚果民主共和国", "Congo": "刚果共和国", "Colombia": "哥伦比亚",
    "Costa Rica": "哥斯达黎加", "Cuba": "古巴", "Northern Cyprus": "北塞浦路斯", "Cyprus": "塞浦路斯", "Czech Rep.": "捷克",
    "Germany": "德国", "Djibouti": "吉布提", "Denmark": "丹麦", "Dominican Rep.": "多米尼加共和国", "Algeria": "阿尔及利亚",
    "Ecuador": "厄瓜多尔", "Egypt": "埃及", "Eritrea": "厄立特里亚", "Spain": "西班牙", "Estonia": "爱沙尼亚",
    "Ethiopia": "埃塞俄比亚", "Finland": "芬兰", "Fiji": "斐济", "France": "法国", "Gabon": "加蓬",
    "United Kingdom": "英国", "Georgia": "格鲁吉亚", "Ghana": "加纳", "Guinea": "几内亚", "Gambia": "冈比亚",
    "Guinea-Bissau": "几内亚比绍", "Eq. Guinea": "赤道几内亚", "Greece": "希腊", "Greenland": "格陵兰", "Guatemala": "危地马拉",
    "Guyana": "圭亚那", "Honduras": "洪都拉斯", "Croatia": "克罗地亚", "Haiti": "海地", "Hungary": "匈牙利",
    "Indonesia": "印度尼西亚", "India": "印度", "Ireland": "爱尔兰", "Iran": "伊朗", "Iraq": "伊拉克",
    "Iceland": "冰岛", "Israel": "以色列", "Italy": "意大利", "Jamaica": "牙买加", "Jordan": "约旦",
    "Japan": "日本", "Kazakhstan": "哈萨克斯坦", "Kenya": "肯尼亚", "Kyrgyzstan": "吉尔吉斯斯坦", "Cambodia": "柬埔寨",
    "South Korea": "韩国", "Kuwait": "科威特", "Laos": "老挝", "Lebanon": "黎巴嫩", "Liberia": "利比里亚",
    "Libya": "利比亚", "Sri Lanka": "斯里兰卡", "Lesotho": "莱索托", "Lithuania": "立陶宛", "Luxembourg": "卢森堡",
    "Latvia": "拉脱维亚", "Morocco": "摩洛哥", "Moldova": "摩尔多瓦", "Madagascar": "马达加斯加", "Mexico": "墨西哥",
    "Macedonia": "马其顿", "Mali": "马里", "Myanmar": "缅甸", "Montenegro": "黑山", "Mongolia": "蒙古",
    "Mozambique": "莫桑比克", "Mauritania": "毛里塔尼亚", "Malawi": "马拉维", "Malaysia": "马来西亚", "Namibia": "纳米比亚",
    "New Caledonia": "新喀里多尼亚", "Niger": "尼日尔", "Nigeria": "尼日利亚", "Nicaragua": "尼加拉瓜", "Netherlands": "荷兰",
    "Norway": "挪威", "Nepal": "尼泊尔", "New Zealand": "新西兰", "Oman": "阿曼", "Pakistan": "巴基斯坦",
    "Panama": "巴拿马", "Peru": "秘鲁", "Philippines": "菲律宾", "Papua New Guinea": "巴布亚新几内亚", "Poland": "波兰",
    "Puerto Rico": "波多黎各", "North Korea": "朝鲜", "Portugal": "葡萄牙", "Paraguay": "巴拉圭", "Qatar": "卡塔尔",
    "Romania": "罗马尼亚", "Russia": "俄罗斯", "Rwanda": "卢旺达", "W. Sahara": "西撒哈拉", "Saudi Arabia": "沙特阿拉伯",
    "Sudan": "苏丹", "S. Sudan": "南苏丹", "Senegal": "塞内加尔", "Solomon Is.": "所罗门群岛", "Sierra Leone": "塞拉利昂",
    "El Salvador": "萨尔瓦多", "Somaliland": "索马里兰", "Somalia": "索马里", "Serbia": "塞尔维亚", "Suriname": "苏里南",
    "Slovakia": "斯洛伐克", "Slovenia": "斯洛文尼亚", "Sweden": "瑞典", "Swaziland": "斯威士兰", "Syria": "叙利亚",
    "Chad": "乍得", "Togo": "多哥", "Thailand": "泰国", "Tajikistan": "塔吉克斯坦", "Turkmenistan": "土库曼斯坦",
    "East Timor": "东帝汶", "Trinidad and Tobago": "特立尼达和多巴哥", "Tunisia": "突尼斯", "Turkey": "土耳其", "Tanzania": "坦桑尼亚",
    "Uganda": "乌干达", "Ukraine": "乌克兰", "Uruguay": "乌拉圭", "United States": "美国", "Uzbekistan": "乌兹别克斯坦",
    "Venezuela": "委内瑞拉", "Vietnam": "越南", "Vanuatu": "瓦努阿图", "Palestine": "巴勒斯坦", "Yemen": "也门",
    "South Africa": "南非", "Zambia": "赞比亚", "Zimbabwe": "津巴布韦"
}

# 内部 FIPS 到 PyEcharts 英文名映射
FIPS_TO_ECHART_NAME = {
    'BX': 'Brunei', 'CB': 'Cambodia', 'ID': 'Indonesia', 'LA': 'Laos', 'MY': 'Malaysia', 'BM': 'Myanmar', 
    'RP': 'Philippines', 'SN': 'Singapore', 'TH': 'Thailand', 'VM': 'Vietnam', 'TT': 'East Timor',
    'IN': 'India', 'PK': 'Pakistan', 'BG': 'Bangladesh', 'CE': 'Sri Lanka', 'NP': 'Nepal', 'BT': 'Bhutan',
    'IR': 'Iran', 'IZ': 'Iraq', 'SA': 'Saudi Arabia', 'IS': 'Israel', 'TU': 'Turkey', 'EG': 'Egypt', 
    'AE': 'United Arab Emirates', 'QA': 'Qatar', 'SY': 'Syria', 'JO': 'Jordan', 'LE': 'Lebanon',
    'US': 'United States', 'CH': 'China', 'RU': 'Russia', 'GB': 'United Kingdom', 'FR': 'France', 
    'DE': 'Germany', 'JP': 'Japan', 'KR': 'South Korea', 'BR': 'Brazil', 'AU': 'Australia'
}

def render_map(country_name="全部", continent_name="全部"):
    raw_df = fetch_history_data_unified()
    
    # 统一使用与数据对齐的 8 小时偏移逻辑构造日期轴
    now_local = datetime.datetime.now() + datetime.timedelta(hours=8)
    all_dates = [(now_local - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(31)]
    all_dates = sorted(list(set(all_dates)))
    
    if raw_df.empty: return "<div style='height:850px; display:flex; align-items:center; justify-content:center;'>暂无风险数据</div>"
    
    from pyecharts.charts import Map, Timeline
    timeline = Timeline(init_opts=opts.InitOpts(width="100%", height="850px"))
    
    for date_str in all_dates:
        day_df = raw_df[raw_df['date_str'] == date_str]
        map_data = []
        for _, row in day_df.iterrows():
            echart_name = FIPS_TO_ECHART_NAME.get(row['country_code'])
            if echart_name:
                map_data.append((echart_name, round(float(row['risk_index']), 2)))
        
        m = Map()
        # 确保 map_data 永远不为空，避开 pyecharts 内部对 data_pair[0] 的访问导致的 IndexError
        safe_map_data = map_data if map_data else [("China", None)]
        
        m.add(
            "风险指数",
            safe_map_data,
            maptype="world",
            is_map_symbol_show=False,
            name_map=WORLD_NAME_MAP,
            label_opts=opts.LabelOpts(is_show=False),
        )

        m.set_global_opts(
            title_opts=opts.TitleOpts(title=f"全球风险动态演变 ({date_str})", pos_left="center", pos_top="10px"),
            visualmap_opts=opts.VisualMapOpts(
                min_=0, max_=100,
                range_color=["#2ECC71", "#F1C40F", "#E74C3C"],
                is_piecewise=False,
                pos_left="30px", pos_bottom="30px"
            ),
        )
        timeline.add(m, date_str)
        
    timeline.add_schema(is_auto_play=True, play_interval=1000, pos_bottom="20px")
    return wrap_in_iframe(timeline, height="850px")

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

def update_news(country_name="全部", continent_name="全部", search_keyword="", start_date=None, end_date=None):
    logger.info(f"📰 更新实时新闻: {country_name}, {continent_name}, 关键词: {search_keyword}, 日期: {start_date} ~ {end_date}")
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

    # 关键词过滤
    search_clause = ""
    if search_keyword and search_keyword.strip():
        search_clause = "AND (title_zh ILIKE :kw OR summary_zh ILIKE :kw OR title ILIKE :kw)"
        params["kw"] = f"%{search_keyword}%"

    # 日期范围过滤
    date_clause = ""
    if start_date:
        date_clause += " AND event_date >= :start"
        params["start"] = start_date
    if end_date:
        date_clause += " AND event_date <= :end"
        params["end"] = end_date

    query_news = text(f"SELECT event_date, country_code, category, title, title_zh, summary_zh, url, image_url FROM risk_analysis_data WHERE {valid_filter} {geo_clause} {search_clause} {date_clause} ORDER BY event_date DESC LIMIT 50")
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

def update_visualizations(country_name, continent_name):
    logger.info(f"📊 更新图表可视化: {country_name}, {continent_name}")
    fig_map_html = render_map(country_name, continent_name)
    line_html = render_line(country_name, continent_name)
    predict_html = render_prediction_chart(country_name, continent_name)
    return fig_map_html, predict_html, line_html

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

    with gr.Tabs() as tabs:
        with gr.TabItem("🗺️ 风险动态地图", id="map_tab"):
            map_plot = gr.HTML()
        
        with gr.TabItem("📈 风险分析与预测", id="analysis_tab"):
            predict_plot = gr.HTML()
            trend_box = gr.HTML()

        with gr.TabItem("📰 实时新闻", id="news_tab"):
            with gr.Row():
                search_input = gr.Textbox(label="🔍 关键词搜索", placeholder="输入关键词...")
                start_date_input = gr.DateTime(label="📅 开始日期", type="datetime")
                end_date_input = gr.DateTime(label="📅 结束日期", type="datetime")
            news_html_box = gr.HTML()

        with gr.TabItem("🤖 AI 研判报告", id="report_tab"):
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

    # 核心优化：按需刷新逻辑
    # 1. 只有地图 Tab 选中时刷新地图
    # 2. 只有分析 Tab 选中时刷新预测和趋势图
    # 3. 只有新闻 Tab 选中时刷新新闻列表
    
    vis_inputs = [country_selector, continent_selector]
    news_inputs = [country_selector, continent_selector, search_input, start_date_input, end_date_input]

    # 初始化加载
    demo.load(render_map, inputs=vis_inputs, outputs=map_plot)
    demo.load(render_prediction_chart, inputs=vis_inputs, outputs=predict_plot)
    demo.load(render_line, inputs=vis_inputs, outputs=trend_box)
    demo.load(update_news, inputs=news_inputs, outputs=news_html_box)

    # 联动更新 (仅更新当前可能可见的内容)
    # 地图和分析图表共享输入
    country_selector.change(render_map, inputs=vis_inputs, outputs=map_plot)
    country_selector.change(render_prediction_chart, inputs=vis_inputs, outputs=predict_plot)
    country_selector.change(render_line, inputs=vis_inputs, outputs=trend_box)
    country_selector.change(update_news, inputs=news_inputs, outputs=news_html_box)

    continent_selector.change(render_map, inputs=vis_inputs, outputs=map_plot)
    continent_selector.change(render_prediction_chart, inputs=vis_inputs, outputs=predict_plot)
    continent_selector.change(render_line, inputs=vis_inputs, outputs=trend_box)
    continent_selector.change(update_news, inputs=news_inputs, outputs=news_html_box)

    # 新闻专属更新
    search_input.submit(update_news, inputs=news_inputs, outputs=news_html_box)
    start_date_input.change(update_news, inputs=news_inputs, outputs=news_html_box)
    end_date_input.change(update_news, inputs=news_inputs, outputs=news_html_box)
    
    # 计时器仅刷新新闻（相对轻量）
    gr.Timer(60).tick(update_news, inputs=news_inputs, outputs=news_html_box)
    
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
