import unittest

from src.incident.case_builder import IncidentCase
from src.incident.persistence_adapter import (
    IncidentPersistenceAdapterError,
    incident_case_to_persistence_payload,
    persist_incident_case,
)


def build_incident():
    return IncidentCase(
        schema_version="1.0",
        environment="LAB",
        incident_id="INC-TEST-001",
        ioc_type="domain",
        ioc_value="malicious-example.test",
        ioc_fingerprint="a" * 64,
        source_event_id="SOURCE-001",
        threat_provider="TEST",
        threat_known=True,
        threat_reputation="MALICIOUS",
        threat_score=95,
        risk_score=100,
        risk_level="CRITICAL",
        policy_decision="ESCALATE",
        status="ESCALATED",
        summary="Synthetic incident",
        reasons=("test",),
        operational_action_allowed=False,
        human_review_required=True,
        human_review_completed=False,
    )


class IncidentPersistenceAdapterTests(
    unittest.TestCase
):

    def test_builds_existing_persistence_contract(self):
        incident = build_incident()

        payload = (
            incident_case_to_persistence_payload(
                incident=incident,
                occurred_at=(
                    "2026-10-06T16:30:00Z"
                ),
                collection_id="LAB-IOC-001",
                collection_sequence=1,
            )
        )

        self.assertEqual(
            payload["environment"],
            "LAB",
        )

        self.assertEqual(
            payload["source"],
            "SOC-LAB",
        )

        self.assertEqual(
            payload["raw_event"]["event_type"],
            "ioc_incident",
        )

        self.assertEqual(
            payload["raw_event"]["severity"],
            "critical",
        )

    def test_contains_three_evidence_records(self):
        incident = build_incident()

        payload = (
            incident_case_to_persistence_payload(
                incident=incident,
                occurred_at=(
                    "2026-10-06T16:30:00Z"
                ),
                collection_id="LAB-IOC-001",
                collection_sequence=1,
            )
        )

        evidence = payload[
            "raw_event"
        ]["evidence"]

        self.assertEqual(
            len(evidence),
            3,
        )

        ids = {
            item["evidence_id"]
            for item in evidence
        }

        self.assertEqual(
            len(ids),
            3,
        )

    def test_ioc_is_preserved_as_entity(self):
        incident = build_incident()

        payload = (
            incident_case_to_persistence_payload(
                incident=incident,
                occurred_at=(
                    "2026-10-06T16:30:00Z"
                ),
                collection_id="LAB-IOC-001",
                collection_sequence=1,
            )
        )

        entity = payload[
            "raw_event"
        ]["entity"]

        self.assertEqual(
            entity["ioc_fingerprint"],
            incident.ioc_fingerprint,
        )

    def test_operational_action_must_remain_blocked(
        self,
    ):
        incident = build_incident()

        bad = IncidentCase(
            **{
                **incident.__dict__,
                "operational_action_allowed":
                    True,
            }
        )

        with self.assertRaises(
            IncidentPersistenceAdapterError
        ):
            incident_case_to_persistence_payload(
                incident=bad,
                occurred_at=(
                    "2026-10-06T16:30:00Z"
                ),
                collection_id="LAB-IOC-001",
                collection_sequence=1,
            )

    def test_human_review_must_remain_required(
        self,
    ):
        incident = build_incident()

        bad = IncidentCase(
            **{
                **incident.__dict__,
                "human_review_required":
                    False,
            }
        )

        with self.assertRaises(
            IncidentPersistenceAdapterError
        ):
            incident_case_to_persistence_payload(
                incident=bad,
                occurred_at=(
                    "2026-10-06T16:30:00Z"
                ),
                collection_id="LAB-IOC-001",
                collection_sequence=1,
            )

    def test_persist_uses_injected_processor(self):
        incident = build_incident()

        captured = {}

        def fake_process(payload):
            captured["payload"] = payload

            return {
                "status": "NEW_EVENT",
                "should_analyze": True,
                "investigation_id":
                    "fake-investigation",
            }

        result = persist_incident_case(
            incident=incident,
            occurred_at=(
                "2026-10-06T16:30:00Z"
            ),
            collection_id="LAB-IOC-001",
            collection_sequence=1,
            process_func=fake_process,
        )

        self.assertEqual(
            result["status"],
            "NEW_EVENT",
        )

        self.assertEqual(
            captured["payload"][
                "environment"
            ],
            "LAB",
        )

    def test_invalid_processor_result_is_rejected(
        self,
    ):
        incident = build_incident()

        def fake_process(_payload):
            return None

        with self.assertRaises(
            IncidentPersistenceAdapterError
        ):
            persist_incident_case(
                incident=incident,
                occurred_at=(
                    "2026-10-06T16:30:00Z"
                ),
                collection_id="LAB-IOC-001",
                collection_sequence=1,
                process_func=fake_process,
            )


if __name__ == "__main__":
    unittest.main()
