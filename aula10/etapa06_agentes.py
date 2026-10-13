"""
ETAPA 6 -- Os especialistas, cada um com UMA responsabilidade e SÓ as tools de que precisa.

ESQUELETO:
  ETAPA 6.1 -- criar_normas(), criar_escala(), criar_financeiro(), criar_redator()
  ETAPA 6.2 -- criar_coordenador(): usa Normas, Escala e Financeiro como TOOLS (as_tool)

As tools abaixo (PRONTAS) só repassam a chamada ao MCP Server do RH (cliente_mcp.chamar_mcp_async). Dar a cada agente
só as tools dele é o PRIVILÉGIO MÍNIMO (Etapa 9.1); o hook do 🆕 B (etapa10_governanca.py) confere isso em tempo de execução.

REFERÊNCIAS NAS AULAS
  aula4/ex03_agente_as_tool.py                         Coordenador que chama especialistas como tools    <- o mais parecido
  aula2/agente_handoff2.py                             as_tool com tool_name e tool_description
  aula4/ex02_handoff_roteamento.py                     handoff: compare (quem responde no fim?)
  aula7/exemplos/02_agentes_especializados/main.py     uma responsabilidade por agente
  aula7/agentes.py                                     ModelSettings(temperature=0) para respostas mais estáveis
  aula8/exemplos/06_excessive_agency/1_codigo_pronto/main.py   o problema de dar tools DEMAIS a um agente
"""
import json

from agents import Agent, ModelSettings, RunHooks, function_tool

from etapa05_cliente_mcp import chamar_mcp_async
from etapa04_ferramentas import cotacao_usd_brl

CONFIG = ModelSettings(temperature=0)


# ------------------------------------------------------------------ tools (PRONTAS)
@function_tool
async def consultar_normas(tema: str) -> str:
    """Regras da norma interna sobre um tema: férias, prazos, escala, abono, diária, aprovação, saúde ou dados."""
    return json.dumps(await chamar_mcp_async("consultar_normas", {"tema": tema}), ensure_ascii=False)


@function_tool
async def consultar_escala(equipe: str, inicio: str, fim: str) -> str:
    """Afastamentos da equipe que se sobrepõem ao período (AAAA-MM-DD) e o limite de afastados da regra N5."""
    return json.dumps(await chamar_mcp_async("consultar_escala", {"equipe": equipe, "inicio": inicio, "fim": fim}),
                      ensure_ascii=False)


@function_tool
async def tabela_diarias(tipo_destino: str) -> str:
    """Moeda e valor da diária para o tipo de destino: capital, interior ou exterior."""
    return json.dumps(await chamar_mcp_async("tabela_diarias", {"tipo_destino": tipo_destino}), ensure_ascii=False)


@function_tool
async def consultar_remuneracao(matricula: str) -> str:
    """[RESTRITA] Salário-base de um servidor. Só para calcular a venda de férias (N2)."""
    print(f"[tool] consultar_remuneracao({matricula}) EXECUTOU")  # o 🆕 B prova que, barrada, ela NÃO executa
    return json.dumps(await chamar_mcp_async("consultar_remuneracao", {"matricula": matricula}), ensure_ascii=False)


@function_tool
def cotacao_dolar() -> str:
    """Cotação atual do dólar em reais (USD->BRL). Devolve 'indisponível' se a API falhar: nunca invente o câmbio."""
    cotacao = cotacao_usd_brl()
    return f"{cotacao:.4f}" if cotacao else "indisponível"


# ------------------------------------------------------------------ ETAPA 6.1: especialistas
def criar_normas() -> Agent:
    # ETAPA 6.1 -- Agent(name="Normas", instructions=..., tools=[consultar_normas], model_settings=CONFIG)
    return Agent(
        name="Normas",
        instructions=(
            "Você é o especialista em Normas Internas da PCDF (férias, abonos, diárias e licenças). "
            "Sua responsabilidade é consultar a ferramenta consultar_normas para verificar quais regras se aplicam "
            "ao pedido e explicá-las com clareza em linguagem direta. "
            "Você também recebe as violações objetivas identificadas para contextualizá-las juridicamente. "
            "NÃO calcula valores monetários e NÃO consulta escala de plantão."
        ),
        tools=[consultar_normas],
        model_settings=CONFIG,
    )


def criar_escala() -> Agent:
    # ETAPA 6.1 -- tools=[consultar_escala]. Confere a N5 e, se houver conflito, SUGERE outro período
    return Agent(
        name="Escala",
        instructions=(
            "Você é o especialista em Escala de Plantão da PCDF. "
            "Sua responsabilidade é usar consultar_escala para verificar conflitos com afastamentos de colegas da equipe (regra N5). "
            "Se houver conflito (mais de 30% da equipe afastada no mesmo período), SUGIRA um período alternativo viável "
            "com a mesma quantidade de dias do pedido, iniciando em dia útil permitido (regra N3: nunca quinta, sexta ou véspera de feriado)."
        ),
        tools=[consultar_escala],
        model_settings=CONFIG,
    )


def criar_financeiro() -> Agent:
    # ETAPA 6.1 -- tools=[tabela_diarias, consultar_remuneracao, cotacao_dolar].
    return Agent(
        name="Financeiro",
        instructions=(
            "Você é o especialista Financeiro do RH da PCDF. "
            "Você é o ÚNICO agente autorizado a consultar remuneração de servidores. "
            "Para pedidos com venda de férias (regra N2): consulte o salário com consultar_remuneracao e calcule: "
            "valor = dias_vendidos * (salario_base / 30). "
            "Para pedidos de diária (regra N7): consulte tabela_diarias e cotacao_dolar. Calcule: "
            "1 diária por pernoite + 0.5 diária no dia de retorno. Se exterior, converta o total em USD para BRL usando a cotação. "
            "Se o câmbio estiver indisponível, informe 'a calcular'. Apresente a memória de cálculo de forma explícita."
        ),
        tools=[tabela_diarias, consultar_remuneracao, cotacao_dolar],
        model_settings=CONFIG,
    )


def criar_redator() -> Agent:
    # ETAPA 6.1 -- sem tools. Escreve o DESPACHO (deferimento ou indeferimento) usando SÓ os fatos recebidos
    return Agent(
        name="Redator",
        instructions=(
            "Você é o Redator oficial de despachos administrativos do RH da PCDF. "
            "Escreva o texto final do despacho administrativo fundamentado (DEFERIMENTO ou INDEFERIMENTO) usando "
            "estritamente as informações fornecidas nos pareceres e fatos. "
            "O despacho DEVE obrigatoriamente mencionar: a matrícula do servidor, o período de afastamento com a data de início, "
            "a decisão explícita (deferido ou indeferido), as regras legais aplicadas, valores financeiros se houver, e a sugestão "
            "de datas no caso de indeferimento por escala. "
            "NUNCA inclua CPF, CID, laudos ou detalhes médicos de saúde no despacho (regra N10). "
            "Se receber feedback corretivo, ajuste o despacho para sanar exatamente o que foi apontado."
        ),
        tools=[],
        model_settings=CONFIG,
    )


# ------------------------------------------------------------------ ETAPA 6.2: coordenador
def criar_coordenador(hooks: RunHooks | None = None, tools_extras: list | None = None) -> Agent:
    # ETAPA 6.2 -- Agent(name="Coordenador", instructions=..., tools=[...])
    tools = [
        criar_normas().as_tool(
            tool_name="parecer_normas",
            tool_description="Consulta o especialista em Normas sobre regras aplicáveis e enquadramento legal.",
            hooks=hooks,
            failure_error_function=None,
        ),
        criar_escala().as_tool(
            tool_name="parecer_escala",
            tool_description="Consulta o especialista em Escala sobre afastamentos da equipe e sugestão de datas.",
            hooks=hooks,
            failure_error_function=None,
        ),
        criar_financeiro().as_tool(
            tool_name="parecer_financeiro",
            tool_description="Consulta o especialista Financeiro sobre cálculo de venda de férias ou valor de diárias.",
            hooks=hooks,
            failure_error_function=None,
        ),
        *(tools_extras or []),
    ]

    return Agent(
        name="Coordenador",
        instructions=(
            "Você é o Coordenador da equipe de análise de pedidos de RH da PCDF. "
            "Sua responsabilidade é avaliar o pedido do servidor acionando as ferramentas de pareceres especializados "
            "(parecer_normas, parecer_escala, parecer_financeiro). "
            "Consulte apenas as ferramentas necessárias para o tipo de pedido (por exemplo, abono simples não requer cálculo financeiro). "
            "Consolide os pareceres recebidos em uma síntese clara e bem estruturada."
        ),
        tools=tools,
        model_settings=CONFIG,
    )
