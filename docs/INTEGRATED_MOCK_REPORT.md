# Integrated MOCK Report - Stage 15

## Objective

Integrate the verified SOC-LAB MOCK pipeline with the
existing WF-05 HTML report generator.

The original report generator remains unchanged.

## Components

- src/reports/integrated_mock_adapter.py
- tests/test_integrated_mock_report.py
- src/reports/report_builder.py (reused)

## Input contract

The adapter combines:

1. Queue 12: historical result, version 1.
2. Queue 13: current MOCK result, version 2.
3. Independently supplied validated historical envelope.

The historical result remains SKIPPED, without analysis.

The current result must have integrity status
VERIFIED_IN_MEMORY.

The consolidated envelope is validated using the existing
WF-05 validate_contract() before build_report() is called.

## Security boundaries

- Synthetic SOC-LAB scenario only.
- No real Ollama execution.
- No automatic notifications or ticket creation.
- No database writes or report distribution.
- No operational dispatch.
- Human review remains mandatory.

VERIFIED_IN_MEMORY does not mean PostgreSQL verification.

The generated HTML is returned in memory and is not
automatically saved or sent.

## Scope limitation

The original WF-05 validator expects the synthetic scenario
with versions 1 and 2, Queues 12 and 13, event LAB-0001,
and evidence IDs LAB-EV-001 and LAB-EV-002.

Supporting arbitrary investigations will require separate
contract generalization and additional tests.

## Homologation

- Integrated MOCK report: 9/9 tests passed.
- Consolidated offline regression: 108/108 tests passed.
- Original WF-05 generator: 7 checks passed.
- No real Ollama calls, database writes or notifications.

## GitHub Actions

Offline Security CI includes 12 offline test suites.

Expected consolidated regression: 108 tests.

The GitHub Actions result must be verified after publication.
