"""
SOC Intelligence Orchestrator
FASE 11.2 - Smoke Test LangChain + Ollama

Teste isolado, utilizando somente o modelo local.

Nao acessa PostgreSQL.
Nao executa ferramentas externas.
Nao envia notificacoes.
"""

from langchain_ollama import ChatOllama

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
)


def main():

    print("")
    print("========================================")
    print(" SOC LAB - LANGCHAIN + OLLAMA")
    print("========================================")
    print("")

    modelo = ChatOllama(
        model="qwen3:4b-instruct",
        base_url="http://127.0.0.1:11434",
        temperature=0,
        num_predict=100,
    )

    mensagens = [
        SystemMessage(
            content=(
                "Voce e um assistente tecnico em um "
                "laboratorio ficticio de seguranca. "
                "Responda em portugues, de forma breve. "
                "Nao solicite nem execute acoes."
            )
        ),
        HumanMessage(
            content=(
                "Complete em apenas uma frase: "
                "SOC Intelligence Orchestrator e "
                "um projeto de laboratorio para..."
            )
        ),
    ]

    print("Consultando qwen3:4b-instruct localmente...")

    resposta = modelo.invoke(mensagens)

    conteudo = resposta.content

    if not isinstance(conteudo, str):
        raise RuntimeError(
            "O modelo nao retornou uma resposta textual."
        )

    if not conteudo.strip():
        raise RuntimeError(
            "O modelo retornou uma resposta vazia."
        )

    print("")
    print("=== RESPOSTA DO QWEN ===")
    print(conteudo)

    print("")
    print("[OK] Ollama respondeu.")
    print("[OK] LangChain realizou a chamada.")
    print("[OK] Resposta textual nao vazia.")
    print("[OK] Nenhuma acao operacional executada.")
    print("")
    print("FASE 11.2 - SMOKE TEST APROVADO")


if __name__ == "__main__":
    main()