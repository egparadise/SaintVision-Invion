-- Persist the immutable byte provider and its provider-native opaque locator.
-- Existing bounded-local rows retain the exact historical object key so their
-- checkpoint provider/content digest remains unchanged.
ALTER TABLE inv.storage_objects
  ADD COLUMN provider_id text,
  ADD COLUMN locator text;

UPDATE inv.storage_objects
SET provider_id = 'local-bounded-v1',
    locator = 'obj-' || replace(object_id::text, '-', '');

ALTER TABLE inv.storage_objects
  ALTER COLUMN provider_id SET NOT NULL,
  ALTER COLUMN locator SET NOT NULL,
  ADD CONSTRAINT ck_storage_objects_provider_id
    CHECK (provider_id ~ '^[a-z0-9][a-z0-9.-]{0,63}$'),
  ADD CONSTRAINT ck_storage_objects_locator
    CHECK (length(locator) BETWEEN 1 AND 1024 AND locator !~ E'[\r\n]'),
  ADD CONSTRAINT uq_storage_objects_provider_locator UNIQUE(provider_id, locator);

CREATE OR REPLACE FUNCTION inv.guard_storage_object() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'uploading' THEN RAISE EXCEPTION 'objects begin uploading' USING ERRCODE='23514'; END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='DELETE' OR
 (NEW.tenant_id,NEW.project_id,NEW.object_id,NEW.provider_id,NEW.locator,
  NEW.content_hash,NEW.size_bytes,NEW.created_at)
 IS DISTINCT FROM
 (OLD.tenant_id,OLD.project_id,OLD.object_id,OLD.provider_id,OLD.locator,
  OLD.content_hash,OLD.size_bytes,OLD.created_at)
 OR NOT (NEW.state=OLD.state OR (OLD.state='uploading' AND NEW.state IN ('ready','deleting'))
 OR (OLD.state='ready' AND NEW.state='deleting') OR (OLD.state='deleting' AND NEW.state='deleted')) THEN
  RAISE EXCEPTION 'immutable object identity or invalid progress' USING ERRCODE='23514';
 END IF;
 IF NEW.state IN ('deleting','deleted') AND EXISTS(SELECT 1 FROM inv.checkpoint_objects WHERE tenant_id=NEW.tenant_id AND object_id=NEW.object_id) THEN
  RAISE EXCEPTION 'checkpoint pins object' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
REVOKE ALL ON FUNCTION inv.guard_storage_object() FROM PUBLIC;
