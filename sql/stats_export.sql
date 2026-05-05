-- 统计 Export 表（事件表）数据日期的分布情况
SELECT 
    to_date("Day"::text, 'YYYYMMDD') AS "数据日期",
    count(*) AS "事件数"
FROM export
WHERE "Day" IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;
