-- SaintVision PostgreSQL Initial Database Bootstrap
-- Creates application role with NOBYPASSRLS for row-level security (RLS) enforcement

CREATE ROLE inv_app WITH LOGIN PASSWORD 'apptestonly' NOBYPASSRLS;
GRANT ALL PRIVILEGES ON DATABASE saintvision TO inv_app;
GRANT ALL ON SCHEMA public TO inv_app;
