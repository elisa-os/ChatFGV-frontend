# -*- coding: utf-8 -*-
"""
app.py - ChatFGV Streamlit (layout em duas colunas)

- Coluna esquerda: painel de terminal estático (log_panel.py)
- Coluna direita: chat com histórico

Requer:
- frontend/streamlit/rag.py
- frontend/streamlit/sql.py
- frontend/streamlit/ui.py
- frontend/streamlit/chat.py
- frontend/streamlit/log_panel.py

Modo de uso minimo:
    streamlit run frontend/streamlit/app.py

Variaveis de ambiente relevantes:
- CHATFGV_INDEX       : caminho do indice FAISS (padrao: ./faiss_index)
- CHATFGV_DHBB        : caminho dos textos DHBB (padrao: ./DHBB/text)
- CHATFGV_PG_DSN      : DSN do Postgres (se quiser banco real)
- CHATFGV_SQL_MOCK    : "1" para usar banco mock
- CHATFGV_LOG_PATH    : caminho do arquivo de log a monitorar
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))

if HERE not in sys.path:
    sys.path.insert(0, HERE)

from rag import (
    StreamlitRAGStore,
)
from sql import (
    get_sql_engine,
    list_tables,
    run_query,
)

from ui import (
    render_message,
    render_status_erro,
)
from chat import (
    add_message,
)
from log_panel import log_panel


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
        state.config = {
            "modo": "Auto",
            "top_k": 3,
            "sql_mock": True,
            "show_context": True,
        }


# ==================================================================
# GERADOR DE RESPOSTA (placeholder)
# ==================================================================

def response_generator(
    usuario: str,
    contexto: str,
    fontes: List[str],
    sql_query: Optional[str] = None,
    sql_result: Optional[Any] = None,
) -> str:
    partes = [f"Pergunta: {usuario}"]

    if contexto.strip():
        linhas = [p for p in contexto.split("\n") if p.strip()]
        if linhas:
            partes.append("\nContexto recuperado (resumo):")
            for p in linhas[:3]:
                partes.append("- " + p[:3000])
            if len(linhas) > 3:
                partes.append(
                    f"... ({len(linhas)} verbetes recuperados no total)"
                )
        else:
            partes.append("Contexto recuperado: (nenhum verrete encontrado)")

    if fontes:
        partes.append("\nFontes DHBB: " + ", ".join(fontes))

    if sql_query:
        partes.append(f"\nQuery SQL gerada:\n{sql_query}")
    if sql_result is not None:
        if isinstance(sql_result, list):
            partes.append(
                "\nResultado da query (preview): " + f"{len(sql_result)} linhas"
            )
        else:
            partes.append("\nResultado da query (preview): " + str(sql_result))

    if not contexto.strip() and not sql_query:
        partes.append(
            "\nNão encontrei informação no DHBB nem no banco estruturado "
            "para esta pergunta. Tente reformular ou escolher outro modo."
        )

    return "\n".join(partes)


# ==================================================================
# FLUXO PRINCIPAL (duas colunas)
# ==================================================================

def main() -> None:
    st.set_page_config(
        page_title="ChatFGV",
        page_icon=":speech_balloon:",
        layout="wide",
    )

    init_state()

    # Backend SQL sob demanda
    sql_engine = state_sql(st.session_state.config)

    # Container com duas colunas
    col_e, col_d = st.columns([1, 2], gap="medium")

    with col_e:
        log_panel()

    with col_d:
        st.title("ChatFGV")
        st.caption(
            "Interface de pergunta sobre bases publicas brasileiras "
            "(DHBB + SQL)"
        )

        if st.session_state.config["sql_mock"] and sql_engine is not None:
            with st.expander("Tabelas disponiveis (mock)"):
                st.code(
                    "Tabelas mock:\n" + "\n".join(list_tables(sql_engine)),
                    language="text",
                )

        # Historico
        for msg in st.session_state.messages:
            extras_ = _adapt_extras(msg, sql_engine, st.session_state.config["sql_mock"])
            render_message(msg["role"], msg["content"], extras_)

        # Input do usuario
        if usuario := st.chat_input("Digite sua pergunta..."):
            add_message("user", usuario)
            st.chat_message("user").markdown(usuario)

            start = time.time()
            resposta, extras = processar_pedido(
                usuario=usuario,
                rag=state_rag(st.session_state.config),
                sql_engine=sql_engine,
            )
            elapsed = round(time.time() - start, 2)

            add_message("assistant", resposta, extras)
            render_message("assistant", resposta, extras)
            st.caption(f" Tempo de resposta: {elapsed}s")


# ==================================================================
# BACKEND
# ==================================================================

def state_rag(cfg: Dict[str, Any]) -> Optional[StreamlitRAGStore]:
    state = st.session_state
    if state.rag is not None:
        return state.rag
    try:
        store = StreamlitRAGStore(
            index=cfg.get("index_path"),
            text_root=cfg.get("text_root"),
            top_k=cfg.get("top_k", 3),
            show_context=cfg.get("show_context", True),
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
        engine = get_sql_engine(force_mock=cfg.get("sql_mock", True))
    except Exception as exc:
        render_status_erro("SQL", f"nao foi possivel conectar ao Postgres: {exc}")
        state.sql_engine = None
        return None
    state.sql_engine = engine
    return engine


def _adapt_extras(
    msg: Dict[str, Any],
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
    return extras


# ==================================================================
# PROCESSAMENTO
# ==================================================================

def processar_pedido(
    usuario: str,
    rag: Optional[StreamlitRAGStore],
    sql_engine: Optional[Any],
) -> tuple:
    """Decide modo e orquestra recuperacao (DHBB) e/ou SQL."""
    extras: Dict[str, Any] = {}

    # Usa modo default se nao tiver sido configurado
    modo = st.session_state.config.get("modo", "Auto")
    if modo == "DHBB":
        selecionar_dhbb = True
        selecionar_sql = False
    elif modo == "SQL":
        selecionar_sql = True
        selecionar_dhbb = False
    else:
        # Auto
        if _elegivel_sql(usuario):
            selecionar_sql = True
            selecionar_dhbb = False
        else:
            selecionar_sql = False
            selecionar_dhbb = True

    sql_query = None
    sql_result = None

    if selecionar_sql and sql_engine is not None:
        sql_query, sql_result = gerar_sql(
            usuario=usuario,
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
    """Monta a resposta a partir da query+resultado SQL."""
    extras: Dict[str, Any] = {
        "sql_query": sql_query,
        "sql_result": sql_result,
    }

    response = response_generator(
        usuario=usuario,
        contexto="",
        fontes=[],
        sql_query=sql_query,
        sql_result=sql_result,
    )
    return response, extras


def gerar_sql(usuario: str, engine: Any) -> tuple:
    """Agent 1 (geracao de query SQL) - placeholder."""
    try:
        tables = list_tables(engine)
    except Exception:
        tables = []

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
    """Placeholder to produce a SQL query based on keywords."""
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
    """Heuristica simples para decidir se a pergunta parece ser sobre SQL."""
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
