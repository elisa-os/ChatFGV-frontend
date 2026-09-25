<ADR/>

# Painel de terminal live no ChatFGV Streamlit

## Contexto
- O frontend atual tem a sidebar esquerda ocupada com configurações (modo, top_k, mock SQL, show_context) e pequeno status do backend.
- Quem roda quem usa quer uma visão de "o que acontece no terminal em tempo real" ao lado de um chat limpo.
- Restrição: tudo no mesmo Streamlit app; autorefresh a cada 5s sem deixar o chat travado.

## Decisão
- Substituir a sidebar de configurações por um painel de log em tempo real na coluna esquerda.
- Manter as configurações de consumo (modo, top_k, mock SQL, show_context) em um expander discreto no topo da coluna do chat, porque elas ainda são necessárias para o fluxo de pergunta/resposta.
- Status do backend (FAISS / mock SQL) aparece em um expander pequeno no mesmo painel.
- Autorefresh implementado com `st.rerun()` controlado por `st.session_state["_last_log_refresh"]` + verificação de tempo — sem `time.sleep`, para não bloquear a interação no chat.
- Caminho do log configurável via `CHATFGV_LOG_PATH`; padrão deriva do `streamlit.log` na raiz do projeto (computado a partir do `__file__` de `log_panel.py`).

## Trade-offs
- Rerun a cada 5s recarrega a página toda; isso pode derrubar um rascunho não-enviado do `st.chat_input` se o usuário estiver digitando exatamente no instante do rerun. É aceitável para uso de "olhar o terminal", não ideal para digitação longa; a troca é documentada aqui.
- Leitura do arquivo de log a cada refresh; para logs grandes, usa apenas as últimas N linhas (150 por padrão) para não estourar a renderização.

## Rollback
- O app.py e o log_panel.py são novos/alterados sobre o último commit; reverter com `git restore frontend/streamlit/app.py` e removendo `frontend/streamlit/log_panel.py` volta ao estado anterior.
