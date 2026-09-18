# -*- coding: utf-8 -*-
"""
chat.py - Estado e helpers de chat do ChatFGV Streamlit

Separa a gestao do historico de mensagens e pequenos helpers de formato.
Nao depende de backend; apenas interface com st.session_state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st


def init_chat_state() -> None:
    """Inicializa o historico de mensagens no streamlit se ainda nao existir."""
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Oi. Sou o ChatFGV. Pergunte sobre o Dicionario "
                    "Historico-Biografico Brasileiro (DHBB) ou sobre dados "
                    "esticos: acidentes de transito, censo demografico e "
                    "contagem de traco."
                ),
                "extras": None,
            },
        ]
    else:
        # Garante estrutura minima por mensagem
        for msg in st.session_state.messages:
            if "extras" not in msg:
                msg["extras"] = None


def add_message(role: str, content: str, extras: Optional[Dict[str, Any]] = None) -> None:
    st.session_state.messages.append(
        {"role": role, "content": content, "extras": extras}
    )


def iter_messages() -> List[Dict[str, Any]]:
    return list(getattr(st.session_state, "messages", []))


def recent_assistant_excerpts(n: int = 3) -> List[str]:
    """Ultimas N respostas do assistente (para contexto futuro se necessario)."""
    out: List[str] = []
    for msg in reversed(iter_messages()):
        if msg.get("role") == "assistant" and msg.get("content"):
            out.append(msg["content"])
        if len(out) >= n:
            break
    return list(reversed(out))
