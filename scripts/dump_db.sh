#!/bin/bash

# 数据库迁移脚本 - 导出部分
# 确保在本地运行此脚本以生成数据快照

DB_NAME="dgelt"
DB_USER="zhenxian"
DUMP_FILE="gdelt_data_backup_$(date +%Y%m%d).sql"

echo "🚀 正在导出数据库: $DB_NAME ..."

# 导出完整的数据库结构和数据
# 注意：这包含了 risk_analysis_data, risk_index_history 等所有核心表
pg_dump -U $DB_USER -d $DB_NAME > $DUMP_FILE

if [ $? -eq 0 ]; then
    echo "✅ 导出成功: $DUMP_FILE"
    echo "📦 正在压缩文件以减小体积..."
    gzip $DUMP_FILE
    echo "🎯 最终文件: ${DUMP_FILE}.gz"
    echo ""
    echo "💡 迁移建议："
    echo "1. 使用 git push 将代码推送到 GitHub。"
    echo "2. 使用 scp 或 rsync 将 ${DUMP_FILE}.gz 传输到远程服务器。"
    echo "3. 在远程服务器运行：gunzip -c ${DUMP_FILE}.gz | psql -U <username> -d <dbname>"
else
    echo "❌ 导出失败，请检查数据库权限和名称。"
fi
