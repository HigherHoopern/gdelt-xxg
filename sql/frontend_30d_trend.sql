-- 查询与前端 30 天走势图一致的聚合数据 (北京时间)
SELECT 
    country_code AS "国家代码",
    date_trunc('day', calculation_date + INTERVAL '8 hours') AS "北京日期",
    ROUND(AVG(risk_index)::numeric, 2) AS "日均风险指数"
FROM risk_index_history
WHERE calculation_date >= NOW() - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 2 DESC, 1 ASC;
