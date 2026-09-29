-- The record of a trusted worker's measurement of a model version's bytes
-- (G-04 W3 seam design v1.1 §4, PR #209). Kernel-owned and append-only: a row
-- is written only by the kernel's accept path after the node's signed
-- observation (node-model-measure-v1) has been verified against the channel,
-- the leaf certificate and the challenge; nothing rewrites or deletes it.
-- public.model_versions.verified_measurement_id (alembic 0054) points here, so
-- exactly which observation promoted a version is provable from the row.
CREATE TABLE inv.model_version_measurements (
  tenant_id uuid NOT NULL,
  measurement_id char(30) NOT NULL,
  request_id uuid NOT NULL,
  project_id char(30) NOT NULL,
  model_version_id char(30) NOT NULL,
  uri text NOT NULL CHECK (uri LIKE 'inv://models/%'),
  -- The single immutable DataLocation that was read (v1: exactly one).
  contribution_id char(30) NOT NULL,
  contribution_version bigint NOT NULL CHECK (contribution_version >= 1),
  location_id char(30) NOT NULL,
  location_version bigint NOT NULL CHECK (location_version >= 1),
  relative_path text NOT NULL CHECK (length(relative_path) BETWEEN 1 AND 4096),
  -- The channel binding at issue time, re-locked and matched at accept.
  node_id char(30) NOT NULL,
  recovery_epoch uuid NOT NULL,
  channel_version bigint NOT NULL CHECK (channel_version >= 1),
  certificate_sha256 text NOT NULL CHECK (certificate_sha256 ~ '^[0-9a-f]{64}$'),
  -- What the node actually saw.
  sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  byte_size bigint NOT NULL CHECK (byte_size >= 0),
  observed_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  challenge_sha256 text NOT NULL CHECK (challenge_sha256 ~ '^[0-9a-f]{64}$'),
  response_sha256 text NOT NULL CHECK (response_sha256 ~ '^[0-9a-f]{64}$'),
  duration_seconds double precision NOT NULL CHECK (duration_seconds >= 0),
  PRIMARY KEY (tenant_id, measurement_id),
  UNIQUE (tenant_id, request_id),
  CHECK (observed_at <= recorded_at)
);
-- No key back to public.model_versions: the binding is enforced from the
-- public side (0054's composite key and CHECK) and by the service matching
-- tenant, version and digest. The kernel checks that the version exists when
-- it issues the challenge, and a measurement nothing binds to is inert.
CREATE INDEX model_version_measurements_by_version
  ON inv.model_version_measurements (tenant_id, model_version_id, observed_at DESC);

ALTER TABLE inv.model_version_measurements ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.model_version_measurements FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.model_version_measurements
  USING (tenant_id = nullif(current_setting('inv.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('inv.tenant_id', true), '')::uuid);
REVOKE ALL ON inv.model_version_measurements FROM PUBLIC, inv_app, inv_kernel;
-- The kernel's accept path is the only writer. The application has no
-- privilege on this table and no access to this schema: it reads one
-- measurement at a time through the tenant-bound SECURITY DEFINER reader
-- public.model_version_measurement(text) that alembic 0054 creates.
GRANT SELECT, INSERT ON inv.model_version_measurements TO inv_kernel;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.model_version_measurements
  FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
