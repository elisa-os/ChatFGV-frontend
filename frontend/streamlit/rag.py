# -*- coding: utf-8 -*-
"""
rag.py - Módulo de busca RAG do ChatFGV

Responsabilidade: carregar índice FAISS + embedding e recuperar
contexto dos verbetes do DHBB.

Este arquivo é um placeholder mínimo para permitir que o app
Streamlit inicie sem erro de import. A implementação completa
deve:
- carregar o modelo de embedding (sentence-transformers)
- carregar o índice FAISS
- executar similarity_search e retornar (contexto, fontes)

Dependências: sentence-transformers, faiss-cpu, langchain-community,
langchain-text-splitters, PyYAML.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple


# ------------------------------------------------------------------
# Configuracao via variaveis de ambiente (compativeis com o projeto)
# ------------------------------------------------------------------
INDEX_PATH = os.environ.get("CHATFGV_INDEX", os.path.join(os.getcwd(), "faiss_index"))
DHBB_PATH = os.environ.get("CHATFGV_DHBB", os.path.join(os.getcwd(), "DHBB", "text"))


def get_rag_status() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Retorna (faiss_ok, index_path, dhbb_path).

    Em implementacao completa, verificaria:
    - se INDEX_PATH existe e contem index.faiss
    - se o modelo de embedding esta disponivel
    """
    faiss_ok = os.path.isdir(INDEX_PATH) and os.path.isfile(os.path.join(INDEX_PATH, "index.faiss"))
    return (faiss_ok, INDEX_PATH, DHBB_PATH)


class StreamlitRAGStore:
    """
    Usado pelo app. Mantido aqui por exaustao da dupla.

    Se futuro permitir integracao de LLM/agentes, esta classe pode ser
    estendida para carregar o vetor index e retornar contexto real.
    """

    def __init__(
        self,
        index: Optional[str] = None,
        text_root: Optional[str] = None,
        top_k: int = 2,
        show_context: bool = True,
    ) -> None:
        self.index = index or INDEX_PATH
        self.text_root = text_root or DHBB_PATH
        self.top_k = top_k
        self.show_context = show_context
        # Placeholder: sem carga real de índice por enquanto
        self._loaded = False

    def search(self, query: str) -> Dict[str, Any]:
        """
        Placeholder: retorna contexto vazio + fontes vazias.

        Em implementacao completa, executa a busca semantica.
        """
        return {
            "contexto": "",
            "fontes": [],
            "num_docs": 0,
            "tempo_s": 0.0,
            "top_k": self.top_k,
        }
