-- 一键查看三张核心原始表的数据日期覆盖情况
WITH e_stats AS (
    SELECT to_date("Day"::text, 'YYYYMMDD') d, count(*) cnt FROM export GROUP BY 1
),
m_stats AS (
    SELECT to_date(left("MentionTimeDate"::text, 8), 'YYYYMMDD') d, count(*) cnt FROM mentions GROUP BY 1
),
g_stats AS (
    SELECT to_date(left("DATE"::text, 8), 'YYYYMMDD') d, count(*) cnt FROM gkg GROUP BY 1
)
SELECT 
    COALESCE(e.d, m.d, g.d) AS "数据日期",
    COALESCE(e.cnt, 0) AS "Export 事件",
    COALESCE(m.cnt, 0) AS "Mentions 提及",
    COALESCE(g.cnt, 0) AS "GKG 记录"
FROM e_stats e
FULL OUTER JOIN m_stats m ON e.d = m.d
FULL OUTER JOIN g_stats g ON COALESCE(e.d, m.d) = g.d
WHERE COALESCE(e.d, m.d, g.d) IS NOT NULL
ORDER BY 1 DESC;
