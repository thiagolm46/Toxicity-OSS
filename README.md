# Discord-Unveiled Software Filter

Este projeto filtra os servidores do dataset [SaisExperiments/Discord-Unveiled-Compressed](https://huggingface.co/datasets/SaisExperiments/Discord-Unveiled-Compressed) que parecem ser relacionados a programação, desenvolvimento, engenharia de software e ferramentas open source. Depois disso, extrai apenas as mensagens desses servidores para Parquet e registra views em DuckDB.

## O que o pipeline faz

1. Baixa `server_metadata/servers_metadata.txt` do Hugging Face.
2. Classifica servidores com heurísticas de palavras-chave positivas e negativas usando perfis dinâmicos (`software` ou `gaming`).
3. Salva os servidores selecionados em Parquet e JSON para revisão.
4. Lê `dataset.zst`, que é um `tar.zst` com arquivos `./<guild_id>.json`, e extrai só os servidores selecionados.
5. Salva as mensagens filtradas em Parquet.
6. Cria um banco DuckDB com views sobre os arquivos Parquet.

## Estrutura de saída

- `data/raw/server_metadata/servers_metadata.txt`: metadados originais dos servidores.
- `data/raw/dataset.zst`: dataset principal completo.
- `data/processed/software_servers.parquet`: servidores selecionados.
- `data/processed/software_servers.json`: versão JSON para revisão manual.
- `data/processed/software_messages.parquet`: mensagens filtradas.
- `data/duckdb/discord_unveiled.duckdb`: banco DuckDB com views prontas.

## Comandos

Se `uv` estiver no `PATH`:

```powershell
uv run python main.py download-metadata
uv run python main.py select-servers
uv run python main.py extract-messages-remote
uv run python main.py init-duckdb
```

Se o `uv` não estiver no `PATH`, use o binário local da `.venv`:

```powershell
.\.venv\Scripts\uv.exe run python main.py download-metadata
.\.venv\Scripts\uv.exe run python main.py select-servers
.\.venv\Scripts\uv.exe run python main.py extract-messages-remote
.\.venv\Scripts\uv.exe run python main.py init-duckdb
```

Fluxo alternativo (dataset local completo):

```powershell
.\.venv\Scripts\uv.exe run python main.py download-dataset
.\.venv\Scripts\uv.exe run python main.py extract-messages
```

## Ajustes úteis

Liste os perfis disponíveis:

```powershell
.\.venv\Scripts\uv.exe run python main.py list-profiles
```

Escolha o perfil de filtragem conforme o tema da pesquisa:

```powershell
.\.venv\Scripts\uv.exe run python main.py select-servers --profile software
.\.venv\Scripts\uv.exe run python main.py select-servers --profile gaming
```

Endureça ou afrouxe a seleção ajustando score mínimo e margem:

```powershell
.\.venv\Scripts\uv.exe run python main.py select-servers --profile software --min-positive-score 7 --min-score-margin 3
```

Adicione regex extras sem precisar alterar código:

```powershell
.\.venv\Scripts\uv.exe run python main.py select-servers --profile software --positive-regex "\bllm\b|\bai engineering\b" --negative-regex "\bcasino\b"
```

Você pode remover mensagens de bots na extração:

```powershell
.\.venv\Scripts\uv.exe run python main.py extract-messages-remote --exclude-bots
```

Você pode filtrar canais de forma dinâmica na extração:

```powershell
.\.venv\Scripts\uv.exe run python main.py extract-messages-remote --include-channel-regex "dev|help|code|backend|frontend" --exclude-channel-regex "off-topic|meme|music"
```

## Uso programático (sem flags)

Se você prefere manter tudo em código (paths, perfil, regras), use a API em classes de `pipeline_api.py`.

```python
from pathlib import Path

from pipeline_api import (
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
)

pipeline = DiscordUnveiledPipeline(paths)

pipeline.select_servers(
	SelectionConfig(
		profile="software",
		min_positive_score=6,
		min_score_margin=2,
	)
)

pipeline.extract_messages_remote(
	ExtractRemoteConfig(
		selected_servers_path=paths.selected_servers_parquet,
		output_parquet=paths.messages_parquet,
		exclude_bots=True,
		include_channel_regex=[r"dev|help|code|backend|frontend"],
		exclude_channel_regex=[r"off-topic|meme|music"],
	)
)
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
```

## Observações

- O arquivo principal do dataset tem aproximadamente 118 GB.
- O comando `extract-messages-remote` não salva o `dataset.zst` inteiro em disco local; ele processa o stream e grava somente o Parquet final.
- Como o dataset remoto está em um único `tar.zst`, o processamento ainda precisa percorrer o stream para encontrar os servidores selecionados.
- A heurística de seleção é um ponto de partida. Revise `data/processed/software_servers.json` antes de extrair as mensagens definitivas.
- O Parquet final inclui campos principais da mensagem e colunas JSON serializadas para anexos, embeds, menções e stickers.
