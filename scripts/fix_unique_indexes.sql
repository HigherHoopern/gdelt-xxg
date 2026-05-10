-- 数据库索引修复脚本：将普通索引转换为唯一索引以支持 ON CONFLICT 操作
-- 适用数据库: PostgreSQL (dgelt)
-- 执行方式: docker exec -i gdelt_db psql -U zhenxian -d dgelt -f /app/scripts/fix_unique_indexes.sql

BEGIN;

-- 1. 再次强制清理 export 表重复项（保留 ID 最大的）
DELETE FROM export a USING export b WHERE a.id < b.id AND a."GlobalEventID" = b."GlobalEventID";
DROP INDEX IF EXISTS "ix_export_GlobalEventID";
CREATE UNIQUE INDEX IF NOT EXISTS idx_export_global_unique ON export ("GlobalEventID");

-- 2. 再次强制清理 mentions 表重复项
DELETE FROM mentions a USING mentions b WHERE a.id < b.id AND a."GlobalEventID" = b."GlobalEventID" AND a."MentionIdentifier" = b."MentionIdentifier";
DROP INDEX IF EXISTS "ix_mentions_GlobalEventID";
CREATE UNIQUE INDEX IF NOT EXISTS idx_mention_unique ON mentions ("GlobalEventID", "MentionIdentifier");

-- 3. 再次强制清理 gkg 表重复项
DELETE FROM gkg a USING gkg b WHERE a.id < b.id AND a."GKGRECORDID" = b."GKGRECORDID";
DROP INDEX IF EXISTS "ix_gkg_GKGRECORDID";
CREATE UNIQUE INDEX IF NOT EXISTS idx_gkg_record_unique ON gkg ("GKGRECORDID");

COMMIT;

-- 打印索引状态以供核查
SELECT indexname, indexdef FROM pg_indexes WHERE tablename IN ('export', 'mentions', 'gkg') AND indexname LIKE '%unique%';