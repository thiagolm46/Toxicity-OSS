# Discord-Unveiled Software Filter

Este projeto filtra os servidores do dataset [SaisExperiments/Discord-Unveiled-Compressed](https://huggingface.co/datasets/SaisExperiments/Discord-Unveiled-Compressed) que parecem ser relacionados a programação, desenvolvimento, engenharia de software e ferramentas open source. Depois disso, extrai apenas as mensagens desses servidores para Parquet e registra views em DuckDB.

## O que o pipeline faz

1. Baixa `server_metadata/servers_metadata.txt` do Hugging Face.
2. Classifica servidores com heurísticas de palavras-chave positivas e negativas.
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
uv run python main.py download-dataset
uv run python main.py extract-messages
uv run python main.py init-duckdb
```

Se o `uv` não estiver no `PATH`, use o binário local da `.venv`:

```powershell
.\.venv\Scripts\uv.exe run python main.py download-metadata
.\.venv\Scripts\uv.exe run python main.py select-servers
.\.venv\Scripts\uv.exe run python main.py download-dataset
.\.venv\Scripts\uv.exe run python main.py extract-messages
.\.venv\Scripts\uv.exe run python main.py init-duckdb
```

## Ajustes úteis

Você pode endurecer ou afrouxar a seleção de servidores ajustando a pontuação mínima:

```powershell
.\.venv\Scripts\uv.exe run python main.py select-servers --min-positive-score 5
```

Você pode remover mensagens de bots na extração:

```powershell
.\.venv\Scripts\uv.exe run python main.py extract-messages --exclude-bots
```

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
- A heurística de seleção é um ponto de partida. Revise `data/processed/software_servers.json` antes de extrair as mensagens definitivas.
- O Parquet final inclui campos principais da mensagem e colunas JSON serializadas para anexos, embeds, menções e stickers.
