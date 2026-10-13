"""
ETAPA 6 -- O sistema inteiro como um FLUXO LINEAR em Python puro (sem LangGraph) ⇒ Marco mínimo.

ESQUELETO:
  ETAPA 6.3 -- analisar(): o Coordenador junta os pareceres (com os limites da Etapa 4.7)
  ETAPA 6.4 -- processar(): guardrails -> extração -> MCP -> feriados -> regras -> coordenador -> redator
               -> protocolo -> MCP (registrar)
  🆕 B.4    -- (OPCIONAL, bônus) testar_governanca(): os dois testes de bloqueio do --governanca

REFERÊNCIAS NAS AULAS
  aula6/exemplos/01_fluxo_linear/main.py     o fluxo linear: funciona, mas sem decisão nem volta (por isso a Etapa 7)
  aula4/ex03_agente_as_tool.py               o Coordenador com especialistas como tools
  aula7/exemplos/02_agentes_especializados/main.py   cada especialista imprime o que fez: dá para saber quem fez o quê

Rodar:
    python etapa06_linear.py                 # C1, C2, C6 e C11
    python etapa06_linear.py --governanca    # 🆕 B (opcional): os dois testes de bloqueio

Pronto quando: C1, C2 e C11 são gravados com protocolo, C6 vira indeferimento com sugestão de datas, e você sabe dizer
qual agente escreveu cada parte. (Opcional) no --governanca: a tool restrita NÃO executa e o C2 para no orçamento.
"""
import json
import os
import sys

from agents import RunHooks

import etapa06_agentes as agentes
from etapa05_cliente_mcp import chamar_mcp
from dados.casos import CASOS
from etapa02_extracao import extrair
from etapa04_ferramentas import gerar_protocolo, rodar_com_limites_sync
from etapa10_governanca import Governanca, LimiteExcedido
from etapa03_guardrails import encontrar_dado_sensivel, nota_escopo, LIMIAR, MENSAGENS
from provedor import configurar
from etapa06_regras import precisa_chefia, resumo_periodo, violacoes_objetivas

MODELO = configurar()


def analisar(pedido: dict, servidor: dict, periodo: dict, violacoes: list[str], hooks: RunHooks | None = None) -> str:
    # ETAPA 6.3 -- monte um texto com o pedido, o servidor (matrícula e equipe), o período e as violações objetivas,
    entrada = (
        f"PEDIDO: {pedido}\n"
        f"SERVIDOR: matrícula {servidor.get('matricula')}, equipe {servidor.get('equipe')}, "
        f"saldo de férias {servidor.get('saldo_ferias_dias')}, abonos restantes {servidor.get('abonos_restantes')}\n"
        f"PERÍODO: {periodo}\n"
        f"VIOLAÇÕES OBJETIVAS: {violacoes or 'nenhuma'}"
    )
    coordenador = agentes.criar_coordenador(hooks=hooks)
    resultado = rodar_com_limites_sync(coordenador, entrada, hooks=hooks)
    return resultado.final_output


def processar(texto: str, hooks: RunHooks | None = None) -> dict:
    # ETAPA 6.4 -- encadeie, imprimindo cada passo ("[1/9] guardrails", ...):
    print("[1/9] guardrails")
    sensivel = encontrar_dado_sensivel(texto)
    if sensivel:
        return {"resultado": "bloqueado", "mensagem": MENSAGENS[sensivel]}
    nota, _ = nota_escopo(texto)
    if nota >= LIMIAR:
        return {"resultado": "bloqueado", "mensagem": MENSAGENS["fora_do_escopo"]}

    print("[2/9] extração")
    p = extrair(texto)
    pedido = p.model_dump(mode="json")
    if not pedido.get("matricula") or not pedido.get("data_inicio") or not pedido.get("data_fim"):
        return {"resultado": "pedir_dados"}

    print(f"[3/9] servidor: {pedido['matricula']}")
    servidor = chamar_mcp("consultar_servidor", {"matricula": pedido["matricula"]})
    if servidor.get("erro") or not servidor.get("nome"):
        return {"resultado": "pedir_dados"}

    print(f"[4/9] período: {pedido['data_inicio']}..{pedido['data_fim']}")
    periodo = resumo_periodo(pedido["data_inicio"], pedido["data_fim"])

    escala = chamar_mcp("consultar_escala", {
        "equipe": servidor["equipe"],
        "inicio": pedido["data_inicio"],
        "fim": pedido["data_fim"],
    })
    violacoes = violacoes_objetivas(pedido, servidor, periodo, escala)
    print(f"[5/9] violações: {violacoes or 'nenhuma'}")

    print("[6/9] coordenador")
    parecer = analisar(pedido, servidor, periodo, violacoes, hooks=hooks)

    print("[7/9] redator")
    entrada_redator = (
        f"FATOS:\n"
        f"Pedido: {pedido}\n"
        f"Servidor: {servidor}\n"
        f"Período: {periodo}\n"
        f"Violações: {violacoes or 'nenhuma'}\n\n"
        f"PARECER:\n{parecer}"
    )
    despacho = rodar_com_limites_sync(agentes.criar_redator(), entrada_redator, hooks=hooks).final_output

    protocolo = gerar_protocolo(pedido["matricula"], pedido["tipo"], pedido["data_inicio"], pedido["data_fim"])
    print(f"[8/9] protocolo {protocolo}")

    decisao = "indeferido" if violacoes else "deferido"
    aprovador = "pendente_chefia" if precisa_chefia(pedido, violacoes) else "sistema"
    registro_arg = {
        "protocolo": protocolo,
        "matricula": pedido["matricula"],
        "tipo": pedido["tipo"],
        "inicio": pedido["data_inicio"],
        "fim": pedido["data_fim"],
        "decisao": decisao,
        "aprovador": aprovador,
        "despacho": despacho,
        "token": os.getenv("TOKEN_REGISTRO", ""),
        "thread_id": "linear",
    }
    resp_mcp = chamar_mcp("registrar_decisao", registro_arg)
    print(f"[9/9] registrar: {resp_mcp}")

    resultado_final = "registrado" if resp_mcp.get("sucesso") else "negado_pelo_server"
    return {
        "resultado": resultado_final,
        "protocolo": protocolo,
        "despacho": despacho,
        "parecer": parecer,
    }


def testar_governanca() -> None:
    # 🆕 B.4 (opcional) -- dois testes, cada um tratando LimiteExcedido e imprimindo o motivo:
    print("a) Coordenador com uma tool que não é dele")
    try:
        coordenador = agentes.criar_coordenador(hooks=Governanca(), tools_extras=[agentes.consultar_remuneracao])
        rodar_com_limites_sync(coordenador, "Qual o salário da matrícula 1002?", hooks=Governanca())
    except LimiteExcedido as e:
        print(f"   barrado: {e}")

    print("\nb) C2 com MAX_TOOLS = 1")
    try:
        processar(CASOS["C2_ferias_com_venda"]["pedido"], hooks=Governanca(max_tools=1))
    except LimiteExcedido as e:
        print(f"   barrado: {e}")


if __name__ == "__main__":
    print(f"[modelo] {MODELO}")
    if "--governanca" in sys.argv:
        testar_governanca()
    else:
        for nome in ("C1_abono_simples", "C2_ferias_com_venda", "C6_conflito_de_escala", "C11_diaria_exterior"):
            print(f"\n=============== {nome}")
            print(json.dumps(processar(CASOS[nome]["pedido"]), ensure_ascii=False, indent=2))
