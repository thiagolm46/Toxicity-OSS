# Disentanglement v2: metodo hibrido auditavel

## O que mudou em relacao a v1

A v1 ja reconstruia conversas como grafo mensagem -> mensagem anterior, preservava replies explicitos e gerava artefatos auditaveis. A v2 mantem esse desenho e adiciona:

- configuracao em `configs/disentanglement_default.yaml`;
- embeddings semanticos opcionais com fallback TF-IDF;
- `candidate_features.csv` alem de `candidate_pairs.csv`;
- score hibrido com campos de similaridade semantica, TF-IDF e evidencias;
- metricas diagnosticas sem anotacao manual;
- exports Neo4j enriquecidos com `PredictedConversation`;
- documentacao explicita das limitacoes cientificas.

## Por que embeddings foram adicionados

Chats tecnicos contem mensagens curtas, sinonimos, erros, codigo e reformulacoes. TF-IDF captura repeticao lexical, mas falha quando duas mensagens sao semanticamente relacionadas sem compartilhar muitos tokens. Embeddings entram como sinal adicional, nao como decisor unico.

Se `sentence-transformers` ou o modelo configurado nao estiver disponivel, o pipeline registra o fallback em `embedding_metadata.json` e continua com TF-IDF.

## Configuracao recomendada para GPU de 8 GB

Para uma GPU de notebook com 8 GB de VRAM, como RTX 2000 Ada Generation Laptop GPU, a configuracao padrao segura e:

```yaml
embeddings:
  enabled: true
  model_name: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  batch_size: 8
  min_batch_size: 1
  max_seq_length: 256
  device: auto
  precision: fp16
```

Essa configuracao prioriza estabilidade e evita OOM. O encoder reduz automaticamente o batch em caso de CUDA OOM recuperavel. Para maxima qualidade, `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` pode ser testado com `batch_size: 2` ou `4`, mas nao e o perfil recomendado para execucao completa inicial em 8 GB.

## Por que continuamos com mensagem -> mensagem

O metodo principal continua inferindo um parent para cada mensagem candidata. Isso preserva auditabilidade: cada aresta tem score, metodo, evidencia e candidatos alternativos. Clustering semantico global nao e usado como metodo principal porque tende a agrupar topicos parecidos sem respeitar turno, tempo, mencoes e continuidade conversacional.

## Explicit replies

Replies explicitos, `message_reference`, mensagens referenciadas e thread nativa sao extraidos antes das inferencias. Quando ha reply explicito, ele vence a heuristica e recebe score 1.0.

## Geracao de candidatos

Para cada mensagem source, o target deve ser anterior ao source, salvo relacoes explicitas ja documentadas. A v2 combina:

- janela temporal;
- ultimas N mensagens;
- replies explicitos;
- mencoes e continuidade de participante;
- TF-IDF;
- embeddings opcionais;
- tokens tecnicos compartilhados;
- URL, codigo e marcadores de erro.

`thread_id` nao e usado como feature direta de predicao. Quando disponivel, serve apenas como estrutura explicita nativa ou referencia silver para diagnostico.

## Score hibrido

O score preserva os pesos da v1 e adiciona campos explicitos para `semantic_similarity`, `tfidf_similarity`, `score_heuristic`, `score_final` e `model_version`. Similaridade semantica isolada nao deve criar link forte sem suporte temporal ou social. Mensagens curtas continuam preservadas e dependem mais de tempo, mencao e continuidade de participantes.

Links com candidatos proximos sao marcados como `uncertain_reply`; links mais estaveis sao `inferred_reply`; replies nativos continuam como `explicit_reply`.

## Extracao de threads

O baseline continua usando componentes conectados fracos sobre o grafo de mensagens. Depois disso, o pipeline marca threads por status:

- `ok`;
- `ambiguous`;
- `needs_review`.

Sinais de revisao incluem baixa confianca, links incertos, grandes lacunas temporais, muitas mensagens curtas, singletons e possiveis over-merges.

## Avaliacao sem anotacao manual

A v2 gera:

- `reports/metrics/disentanglement_metrics.json`;
- `reports/metrics/disentanglement_metrics.csv`;
- `reports/metrics/threshold_sensitivity.csv`;
- `reports/metrics/ablation_results.csv`;
- `reports/errors/*.csv`.

Essas metricas nao provam verdade conversacional definitiva. Explicit replies e `thread_id` nativo sao referencias fracas/silver. Elas servem para diagnostico, comparacao de configuracoes e robustez estrutural.

Metricas principais:

- coverage;
- explicit reply recovery rate;
- precision/recall@1 contra explicit replies;
- numero de threads;
- singletons;
- pairwise precision/recall/F1 contra silver labels;
- ARI, NMI e purity quando ha referencia nativa;
- sensibilidade por threshold.

## Interface

O HTML principal continua offline e sem CDN. Ele mostra cobertura, metricas, lista de threads, mensagens ordenadas, parent escolhido, score, evidencias e candidatos alternativos. As paginas individuais em `reports/thread_graphs/*.html` continuam textuais para leitura e auditoria.

## Neo4j

A v2 preserva os exports antigos e adiciona:

- `neo4j_predicted_conversations.csv`;
- `neo4j_message_belongs_to_predicted_conversation.csv`;
- `neo4j_predicted_replies_to_relationships.csv`;
- `neo4j_message_disentanglement_properties.csv`;
- `neo4j_import_disentanglement.cypher`;
- `README_NEO4J_IMPORT.md`.

O Neo4j e uma camada de exploracao posterior do grafo, nao o mecanismo que decide os links.

## Limitacoes

- O pipeline nao classifica incivilidade.
- O pipeline nao classifica toxicidade.
- O pipeline nao produz ground truth definitivo.
- Sem anotacao manual, a avaliacao e estrutural, diagnostica e comparativa.
- Embeddings dependem de disponibilidade local de dependencia/modelo; o fallback TF-IDF e esperado em ambientes offline.
- A qualidade depende da cobertura do dataset de entrada e da presenca de replies explicitos.
