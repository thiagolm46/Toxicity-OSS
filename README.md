# Discord-Unveiled Software Filter

## Conversation disentanglement do canal Neo4J

O pacote `discord_disentanglement` implementa uma primeira versao do pipeline de reconstrucao de threads para exports JSON/CSV/Parquet do Discord. Ele pode filtrar o servidor `Neo4j` pelo campo `guild_name`, anonimiza usuarios, extrai replies explicitos, cria candidatos mensagem->mensagem, calcula features auditaveis, aplica um baseline heuristico, constroi um grafo conversacional e exporta relatorios para revisao humana.

Comando principal para o Parquet produzido pelo pipeline anterior:

```powershell
.\.venv\Scripts\python.exe -m discord_disentanglement run `
  --input data/processed/software_messages_software.parquet `
  --guild-name Neo4j `
  --out data/processed/neo4j_threads `
  --threshold 0.50
```

Tambem aceita JSON/CSV e filtro por canal quando necessario:

```powershell
.\.venv\Scripts\python.exe -m discord_disentanglement run `
  --input data/raw/discord_export.csv `
  --guild-name Neo4j `
  --channel-name app-dev `
  --out data/processed/neo4j_threads
```

Arquivos gerados:

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
- `reports/thread_graphs/T_0001.html` etc. com paginas simples por thread
- `exports/neo4j_users.csv`
- `exports/neo4j_threads.csv`
- `exports/neo4j_messages.csv`
- `exports/neo4j_authored_relationships.csv`
- `exports/neo4j_belongs_to_relationships.csv`
- `exports/neo4j_replies_to_relationships.csv`
- `exports/neo4j_import.cypher`

Para visualizar o grafo diretamente no Neo4j, copie os arquivos `exports/neo4j_*.csv` para a pasta `import/` da sua instância Neo4j e execute o script `exports/neo4j_import.cypher` no Neo4j Browser. Isso cria nós `:User`, `:Message`, `:Thread` e relações `:AUTHORED`, `:BELONGS_TO` e `:REPLIES_TO` para exploração do grafo no Browser ou Bloom.

Para abrir o explorer local simplificado sem depender de Streamlit:

```powershell
.\.venv\Scripts\python.exe apps/thread_explorer.py --data data/processed/neo4j_threads
```

Ou servir os HTMLs localmente:

```powershell
.\.venv\Scripts\python.exe apps/thread_explorer.py --data data/processed/neo4j_threads --serve --port 8501
```

Campos de incivilidade ainda nao sao calculados. `thread_summaries.csv` ja inclui `scd_summary`, `incivility_label` e `derailment_risk` vazios para a proxima etapa.

Este projeto filtra servidores candidatos do dataset [SaisExperiments/Discord-Unveiled-Compressed](https://huggingface.co/datasets/SaisExperiments/Discord-Unveiled-Compressed) que parecem ser relacionados a programação, desenvolvimento, engenharia de software e ferramentas open source. Depois disso, extrai mensagens, pontua canais textuais por evidencias tecnicas e registra views em DuckDB.

A unidade final de inclusao da pesquisa deve ser **servidor valido de SE/OSS + canal valido de software**. Isso evita tratar todo canal de um servidor tecnico como automaticamente relevante para engenharia de software.

## O que o pipeline faz

1. Baixa `server_metadata/servers_metadata.txt` do Hugging Face.
2. Classifica servidores candidatos de SE/OSS com heurísticas de palavras-chave positivas e negativas usando o perfil `software`.
3. Salva os servidores selecionados em Parquet e JSON para revisão.
4. Lê `dataset.zst`, que é um `tar.zst` com arquivos `./<guild_id>.json`, e extrai só os servidores selecionados.
5. Salva as mensagens filtradas em Parquet.
6. Pontua canais por nome, evidencias lexicas de software e evidencias de OSS/repositórios.
7. Classifica canais em A/B/C/D para apoiar revisão manual.
8. Cria um banco DuckDB com views sobre os arquivos Parquet.

## Estrutura de saída

- `data/raw/server_metadata/servers_metadata.txt`: metadados originais dos servidores.
- `data/raw/dataset.zst`: dataset principal completo.
- `data/processed/software_servers.parquet`: servidores selecionados.
- `data/processed/software_servers.json`: versão JSON para revisão manual.
- `data/processed/software_messages.parquet`: mensagens filtradas.
- `data/processed/software_channels.parquet`: canais pontuados e classificados.
- `data/processed/software_channels.json`: versão JSON para revisão manual dos canais.
- `data/duckdb/discord_unveiled.duckdb`: banco DuckDB com views prontas.

## Comandos

Se `uv` estiver no `PATH`:

```powershell
uv run python main.py download-metadata
uv run python main.py select-servers
uv run python main.py extract-messages-remote
uv run python main.py score-channels
uv run python main.py init-duckdb
```

Se o `uv` não estiver no `PATH`, use o Python local da `.venv`:

```powershell
.\.venv\Scripts\python.exe main.py download-metadata
.\.venv\Scripts\python.exe main.py select-servers
.\.venv\Scripts\python.exe main.py extract-messages-remote
.\.venv\Scripts\python.exe main.py score-channels
.\.venv\Scripts\python.exe main.py init-duckdb
```

Fluxo alternativo (dataset local completo):

```powershell
.\.venv\Scripts\python.exe main.py download-dataset
.\.venv\Scripts\python.exe main.py extract-messages
```

## Ajustes úteis

Liste os perfis disponíveis:

```powershell
.\.venv\Scripts\python.exe main.py list-profiles
```

Execute a seleção com o perfil de software:

```powershell
.\.venv\Scripts\python.exe main.py select-servers --profile software
```

Endureça ou afrouxe a seleção ajustando score mínimo e margem:

```powershell
.\.venv\Scripts\python.exe main.py select-servers --profile software --min-positive-score 8 --min-score-margin 2 --max-negative-score 2
```

Adicione regex extras sem precisar alterar código:

```powershell
.\.venv\Scripts\python.exe main.py select-servers --profile software --positive-regex "\bllm\b|\bai engineering\b" --negative-regex "\bcasino\b"
```

Por padrão, a extração remove mensagens de bots. Para manter bots em uma execução exploratória, use `--no-exclude-bots`:

```powershell
.\.venv\Scripts\python.exe main.py extract-messages-remote --no-exclude-bots
```

Você pode filtrar canais de forma dinâmica na extração, apenas para testes exploratórios:

```powershell
.\.venv\Scripts\python.exe main.py extract-messages-remote --include-channel-regex "dev|help|code|backend|frontend" --exclude-channel-regex "off-topic|meme|music"
```

Para a metodologia final, prefira extração ampla dos canais textuais dos servidores candidatos e use `score-channels` para a triagem temática posterior.

Depois da extração, gere a pontuação de canais:

```powershell
.\.venv\Scripts\python.exe main.py score-channels --min-messages 50
```

Classes geradas:

| Classe | Descrição                                      | Uso recomendado                      |
| ------ | ---------------------------------------------- | ------------------------------------ |
| A      | Canal técnico central                          | Entra na análise principal           |
| B      | Canal técnico periférico ou ambíguo            | Revisão manual ou análise secundária |
| C      | Canal social/comunitário                       | Excluir da análise principal         |
| D      | Canal administrativo, bot, regras, logs ou voz | Excluir da análise principal         |

O score automático atual é uma triagem baseada em conteúdo e metadados do canal. Para a dissertação, a etapa final deve combinar essa triagem com modelagem semântica, por exemplo SBERT + BERTopic, e validação manual. O protocolo detalhado está em [docs/methodology/CHANNEL_SELECTION_PROTOCOL.md](docs/methodology/CHANNEL_SELECTION_PROTOCOL.md).

## Documentação

- [docs/methodology/PIPELINE_USAGE_AND_METHODOLOGY.md](docs/methodology/PIPELINE_USAGE_AND_METHODOLOGY.md): passo a passo completo e metodologia de replicação.
- [docs/methodology/FILTERING_FINDINGS.md](docs/methodology/FILTERING_FINDINGS.md): achados da filtragem de servidores com o corte atual.
- [docs/methodology/CHANNEL_SELECTION_PROTOCOL.md](docs/methodology/CHANNEL_SELECTION_PROTOCOL.md): protocolo de seleção e validação de canais.
- [docs/methodology/NEO4J_DISENTANGLEMENT_INTERFACE_METHODOLOGY.md](docs/methodology/NEO4J_DISENTANGLEMENT_INTERFACE_METHODOLOGY.md): metodologia do disentanglement e da interface de inspecao do Neo4j.
- [docs/methodology/DISENTANGLEMENT_DEVELOPMENT_PROCESS.md](docs/methodology/DISENTANGLEMENT_DEVELOPMENT_PROCESS.md): historico de desenvolvimento da funcionalidade de disentanglement, com exemplos iniciais e decisoes de implementacao.
- [docs/research/](docs/research/): notas de fundamentação teórica que não são necessárias para executar o pipeline.

## Uso programático (sem flags)

Se você prefere manter tudo em código (paths, perfil, regras), use a API em classes de `pipeline_api.py`.

```python
from pathlib import Path

from pipeline_api import (
	ChannelScoringConfig,
	DiscordUnveiledPipeline,
	ExtractRemoteConfig,
	ProjectPaths,
	SelectionConfig,
)

paths = ProjectPaths(
	metadata_path=Path("data/raw/server_metadata/servers_metadata.txt"),
	selected_servers_parquet=Path("data/processed/software_servers_software.parquet"),
	selected_servers_json=Path("data/processed/software_servers_software.json"),
	messages_parquet=Path("data/processed/software_messages_software.parquet"),
	channel_scores_parquet=Path("data/processed/software_channels_software.parquet"),
	channel_scores_json=Path("data/processed/software_channels_software.json"),
)

pipeline = DiscordUnveiledPipeline(paths)

pipeline.select_servers(
	SelectionConfig(
		profile="software",
		min_positive_score=8,
		min_score_margin=2,
		max_negative_score=2,
	)
)

pipeline.extract_messages_remote(
	ExtractRemoteConfig(
		selected_servers_path=paths.selected_servers_parquet,
		output_parquet=paths.messages_parquet,
		exclude_bots=True,
	)
)

pipeline.score_channels(
	ChannelScoringConfig(
		messages_parquet=paths.messages_parquet,
		output_parquet=paths.channel_scores_parquet,
		output_json=paths.channel_scores_json,
		min_messages=50,
	)
)

pipeline.init_duckdb()
```

Exemplo pronto para copiar e adaptar: `scripts/run_programmatic_pipeline.py`.

## Consultando no DuckDB

Abra o banco:

```powershell
duckdb data/duckdb/discord_unveiled.duckdb
```

Algumas consultas úteis:

```sql
SELECT guild_name, COUNT(*) AS messages
FROM software_messages
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20;

SELECT date_trunc('month', CAST(timestamp AS TIMESTAMPTZ)) AS month, COUNT(*) AS messages
FROM software_messages
GROUP BY 1
ORDER BY 1;

SELECT *
FROM server_message_stats
LIMIT 20;

SELECT guild_name, channel_name, channel_class, software_channel_score, n_messages
FROM software_channels
ORDER BY software_channel_score DESC, n_messages DESC
LIMIT 25;
```

## Validação local

Execute a suíte mínima de testes metodológicos:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Esses testes verificam se o corte por `max_negative_score` exclui candidatos ruidosos e se um canal tecnicamente forte com nome genérico, como `general`, não é descartado por depender apenas do nome.

## Observações

- O arquivo principal do dataset tem aproximadamente 118 GB.
- O comando `extract-messages-remote` não salva o `dataset.zst` inteiro em disco local; ele processa o stream e grava somente o Parquet final.
- Como o dataset remoto está em um único `tar.zst`, o processamento ainda precisa percorrer o stream para encontrar os servidores selecionados.
- A heurística de seleção de servidores é um ponto de partida. Revise `data/processed/software_servers.json` antes de extrair as mensagens definitivas.
- A classificação de canais também é uma triagem. Revise `data/processed/software_channels.json`, especialmente canais B e faixas próximas ao limiar.
- O Parquet final inclui campos principais da mensagem e colunas JSON serializadas para anexos, embeds, menções e stickers.
