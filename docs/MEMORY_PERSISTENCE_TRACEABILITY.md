# Memory Persistence Traceability - Stage 16

## Objective

Provide controlled in-memory traceability and deterministic
duplicate/conflict handling for the integrated SOC-LAB MOCK
review and WF-05 report pipeline.

This stage does not perform PostgreSQL persistence.

## New components

- `src/observability/persistence_traceability.py`
- `src/observability/memory_trace_registry.py`
- `tests/test_memory_traceability.py`
- `tests/test_memory_trace_registry.py`

The existing WF-04 integrity functions and WF-05 report
validator are reused without modification.

## Traceability contract

`build_memory_traceability(contract, integrity_record)`
validates the original WF-05 contract and compares the
provided integrity record against the reconstructed
WF-04 result.

The output contains an allowlist of audit metadata:

- Investigation identity and version.
- Historical control for Queue 12.
- Content signature.
- Analysis signature.
- Result key.
- Integrity and persistence states.
- Human-review and operational-dispatch restrictions.

The complete analysis and generated HTML are not included.

## Integrity states

- `VERIFIED_IN_MEMORY`: SHA-256 verified in memory.
- `NOT_ATTEMPTED`: no persistence attempted.
- `SHA256_IN_MEMORY`: verification method.

The output explicitly declares:

- `database_record_id: null`
- `verified_against_database: false`
- `operational_dispatch_allowed: false`
- `notification_sent: false`
- `human_review_required: true`

No PostgreSQL persistence receipt is fabricated.

## In-memory duplicate and conflict handling

`MemoryTraceRegistry` uses private per-instance storage.

The outcomes are:

- `MEMORY_NEW_RESULT`: first accepted trace.
- `MEMORY_ALREADY_REGISTERED`: identical repetition.
- `INTEGRITY_CONFLICT`: conflicting logical identity
  or result key, without overwriting the stored trace.

Input data is deep-copied before storage.

The registry is restricted to the homologated synthetic
SOC-LAB scenario, Queues 12 and 13.

The registry receives metadata already validated by
`build_memory_traceability()`. Because it does not receive
the original analysis, it cannot independently recalculate
the analysis signature and must not be exposed as a public
ingestion interface.

## Scope and isolation

- No PostgreSQL connections, schema changes or writes.
- No real Ollama invocation.
- No corporate service integration.
- No operational dispatch or notifications.
- No persistent state across separate registry instances.
- No transactional concurrency guarantee.
- No authentication or durability claim.

The existing transactional persistence implementation is
a separate component and remains unchanged.

## Local validation

Stage 16.3:

- Memory traceability: 14/14 tests passed.

Stage 16.4:

- In-memory registry: 16/16 tests passed.

Stage 16.5:

- Consolidated regression: 138/138 tests passed.
- 14 offline test suites.
- Original WF-05 generator: 7 additional checks passed.

## GitHub Actions

Offline Security CI now includes both Stage 16 suites.

Expected result: 14 suites and 138 offline tests.

The final GitHub Actions execution must be verified
after publication to main.
