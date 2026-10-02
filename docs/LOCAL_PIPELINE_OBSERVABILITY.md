# Local Pipeline Observability - Stage 14

## Objective

Add optional local observability to the existing integrated
SOC Intelligence Orchestrator MOCK pipeline.

The original integrated pipeline remains unchanged.

## Components

- `src/observability/collector.py`
- `src/observability/pipeline.py`
- `tests/test_observability_collector.py`
- `tests/test_observed_mock_pipeline.py`
- `tests/test_observability_integration.py`

## Integration

The function `run_observed_mock_review(queue_id, cache=None)`
wraps the existing `run_integrated_mock_review()`.

Its output contains two separate objects:

- `result`: original pipeline result.
- `telemetry`: sanitized execution metrics.

The wrapper measures execution duration using a monotonic
clock and preserves the identity of the original result.

## Telemetry contract

Only the following fields are exported:

- schema_version
- environment
- pipeline_status
- gate_decision
- review_status
- integrity_status
- cache_hit
- duration_ms
- error_category

The collector uses an explicit allowlist and builds a new
dictionary instead of copying the original result.

`cache_hit` is null for historical or blocked reviews.

`VERIFIED_IN_MEMORY` does not represent verification against
the PostgreSQL database.

## Security constraints

- No tokens or credentials in telemetry.
- No raw events, evidence, prompts or AI responses exported.
- No integrity signatures exported.
- No external metrics service.
- No file-based logging or database persistence.
- No operational dispatch or notifications.
- No real Ollama execution.
- Human review remains mandatory.

Pipeline exceptions are propagated without converting failures
into successful executions.

The current wrapper produces telemetry for successfully
completed pipeline calls. Error classification and aggregation
are not implemented in this version.

## Validation

Stage 14 includes:

| Suite | Tests |
|---|---:|
| Observability collector | 8 |
| Observed MOCK pipeline | 10 |
| Observability integration | 6 |
| **Total observability** | **24** |

The targeted offline regression includes the previous
75 tests and the 24 new observability tests.

**Consolidated local result: 99/99 tests passed.**

The local integration test requiring the authenticated
PostgreSQL LAB remains separate from GitHub Actions.

## CI

The existing Offline Security CI workflow has been extended
with the three Stage 14 test suites.

Expected total: 11 offline suites and 99 tests.

The GitHub Actions execution must be verified after publication.
