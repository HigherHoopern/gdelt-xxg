-- 统计 GKG 表（全球知识图谱表）数据日期的分布情况
-- 将 YYYYMMDDHHMMSS 格式的 BigInt 截取前 8 位转为日期
SELECT 
    to_date(left("DATE"::text, 8), 'YYYYMMDD') AS "数据日期",
    count(*) AS "记录数"
FROM gkg
WHERE "DATE" IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;
