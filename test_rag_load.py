#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste rápido: verifica se o modelo Serafim pode ser carregado.
"""
import os
import sys

os.environ['CHATFGV_INDEX'] = '/home/elisaos/fgv/6periodo/cepesp_data/ChatFGV-frontend/faiss_index'

print("Iniciando teste de carregamento...", flush=True)
print(f"Working dir: {os.getcwd()}", flush=True)
print(f"Python: {sys.executable}", flush=True)

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    print("Imports OK", flush=True)
except Exception as e:
    print(f"Falha no import: {e}", flush=True)
    sys.exit(1)

print("Criando embeddings...", flush=True)
try:
    emb = HuggingFaceEmbeddings(model_name="PORTULAN/serafim-900m-portuguese-pt-sentence-encoder-ir")
    print("HuggingFaceEmbeddings criado", flush=True)
except Exception as e:
    print(f"Falha no HuggingFaceEmbeddings: {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Carregando FAISS...", flush=True)
try:
    from langchain_community.vectorstores import FAISS
    vs = FAISS.load_local(
        '/home/elisaos/fgv/6periodo/cepesp_data/ChatFGV-frontend/faiss_index',
        emb,
        allow_dangerous_deserialization=True,
    )
    print("FAISS carregado com sucesso!", flush=True)
except Exception as e:
    print(f"Falha no FAISS: {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Executando busca de teste...", flush=True)
docs = vs.similarity_search("Quem foi Getulio Vargas?", k=2)
print(f"Encontrados {len(docs)} documents", flush=True)
for i, doc in enumerate(docs):
    print(f"  Doc {i+1}: {doc.metadata.get('source', 'unknown')} ({len(doc.page_content)} chars)", flush=True)

print("\nTESTE FINALIZADO COM SUCESSO", flush=True)
