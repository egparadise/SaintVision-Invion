-- Candidate storage, outside automatic migrations pending a shared writer fence.
CREATE TABLE e1.reservations (
    tenant_id uuid NOT NULL,
    pc text NOT NULL CHECK (pc = 'PC1'),
    node_id text NOT NULL CHECK (node_id = 'nod_00000000000000000000000PC1'),
    request_id uuid NOT NULL,
    holder text NOT NULL,
    generation bigint NOT NULL CHECK (generation > 0),
    binding jsonb NOT NULL,
    digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (tenant_id, pc),
    UNIQUE (tenant_id, node_id),
    UNIQUE (tenant_id, request_id)
);
