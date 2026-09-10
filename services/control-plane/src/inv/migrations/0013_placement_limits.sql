-- Canonical project reservation ceiling, independent of descriptive pool CRUD.
CREATE TABLE inv.project_resource_limits (
 tenant_id uuid NOT NULL, project_id text NOT NULL,
 cpu_millis bigint NOT NULL CHECK(cpu_millis BETWEEN 0 AND 9007199254740991),
 memory_bytes bigint NOT NULL CHECK(memory_bytes BETWEEN 0 AND 9007199254740991),
 version bigint NOT NULL DEFAULT 1 CHECK(version>0),
 PRIMARY KEY(tenant_id,project_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES inv.projects(tenant_id,project_id)
);
ALTER TABLE inv.project_resource_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.project_resource_limits FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.project_resource_limits
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE FUNCTION inv.guard_project_limits() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE cpu numeric; memory numeric;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'resource ceilings cannot be removed' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  -- Serializes first provisioning against reservations that see no ceiling yet.
  PERFORM project_id FROM inv.projects WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id FOR NO KEY UPDATE;
  IF NEW.version<>1 THEN RAISE EXCEPTION 'ceiling begins at version one' USING ERRCODE='23514'; END IF;
 ELSE
  -- UPDATE already owns the ceiling row used by every reservation. It must not
  -- acquire the earlier project mutex and invert that lock order.
  IF (NEW.tenant_id,NEW.project_id) IS DISTINCT FROM (OLD.tenant_id,OLD.project_id) OR NEW.version<>OLD.version+1 THEN
   RAISE EXCEPTION 'immutable ceiling identity or stale version' USING ERRCODE='23514';
  END IF;
 END IF;
 SELECT coalesce(sum(l.amount) FILTER(WHERE r.kind='cpu'),0),coalesce(sum(l.amount) FILTER(WHERE r.kind='memory'),0)
 INTO cpu,memory FROM inv.resource_leases l JOIN inv.resources r USING(tenant_id,resource_id)
 WHERE l.tenant_id=NEW.tenant_id AND l.project_id=NEW.project_id AND l.released_at IS NULL;
 IF cpu>NEW.cpu_millis OR memory>NEW.memory_bytes THEN
  RAISE EXCEPTION 'ceiling cannot undercut reserved resources' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER project_limits_guard BEFORE INSERT OR UPDATE OR DELETE ON inv.project_resource_limits
 FOR EACH ROW EXECUTE FUNCTION inv.guard_project_limits();
REVOKE ALL ON FUNCTION inv.guard_project_limits() FROM PUBLIC;
