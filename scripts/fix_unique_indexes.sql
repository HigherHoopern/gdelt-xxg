-- 数据库索引修复脚本：将普通索引转换为唯一索引以支持 ON CONFLICT 操作
-- 适用数据库: PostgreSQL (dgelt)
-- 执行方式: docker exec -i gdelt_db psql -U zhenxian -d dgelt -f /app/scripts/fix_unique_indexes.sql

BEGIN;

-- 1. 修复 export 表
-- 必须先删除已存在的非唯一索引，否则创建唯一索引会冲突或导致 ON CONFLICT 匹配失败
DROP INDEX IF EXISTS "ix_export_GlobalEventID";
CREATE UNIQUE INDEX IF NOT EXISTS idx_export_global_unique ON export ("GlobalEventID");

-- 2. 修复 mentions 表
-- 删除旧的单列非唯一索引，创建复合唯一索引
DROP INDEX IF EXISTS "ix_mentions_GlobalEventID";
CREATE UNIQUE INDEX IF NOT EXISTS idx_mention_unique ON mentions ("GlobalEventID", "MentionIdentifier");

-- 3. 修复 gkg 表
-- 删除旧的非唯一索引，创建唯一索引
DROP INDEX IF EXISTS "ix_gkg_GKGRECORDID";
CREATE UNIQUE INDEX IF NOT EXISTS idx_gkg_record_unique ON gkg ("GKGRECORDID");

COMMIT;

-- 打印索引状态以供核查
SELECT indexname, indexdef FROM pg_indexes WHERE tablename IN ('export', 'mentions', 'gkg') AND indexname LIKE '%unique%';