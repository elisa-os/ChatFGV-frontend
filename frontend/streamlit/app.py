# -*- coding: utf-8 -*-
"""
app.py - ChatFGV Streamlit

Executa a interface de chat. Requer:
- frontend/streamlit/rag.py
- frontend/streamlit/sql.py
- frontend/streamlit/ui.py
- frontend/streamlit/chat.py

Modo de uso minimo (apenas recuperacao sem gerador final):
    streamlit run frontend/streamlit/app.py

Variaveis de ambiente relevantes:
- CHATFGV_INDEX       : caminho do indice FAISS (padrao: ./faiss_index)
- CHATFGV_DHBB        : caminho dos textos DHBB (padrao: ./DHBB/text)
- CHATFGV_PG_DSN      : DSN do Postgres (se quiser banco real)
- CHATFGV_SQL_MOCK    : "1" para usar banco mock
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

# ------------------------------------------------------------------
# PATH: garantir que o diretório dos modulos esteja importavel
# O app deve rodar a partir de qualquer cwd, entao forca o caminho
# do arquivo atual para que os imports locais (rag, sql, ui, chat)
# funcionem.
# ------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))

if HERE not in sys.path:
    sys.path.insert(0, HERE)

from rag import (
    StreamlitRAGStore,
    get_rag_status,
)
from sql import (
    get_sql_engine,
    list_tables,
    run_query,
    describe_schema_tables,
)

from ui import (
    sidebar_config,
    show_db_status,
    render_message,
    render_status_erro,
)
from chat import (
    init_chat_state,
    add_message,
)


# ==================================================================
# CONFIGURACAO E ESTADO
# ==================================================================

def init_state() -> None:
    state = st.session_state
    if "messages" not in state:
        state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Oi. Sou o ChatFGV. Pode me perguntar sobre o Dicionario "
                    "Historico-Biografico Brasileiro (DHBB) ou sobre dados "
                    "esticos: acidentes de transito, censo demografico e "
                    "contagem de traco."
                ),
                "extras": None,
            },
        ]
    if "rag" not in state:
        state.rag = None
    if "sql_engine" not in state:
        state.sql_engine = None
    if "show_context" not in state:
        state.show_context = True
    if "config" not in state:
        state.config = {}


# ==================================================================
# GERADOR DE RESPOSTA (placeholder)
# ==================================================================
# Esta versao ainda nao tem LLM integrado. A funcao response_generator
# deve ser preenchida pela dupla para gerar resposta a partir do
# contexto recuperado (DHBB) e/ou resultado SQL.
# ==================================================================

def response_generator(
    usuario: str,
    contexto: str,
    fontes: List[str],
    sql_query: Optional[str] = None,
    sql_result: Optional[Any] = None,
) -> str:
    """
    Placeholder: retorna o que foi recuperado a ser completado com
    gerador de linguagem natural (Copilot/LLM/ API).

    Hoje: resume o que foi recuperado, lista fontes e, se houver,
    mostra query + resultado.
    """
    parts = []
    parts.append(f"Pergunta: {usuario}")

    if contexto.strip():
        partes_c = [p for p in contexto.split("\n") if p.strip()]
        if partes_c:
            partes_c_short = partes_c[:3]
            parts.append("\nContexto recuperado (resumo):")
            for p in partes_c_short:
                parts.append("- " + p[:3000])
            if len(partes_c) > 3:
                parts.append(
                    f"... ({len(partes_c)} verbetes recuperados no total)"
                )
        else:
            parts.append("Contexto recuperado: (nenhum verrete encontrado)")

    if fontes:
        parts.append("\nFontes DHBB: " + ", ".join(fontes))

    if sql_query:
        parts.append(f"\nQuery SQL gerada:\n{sql_query}")
    if sql_result is not None:
        parts.append(
            "\nResultado da query (preview): "
            + f"{len(sql_result)} linhas"
            if isinstance(sql_result, list)
            else str(sql_result)
        )

    if not contexto.strip() and not sql_query:
        parts.append(
            "\nNão encontrei informação no DHBB nem no banco estruturado "
            "para esta pergunta. Tente reformular ou escolher outro modo."
        )

    return "\n".join(parts)


# ==================================================================
# FLUXO PRINCIPAL
# ==================================================================

def main() -> None:
    st.set_page_config(
        page_title="ChatFGV",
        page_icon=":speech_balloon:",
        layout="wide",
    )
    st.title("ChatFGV")
    st.caption(
        "Interface de pergunta sobre bases publicas brasileiras (DHBB + SQL)"
    )

    init_state()
    cfg = sidebar_config()
    st.session_state.config = cfg
    st.session_state.show_context = cfg["show_context"]

    # Estado do backend (somente leitura na sidebar)
    faiss_ok, index_path, dhbb_path = get_rag_status()
    show_db_status(faiss_ok, False, cfg["sql_mock"])

    # Carregar backend sob demanda
    rag = state_rag(cfg)
    sql_engine = state_sql(cfg)

    if cfg["sql_mock"] and sql_engine is not None:
        with st.sidebar:
            st.code(
                "Tabelas mock:\n" + "\n".join(list_tables(sql_engine)),
                language="text",
            )

    # Renderizar historico
    for msg in st.session_state.messages:
        extras_ = _adapt_extras(msg, cfg, sql_engine, cfg["sql_mock"])
        render_message(msg["role"], msg["content"], extras_)

    # Entrada do usuario
    if usuario := st.chat_input("Digite sua pergunta..."):
        add_message("user", usuario)
        st.chat_message("user").markdown(usuario)

        start = time.time()
        resposta, extras = processar_pedido(
            usuario=usuario,
            cfg=cfg,
            rag=rag,
            sql_engine=sql_engine,
        )
        elapsed = round(time.time() - start, 2)

        add_message("assistant", resposta, extras)
        render_message("assistant", resposta, extras)
        st.caption(f" Tempo de resposta: {elapsed}s")


def state_rag(cfg: Dict[str, Any]) -> Optional[StreamlitRAGStore]:
    state = st.session_state
    if state.rag is not None:
        return state.rag
    faiss_ok, index_path, dhbb_path = get_rag_status()
    if not faiss_ok:
        state.rag = None
        return None
    try:
        store = StreamlitRAGStore(
            index=index_path,
            text_root=dhbb_path,
            top_k=cfg["top_k"],
            show_context=cfg["show_context"],
        )
    except Exception as exc:
        state.rag = None
        render_status_erro("DHBB", f"nao foi possivel carregar o indice: {exc}")
        return None
    state.rag = store
    return store


def state_sql(cfg: Dict[str, Any]) -> Optional[Any]:
    state = st.session_state
    if state.sql_engine is not None:
        return state.sql_engine
    try:
        engine = get_sql_engine(force_mock=cfg["sql_mock"])
    except Exception as exc:
        render_status_erro("SQL", f"nao foi possivel conectar ao Postgres: {exc}")
        state.sql_engine = None
        return None
    state.sql_engine = engine
    return engine


def _adapt_extras(
    msg: Dict[str, Any],
    cfg: Dict[str, Any],
    sql_engine: Optional[Any],
    sql_mock: bool,
):
    extras_raw = msg.get("extras") or {}
    extras = dict(extras_raw)

    if sql_engine is not None and msg["role"] == "assistant" and "sql_result" in extras:
        try:
            df = extras["sql_result"]
            if isinstance(df, str) and df.strip():
                extras["sql_result"] = df
        except Exception:
            pass
    return msg, extras


def processar_pedido(
    usuario: str,
    cfg: Dict[str, Any],
    rag: Optional[StreamlitRAGStore],
    sql_engine: Optional[Any],
) -> tuple:
    """
    Decide modo e orquestra recuperacao (DHBB) e/ou SQL.
    Retorna (texto_resposta, extras).
    """
    modo = cfg["modo"]

    extras: Dict[str, Any] = {}

    selecionar_sql = False
    selecionar_dhbb = False

    if modo == "DHBB":
        selecionar_dhbb = True
    elif modo == "SQL":
        selecionar_sql = True
    else:
        # Auto
        if _elegivel_sql(usuario):
            selecionar_sql = True
        else:
            selecionar_dhbb = True

    sql_query = None
    sql_result = None

    if selecionar_sql and sql_engine is not None:
        sql_query, sql_result = gerar_sql(
            usuario=usuario,
            cfg=cfg,
            engine=sql_engine,
        )
        if sql_query:
            extras["sql_query"] = sql_query
            extras["sql_result"] = sql_result
            return sql_resolver_usuario(usuario, sql_query, sql_result)

    if selecionar_dhbb and rag is not None:
        try:
            resultado = rag.search(usuario)
        except Exception as exc:
            texto = (
                f"Nao foi possivel buscar no DHBB: {exc}. "
                "Tente novamente ou use outro modo."
            )
            extras["erro"] = str(exc)
            return texto, extras

        contexto = resultado.get("contexto", "")
        fontes = resultado.get("fontes", [])
        extras["contexto"] = contexto
        extras["fonte" if len(fontes) == 1 else "fontes"] = (
            [fontes[0]] if len(fontes) == 1 else fontes
        )
        if len(fontes) == 1:
            extras["fonte"] = fontes[0]

        if not contexto.strip():
            extras["nao_encontrado"] = (
                "Nao encontrei verbetes no DHBB para esta pergunta. "
                "Tente reformular ou aumentar top-k."
            )

        resposta = response_generator(usuario, contexto, fontes, sql_query, sql_result)
        return resposta, extras

    if not selecionar_dhbb and not selecionar_sql:
        return (
            "Não foi possivel decidir o backend para esta pergunta. "
            "Tente definir o modo manualmente na sidebar.",
            {},
        )

    return (
        "Não foi possivel processar a pergunta. Verifique a configuracao do backend.",
        {},
    )


def sql_resolver_usuario(usuario: str, sql_query: str, sql_result: Any) -> tuple:
    """
    Monta a resposta a partir da query+resultado SQL.
    Placeholder: em versão final, aqui entra o Agent 2 (gerador final).
    """
    extras: Dict[str, Any] = {
        "sql_query": sql_query,
        "sql_result": sql_result,
    }

    n_rows = len(sql_result) if isinstance(sql_result, list) else 0
    response = response_generator(
        usuario=usuario,
        contexto="",
        fontes=[],
        sql_query=sql_query,
        sql_result=sql_result,
    )
    return response, extras


def gerar_sql(usuario: str, cfg: Dict[str, Any], engine: Any) -> tuple:
    """
    Agent 1 (geracao de query SQL) - placeholder.
    Em versao final, aqui entra o LLM/agente que olha o schema e
    produz a query. Hoje retorna (
        query gerada por placeholder ou None,
        resultado da query (DataFrame ou list)
    )
    """
    try:
        tables = list_tables(engine)
        schema_desc = describe_schema_tables(tables)
    except Exception:
        tables = []
        schema_desc = "n/a"

    # Placeholder: montamos uma query de exemplo baseada em palavras chave.
    query = _placeholder_sql_from_keywords(usuario, tables)
    if query is None:
        return None, None

    try:
        result = run_query(engine, query)
    except Exception as exc:
        render_status_erro("SQL", f"nao foi possivel executar a query: {exc}")
        return query, []

    if isinstance(result, list):
        result_list: Any = result
    else:
        result_list = (
            result.to_dict(orient="records") if not result.empty else []
        )
    return query, result_list


def _placeholder_sql_from_keywords(usuario: str, tables: List[str]) -> Optional[str]:
    """
    Placeholder to produce a SQL query based on keywords.
    Saves implementation effort before integrating Agent 1 (LLM).
    """
    n = usuario.lower()
    for tbl in tables:
        if "acidentes_transito" in tbl:
            if "acidente" in n or "transito" in n or "via" in n:
                return f"SELECT COUNT(*) FROM {tbl}"
            if "causa" in n:
                return f"SELECT causa_acidente, COUNT(*) FROM {tbl} GROUP BY causa_acidente ORDER BY COUNT(*) DESC LIMIT 5"
            if "estado" in n or "uf" in n or "regiao" in n:
                return f"SELECT br, COUNT(*) FROM {tbl} GROUP BY br ORDER BY COUNT(*) DESC LIMIT 5"
        if "censo" in tbl and "setores" in tbl:
            if "populacao" in n or "habitante" in n or "quantos" in n:
                return f"SELECT SUM(populacao) AS populacao FROM {tbl}"
            if "estado" in n or "uf" in n:
                return f"SELECT NM_UF, SUM(populacao) AS populacao FROM {tbl} GROUP BY NM_UF ORDER BY populacao DESC LIMIT 5"
        if "contagem" in tbl:
            if "traco" in n or "veiculo" in n or "fluxo" in n:
                return f"SELECT sg_uf, SUM(vmda_c) AS volume FROM {tbl} GROUP BY sg_uf ORDER BY volume DESC LIMIT 5"
    return None


def _elegivel_sql(usuario: str) -> bool:
    """
    Heuristica simples para decidir se a pergunta parece ser sobre dados
    estruturados (SQL) ou biografica/historica (DHBB).
    """
    n = usuario.lower()
    sql_signals = [
        "acidente", "transito", "censo", "populacao", "habitante",
        "quantos", "quantas", "percentual", "estat", "traco", "contagem",
        "geograf", "estad", "mortalidade", "alfabetiz",
    ]
    dhbb_signals = [
        "quem", "quem foi", "quem e", "biografia", "poligrafo",
        "histori", "governo", "presidente", "revoluc", "partido",
        "constituinte", "senador", "deputado", "ministerio",
    ]
    if any(s in n for s in sql_signals):
        return True
    if any(s in n for s in dhbb_signals):
        return False
    # Padrao: DHBB
    return False


# ==================================================================
# ENTRY POINT
# ==================================================================

if __name__ == "__main__":
    main()
