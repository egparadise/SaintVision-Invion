-- Binary content stays outside PostgreSQL. Limits belong to the local pilot
-- provider; the S3 50 GiB/presigned adapter has not been selected or deployed.
CREATE TABLE inv.storage_budgets (
 tenant_id uuid NOT NULL, project_id text NOT NULL,
 quota_bytes bigint NOT NULL CHECK(quota_bytes>=0),
 PRIMARY KEY(tenant_id,project_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES inv.projects(tenant_id,project_id)
);
CREATE TABLE inv.storage_objects (
 tenant_id uuid NOT NULL, project_id text NOT NULL, object_id uuid NOT NULL,
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 size_bytes bigint NOT NULL CHECK(size_bytes BETWEEN 0 AND 67108864),
 state text NOT NULL DEFAULT 'uploading' CHECK(state IN ('uploading','ready','deleting','deleted')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,project_id,object_id), UNIQUE(object_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES inv.storage_budgets(tenant_id,project_id)
);
CREATE TABLE inv.storage_parts (
 tenant_id uuid NOT NULL, project_id text NOT NULL, object_id uuid NOT NULL,
 part_index integer NOT NULL CHECK(part_index BETWEEN 0 AND 3),
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 size_bytes integer NOT NULL CHECK(size_bytes BETWEEN 1 AND 16777216),
 PRIMARY KEY(tenant_id,project_id,object_id,part_index),
 FOREIGN KEY(tenant_id,project_id,object_id) REFERENCES inv.storage_objects(tenant_id,project_id,object_id)
);
CREATE TABLE inv.checkpoint_objects (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 attempt integer NOT NULL, step_id text NOT NULL, object_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,run_id,attempt,step_id),
 FOREIGN KEY(tenant_id,run_id,attempt,step_id) REFERENCES inv.checkpoints(tenant_id,run_id,attempt,step_id),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 FOREIGN KEY(tenant_id,project_id,object_id) REFERENCES inv.storage_objects(tenant_id,project_id,object_id)
);
DO $body$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['storage_budgets','storage_objects','storage_parts','checkpoint_objects'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
 END LOOP;
END; $body$;
CREATE TRIGGER storage_parts_immutable BEFORE UPDATE OR DELETE ON inv.storage_parts FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE TRIGGER checkpoint_objects_immutable BEFORE UPDATE OR DELETE ON inv.checkpoint_objects FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE FUNCTION inv.guard_storage_object() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'uploading' THEN RAISE EXCEPTION 'objects begin uploading' USING ERRCODE='23514'; END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='DELETE' OR (NEW.tenant_id,NEW.project_id,NEW.object_id,NEW.content_hash,NEW.size_bytes,NEW.created_at)
 IS DISTINCT FROM (OLD.tenant_id,OLD.project_id,OLD.object_id,OLD.content_hash,OLD.size_bytes,OLD.created_at)
 OR NOT (NEW.state=OLD.state OR (OLD.state='uploading' AND NEW.state IN ('ready','deleting'))
 OR (OLD.state='ready' AND NEW.state='deleting') OR (OLD.state='deleting' AND NEW.state='deleted')) THEN
  RAISE EXCEPTION 'immutable object identity or invalid progress' USING ERRCODE='23514';
 END IF;
 IF NEW.state IN ('deleting','deleted') AND EXISTS(SELECT 1 FROM inv.checkpoint_objects WHERE tenant_id=NEW.tenant_id AND object_id=NEW.object_id) THEN
  RAISE EXCEPTION 'checkpoint pins object' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER storage_object_guard BEFORE INSERT OR UPDATE OR DELETE ON inv.storage_objects FOR EACH ROW EXECUTE FUNCTION inv.guard_storage_object();
REVOKE ALL ON FUNCTION inv.guard_storage_object() FROM PUBLIC;
CREATE FUNCTION inv.guard_checkpoint_object() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE current_state text;
BEGIN
 SELECT state INTO current_state FROM inv.storage_objects WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id AND object_id=NEW.object_id FOR UPDATE;
 IF current_state IS DISTINCT FROM 'ready' THEN RAISE EXCEPTION 'pin requires ready object' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER checkpoint_object_guard BEFORE INSERT ON inv.checkpoint_objects FOR EACH ROW EXECUTE FUNCTION inv.guard_checkpoint_object();
REVOKE ALL ON FUNCTION inv.guard_checkpoint_object() FROM PUBLIC;
