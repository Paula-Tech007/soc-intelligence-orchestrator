"""
Conexao exclusiva da API LAB.

Credencial recebida por variavel de ambiente temporaria.
Nao utiliza o usuario administrativo soc_lab.
"""

import os

import psycopg
from psycopg.rows import dict_row


def connect_bridge_db():

    password = os.environ.get("SOC_BRIDGE_DB_PASSWORD")

    if not password:
        raise RuntimeError(
            "Credencial read-only da ponte nao configurada."
        )

    connection = psycopg.connect(
        host="127.0.0.1",
        port=15432,
        dbname="soc_intelligence",
        user="soc_bridge_ro",
        password=password,
        connect_timeout=5,
        autocommit=True,
        row_factory=dict_row,
        options="-c default_transaction_read_only=on",
    )

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    current_user AS username,
                    current_setting(
                        'transaction_read_only'
                    ) AS read_only
                """
            )

            identity = cursor.fetchone()

            if (
                identity["username"] != "soc_bridge_ro"
                or identity["read_only"] != "on"
            ):
                raise RuntimeError(
                    "Conexao sem identidade read-only valida."
                )

        return connection

    except Exception:
        connection.close()
        raise