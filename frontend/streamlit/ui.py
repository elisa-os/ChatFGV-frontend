# -*- coding: utf-8 -*-
"""
ui.py - Componentes de interface do ChatFGV Streamlit

Responsabilidades:
- Sidebar: configuracoes, modo de uso, estado do backend
- Componentes de apresentacao de resposta: fonte, contexto recuperado, query SQL
- Tela principal: cabeçalho, status, instruções de uso
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st


def sidebar_config() -> Dict[str, Any]:
    """
    Sidebar de configuracao.
    Retorna dict com:
      - modo: "DHBB" | "SQL" | "Auto"
      - top_k: int
      - sql_mock: bool
      - show_context: bool
    """
    st.sidebar.title("Configuracoes")
    st.sidebar.markdown("---")

    modo = st.sidebar.radio(
        "Modo de consulta",
        options=["Auto", "DHBB", "SQL"],
        index=0,
        help=(
            "Auto tenta decidir entre DHBB e SQL pela pergunta. "
            "DHBB usa busca semantica no dicionario historico-biografico. "
            "SQL usa agente de query no Postgres."
        ),
    )

    top_k = st.sidebar.slider(
        "Doc. DHBB recuperados (top-k)",
        min_value=1,
        max_value=10,
        value=3,
        help="Quantos verbetes recuperar na busca semantica.",
    )

    sql_mock = st.sidebar.checkbox(
        "Usar banco mock (sem Postgres)",
        value=True,
        help="Se marcado, o ChatFGV usa dados ficticios para nao exigir Postgres.",
    )
    if not sql_mock:
        st.sidebar.caption("Banco real: configure CHATFGV_PG_DSN para usar Postgres.")

    show_context = st.sidebar.checkbox(
        "Mostrar contexto recuperado (DHBB)",
        value=True,
        help="Exibe os verbetes recuperados antes da resposta.",
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "ChatFGV — hackathon FGV / dados publicos. "
        "DHBB = Dicionario Historico-Biografico Brasileiro (FGV/CPDOC)."
    )

    return {
        "modo": modo,
        "top_k": top_k,
        "sql_mock": sql_mock,
        "show_context": show_context,
    }


def show_db_status(faiss_ok: bool, pg_ok: bool, sql_mock: bool) -> None:
    """Mostra estado do backend na sidebar."""
    st.sidebar.subheader("Estado do backend")
    faiss_label = "OK (indice FAISS)" if faiss_ok else "INDICE NAO ENCONTRADO"
    st.sidebar.caption(f"DHBB (FAISS): {faiss_label}")

    if sql_mock:
        st.sidebar.caption("SQL: MODO MOCK")
    elif pg_ok:
        st.sidebar.caption("SQL: Postgres conectado")
    else:
        st.sidebar.caption("SQL: Postgres NAO CONECTADO")


def render_message(role: str, content: str, extras: Optional[Dict[str, Any]] = None) -> None:
    """
    Renderiza uma mensagem de chat com suporte a extras:
      - fonte / fontes
      - contexto (DHBB)
      - sql_query / sql_result (paraSQL)

    role: "user" | "assistant"
    """
    with st.chat_message(role):
        st.markdown(content)

        if extras:
            if role == "assistant":
                _render_extras(extras)


def _render_extras(extras: Dict[str, Any]) -> None:
    if not isinstance(extras, dict):
        extras = {}
    fonte = extras.get("fonte") or extras.get("fontes")
    if fonte:
        if isinstance(fonte, list):
            label = "Fontes DHBB"
            value = ", ".join(fonte)
        else:
            label = "Fonte DHBB"
            value = fonte
        st.caption(f"**{label}**: {value}")

    contexto = extras.get("contexto")
    if contexto and st.session_state.get("show_context", True):
        with st.expander("Ver contexto recuperado (DHBB)"):
            st.markdown(contexto)

    sql_query = extras.get("sql_query")
    if sql_query:
        with st.expander("Ver query SQL gerada"):
            st.code(sql_query, language="sql")

    sql_result = extras.get("sql_result")
    if sql_result is not None:
        with st.expander("Ver resultado da query"):
            if isinstance(sql_result, list):
                st.dataframe(sql_result)
            else:
                st.dataframe(sql_result, use_container_width=True)

    not_found = extras.get("nao_encontrado")
    if not_found:
        st.warning(not_found)


def render_status_erro(tipo: str, detail: str) -> None:
    """Exibir erro resumido na tela principal."""
    st.error(f"Erro no {tipo}: {detail}")


def render_main_header() -> None:
    """Renderiza o cabeçalho principal com título e descrição."""
    st.title("ChatFGV")
    st.markdown(
        """
        **ChatFGV** é uma interface de pergunta sobre bases públicas brasileiras.

        - **DHBB**: Dicionário Histórico-Biográfico Brasileiro (FGV/CPDOC) — busca semântica em verbetes biográficos e históricos.
        - **SQL**: dados estruturados (acidentes de trânsito, censo demográfico, contagem de tráfego) via agente de query.
        """
    )
    st.caption("Modo atual: dados fictícios (mock) para SQL — sem dependência de Postgres.")

    st.markdown("---")


def render_instructions() -> None:
    """Renderiza instruções rápidas na tela principal."""
    st.subheader("Como usar")
    st.markdown(
        """
        1. Escolha o **modo de consulta** na sidebar (Auto, DHBB ou SQL).
        2. Digite sua pergunta no campo de chat.
        3. Se usar **DHBB**, os verbetes recuperados aparecem como contexto — você pode expandir para ver o original.
        4. Se usar **SQL**, a query gerada e o resultado mostram-se em expansores na resposta.
        5. Use a **transparência**: fontes do DHBB e query SQL são sempre exibidas.
        """
    )
