# Auditoria inicial: upgrade de conversation disentanglement

## Modulos existentes

- `discord_disentanglement/cli.py`: CLI Typer com comando `run`.
- `discord_disentanglement/pipeline.py`: normalizacao, extracao de links, geracao de candidatos, scoring, grafo, threads e exportacao.
- `discord_disentanglement/io.py`: leitura JSON/CSV/Parquet e normalizacao de linhas.
- `discord_disentanglement/models.py`: dataclasses `MessageRecord`, `EdgeRecord` e `ThreadRecord`.
- `discord_disentanglement/text.py`: normalizacao textual, tokenizacao, TF-IDF, similaridade e marcadores discursivos.
- `discord_disentanglement/reports.py`: relatorio HTML principal, paginas por thread e resumo Markdown.
- `apps/thread_explorer.py`: abertura/servidor local para HTMLs gerados.

## Comandos CLI existentes

- `python -m discord_disentanglement run --input ... --guild-name ... --out ... --threshold ...`
- Script instalado: `discord-disentangle = discord_disentanglement.cli:main`.

## Artefatos atualmente gerados

- `messages_normalized.csv`
- `edges_explicit.csv`
- `candidate_pairs.csv`
- `edges_inferred.csv`
- `graph_edges.csv`
- `graph.graphml`
- `graph.json`
- `threads.csv`
- `threads.json`
- `thread_messages.csv`
- `thread_summaries.csv`
- `annotation_review.csv`
- `reports/neo4j_threads.html`
- `reports/neo4j_threads_summary.md`
- `reports/thread_graphs/*.html`
- `exports/neo4j_*.csv`
- `exports/neo4j_import.cypher`

## Testes existentes

- `tests/test_discord_disentanglement.py`: IO, filtro por guild/canal, anonimizacao, explicit replies, candidatos, score, mensagens curtas, grafo, threads, HTML e Cypher.
- `tests/test_pipeline_scoring.py`: selecao de servidores/canais no pipeline mais amplo.

## Pontos do pipeline

- Normalizacao: `normalize_messages()` em `pipeline.py`, com apoio de `normalize_content()` em `text.py`.
- Explicit replies: `extract_explicit_edges()` em `pipeline.py`.
- Geracao de candidatos: `generate_candidate_pairs()` em `pipeline.py`.
- Calculo de score: `calculate_pair_features()` e `score_pair()` em `pipeline.py`.
- Grafo: `build_graph()` e `extract_threads()` em `pipeline.py`.
- HTML: `generate_main_html_report()` e `generate_thread_graph_reports()` em `reports.py`.
- Neo4j: `write_neo4j_exports()` em `pipeline.py`.

## Riscos de compatibilidade

- Alterar nomes de edge pode quebrar contagens antigas; a v2 deve tratar `inferred` e `inferred_reply` como equivalentes.
- Alterar colunas existentes pode quebrar scripts externos; novas colunas devem ser aditivas.
- Embeddings podem exigir dependencias/modelos externos; o fallback TF-IDF deve manter o pipeline funcional.
- `thread_id` nativo nao deve virar feature direta de predicao, exceto como estrutura explicita ja existente.
- Relatorios devem continuar usando `content_normalized` e usuarios anonimizados.
