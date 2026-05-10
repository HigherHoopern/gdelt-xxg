-- 数据库迁移脚本：清理重复数据并添加工业级唯一性约束
-- 适用数据库: PostgreSQL (dgelt)
-- 执行方式: psql -U zhenxian -d dgelt -f scripts/migrate_unique_constraints.sql

BEGIN;

-- 1. 清理 export 表重复项并增加唯一约束
-- 保留 id 最大的记录（通常是最新入库的），删除其余重复的 GlobalEventID
DELETE FROM export a 
USING export b 
WHERE a.id < b.id 
  AND a."GlobalEventID" = b."GlobalEventID";

ALTER TABLE export 
ADD CONSTRAINT unique_export_global_id UNIQUE ("GlobalEventID");

-- 2. 清理 gkg 表重复项并增加唯一约束
-- 保留 id 最大的记录，删除其余重复的 GKGRECORDID
DELETE FROM gkg a 
USING gkg b 
WHERE a.id < b.id 
  AND a."GKGRECORDID" = b."GKGRECORDID";

ALTER TABLE gkg 
ADD CONSTRAINT unique_gkg_record_id UNIQUE ("GKGRECORDID");

-- 3. 清理 mentions 表重复项并增加复合唯一索引
-- 基于 GlobalEventID 和 MentionIdentifier 的组合进行去重
DELETE FROM mentions a 
USING mentions b 
WHERE a.id < b.id 
  AND a."GlobalEventID" = b."GlobalEventID" 
  AND a."MentionIdentifier" = b."MentionIdentifier";

CREATE UNIQUE INDEX idx_mention_unique ON mentions ("GlobalEventID", "MentionIdentifier");

COMMIT;

-- 验证索引和约束是否生效
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'export'::regclass;
-- SELECT indexname FROM pg_indexes WHERE tablename = 'mentions';