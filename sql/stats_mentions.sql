-- 统计 Mentions 表（提及表）数据日期的分布情况
-- 将 YYYYMMDDHHMMSS 格式的 BigInt 截取前 8 位转为日期
SELECT 
    to_date(left("MentionTimeDate"::text, 8), 'YYYYMMDD') AS "数据日期",
    count(*) AS "提及数"
FROM mentions
WHERE "MentionTimeDate" IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;
