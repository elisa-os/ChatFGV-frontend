# Adaptação mínima do dhbb-query.py para ser importável no streamlit

O script atual funciona, mas a busca recarrega embedding + FAISS a cada chamada.
Para o streamlit, idealmente:

1. Separar inicialização do índice (modelo + FAISS) de `search_dhbb()`.
2. Carregar o índice uma única vez via `@st.cache_resource` ou variável global.
3. Manter compatibilidade com a interface atual do script (CLI + JSON).

O esboço abaixo mostra a forma que o ChatFGVStreamlit usa hoje:
  - `StreamlitRAGStore`: carrega index/modelo sob demanda, retorna contexto + fontes.
  - Mantém `main()` original intacto para o CLI continuar funcionando.

Detalhes de implementação e opções de cache estão em:
  frontend/streamlit/app.py
