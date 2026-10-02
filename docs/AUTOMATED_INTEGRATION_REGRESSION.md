# Automated Integration Regression - Stage 12

## Objective

Provide reproducible regression coverage for the integrated
SOC Intelligence Orchestrator pipeline.

Two independent execution modes are available:

1. Fully offline integration regression.
2. Optional authenticated local regression using PostgreSQL LAB.

Only synthetic SOC-LAB events are used.

## Components

- src/context/integrated_mock_pipeline.py
- tests/test_integrated_mock_regression.py
- tests/local_integrated_regression.py
- scripts/run-local-integrated-regression.ps1

## Integrated pipeline

```text
Authenticated HTTP Client / simulated HTTP response
                 |
                 v
          Context Decision Gate
                 |
                 v
           AI Review Adapter
                 |
                 v
       AI Review Orchestrator MOCK
                 |
                 v
        AnalysisCache + WF-04
                 |
                 v
         Integrity Verification
```

## Mode 1 - Offline

The HTTP response is simulated using the existing synthetic
WF-03 context snapshots.

The Gate, adapter, MOCK AI engine, cache and integrity
components are executed normally.

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover `
    -s tests `
    -p "test_integrated_mock_regression.py" `
    -v
```

Nine offline integrated tests were approved.

The targeted consolidated regression covers eight suites,
with 75 expected tests.

No PostgreSQL server, FastAPI process or real token is needed.

## Mode 2 - Optional Local Integration

This mode queries the synthetic PostgreSQL LAB through the
authenticated FastAPI bridge bound to 127.0.0.1:8765.

Terminal 1:

```powershell
.\scripts\start-local-bridge.ps1
```

Terminal 2:

```powershell
.\scripts\run-local-integrated-regression.ps1
```

The runner retrieves the HTTP token from the local DPAPI
protected file and removes its temporary environment
variable when execution finishes.

One integrated local test was approved.

### Verified scenarios

Queue 12:

- Gate: HISTORICAL_CONTEXT.
- Review: HISTORICAL_SKIPPED.
- No model invocation.
- No integrity record generated.

Queue 13:

- Gate: READY_FOR_AI_REVIEW.
- Review: MOCK_ANALYSIS_COMPLETED.
- Integrity: VERIFIED_IN_MEMORY.
- Second execution: cache hit.
- Integrity signatures preserved.

## CI separation

The optional local integration file is deliberately named:

tests/local_integrated_regression.py

It is excluded from ordinary test_*.py discovery.

Do not upload the DPAPI secret file or configure the local
integration test to access corporate infrastructure.

## Security boundaries

- No actual Ollama model is instantiated by the reviewed path.
- The review model is deterministic and MOCK only.
- No database writes are performed.
- No notification or operational dispatch is enabled.
- Integrity is verified in memory, not against PostgreSQL.
- No corporate n8n integration.
- Human review remains mandatory.

The n8n E2E MOCK_SNAPSHOT workflow remains unchanged.
