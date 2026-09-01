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
  evaluation/                 métricas silver, bootstrap e leakage audit
  training/                   geração reproduzível de checkpoints externos leves
  ui/                         inspeção Streamlit de artefatos concluídos
configs/
  approaches/                 checkpoints JSON versionados
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

Para incluir a interface científica:

```powershell
uv sync --extra ui
```

Comandos instalados:

- `discord-data`: download, extração e DuckDB;
- `discord-filter`: seleção de servidores e canais;
- `discord-disentangle`: cinco experimentos comparáveis;
- `discord-disentangle-ui`: inspeção científica dos artefatos prontos.

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

As cinco abordagens são executáveis separadamente:

- `zero_shot`: combinação fixa de sinais, sem ajuste por rótulos;
- `co_training`: duas visões com pseudo-rótulos;
- `weak_supervision`: ranker pairwise treinado somente com replies explícitos de treino.
- `chi_zero_shot`: response selection externo auto-supervisionado, sem labels Discord;
- `irc_transfer`: ranker treinado em replies anotados do Ubuntu IRC, sem fine-tuning Discord.

Executar todas com a mesma preparação e o mesmo conjunto de candidatos:

```powershell
discord-disentangle all `
  --config configs/experiments/neo4j_pilot.json `
  --input data/processed/software_messages.parquet `
  --output data/processed/disentanglement_experiments/neo4j_pilot_v2
```

Para uma abordagem isolada:

```powershell
discord-disentangle run `
  --approach zero_shot `
  --config configs/experiments/neo4j_pilot.json `
  --input data/processed/software_messages.parquet `
  --output data/processed/disentanglement_experiments/neo4j_zero_shot
```

Os valores válidos de `--approach` são `zero_shot`, `co_training`,
`weak_supervision`, `chi_zero_shot` e `irc_transfer`.

### Janelas nativas para anotação humana

Para separar as mensagens do Neo4j no export do Discord Unveiled e criar as
unidades de anotação humana:

```powershell
discord-disentangle gold-standard `
  --input data/processed/software_messages_discord_unveiled_2026-08-25.parquet `
  --output data/processed/disentanglement_experiments/neo4j_annotation_windows_w100_c200 `
  --annotated-window-size 100 `
  --context-message-count 200
```

O comando restringe a entrada ao `guild_id` Neo4j por padrão. Para um único
canal, acrescente `--channel-id <id>` ou `--channel-name <nome>`.

A unidade é uma janela contínua de mensagens de um único canal, e não uma
conversa inferida. As janelas anotadas são consecutivas e não se sobrepõem; cada
uma recebe até `--context-message-count` mensagens imediatamente anteriores.
Os valores 100/200 são apenas o primeiro piloto e devem ser variados antes da
definição do protocolo final.

A saída contém `native_reply_messages.parquet` (recorte Neo4j),
`native_reply_edges.parquet` (evidência de respostas diretas válidas) e
`native_reply_annotation_windows.csv` (uma linha por janela). Em
`messages_json`, as mensagens estão em ordem temporal e `window_role` distingue
`context` de `annotated`. Apenas `annotated` recebe tarefa em
`human_reply_source_statuses_json`; qualquer mensagem anterior visível, inclusive
`context`, pode ser escolhida como antecedente em `human_reply_edges_json`. Uma
fonte pode registrar múltiplas arestas. Um reply para uma mensagem anterior ao
contexto é contabilizado em `native_reply_targets_outside_window_count`, sem
inventar uma fronteira de conversa.

A saída preserva IDs de servidor/canal/autor, timestamps original e de edição,
tipo de mensagem, reply e thread nativos, menções, reactions, attachments,
embeds, stickers, roles, flags, bot/webhook e o payload original em
`native_fields_json`. `native_available_fields` mostra o que existia na fonte;
um campo indisponível não pode ser lido como vazio ou negativo. Esses metadados
não entram como features sem uma decisão experimental explícita.

Antes de anotar, achate as janelas em tabelas Parquet:

```powershell
discord-disentangle build-annotation-bundle `
  --annotation-windows data/processed/disentanglement_experiments/neo4j_annotation_windows_rich_2026-09-01_w100_c200/native_reply_annotation_windows.csv `
  --output data/processed/disentanglement_experiments/neo4j_annotation_bundle_rich_2026-09-01_w100_c200
```

O bundle contém `messages.parquet` com uma linha por mensagem real,
`sample_messages.parquet` com a participação de cada mensagem em uma amostra,
`annotations.parquet` com uma linha por aresta humana e `source_statuses.parquet`
para decisões sem aresta. `sample_messages.parquet` concentra `sample_id`,
`is_context` e `sequence`, evitando duplicar conteúdo e metadados. O anotador
não atribui `conversation_id`; uma fonte pode ter múltiplos antecedentes em
`annotations.parquet`.

Para trabalhar somente em um diretório de dados, publique o conjunto autocontido:

```powershell
discord-disentangle publish-annotation-dataset `
  --bundle-dir data/processed/disentanglement_experiments/neo4j_annotation_bundle_rich_2026-09-01_w100_c200 `
  --native-reply-edges data/processed/disentanglement_experiments/neo4j_annotation_windows_rich_2026-09-01_w100_c200/native_reply_edges.parquet `
  --codebook docs/methodology/ANNOTATION_CODEBOOK.md `
  --output data/annotation/neo4j_v1_w100_c200
```

Esse diretório contém somente `messages.parquet`, `sample_messages.parquet`,
`annotations.parquet`, `source_statuses.parquet`,
`silver_native_reply_edges.parquet`, `CODEBOOK.md` e `manifest.json`.

Após a anotação, derive os componentes conectados com:

```powershell
discord-disentangle derive-annotation-components `
  --messages data/annotation/neo4j_v1_w100_c200/messages.parquet `
  --sample-messages data/annotation/neo4j_v1_w100_c200/sample_messages.parquet `
  --annotations data/annotation/neo4j_v1_w100_c200/annotations.parquet `
  --source-statuses data/annotation/neo4j_v1_w100_c200/source_statuses.parquet `
  --output data/processed/disentanglement_experiments/neo4j_human_gold
```

As respostas explícitas continuam sendo evidência *silver*; somente as arestas
humanas podem formar o gold standard final. `no_reply`, `outside_context` e
`ambiguous` não significam, por si, o início de uma nova conversa;
`new_conversation` é explícito e só vira self-link na materialização.

O procedimento e os valores permitidos estão em
[`ANNOTATION_CODEBOOK.md`](docs/methodology/ANNOTATION_CODEBOOK.md).

Os três módulos anteriores continuam marcados `PILOT_PROXY`; os dois novos são
`INSPIRED_BY`. Nenhum é reprodução oficial. A avaliação separa geração de
candidatos, ranking overall/conditional e reconstrução projetada de threads
silver. Candidatos e links são sempre do mesmo canal e apontam estritamente para
uma mensagem anterior.

Para abrir a interface após a execução:

```powershell
discord-disentangle-ui
```

A UI lê os Parquets/JSON existentes e permite explorar mensagens cronológicas,
referência silver, threads previstas, top-K, divergência entre métodos e erros.
Ela não executa treinamento nem inferência.

## Resultado preservado do piloto v1

| Abordagem | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---:|---:|---:|---:|
| zero-shot | 0,5503 | 0,7220 | 0,7529 | 0,6398 |
| co-training | 0,5065 | 0,6875 | 0,7349 | 0,6051 |
| weak supervision | 0,5797 | 0,7284 | 0,7572 | 0,6575 |

A cobertura do pai verdadeiro no conjunto de candidatos foi 0,7809. Portanto,
as métricas de ranking não devem ser interpretadas sem essa limitação.

O piloto v1 permanece preservado para regressão. O piloto v2 das cinco abordagens
foi concluído em `data/processed/disentanglement_experiments/neo4j_pilot_v2`:
Candidate Recall@50 = 0,7845; o maior MRR overall observado foi 0,6541 em
`weak_supervision`. A tabela completa, intervalos e restrições de interpretação
estão no registro metodológico.

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
do piloto estão em `docs/methodology/REFACTORING_RESEARCH_LOG.md`. A definição
dos cinco métodos está em `docs/methodology/DISENTANGLEMENT_METHODS.md`; o
protocolo das métricas está em
`docs/methodology/DISENTANGLEMENT_EVALUATION.md`.
