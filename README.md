# Toxicity-OSS

Pipeline de pesquisa para duas investigações independentes sobre incivilidade em
comunidades Discord:

1. comunidades de software livre e open source;
2. comunidades de jogos.

As duas pesquisas reutilizam o mesmo motor de filtragem, mas possuem perfis,
corpora, decisões humanas e resultados separados. O servidor **Neo4j pertence
somente à pesquisa de software**.

## Estrutura

```text
discord_data/                 aquisição, extração e DuckDB
discord_filtering/            filtragem genérica por perfil externo
discord_disentanglement/
  approaches/                 uma implementação por abordagem
  experiments/                preparação, avaliação e artefatos comuns
configs/
  filtering/                  keywords, pesos e limiares por domínio
  experiments/                configuração do piloto Neo4j
annotations/                  decisões humanas versionáveis
docs/methodology/             registro metodológico vigente
docs/research/                notas de fundamentação da pesquisa
tests/                        testes dos fluxos mantidos
```

Não existem keywords de domínio dentro do código Python. Para estudar outro tipo
de comunidade, copie um perfil JSON, atribua um novo `profile_id` e ajuste os
grupos de termos, pesos e limiares.

## Instalação

```powershell
uv sync
```

Comandos instalados:

- `discord-data`: download, extração e DuckDB;
- `discord-filter`: seleção de servidores e canais;
- `discord-disentangle`: três experimentos comparáveis.

## Fonte congelada de software

O corpus atual está em `data/processed/software_messages.parquet`:

- SHA-256: `5fe780aeee4465e1b48419f21973e4e6b31ce33bd398a8f90b7070fae1f76f19`;
- 7.092.851 mensagens;
- 25 servidores;
- 482 canais.

Esse arquivo é fonte imutável. Os comandos de extração recusam sobrescrevê-lo.

## Filtragem reutilizável

Validar e listar perfis:

```powershell
discord-filter validate-profile --profile configs/filtering/software.v1.json
discord-filter validate-profile --profile configs/filtering/games.v1.json
```

Selecionar servidores de software:

```powershell
discord-filter select-servers `
  --profile configs/filtering/software.v1.json `
  --input data/raw/server_metadata/servers_metadata.txt `
  --output data/processed/filtering/software/<run_id>/servers_audit.parquet
```

Pontuar canais do Neo4j na pesquisa de software:

```powershell
discord-filter score-channels `
  --profile configs/filtering/software.v1.json `
  --input data/processed/software_messages.parquet `
  --output data/processed/filtering/software/<run_id>/neo4j_channels.parquet `
  --guild-id 787399249741479977 `
  --min-messages 50
```

O perfil de jogos deve ser executado sobre metadados e mensagens da pesquisa de
jogos. Não se deve aplicar `games.v1.json` ao corpus de software para produzir
um suposto resultado do Neo4j.

Cada saída possui um manifesto ao lado com hashes da entrada e do perfil,
parâmetros, contagens e versão do esquema. Canais abaixo do volume mínimo são
preservados como `insufficient_data`, não descartados silenciosamente.

As decisões humanas do piloto ficam em
`annotations/neo4j_channel_decisions.csv`. O Parquet filtrado não substitui esse
registro de validação.

## Disentanglement no Neo4j

As três abordagens são executáveis separadamente:

- `zero_shot`: combinação fixa de sinais, sem ajuste por rótulos;
- `co_training`: duas visões com pseudo-rótulos;
- `weak_supervision`: ranker pairwise treinado somente com replies explícitos de treino.

Executar todas com a mesma preparação e o mesmo conjunto de candidatos:

```powershell
discord-disentangle all `
  --config configs/experiments/neo4j_pilot.json `
  --input data/processed/software_messages.parquet `
  --output data/processed/disentanglement_experiments/neo4j_pilot_v1
```

Para uma abordagem isolada:

```powershell
discord-disentangle run `
  --approach zero_shot `
  --config configs/experiments/neo4j_pilot.json `
  --input data/processed/software_messages.parquet `
  --output data/processed/disentanglement_experiments/neo4j_zero_shot
```

Os valores válidos de `--approach` são `zero_shot`, `co_training` e
`weak_supervision`.

Os módulos são adaptações exploratórias marcadas como `pilot_proxy`; não são
reproduções oficiais dos métodos SOTA. A avaliação usa replies explícitos como
silver standard, somente no split de teste. Candidatos e links são sempre do
mesmo canal e apontam estritamente para uma mensagem anterior.

## Resultado atual do piloto

| Abordagem | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---:|---:|---:|---:|
| zero-shot | 0,5503 | 0,7220 | 0,7529 | 0,6398 |
| co-training | 0,5065 | 0,6875 | 0,7349 | 0,6051 |
| weak supervision | 0,5797 | 0,7284 | 0,7572 | 0,6575 |

A cobertura do pai verdadeiro no conjunto de candidatos foi 0,7809. Portanto,
as métricas de ranking não devem ser interpretadas sem essa limitação.

## Aquisição e extração

```powershell
discord-data download-metadata

discord-data extract-remote `
  --selected-servers-path <servers_audit.parquet> `
  --output-path <novo_messages.parquet>
```

Use `discord-data --help` para extração local e criação das views DuckDB.

## Verificação

```powershell
uv run pytest -q
```

O histórico técnico, as decisões metodológicas, limitações e valores completos
do piloto estão em `docs/methodology/REFACTORING_RESEARCH_LOG.md`.
