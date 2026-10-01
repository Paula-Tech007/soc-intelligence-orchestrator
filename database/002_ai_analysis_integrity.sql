-- ==========================================================
-- SOC INTELLIGENCE ORCHESTRATOR
-- FASE 13.7.3
--
-- Persistencia de integridade das analises do WF-04.
--
-- Escopo inicial: LAB / MOCK.
-- Nao altera as seis tabelas existentes.
-- ==========================================================

BEGIN;

CREATE TABLE public.ai_analysis_integrity (

    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Identificacao da investigacao e do item processado.

    investigation_id UUID NOT NULL,

    investigation_version INTEGER NOT NULL,

    queue_id BIGINT NOT NULL,

    source_event_id TEXT NOT NULL,

    -- Identificacao do processamento da IA.

    model_id TEXT NOT NULL,

    execution_mode VARCHAR(32) NOT NULL
        DEFAULT 'MOCK_AI_RESPONSE',

    -- Assinaturas independentes.

    content_signature CHAR(64) NOT NULL,

    analysis_signature CHAR(64) NOT NULL,

    result_key CHAR(64) NOT NULL,

    -- Resultado estruturado e validado pelo Python.

    analysis_data JSONB NOT NULL,

    status VARCHAR(32) NOT NULL
        DEFAULT 'VALIDATED',

    -- Este registro nao autoriza operacoes automaticas.

    operational_dispatch_allowed BOOLEAN NOT NULL
        DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    -- Vinculo com a versao registrada da investigacao.

    CONSTRAINT fk_ai_integrity_version
        FOREIGN KEY (
            investigation_id,
            investigation_version
        )
        REFERENCES public.investigation_versions (
            investigation_id,
            version_number
        ),

    -- Vinculo com a fila de analise.

    CONSTRAINT fk_ai_integrity_queue
        FOREIGN KEY (queue_id)
        REFERENCES public.analysis_queue (id),

    -- Cada result_key deve existir somente uma vez.

    CONSTRAINT uq_ai_integrity_result_key
        UNIQUE (result_key),

    -- Uma mesma identidade logica nao pode registrar
    -- outra analise silenciosamente.

    CONSTRAINT uq_ai_integrity_logical_identity
        UNIQUE (
            investigation_id,
            investigation_version,
            model_id,
            execution_mode
        ),

    CONSTRAINT ck_ai_integrity_version
        CHECK (investigation_version >= 1),

    CONSTRAINT ck_ai_integrity_event
        CHECK (LENGTH(TRIM(source_event_id)) > 0),

    CONSTRAINT ck_ai_integrity_model
        CHECK (LENGTH(TRIM(model_id)) > 0),

    CONSTRAINT ck_ai_integrity_mode
        CHECK (
            execution_mode = 'MOCK_AI_RESPONSE'
        ),

    -- Validar o formato de cada SHA-256.

    CONSTRAINT ck_ai_integrity_content_signature
        CHECK (
            content_signature ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT ck_ai_integrity_analysis_signature
        CHECK (
            analysis_signature ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT ck_ai_integrity_result_key
        CHECK (
            result_key ~ '^[0-9a-f]{64}$'
        ),

    -- O conteudo deve ser um objeto JSON.

    CONSTRAINT ck_ai_integrity_analysis_json
        CHECK (
            jsonb_typeof(analysis_data) = 'object'
        ),

    CONSTRAINT ck_ai_integrity_status
        CHECK (
            status = 'VALIDATED'
        ),

    CONSTRAINT ck_ai_integrity_no_dispatch
        CHECK (
            operational_dispatch_allowed = FALSE
        )

);

-- Indice para consultas por fila.

CREATE INDEX idx_ai_integrity_queue
    ON public.ai_analysis_integrity (queue_id);

-- Indice para consultas e auditorias por investigacao.

CREATE INDEX idx_ai_integrity_investigation
    ON public.ai_analysis_integrity (
        investigation_id,
        created_at DESC
    );

COMMIT;
