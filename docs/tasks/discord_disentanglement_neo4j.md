# Task: Discord Conversation Disentanglement para canal Neo4J

## Objetivo

Implementar um pipeline inicial e robusto para transformar mensagens brutas de um canal do Discord chamado `Neo4J` em threads úteis, coerentes e interpretáveis.

A tarefa atual é apenas conversation disentanglement. Não implementar ainda classificação de incivilidade, toxicidade ou derailment.

## Ideia central

Modelar o problema como grafo conversacional:

- nó = mensagem;
- aresta = relação explícita ou inferida entre mensagens;
- componente conectado = thread candidata.

Não usar clustering semântico puro como abordagem principal. O método deve inferir relações mensagem→mensagem.

## Entrada

Aceitar JSON ou CSV exportado do Discord.

Campos desejados, quando existirem:

- message_id
- guild_id
- channel_id
- channel_name
- native_thread_id
- author_id
- timestamp
- edited_timestamp
- content
- mentions
- attachments
- embeds
- reactions
- message_reference
- referenced_message
- reply_to_message_id
- is_bot
- is_webhook
- message_type

Deve haver filtro por:

- `--channel-name Neo4J`
- ou `--channel-id`

## Saída esperada

Gerar diretório de saída, por exemplo:

```text
data/processed/neo4j_threads/
```

Com arquivos:

```text
messages_normalized.csv
edges_explicit.csv
candidate_pairs.csv
edges_inferred.csv
graph_edges.csv
threads.csv
threads.json
thread_messages.csv
thread_summaries.csv
reports/neo4j_threads.html
reports/neo4j_threads_summary.md
exports/neo4j_import.cypher
```

## Privacidade

Anonimizar usuários:

```text
author_id real → USER_001, USER_002, ...
```

Nas visualizações, nunca mostrar IDs reais.

Preservar `content_raw` internamente apenas se configurado. Para visualização, usar `content_normalized`.

## Normalização

Criar:

- `content_raw`
- `content_normalized`

Regras:

- menções → `USER_XXX`;
- canais → `CHANNEL_XXX`;
- URLs → `<URL>`;
- blocos de código → `<CODE_BLOCK>`;
- anexos → `<ATTACHMENT:type>`;
- preservar emojis;
- preservar `?` e `!`;
- não remover mensagens curtas como “sim”, “não”, “isso”, “?”, “kkkk”, “valeu”.

## Links explícitos

Extrair primeiro:

- reply explícito;
- `message_reference`;
- `referenced_message`;
- thread nativa;
- link de mensagem colado no texto, se reconhecível.

Arquivo:

```text
edges_explicit.csv
```

Colunas:

```text
source_message_id,target_message_id,edge_type,confidence,evidence_json
```

Confiança:

```text
explicit_reply = 1.0
native_thread = 0.95
quoted_message_link = 0.90
```

Menção direta não deve virar edge automaticamente; deve ser feature.

## Geração de candidatos

Para cada mensagem atual `m_i`, gerar candidatos anteriores `m_j`.

Critérios:

- últimas 50 mensagens anteriores;
- mensagens nas últimas 24h;
- mensagens de usuários mencionados;
- mensagens que mencionaram o autor atual;
- mensagens da mesma thread nativa;
- mensagens com similaridade textual;
- mensagens com termos técnicos compartilhados.

Gerar:

```text
candidate_pairs.csv
```

## Features por par

Temporais:

- `delta_seconds`
- `log_delta_seconds`
- `temporal_score`
- `same_burst`

Participantes:

- `same_author`
- `source_mentions_target_author`
- `target_mentions_source_author`
- `author_participated_recently`

Textuais:

- TF-IDF cosine similarity;
- fallback obrigatório sem embeddings;
- lexical overlap;
- shared technical tokens;
- shared URL;
- shared code/error marker.

Discursivas:

- target tem pergunta;
- source parece resposta;
- source começa com “sim”, “não”, “isso”, “depende”, “tenta”, “verifica”;
- source tem marcador de desacordo: “mas”, “porém”, “não é isso”, “na verdade”;
- source tem marcador de razão: “porque”, “pois”, “então”, “because”, “since”;
- source usa segunda pessoa: “você”, “seu”, “teu”, “you”, “your”.

Estruturais:

- explicit reply;
- same native thread;
- same channel;
- source/target bot;
- attachment;
- code block.

## Scoring heurístico inicial

Criar score auditável:

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

Regras:

- se explicit reply existir, score = 1.0;
- se mesma thread nativa, aumentar score;
- se distância temporal for muito grande sem reply/menção, penalizar;
- mensagens curtas devem depender mais de tempo, menção e participante;
- pergunta→resposta deve aumentar score;
- similaridade semântica sozinha não deve criar link forte se tempo e participantes não sustentarem.

Threshold padrão:

```text
0.50
```

Se nenhum candidato atingir threshold, a mensagem inicia nova thread.

## Grafo

Usar `networkx`.

Criar grafo direcionado:

```text
source = mensagem atual
target = mensagem anterior/pai
```

Exportar:

```text
graph_edges.csv
graph.graphml
graph.json
```

## Extração de threads

Converter o grafo para não-direcionado e extrair componentes conectados.

Cada thread deve conter:

- thread_id;
- root_message_id;
- mensagens em ordem temporal;
- participantes;
- início;
- fim;
- duração;
- quantidade de mensagens;
- quantidade de participantes;
- confiança média;
- número de links explícitos;
- número de links inferidos;
- número de links incertos;
- palavras-chave;
- forma conversacional preliminar.

Formas preliminares:

- pergunta-resposta;
- discussão técnica;
- sequência informativa;
- conversa social;
- ambígua;
- thread curta.

## Pós-processamento

Implementar:

1. split por grande lacuna temporal;
2. marcação de threads ambíguas;
3. sugestão de merge, sem fazer merge destrutivo automaticamente.

Critérios de ambiguidade:

- baixa confiança média;
- muitos links incertos;
- muitas mensagens curtas;
- múltiplos pais possíveis com scores próximos.

## Visualização

Gerar HTML estático:

```text
reports/neo4j_threads.html
```

A página deve mostrar:

- lista de threads;
- filtros por confiança, tamanho, participante e palavra-chave;
- cards de thread;
- mensagens em ordem temporal;
- participantes anonimizados;
- confiança média;
- badges: explicit, inferred, uncertain, ambiguous;
- arestas como “mensagem X responde/continua mensagem Y”.

Gerar também:

```text
reports/neo4j_threads_summary.md
```

## Export para Neo4j

Gerar opcionalmente:

```text
exports/neo4j_import.cypher
```

Modelo:

```cypher
(:User)-[:AUTHORED]->(:Message)
(:Message)-[:REPLIES_TO {confidence, method}]->(:Message)
(:Message)-[:BELONGS_TO]->(:Thread)
```

Não conectar automaticamente ao banco.

## Preparação para incivilidade posterior

Criar `thread_summaries.csv` com:

```text
thread_id,title,neutral_summary,scd_summary,incivility_label,derailment_risk
```

Por enquanto:

```text
scd_summary = null
incivility_label = null
derailment_risk = null
```

## CLI desejada

Exemplo:

```bash
python -m discord_disentanglement run \
  --input data/raw/discord_export.json \
  --channel-name Neo4J \
  --out data/processed/neo4j_threads \
  --threshold 0.50
```

Também aceitar CSV.

## Testes

Criar testes com `pytest` para:

- carregar JSON;
- carregar CSV;
- anonimizar usuários;
- extrair reply explícito;
- gerar candidatos;
- calcular score;
- construir grafo;
- extrair threads;
- gerar HTML.

Criar fixture sintética com:

- duas conversas intercaladas;
- uma reply explícita;
- uma menção;
- uma mensagem curta;
- uma resposta tardia;
- uma mensagem que inicia nova thread.

## Critérios de aceitação

O pipeline deve:

- rodar de ponta a ponta;
- filtrar o canal `Neo4J`;
- anonimizar usuários;
- preservar links explícitos;
- inferir links implícitos com confiança e evidências;
- gerar threads candidatas;
- gerar HTML navegável;
- não classificar incivilidade ainda;
- ser modular para futuro modelo supervisionado.

## Visualização robusta: Thread Explorer

Além do relatório HTML simples, implementar uma visualização robusta para inspeção humana do processo de conversation disentanglement.

O objetivo da visualização não é classificar incivilidade ainda. O objetivo é auditar e validar a reconstrução das threads.

A visualização deve ajudar a responder:

1. A thread reconstruída está coerente?
2. Quais mensagens foram ligadas?
3. Qual foi a evidência usada em cada ligação?
4. Onde o algoritmo está inseguro?
5. Quais threads precisam de revisão manual?

### Modos de visualização

Implementar dois modos:

1. Relatório HTML estático:
   - `reports/neo4j_threads.html`
   - adequado para compartilhamento, inspeção rápida e artefato reproduzível.

2. Dashboard interativo local:
   - preferencialmente com Streamlit;
   - arquivo sugerido: `apps/thread_explorer.py`;
   - comando sugerido:

```bash
streamlit run apps/thread_explorer.py -- \
  --data data/processed/neo4j_threads
```

Caso Streamlit não esteja disponível, implementar ao menos um HTML interativo com JavaScript local e dados embutidos em JSON.

### Estrutura do dashboard

O dashboard deve ter as seguintes seções:

#### 1. Overview do canal

Mostrar métricas gerais:

- total de mensagens processadas;
- total de threads extraídas;
- média e mediana de mensagens por thread;
- número de threads curtas;
- número de threads longas;
- número de threads ambíguas;
- percentual de links explícitos;
- percentual de links inferidos;
- percentual de links incertos;
- confiança média geral;
- distribuição de tamanhos de thread;
- distribuição de confiança das threads.

#### 2. Timeline do canal

Criar uma visualização temporal das mensagens e threads.

A timeline deve permitir identificar:

- períodos de alta atividade;
- múltiplas conversas simultâneas;
- threads que atravessam grandes lacunas temporais;
- possíveis erros de merge;
- possíveis erros de split.

Cada mensagem deve aparecer associada ao seu `thread_id`.

#### 3. Thread Explorer

Criar uma tela principal de inspeção de threads.

Cada thread deve aparecer como um card contendo:

- `thread_id`;
- título automático;
- root message;
- horário inicial;
- horário final;
- duração;
- número de mensagens;
- número de participantes;
- participantes anonimizados;
- confiança média;
- número de links explícitos;
- número de links inferidos;
- número de links incertos;
- palavras-chave;
- forma conversacional preliminar;
- status: `ok`, `ambiguous`, `needs_review`.

Dentro de cada card, mostrar as mensagens em ordem temporal:

- posição na thread;
- `message_id`;
- autor anonimizado;
- timestamp;
- conteúdo normalizado;
- mensagem pai, se existir;
- score do vínculo com a mensagem pai;
- tipo de link: `explicit_reply`, `native_thread`, `inferred`, `uncertain`;
- principais evidências do vínculo.

Exemplo de exibição textual:

```text
USER_001 · 10:03
Como faço relacionamento many-to-many no Neo4J?

USER_002 · 10:04
Você pode criar um nó intermediário...
↳ responde a m_001 | score=0.91 | evidências: tempo, pergunta-resposta, similaridade
```

#### 4. Graph Viewer da thread

Para cada thread, permitir visualizar o grafo da conversa.

Requisitos:

- nó = mensagem;
- aresta = relação mensagem → mensagem anterior;
- aresta explícita deve ser distinguível de aresta inferida;
- aresta incerta deve ser destacada;
- espessura ou opacidade da aresta deve representar confiança;
- clique em um nó deve mostrar a mensagem;
- clique em uma aresta deve mostrar as evidências.

Implementação sugerida:

- `networkx` para construção;
- `pyvis` ou `vis-network` para visualização interativa;
- exportar também um HTML por thread, se possível:

```text
reports/thread_graphs/T_0001.html
reports/thread_graphs/T_0002.html
```

#### 5. Evidence Inspector

Implementar uma área de inspeção de evidências para cada link.

Ao selecionar uma aresta, mostrar:

- `source_message_id`;
- `target_message_id`;
- conteúdo da mensagem source;
- conteúdo da mensagem target;
- `confidence`;
- `method`;
- `edge_type`;
- `delta_seconds`;
- `semantic_similarity`;
- `temporal_score`;
- `mention_score`;
- `lexical_overlap`;
- `question_answer_score`;
- `same_native_thread_score`;
- `participant_continuity_score`;
- `candidate_rank`;
- lista dos principais candidatos alternativos, se houver.

Exemplo de estrutura:

```json
{
  "source_message_id": "m_105",
  "target_message_id": "m_102",
  "confidence": 0.84,
  "method": "heuristic_v1",
  "evidence": {
    "delta_seconds": 42,
    "semantic_similarity": 0.71,
    "temporal_score": 0.93,
    "mention_score": 0.0,
    "lexical_overlap": 0.4,
    "question_answer_score": 0.8,
    "same_native_thread_score": 0.0,
    "participant_continuity_score": 0.65
  },
  "alternative_parents": [
    { "message_id": "m_101", "score": 0.66 },
    { "message_id": "m_099", "score": 0.52 }
  ]
}
```

#### 6. Ambiguity and Review View

Criar uma seção específica para revisão de casos problemáticos.

Listar automaticamente:

- threads com confiança média baixa;
- threads com muitos links incertos;
- threads com mensagens demais;
- threads com apenas uma mensagem;
- mensagens sem pai;
- mensagens com múltiplos pais candidatos próximos;
- possíveis splits;
- possíveis merges;
- mensagens curtas com baixa confiança;
- replies inferidos após grande lacuna temporal.

Cada item deve ter um motivo de revisão:

```text
needs_review_reason = "low_avg_confidence"
needs_review_reason = "large_temporal_gap"
needs_review_reason = "many_uncertain_edges"
needs_review_reason = "possible_wrong_merge"
needs_review_reason = "possible_over_split"
```

#### 7. Annotation Mode opcional

Preparar a estrutura para anotação manual, mesmo que simples.

Permitir exportar um CSV de revisão:

```text
annotation_review.csv
```

Colunas:

```text
thread_id,message_id,current_parent_id,suggested_parent_id,annotator_parent_id,review_status,notes
```

O dashboard pode permitir apenas marcar manualmente via arquivo CSV por enquanto. Não é obrigatório implementar edição interativa completa na primeira versão.

#### 8. Preparação para incivilidade futura

Na visualização, deixar campos preparados, mas vazios:

- `neutral_summary`;
- `scd_summary`;
- `incivility_label`;
- `derailment_risk`;
- `derailment_point`;
- `tone_markers`;
- `tension_triggers`.

Na interface, exibir esses campos como “not computed yet”.

Não implementar classificação agora.

### Arquivos adicionais esperados

Gerar:

```text
reports/neo4j_threads.html
reports/neo4j_threads_summary.md
reports/thread_graphs/
apps/thread_explorer.py
```

Se usar Streamlit, atualizar `requirements.txt` com:

```text
streamlit
plotly
pyvis
networkx
pandas
```

Se optar por HTML estático com JavaScript, evitar dependências externas online. Preferir arquivos locais ou CDN opcional documentada.

### Critérios de aceitação da visualização

A visualização será considerada satisfatória quando:

1. permitir navegar pelas threads reconstruídas;
2. mostrar mensagens em ordem temporal;
3. mostrar grafo de resposta/continuidade;
4. mostrar confiança de cada link;
5. mostrar evidências de cada link;
6. destacar threads ambíguas;
7. permitir identificar possíveis erros de merge e split;
8. não expor IDs reais de usuários;
9. carregar os arquivos gerados pelo pipeline;
10. preparar o caminho para futura anotação manual e classificação de incivilidade.
