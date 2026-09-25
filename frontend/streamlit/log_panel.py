# -*- coding: utf-8 -*-
"""
log_panel.py - Painel de terminal + estado do backend (ChatFGV Streamlit)

- Coluna esquerda: terminal log estático (sem autorefresh) + estado resumido
  do backend (FAISS / SQL mock / Postgres).
- O chat fica na coluna direita.
- Não há auto-refresh: o log só muda quando a página é recarregada (manual)
  ou quando o Streamlit reexecuta por interação do usuário.
- Configurações não são visíveis, usa defaults: modo=Auto, mock=True, top_k=3,
  show_context=True.
"""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st


# ==================================================================
# CONFIGURACAO DO PAINEL DE LOG
# ==================================================================

LOG_LINES_MAX = 150
LOG_LINES_MIN = 20
LOG_LINES_MAX_INPUT = 500

# Caminho padrão do log do Streamlit (relativo ao repo da dupla).
_DEFAULT_LOG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "streamlit.log")
)


def _log_path_env() -> Optional[str]:
    """Caminho do log vindo de CHATFGV_LOG_PATH, se definido."""
    raw = os.environ.get("CHATFGV_LOG_PATH")
    if raw:
        return os.path.abspath(raw.strip())
    return None


def log_path() -> str:
    """Resolve o caminho do log a usar (variavel de ambiente > padrao)."""
    env_path = _log_path_env()
    if env_path and os.path.isfile(env_path):
        return env_path
    fallback = _DEFAULT_LOG_PATH
    if os.path.isfile(fallback):
        return fallback
    return _DEFAULT_LOG_PATH


# ==================================================================
# PAINEL
# ==================================================================

def log_panel(
    *,
    log_path_: Optional[str] = None,
) -> None:
    """Renderiza o painel esquerdo: titulo e log estático."""
    path = log_path() if log_path_ is None else log_path_
    state = st.session_state

    if "log_lines_qtd" not in state:
        state.log_lines_qtd = LOG_LINES_MAX

    st.title("Terminal")
    st.caption(f"Monitorando: {path}")
    st.caption("Log estático — recarregue a página para atualizar.")

    st.markdown("---")

    qty = st.number_input(
        "Quantidade de linhas",
        min_value=LOG_LINES_MIN,
        max_value=LOG_LINES_MAX_INPUT,
        value=state.log_lines_qtd,
        step=10,
        key="log_lines_qtd",
    )

    _render_log_content(path=path, lines_qty=qty)


def _render_log_content(*, path: str, lines_qty: int) -> None:
    """Lê o arquivo de log e renderiza as últimas `lines_qty` linhas."""
    if not os.path.isfile(path):
        st.warning(f"Arquivo de log nao encontrado: {path}")
        return

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            linhas = fh.readlines()
    except Exception as exc:
        st.error(f"Nao foi possivel ler o log: {exc}")
        return

    if not linhas:
        st.caption("O arquivo de log esta vazio.")
        return

    selecionadas = linhas[-max(lines_qty, 1):]
    texto = "".join(selecionadas)

    st.code(texto, language="text", line_numbers=True)
