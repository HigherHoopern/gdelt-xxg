# GDELT v2 数据表字段定义文档

本文档汇总了 GDELT v2 版本中三张核心数据表（Mentions, Export, GKG）的字段名称、索引位置及其含义说明。

---

## 1. Mentions 表 (提及表)
记录了哪些新闻报道提及了特定的事件。通常用于获取新闻 URL。
**文件后缀**: `.mentions.CSV.zip` | **列数**: 16

| 序号 | 字段名称 (Column Name) | 说明 |
| :--- | :--- | :--- |
| 1 | GlobalEventID | 全球事件 ID（关联 Export 表） |
| 2 | EventTimeDate | 该事件首次被发现的时间 (YYYYMMDDHHMMSS) |
| 3 | MentionTimeDate | 本次提及的时间 (YYYYMMDDHHMMSS) |
| 4 | MentionType | 来源类型 (1=Web, 2=Broadcast, 3=Print, 4=Television) |
| 5 | MentionSourceName | 来源媒体名称 (如 cnn.com) |
| 6 | MentionIdentifier | **来源标识符 (通常是新闻原始 URL)** |
| 7 | SentenceID | 事件在文中首次被提及的句子序号 |
| 8 | Actor1CharOffset | 角色 1 在文中的字符偏移量 |
| 9 | Actor2CharOffset | 角色 2 在文中的字符偏移量 |
| 10 | ActionCharOffset | 动作核心在文中的字符偏移量 |
| 11 | InRawText | 是否在正文中直接提及 (1=是) |
| 12 | Confidence | 置信度 (0-100) |
| 13 | MentionDocLen | 文章总长度（字符数） |
| 14 | MentionDocTone | 文章语气得分 (-100 到 100) |
| 15 | MentionDocTranslationInfo | 翻译元数据 |
| 16 | Extras | 扩展字段 |

---

## 2. Export 表 (Event 事件表)
记录事件的属性（谁、在哪、做了什么）。
**文件后缀**: `.export.CSV.zip` | **列数**: 61

### 2.1 标识与日期
*   **0: GLOBALEVENTID**: 唯一事件 ID。
*   **1: SQLDATE**: 事件发生日期 (YYYYMMDD)。
*   **2: MonthYear**: YYYYMM。
*   **3: Year**: YYYY。
*   **4: FractionDate**: 小数日期。

### 2.2 参与者属性 (Actor 1 & Actor 2)
*字段 5-14 为 Actor1，15-24 为 Actor2。*
*   **ActorCode**: CAMEO 代码。
*   **ActorName**: 名称。
*   **ActorCountryCode**: 国家代码 (3位)。
*   **ActorType1/2/3Code**: 身份代码 (如 GOV, MIL, COP)。

### 2.3 动作与影响力
*   **25: IsRootEvent**: 是否核心事件。
*   **26: EventCode**: 动作代码 (CAMEO)。
*   **29: QuadClass**: 四象限分类 (1=言论合作, 4=物质冲突等)。
*   **30: GoldsteinScale**: 影响力得分 (-10 到 +10)。
*   **31: NumMentions**: 总提及次数。
*   **34: AvgTone**: 平均语气得分。

### 2.4 地理信息 (Actor1Geo, Actor2Geo, ActionGeo)
*字段 35-42 (Actor1), 43-50 (Actor2), 51-58 (Action)。*
*   **Geo_Type**: 位置类型 (1=国家, 3=城市等)。
*   **Geo_FullName**: 地名全称。
*   **Geo_CountryCode**: 国家代码 (FIPS)。
*   **Geo_Lat / Geo_Long**: 经纬度坐标。

### 2.5 数据源
*   **60: SOURCEURL**: 该事件的首篇报道 URL。

---

## 3. GKG 表 (Global Knowledge Graph 全球知识图谱)
记录文章中的实体、主题、情绪等深度元数据。
**文件后缀**: `.gkg.csv.zip` | **列数**: 27

| 序号 | 字段名称 | 说明 |
| :--- | :--- | :--- |
| 1 | GKGRECORDID | 记录唯一 ID |
| 2 | DATE | 处理时间戳 |
| 3 | SourceCollectionIdentifier | 来源类型 (1=Web 等) |
| 4 | SourceCommonName | 媒体域名 |
| 5 | **DocumentIdentifier** | **新闻原文 URL** |
| 6 | Counts | 文中提到的数量统计 |
| 8 | Themes | **主题标签 (分号分隔)** |
| 10 | Locations | **文中提到的所有地理位置** |
| 12 | Persons | 文中提到的人物姓名 |
| 14 | Organizations | 文中提到的组织名称 |
| 16 | V2Tone | 7 个维度的情感分析得分 |
| 18 | GCAM | 深度内容分析指标 (数千个词典) |
| 19 | SharingImage | 文章主图 URL |
| 23 | Quotations | 文中的直接引语 |
| 26 | TranslationInfo | 翻译元数据 |

---
*注：带有 V2 前缀的字段（如 V2Themes, V2Locations）包含了实体在文中的字符偏移量位置。*
