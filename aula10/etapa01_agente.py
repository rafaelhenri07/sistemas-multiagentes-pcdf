"""
ETAPA 1 -- Primeiro agente com tool local (15 min).

ESQUELETO: implemente as etapas na ordem. Cada uma está marcada com um comentário e um
raise NotImplementedError: troque esse raise pelo código da etapa e rode o arquivo.
  ETAPA 1.1 -- a tool consultar_servidor (SEM o salário)
  ETAPA 1.2 -- o agente AtendenteRH com a tool
  ETAPA 1.3 -- duas perguntas: uma que precisa da tool e uma que não precisa

REFERÊNCIAS NAS AULAS
  aula1/segundo_agente.py                            Agent + @function_tool + Runner.run_sync (o básico)
  exercicios_resolvidos/aula4/ex10_function_tool.py  tool que consulta uma TABELA e devolve JSON  <- o mais parecido
  aula8/exemplos/02_agente_tool/main.py              o agente decide quando chamar a tool (e quando não)

Rodar (a partir de aula10/):
    python etapa01_agente.py

Pronto quando: a tool é chamada só na primeira pergunta (o print dentro dela prova).
"""
import json

from agents import Agent, Runner, function_tool

from dados_rh import servidor_publico
from provedor import configurar

MODELO = configurar()  # LLM REAL: PROVEDOR no .env (openai ou ollama)


# ETAPA 1.1 -- a tool
@function_tool
def consultar_servidor(matricula: str) -> str:
    """Consulta os dados cadastrais públicos de um servidor pelo número de matrícula (sem o salário).

    Args:
        matricula: Número de matrícula do servidor (string numérica com 4 dígitos, ex.: '1002').
    """
    print("[tool] consultar_servidor", matricula)
    return json.dumps(servidor_publico(matricula), ensure_ascii=False)


def criar_atendente() -> Agent:
    # ETAPA 1.2 -- o agente
    return Agent(
        name="AtendenteRH",
        instructions=(
            "Você é o atendente do RH da PCDF. Responda às dúvidas dos servidores em português de forma clara e breve. "
            "Use a ferramenta consultar_servidor quando a pergunta for sobre os dados de um servidor específico "
            "(saldo de férias, abonos restantes, equipe ou cargo). "
            "Nunca invente saldo de cabeça. Para dúvidas gerais sobre normas ou conceitos, responda diretamente sem chamar a ferramenta."
        ),
        tools=[consultar_servidor],
    )


def main() -> None:
    # ETAPA 1.3 -- rode as duas perguntas com Runner.run_sync e imprima resultado.final_output
    atendente = criar_atendente()
    r1 = Runner.run_sync(atendente, "Quantos dias de férias a matrícula 1002 ainda tem?")
    print(r1.final_output)

    r2 = Runner.run_sync(atendente, "O que é abono pecuniário?")
    print(r2.final_output)


if __name__ == "__main__":
    print(f"[modelo] {MODELO}")
    main()
