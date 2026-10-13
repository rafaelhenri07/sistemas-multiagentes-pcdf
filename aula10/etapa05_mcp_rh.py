"""
ETAPA 5 -- MCP Server do RH (30 min). Volta aqui na ETAPA 9 (token, regra N8 e auditoria).

Os dados saem de dentro do agente e passam a morar num PROCESSO SEPARADO, que fala MCP. O agente (Etapa 5.3) e os
nós do grafo (Etapa 7, via cliente_mcp.chamar_mcp) só enxergam as tools abaixo: nunca os CSVs.

ESQUELETO: implemente as etapas na ordem (troque cada raise NotImplementedError pelo código da etapa).
  ETAPA 5.1 -- as 5 tools de LEITURA: declare cada uma com @mcp.tool(), escreva a DOCSTRING (é o "schema" que o LLM
               lê) e devolva o resultado da consulta pronta de dados_rh.py. Toda tool devolve UM dict.
  ETAPA 5.2 -- a tool de ESCRITA registrar_decisao, IDEMPOTENTE (protocolo repetido não duplica)
  ETAPA 9.2 -- autorização NO SERVER: token + regra N8 (chefia certa, nunca o próprio servidor) + decisão num enum
  ETAPA 9.3 -- auditoria: toda tentativa de escrita (ALLOW ou DENY) vira uma linha em saidas/auditoria.jsonl

REFERÊNCIAS NAS AULAS
  aula6/desafio2/mcp_unidades.py               MCP Server que lê um CSV                          <- o mais parecido (5.1)
  aula5/exemplos/03_mcp_parametros/server.py   tool com parâmetros opcionais
  aula5/exemplos/05_multiplas_tools/server.py  várias tools no mesmo server, tool de "descoberta"
  aula3/agente_retry3.py                       idempotência (5.2)
  aula5/exemplos/10_seguranca/server_seguro.py token, enum fechado e auditoria NO SERVER        <- o mais parecido (9.2/9.3)

Testar sem agente (MCP Inspector, precisa de Node.js):
    npx @modelcontextprotocol/inspector python etapa05_mcp_rh.py

Pronto quando: o Inspector lista as 6 tools; registrar C1 duas vezes gera um único registro.
"""
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from dados_rh import PASTA, SAIDAS, carregar_servidores, diaria, escala_da_equipe, normas, remuneracao, servidor_publico

# O server roda como SUBPROCESSO: ele não herda o ambiente de quem o chamou. Por isso carrega o .env sozinho
# (mesmo cuidado de aula5/exemplos/02_mcp_basico/database.py).
load_dotenv(PASTA / ".env")

mcp = MCPServer("rh-mcp")

ARQUIVO_REGISTROS = SAIDAS / "registros.json"
ARQUIVO_AUDITORIA = SAIDAS / "auditoria.jsonl"
TOKEN_REGISTRO = os.getenv("TOKEN_REGISTRO", "")
DECISOES_VALIDAS = {"deferido", "indeferido", "indeferido_pela_chefia"}
TIPOS_COM_CHEFIA = {"ferias", "diaria"}  # regra N8


def _ler_registros() -> dict:
    """(PRONTO) {protocolo: registro} gravados até agora."""
    if ARQUIVO_REGISTROS.exists():
        return json.loads(ARQUIVO_REGISTROS.read_text(encoding="utf-8"))
    return {}


def _gravar_registros(registros: dict) -> None:
    """(PRONTO)"""
    ARQUIVO_REGISTROS.write_text(json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ ETAPA 5.1: leitura
@mcp.tool()
def consultar_servidor(matricula: str) -> dict:
    """Consulta os dados cadastrais públicos de um servidor pelo número de matrícula (sem o salário).

    Args:
        matricula: Número de matrícula do servidor (string de 4 dígitos, ex.: '1002').
    """
    return servidor_publico(matricula)


@mcp.tool()
def consultar_escala(equipe: str, inicio: str, fim: str) -> dict:
    """Consulta os afastamentos agendados de uma equipe em determinado período e o limite da regra N5.

    Args:
        equipe: Nome da equipe policial (ex.: 'Plantão A', 'Cartório').
        inicio: Data de início do período no formato AAAA-MM-DD.
        fim: Data de término do período no formato AAAA-MM-DD.
    """
    return escala_da_equipe(equipe, inicio, fim)


@mcp.tool()
def consultar_normas(tema: str) -> dict:
    """Consulta as regras da Norma Interna da PCDF por tema (férias, prazos, escala, abono, diária, aprovação, saúde, dados).

    Args:
        tema: Tema da norma a consultar (ex.: 'férias', 'abono', 'diária', 'escala', 'prazos', 'aprovação').
    """
    return {"tema": tema, "regras": normas(tema)}


@mcp.tool()
def tabela_diarias(tipo_destino: str) -> dict:
    """Consulta a moeda e valor da diária para viagens a serviço conforme o tipo de destino.

    Args:
        tipo_destino: Tipo de destino da viagem: 'capital', 'interior' ou 'exterior'.
    """
    return diaria(tipo_destino)


@mcp.tool()
def consultar_remuneracao(matricula: str) -> dict:
    """[RESTRITA] Consulta o salário-base de um servidor. Ferramenta de uso exclusivo do especialista Financeiro (regra N2).

    Args:
        matricula: Número de matrícula do servidor (string de 4 dígitos, ex.: '1002').
    """
    return remuneracao(matricula)


# ------------------------------------------------------------------ ETAPA 5.2 / 9.2 / 9.3: escrita
def _auditar(protocolo: str, decisao_acesso: str, motivo: str, parametros: dict) -> None:
    # ETAPA 9.3 -- acrescente UMA linha JSON em ARQUIVO_AUDITORIA com: quando (datetime.now().isoformat()),
    #   thread_id, quem pediu (aprovador), tool ("registrar_decisao"), protocolo, decisao_acesso ("ALLOW"/"DENY"),
    #   motivo e os parâmetros (SEM o token e SEM o despacho inteiro).
    linha = {
        "quando": datetime.now().isoformat(),
        "thread_id": parametros.get("thread_id", ""),
        "quem": parametros.get("aprovador", ""),
        "tool": "registrar_decisao",
        "protocolo": protocolo,
        "decisao_acesso": decisao_acesso,
        "motivo": motivo,
        "parametros": {k: v for k, v in parametros.items() if k not in ("token", "despacho")},
    }
    with open(ARQUIVO_AUDITORIA, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


@mcp.tool()
def registrar_decisao(protocolo: str, matricula: str, tipo: str, inicio: str, fim: str, decisao: str,
                      aprovador: str, despacho: str, token: str, thread_id: str = "") -> dict:
    """[ESCRITA -- requer autorização] Registra formalmente a decisão sobre o pedido no RH com auditoria e idempotência.

    Args:
        protocolo: Protocolo idempotente do pedido (ferramentas.gerar_protocolo).
        matricula: Número de matrícula do servidor requerente.
        tipo: Tipo de afastamento ('ferias', 'abono', 'diaria').
        inicio: Data de início do afastamento no formato AAAA-MM-DD.
        fim: Data de término do afastamento no formato AAAA-MM-DD.
        decisao: Decisão do pedido ('deferido', 'indeferido', 'indeferido_pela_chefia').
        aprovador: Matrícula da chefia responsável pela aprovação ou 'sistema'.
        despacho: Texto fundamentado do despacho redigido.
        token: Token de autorização para escrita no servidor MCP.
        thread_id: Identificador da thread de execução do LangGraph.
    """
    parametros = {"matricula": matricula, "tipo": tipo, "inicio": inicio, "fim": fim, "decisao": decisao,
                  "aprovador": aprovador, "thread_id": thread_id}

    # ETAPA 9.2 -- ANTES de gravar, negue (e audite com DENY) quando:
    #   - token != TOKEN_REGISTRO (ou TOKEN_REGISTRO vazio);
    if not TOKEN_REGISTRO or token != TOKEN_REGISTRO:
        _auditar(protocolo, "DENY", "token inválido", parametros)
        return {"sucesso": False, "erro": "token inválido"}

    #   - decisao não está em DECISOES_VALIDAS;
    if decisao not in DECISOES_VALIDAS:
        _auditar(protocolo, "DENY", f"decisão inválida: {decisao}", parametros)
        return {"sucesso": False, "erro": f"decisão inválida: {decisao}"}

    #   - aprovador == matricula (ninguém aprova o próprio pedido, N8);
    if aprovador == matricula:
        _auditar(protocolo, "DENY", "autoaprovação (N8)", parametros)
        return {"sucesso": False, "erro": "autoaprovação (N8)"}

    #   - decisao == "deferido" e tipo in TIPOS_COM_CHEFIA e aprovador != chefia do servidor no cadastro.
    if decisao == "deferido" and tipo in TIPOS_COM_CHEFIA:
        servidores = carregar_servidores()
        servidor = servidores.get(str(matricula).strip())
        chefia_esperada = servidor.get("chefia") if servidor else None
        if aprovador != chefia_esperada:
            motivo = f"aprovador não é a chefia {chefia_esperada} (N8)"
            _auditar(protocolo, "DENY", motivo, parametros)
            return {"sucesso": False, "erro": motivo}

    # ETAPA 5.2 -- grave em ARQUIVO_REGISTROS (use _ler_registros/_gravar_registros).
    registros = _ler_registros()
    if protocolo in registros:
        _auditar(protocolo, "ALLOW", "duplicado", parametros)
        return {"sucesso": True, "duplicado": True, "protocolo": protocolo}

    registros[protocolo] = {
        **parametros,
        "despacho": despacho,
        "registrado_em": datetime.now().isoformat(),
    }
    _gravar_registros(registros)
    _auditar(protocolo, "ALLOW", "gravado", parametros)
    return {"sucesso": True, "protocolo": protocolo}


if __name__ == "__main__":
    mcp.run(transport="stdio")
