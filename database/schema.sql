-- =========================================================
-- SOC INTELLIGENCE ORCHESTRATOR
-- DATABASE SCHEMA V1
-- Ambiente: LAB
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 1. INVESTIGACOES
-- Identidade estavel do evento e estado mais recente.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS investigations (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    source VARCHAR(100) NOT NULL,

    source_event_id VARCHAR(255) NOT NULL,

    event_type VARCHAR(150) NOT NULL,

    current_signature TEXT NOT NULL,

    latest_event JSONB NOT NULL,

    investigation_version INTEGER NOT NULL DEFAULT 1
        CHECK (investigation_version >= 1),

    occurrence_count INTEGER NOT NULL DEFAULT 1
        CHECK (occurrence_count >= 1),

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_investigation_identity
        UNIQUE (source, source_event_id, event_type)
);

-- ---------------------------------------------------------
-- 2. VERSOES DAS INVESTIGACOES
-- Preserva o historico das mudancas materiais.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS investigation_versions (

    id BIGSERIAL PRIMARY KEY,

    investigation_id UUID NOT NULL
        REFERENCES investigations(id),

    version_number INTEGER NOT NULL
        CHECK (version_number >= 1),

    content_signature TEXT NOT NULL,

    normalized_event JSONB NOT NULL,

    changed_fields JSONB NOT NULL DEFAULT '[]'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_investigation_version
        UNIQUE (investigation_id, version_number),

    CONSTRAINT uq_investigation_signature
        UNIQUE (investigation_id, content_signature)
);

-- ---------------------------------------------------------
-- 3. EVIDENCIAS
-- Cada evidencia possui identificador por investigacao.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS evidences (

    id BIGSERIAL PRIMARY KEY,

    investigation_id UUID NOT NULL
        REFERENCES investigations(id),

    evidence_id VARCHAR(255) NOT NULL,

    evidence_data JSONB NOT NULL,

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_investigation_evidence
        UNIQUE (investigation_id, evidence_id)
);

-- ---------------------------------------------------------
-- 4. OCORRENCIAS RECEBIDAS
-- Permite registrar repeticoes e auditoria de ingestao.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS event_occurrences (

    id BIGSERIAL PRIMARY KEY,

    investigation_id UUID NOT NULL
        REFERENCES investigations(id),

    collection_id VARCHAR(255) NOT NULL,

    collection_sequence INTEGER NOT NULL,

    content_signature TEXT NOT NULL,

    classification VARCHAR(30) NOT NULL
        CHECK (
            classification IN (
                'NEW_EVENT',
                'EXACT_REPEAT',
                'MATERIAL_UPDATE'
            )
        ),

    ingested_at TIMESTAMPTZ NOT NULL,

    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_collection_occurrence
        UNIQUE (collection_id, collection_sequence)
);

-- ---------------------------------------------------------
-- 5. FILA DE ANALISE
-- Impede criar duas tarefas para a mesma versao.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS analysis_queue (

    id BIGSERIAL PRIMARY KEY,

    investigation_id UUID NOT NULL
        REFERENCES investigations(id),

    investigation_version INTEGER NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (
            status IN (
                'PENDING',
                'PROCESSING',
                'COMPLETED',
                'FAILED',
                'CANCELLED'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_analysis_version
        UNIQUE (
            investigation_id,
            investigation_version
        )
);

-- ---------------------------------------------------------
-- 6. AUDITORIA
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_log (

    id BIGSERIAL PRIMARY KEY,

    investigation_id UUID
        REFERENCES investigations(id),

    workflow_name VARCHAR(100) NOT NULL,

    action VARCHAR(150) NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- INDICES
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_investigations_last_seen
    ON investigations(last_seen_at);

CREATE INDEX IF NOT EXISTS idx_occurrences_investigation
    ON event_occurrences(investigation_id);

CREATE INDEX IF NOT EXISTS idx_queue_status
    ON analysis_queue(status, created_at);

CREATE INDEX IF NOT EXISTS idx_audit_investigation
    ON audit_log(investigation_id, created_at);

COMMIT;