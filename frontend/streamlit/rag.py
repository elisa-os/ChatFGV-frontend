# -*- coding: utf-8 -*-
"""
rag.py - Módulo de busca RAG do ChatFGV

Responsabilidade: recuperar contexto dos verbetes do DHBB para responder
às perguntas do usuário.

Implementação atual: busca por TF-IDF + similaridade de cosseno usando
sklearn. Esta abordagem não depende de modelos de embedding pesados (como
Serafim) nem de índices FAISS pré-computados. Funciona diretamente com os
arquivos de texto do DHBB.

Dependências: scikit-learn, PyYAML (ambos já estão nas dependências do projeto).
"""

from __future__ import annotations

import glob
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ------------------------------------------------------------------
# Configuração via variáveis de ambiente
# ------------------------------------------------------------------
DHBB_PATH = os.environ.get(
    "CHATFGV_DHBB",
    os.path.join(os.getcwd(), "DHBB", "text"),
)


# ------------------------------------------------------------------
# Cache global do vectorizer (carregado uma vez na primeira busca)
# ------------------------------------------------------------------
_vectorizer: Optional[TfidfVectorizer] = None
_corpus_tfidf = None  # matriz TF-IDF da corpus inteira
_corpus_docs: List[Dict[str, Any]] = []  # metadados de cada documento
_corpus_ready = False
_corpus_error: Optional[str] = None


def _limpar_texto(texto: str) -> str:
    """
    Limpa o texto do verbete removendo YAML frontmatter e normalizando.

    O formato dos verbetes do DHBB é:
        ---
        caminho: ...
        titulo: ...
        ---
        texto do verbete...
    """
    # Remove YAML frontmatter (entre os primeiros ---)
    texto_limpo = re.sub(r'^---\s*\n.*?\n---\s*\n', '', texto, flags=re.DOTALL)
    # Remove quebras de linha múltiplas excessivas
    texto_limpo = re.sub(r'\n{3,}', '\n\n', texto_limpo)
    return texto_limpo.strip()


def _extrair_metadados(texto: str) -> Dict[str, Any]:
    """
    Extrai metadados do frontmatter YAML do verbete.
    """
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', texto, re.DOTALL)
    if not match:
        return {}

    yaml_text = match.group(1)
    try:
        return yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return {}


def _carregar_corpus():
    """
    Carrega todos os verbetes do DHBB e constrói o vetor TF-IDF.

    Esta operação é feita uma única vez e o resultado é cacheado globalmente.
    Para ~7.863 documentos, a construção leva alguns segundos.
    """
    global _vectorizer, _corpus_tfidf, _corpus_docs, _corpus_ready, _corpus_error

    if _corpus_ready:
        return

    t0 = time.time()
    print(f"[RAG] Carregando corpus DHBB de {DHBB_PATH}...", flush=True)

    try:
        # Encontrar todos os arquivos .text
        text_files = sorted(glob.glob(os.path.join(DHBB_PATH, "**/*.text"), recursive=True))
        if not text_files:
            raise FileNotFoundError(
                f"Nenhum arquivo .text encontrado em {DHBB_PATH}. "
                f"Verifique se CHATFGV_DHBB está configurado corretamente."
            )

        print(f"[RAG] Encontrados {len(text_files)} verbetes. Lendo...", flush=True)

        docs_content = []
        _corpus_docs = []

        for file_path in text_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()
            except Exception as exc:
                print(f"[RAG] Aviso: erro ao ler {file_path}: {exc}", flush=True)
                continue

            # Limpar texto e extrair metadados
            content = _limpar_texto(raw_content)
            metadata = _extrair_metadados(raw_content)

            # Armazenar documento
            docs_content.append(content)
            _corpus_docs.append({
                "file_path": file_path,
                "source": os.path.basename(file_path),
                "metadata": metadata,
                "content": content,
            })

        if not docs_content:
            raise ValueError("Nenhum documento válido pôde ser lido.")

        print(f"[RAG] {len(docs_content)} documentos carregados. Construindo TF-IDF...", flush=True)

        # Construir vetorizador TF-IDF e transformar corpus
        _vectorizer = TfidfVectorizer(
            max_features=10000,
            stop_words=None,  # Não temos lista de stop words em português por padrão
            ngram_range=(1, 2),  # Unigramas e bigramas
            min_df=2,  # Ignorar termos que aparecem em menos de 2 documentos
            max_df=0.95,  # Ignorar termos que aparecem em mais de 95% dos documentos
            sublinear_tf=True,  # Aplicar log(1 + tf) para reduzir impacto de termos muito frequentes
        )

        _corpus_tfidf = _vectorizer.fit_transform(docs_content)

        _corpus_ready = True
        elapsed = time.time() - t0
        print(
            f"[RAG] Corpus pronto: {len(docs_content)} docs, "
            f"{_corpus_tfidf.shape[1]} features TF-IDF, "
            f"{elapsed:.1f}s",
            flush=True,
        )

    except Exception as exc:
        _corpus_error = f"Falha ao carregar corpus: {exc}"
        print(f"[RAG] ERRO: {_corpus_error}", flush=True)


def _buscar_similarity_search(query: str, top_k: int = 2) -> Tuple[str, List[str], int]:
    """
    Executa busca por similaridade de cosseno entre a query e o corpus.

    Retorna (contexto, fontes, num_docs).
    contexto é uma string com os textos concatenados.
    fontes é uma lista de nomes de arquivos.
    num_docs é o número de documentos encontrados.
    """
    if not _corpus_ready or _corpus_tfidf is None or _vectorizer is None:
        raise RuntimeError(f"Corpus não carregado: {_corpus_error or 'desconhecido'}")

    # Vectorizar a query
    query_tfidf = _vectorizer.transform([query])

    # Calcular similaridade de cosseno
    similarities: Any = cosine_similarity(query_tfidf, _corpus_tfidf).flatten()

    # Obter índices dos top-k documentos mais similares
    top_indices = similarities.argsort()[::-1][:top_k]

    # Coletar contexto e fontes
    context_parts: List[str] = []
    sources: List[str] = []

    for idx in top_indices:
        sim_score = float(similarities[idx])
        if sim_score <= 0:
            continue  # Ignorar documentos com similaridade zero

        doc = _corpus_docs[idx]
        context_parts.append(doc["content"])
        sources.append(doc["source"])

    context = "\n\n---\n\n".join(context_parts) if context_parts else ""
    num_docs = len(context_parts)

    return context, sources, num_docs


class StreamlitRAGStore:
    """
    Armazenamento de recuperação de contexto para o Streamlit.

    Esta implementação usa TF-IDF + similaridade de cosseno para buscar
    documentos relevantes no DHBB. Não depende de modelos de embedding
    pesados (Serafim) nem de índices FAISS pré-computados.

    Uso:
        rag = StreamlitRAGStore(top_k=3)
        resultado = rag.search("Quem foi Getúlio Vargas?")
        # resultado: {"contexto": "...", "fontes": [...], "num_docs": N, ...}
    """

    def __init__(
        self,
        index: Optional[str] = None,  # Não usado nesta implementação
        text_root: Optional[str] = None,
        top_k: int = 2,
        show_context: bool = True,
    ) -> None:
        """
        Inicializa o RAGStore.

        Args:
            index: Ignorado nesta implementação (parâmetro mantido para
                   compatibilidade com chamadas existentes).
            text_root: Caminho para a raiz dos textos do DHBB. Se None,
                       usa CHATFGV_DHBB ou o padrão ./DHBB/text.
            top_k: Número de documentos a recuperar por busca.
            show_context: Se True, o contexto recuperado será exibido na
                         interface.
        """
        global DHBB_PATH

        if text_root is not None:
            DHBB_PATH = text_root

        self.top_k = top_k
        self.show_context = show_context
        self.index = index  # Armazenado mas não usado

        # Garantir que o corpus está carregado
        _carregar_corpus()

        self._loaded = _corpus_ready and _corpus_error is None

    def search(self, query: str) -> Dict[str, Any]:
        """
        Recupera documentos relevantes do DHBB para a pergunta dada.

        Args:
            query: A pergunta/pergunta do usuário em português.

        Returns:
            Dict com as chaves:
                - contexto: Texto concatenado dos documentos recuperados
                - fontes: Lista de nomes de arquivos das fontes
                - num_docs: Número de documentos recuperados
                - tempo_s: Tempo de execução da busca em segundos
                - top_k: Número de documentos solicitados
                - erro (opcional): Mensagem de erro se a busca falhou
        """
        t0 = time.time()

        try:
            if not _corpus_ready:
                if _corpus_error:
                    return {
                        "contexto": "",
                        "fontes": [],
                        "num_docs": 0,
                        "tempo_s": round(time.time() - t0, 2),
                        "top_k": self.top_k,
                        "erro": _corpus_error,
                    }
                else:
                    return {
                        "contexto": "",
                        "fontes": [],
                        "num_docs": 0,
                        "tempo_s": round(time.time() - t0, 2),
                        "top_k": self.top_k,
                        "erro": "corpus não carregado",
                    }

            if not query or not query.strip():
                return {
                    "contexto": "",
                    "fontes": [],
                    "num_docs": 0,
                    "tempo_s": round(time.time() - t0, 2),
                    "top_k": self.top_k,
                    "erro": "query vazia",
                }

            contexto, fontes, num_docs = _buscar_similarity_search(
                query.strip(), self.top_k
            )

            return {
                "contexto": contexto,
                "fontes": fontes,
                "num_docs": num_docs,
                "tempo_s": round(time.time() - t0, 2),
                "top_k": self.top_k,
            }

        except Exception as exc:
            return {
                "contexto": "",
                "fontes": [],
                "num_docs": 0,
                "tempo_s": round(time.time() - t0, 2),
                "top_k": self.top_k,
                "erro": f"falha na busca: {exc}",
            }


def get_rag_status() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Retorna (corpus_ok, dhbb_path, modelo_tipo).

    Verifica se o corpus DHBB está disponível e carregado.
    """
    dhbb_path = DHBB_PATH
    corpus_ok = _corpus_ready and _corpus_error is None

    modelo_tipo = "TF-IDF + similaridade de cosseno (sklearn)"

    return (corpus_ok, dhbb_path, modelo_tipo)
