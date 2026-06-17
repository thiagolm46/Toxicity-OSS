# Metodologia: disentanglement e interface de inspecao para o servidor Neo4j

Este documento descreve a metodologia usada para construir o pipeline de conversation
disentanglement do servidor `Neo4j` e a interface estatica de inspecao humana gerada em:

```text
data/processed/neo4j_threads/reports/neo4j_threads.html
```

O objetivo desta etapa nao e classificar incivilidade, toxicidade ou derailment. O objetivo
e transformar um fluxo bruto de mensagens do Discord em threads candidatas, auditaveis e
faceis de revisar manualmente.

## Escopo dos dados

A entrada principal usada no experimento atual e:

```text
data/processed/software_messages_software.parquet
```

Esse arquivo vem do pipeline anterior de selecao de servidores e extracao de mensagens. Para
o servidor Neo4j, o filtro usado e:

```text
guild_name == "Neo4j"
```

No processamento atual, o arquivo contem:

```text
3335 mensagens do servidor Neo4j
app-dev: 1981 mensagens
dev-ops: 1162 mensagens
help-others: 192 mensagens
```

Esse numero representa somente as mensagens presentes no Parquet de entrada. Se parecer baixo,
a causa deve ser investigada na extracao upstream do dataset Discord-Unveiled, nao apenas no
disentanglement. O pipeline de disentanglement nao baixa mensagens novas; ele processa somente
o que recebeu.

## Principios metodologicos

O metodo modela a conversa como um grafo:

- no: mensagem;
- aresta: relacao explicita ou inferida entre duas mensagens;
- componente conectado: thread candidata.

A unidade inferida nao e um cluster semantico global. A unidade inferida e uma relacao
mensagem -> mensagem anterior. Isso torna cada link auditavel: para cada aresta, a interface
mostra o parent escolhido, o score e as evidencias usadas.

## Pipeline

O pipeline e implementado no pacote:

```text
discord_disentanglement/
```

O comando principal e:

```powershell
.\.venv\Scripts\python.exe -m discord_disentanglement run `
  --input data/processed/software_messages_software.parquet `
  --guild-name Neo4j `
  --out data/processed/neo4j_threads `
  --threshold 0.50
```

As etapas sao:

1. carregar mensagens de JSON, CSV ou Parquet;
2. filtrar por `guild_name`, `guild_id`, `channel_name` ou `channel_id`;
3. normalizar e anonimizar mensagens;
4. extrair links explicitos;
5. gerar candidatos mensagem atual -> mensagem anterior;
6. calcular features por par;
7. aplicar score heuristico;
8. construir grafo conversacional;
9. extrair componentes conectados como threads candidatas;
10. gerar CSV, JSON, GraphML, Cypher e HTML de inspecao.

## Normalizacao e privacidade

A normalizacao cria uma versao segura para visualizacao:

```text
content_normalized
```

As regras principais sao:

- autores reais viram `USER_001`, `USER_002`, etc.;
- mencoes a usuarios tambem viram `USER_XXX`;
- mencoes a canais viram `CHANNEL_XXX`;
- URLs viram `<URL>`;
- blocos de codigo viram `<CODE_BLOCK>`;
- anexos viram `<ATTACHMENT:tipo>`;
- emojis, `?` e `!` sao preservados;
- mensagens curtas nao sao removidas.

Por padrao, `content_raw` nao e exportado. Isso reduz o risco de expor dado sensivel na
interface. A visualizacao usa somente `content_normalized`.

## Links explicitos

Antes de inferir qualquer relacao, o pipeline preserva links explicitos ja existentes no
Discord:

- reply explicito;
- `message_reference`;
- `referenced_message_id`;
- thread nativa, quando existir;
- link de mensagem colado no texto, quando reconhecivel.

Esses links sao exportados em:

```text
edges_explicit.csv
```

Confiancas padrao:

```text
explicit_reply: 1.00
native_thread: 0.95
quoted_message_link: 0.90
```

Uma mencao direta a usuario nao vira aresta automaticamente. Ela e usada como feature para
inferir relacoes.

## Geracao de candidatos

Para cada mensagem atual `m_i`, o pipeline cria candidatos anteriores `m_j`. A relacao
sempre aponta da mensagem atual para uma mensagem anterior:

```text
source = mensagem atual
target = mensagem anterior candidata
```

Os criterios de entrada no conjunto de candidatos incluem:

- ultimas 50 mensagens anteriores;
- mensagens dentro de uma janela temporal de 24h;
- mensagens de autores mencionados pela mensagem atual;
- mensagens que mencionaram o autor atual;
- mensagens da mesma thread nativa;
- mensagens com similaridade textual;
- mensagens com termos tecnicos compartilhados.

Os candidatos sao exportados em:

```text
candidate_pairs.csv
```

## Features usadas

Cada par candidato recebe features auditaveis.

### Temporais

- `delta_seconds`;
- `log_delta_seconds`;
- `temporal_score`;
- `same_burst`.

### Participantes

- `same_author`;
- `source_mentions_target_author`;
- `target_mentions_source_author`;
- `author_participated_recently`.

### Textuais

- similaridade TF-IDF/cosseno;
- overlap lexical;
- tokens tecnicos compartilhados;
- URL compartilhada;
- marcador de codigo ou erro compartilhado.

O TF-IDF e implementado localmente como fallback simples, sem embeddings obrigatorios. Isso
mantem o pipeline reprodutivel sem depender de modelos externos.

### Discursivas

- target contem pergunta;
- source parece resposta;
- source comeca com marcadores como `sim`, `nao`, `isso`, `depende`, `tenta`, `verifica`;
- source contem marcador de desacordo;
- source contem marcador de razao;
- source usa segunda pessoa.

### Estruturais

- reply explicito;
- mesma thread nativa;
- mesmo canal;
- source/target bot;
- anexo;
- bloco de codigo.

## Score heuristico

O baseline inicial e auditavel e usa a formula:

```text
score =
  0.30 * semantic_similarity
+ 0.20 * temporal_score
+ 0.15 * mention_score
+ 0.10 * lexical_overlap
+ 0.10 * question_answer_score
+ 0.10 * same_native_thread_score
+ 0.05 * participant_continuity_score
```

Regras complementares:

- se existe reply explicito, `score = 1.0`;
- mesma thread nativa recebe reforco;
- discussoes tecnicas com mencao/pergunta e tokens compartilhados recebem reforco;
- grandes lacunas temporais sem reply, mencao ou continuidade sao penalizadas;
- similaridade semantica isolada nao deve criar link forte se tempo e participantes nao
  sustentarem a relacao;
- candidatos proximos em score podem gerar aresta `uncertain`.

O threshold padrao e:

```text
0.50
```

Se nenhum candidato atingir o threshold, a mensagem inicia uma nova thread candidata.

## Construcao do grafo

O grafo e criado com `networkx`:

```text
DiGraph
source -> target
mensagem atual -> mensagem anterior/pai
```

Sao exportados:

```text
graph_edges.csv
graph.graphml
graph.json
```

Para extrair threads, o grafo direcionado e convertido conceitualmente para nao direcionado.
Cada componente conectado vira uma thread candidata.

## Extracao e pos-processamento de threads

Cada thread inclui:

- `thread_id`;
- mensagem raiz;
- mensagens em ordem temporal;
- participantes anonimizados;
- inicio e fim;
- duracao;
- numero de mensagens;
- numero de participantes;
- confianca media;
- links explicitos, inferidos e incertos;
- palavras-chave;
- forma conversacional preliminar;
- status de revisao.

Formas conversacionais preliminares:

- `pergunta_resposta`;
- `discussao_tecnica`;
- `sequencia_informativa`;
- `conversa_social`;
- `ambigua`;
- `thread_curta`.

O pos-processamento tambem:

- divide componentes por grandes lacunas temporais quando nao ha ponte explicita;
- marca threads ambiguas;
- sugere merges nao destrutivos.

## Interface de inspecao

A interface foi desenhada para responder perguntas de auditoria:

1. Quantas mensagens existem no escopo processado?
2. Quais canais entraram no processamento?
3. Quais threads foram reconstruidas?
4. Quais mensagens compoem cada thread?
5. Qual mensagem foi escolhida como pai?
6. Qual foi a evidencia para o link?
7. Onde o algoritmo esta inseguro?

Depois de testar uma visualizacao de grafo por thread, a interface foi simplificada. A versao
atual evita usar o desenho do grafo como tela principal porque, para muitas threads pequenas,
o desenho produz linhas e nos pouco informativos.

A interface principal agora e um HTML estatico com:

- bloco de cobertura dos dados;
- metricas gerais;
- filtros por texto, status e tamanho minimo;
- lista de threads;
- painel de detalhe com mensagens em ordem;
- link pai de cada mensagem;
- score do link;
- evidencias compactas;
- candidatos alternativos, quando existem.

O arquivo principal e:

```text
reports/neo4j_threads.html
```

As paginas individuais por thread ficam em:

```text
reports/thread_graphs/T_0001.html
reports/thread_graphs/T_0002.html
...
```

Apesar do nome historico `thread_graphs`, essas paginas agora sao paginas textuais simples,
nao visualizacoes de grafo. O nome foi mantido para preservar compatibilidade com os artefatos
ja esperados pelo pipeline.

## Como a interface e criada

A interface e gerada por:

```text
discord_disentanglement/reports.py
```

O processo e:

1. reunir threads, mensagens, arestas e candidatos;
2. compactar evidencias para evitar despejar JSON excessivo na tela;
3. montar um payload JSON interno;
4. embutir esse payload no HTML estatico;
5. usar JavaScript local para filtrar, ordenar e selecionar threads;
6. gerar paginas individuais por thread;
7. nao depender de CDN, servidor ou internet.

A escolha por HTML estatico facilita reproducibilidade: o relatorio e um artefato completo,
compartilhavel e versionavel.

## Arquivos gerados

```text
messages_normalized.csv
edges_explicit.csv
candidate_pairs.csv
edges_inferred.csv
graph_edges.csv
graph.graphml
graph.json
threads.csv
threads.json
thread_messages.csv
thread_summaries.csv
annotation_review.csv
reports/neo4j_threads.html
reports/neo4j_threads_summary.md
reports/thread_graphs/T_0001.html
exports/neo4j_import.cypher
```

`thread_summaries.csv` ja prepara os campos futuros:

```text
scd_summary
incivility_label
derailment_risk
```

Nesta etapa, esses campos ficam vazios.

## Export para Neo4j

O pipeline gera um arquivo Cypher opcional:

```text
exports/neo4j_import.cypher
```

Modelo conceitual:

```cypher
(:User)-[:AUTHORED]->(:Message)
(:Message)-[:REPLIES_TO {confidence, method, edge_type}]->(:Message)
(:Message)-[:BELONGS_TO]->(:Thread)
```

O pipeline nao conecta automaticamente ao banco Neo4j. Ele apenas gera o script de import.

## Limitacoes conhecidas

- O metodo atual e heuristico.
- Nao ha embeddings obrigatorios nem modelo supervisionado.
- Muitas mensagens sem reply explicito tendem a virar singletons.
- Mensagens curtas dependem fortemente de tempo, mencao e continuidade de participante.
- A qualidade final depende da cobertura do Parquet de entrada.
- O nome `thread_graphs` ainda existe por compatibilidade, embora a pagina atual seja textual.
- Nao ha classificacao de incivilidade nesta etapa.

## Proximos passos metodologicos

1. Revisar manualmente `annotation_review.csv`.
2. Criar um conjunto ouro de pares mensagem -> pai.
3. Ajustar pesos e threshold por evidencia empirica.
4. Avaliar metricas de link prediction, nao apenas numero de threads.
5. Adicionar embeddings como feature opcional, mantendo fallback TF-IDF.
6. Implementar um ranker supervisionado para escolher o parent.
7. So depois integrar classificacao de incivilidade, SCD e derailment.

