"""
SOC Intelligence Orchestrator
WF-03 - Contexto e Correlacao

Leitura de investigacoes versionadas no PostgreSQL.
Nao altera filas, nao executa IA e nao envia notificacoes.
"""

import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.dedup.persistence import connect_db


def _ioc_identity(ioc):
    """Gera identidade deterministica para correlacao de IOC."""

    fingerprint = ioc.get("fingerprint")

    if isinstance(fingerprint, str) and fingerprint:
        return f"fingerprint:{fingerprint}"

    ioc_type = ioc.get("type")
    value = ioc.get("value")

    if (
        isinstance(ioc_type, str)
        and ioc_type
        and isinstance(value, str)
        and value
    ):
        return f"value:{ioc_type}:{value}"

    return None


def indicators(event):
    """Extrai indicadores presentes no evento informado."""

    entity = event.get("entity", {})

    ips = set()
    hosts = set()
    iocs = {}

    for field in ("src_ip", "dst_ip"):
        value = entity.get(field)

        if isinstance(value, str) and value:
            ips.add(value)

    hostname = entity.get("hostname")

    if isinstance(hostname, str) and hostname:
        hosts.add(hostname)

    related = entity.get("related_hostnames", [])

    if isinstance(related, list):
        hosts.update(
            value for value in related
            if isinstance(value, str) and value
        )

    # IOC canonico produzido pelo novo pipeline.
    ioc_type = entity.get("ioc_type")
    ioc_value = entity.get("ioc_value")
    ioc_fingerprint = entity.get("ioc_fingerprint")

    if (
        isinstance(ioc_type, str)
        and ioc_type
        and isinstance(ioc_value, str)
        and ioc_value
    ):
        ioc = {
            "type": ioc_type,
            "value": ioc_value,
            "fingerprint": (
                ioc_fingerprint
                if isinstance(ioc_fingerprint, str)
                and ioc_fingerprint
                else None
            ),
        }

        identity = _ioc_identity(ioc)

        if identity:
            iocs[identity] = ioc

    for evidence in event.get("evidence", []):

        if not isinstance(evidence, dict):
            continue

        for field in ("src_ip", "dst_ip"):
            value = evidence.get(field)

            if isinstance(value, str) and value:
                ips.add(value)

        hostname = evidence.get("hostname")

        if isinstance(hostname, str) and hostname:
            hosts.add(hostname)

        # Permite futura evidencia que carregue IOC diretamente.
        evidence_ioc_type = evidence.get("ioc_type")
        evidence_ioc_value = evidence.get("ioc_value")
        evidence_ioc_fingerprint = evidence.get(
            "ioc_fingerprint"
        )

        if (
            isinstance(evidence_ioc_type, str)
            and evidence_ioc_type
            and isinstance(evidence_ioc_value, str)
            and evidence_ioc_value
        ):
            ioc = {
                "type": evidence_ioc_type,
                "value": evidence_ioc_value,
                "fingerprint": (
                    evidence_ioc_fingerprint
                    if isinstance(
                        evidence_ioc_fingerprint,
                        str,
                    )
                    and evidence_ioc_fingerprint
                    else None
                ),
            }

            identity = _ioc_identity(ioc)

            if identity:
                iocs[identity] = ioc

    return {
        "ips": sorted(ips),
        "hostnames": sorted(hosts),
        "iocs": [
            iocs[key]
            for key in sorted(iocs)
        ],
    }


def _shared_iocs(current, candidate):
    """Retorna IOCs em comum entre dois conjuntos."""

    current_map = {}

    for ioc in current:
        identity = _ioc_identity(ioc)

        if identity:
            current_map[identity] = ioc

    candidate_keys = {
        identity
        for identity in (
            _ioc_identity(ioc)
            for ioc in candidate
        )
        if identity
    }

    common_keys = sorted(
        set(current_map).intersection(
            candidate_keys
        )
    )

    return [
        current_map[key]
        for key in common_keys
    ]


def build_context(queue_id, *, connection_factory=None):
    """Constroi contexto referente a uma versao especifica."""

    if type(queue_id) is not int or queue_id <= 0:
        raise ValueError("queue_id invalido.")

    with (connection_factory or connect_db)() as connection:

        # Este modulo executa apenas SELECT.
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    q.id AS queue_id,
                    q.status AS queue_status,
                    q.investigation_version AS requested_version,
                    i.id AS investigation_id,
                    i.source,
                    i.source_event_id,
                    i.event_type,
                    i.investigation_version AS current_version,
                    i.occurrence_count,
                    v.normalized_event,
                    v.changed_fields,
                    v.content_signature,
                    v.created_at AS version_created_at
                FROM analysis_queue AS q
                JOIN investigations AS i
                  ON i.id = q.investigation_id
                JOIN investigation_versions AS v
                  ON v.investigation_id = i.id
                 AND v.version_number = q.investigation_version
                WHERE q.id = %s
                  AND i.source = 'SOC-LAB'
                """,
                (queue_id,),
            )

            row = cursor.fetchone()

            if row is None:
                raise LookupError(
                    f"Tarefa LAB nao encontrada: {queue_id}"
                )

            event = row["normalized_event"]

            event_indicators = indicators(event)

            historical = (
                row["requested_version"]
                < row["current_version"]
            )

            eligible = (
                row["queue_status"] == "PENDING"
                and not historical
            )

            # Correlacao informativa com OUTRAS investigacoes.
            # Utiliza somente as ultimas versoes existentes.
            # Nao altera a decisao should_analyze.

            cursor.execute(
                """
                SELECT
                    id,
                    source_event_id,
                    latest_event
                FROM investigations
                WHERE source = 'SOC-LAB'
                  AND id <> %s
                ORDER BY updated_at DESC, id
                LIMIT 100
                """,
                (row["investigation_id"],),
            )

            related = []

            current_ips = set(
                event_indicators["ips"]
            )

            current_hosts = set(
                event_indicators["hostnames"]
            )

            current_iocs = event_indicators[
                "iocs"
            ]

            for candidate in cursor.fetchall():

                candidate_indicators = indicators(
                    candidate["latest_event"]
                )

                common_ips = sorted(
                    current_ips.intersection(
                        candidate_indicators["ips"]
                    )
                )

                common_hosts = sorted(
                    current_hosts.intersection(
                        candidate_indicators[
                            "hostnames"
                        ]
                    )
                )

                common_iocs = _shared_iocs(
                    current_iocs,
                    candidate_indicators["iocs"],
                )

                if (
                    common_ips
                    or common_hosts
                    or common_iocs
                ):

                    related.append({
                        "source_event_id":
                            candidate["source_event_id"],
                        "common_ips":
                            common_ips,
                        "common_hostnames":
                            common_hosts,
                        "common_iocs":
                            common_iocs,
                        "relation_type":
                            "SHARED_INDICATORS",
                    })

            related.sort(
                key=lambda item:
                    item["source_event_id"]
            )

            # Limite de itens no contexto.
            related = related[:10]

            return {
                "schema_version": "1.0",
                "environment": "LAB",
                "processor": "WF-03",
                "queue_id": row["queue_id"],
                "queue_status": row["queue_status"],
                "investigation_id": str(
                    row["investigation_id"]
                ),
                "source_event_id":
                    row["source_event_id"],
                "requested_version":
                    row["requested_version"],
                "current_version":
                    row["current_version"],
                "is_historical_version":
                    historical,
                "eligible_for_context_review":
                    eligible,
                "context_status": (
                    "HISTORICAL_VERSION"
                    if historical
                    else "READY_FOR_REVIEW"
                    if eligible
                    else "NOT_PENDING"
                ),
                "event": event,
                "indicators": event_indicators,
                "evidence_count": len(
                    event.get("evidence", [])
                ),
                "changed_fields":
                    row["changed_fields"],
                "occurrence_count":
                    row["occurrence_count"],
                "correlations": {
                    "type": "INFORMATIONAL",
                    "scope": "SOC-LAB",
                    "candidates_limit": 100,
                    "matches": related,
                },
                "provenance": {
                    "database":
                        "soc_intelligence",
                    "table":
                        "investigation_versions",
                    "version":
                        row["requested_version"],
                    "content_signature":
                        row["content_signature"],
                },
                "dispatch_status": "MOCK_ONLY",
                "ai_executed": False,
                "notification_sent": False,
            }


def main():

    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python src/context/context_builder.py "
            "<queue_id>"
        )

    context = build_context(
        int(sys.argv[1])
    )

    print(
        json.dumps(
            context,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
