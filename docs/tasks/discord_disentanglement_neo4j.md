Você é um engenheiro de pesquisa em NLP, conversation disentanglement, engenharia de software empírica e visualização de dados conversacionais.

Estou trabalhando em um projeto já existente chamado `discord_disentanglement`. NÃO recrie o projeto do zero. Antes de implementar qualquer mudança, leia a estrutura atual do repositório, os módulos existentes, os testes e os documentos metodológicos já presentes.

Documentos metodológicos importantes já existentes:

* `DISENTANGLEMENT_DEVELOPMENT_PROCESS.md`
* `NEO4J_DISENTANGLEMENT_INTERFACE_METHODOLOGY.md`
* `PIPELINE_USAGE_AND_METHODOLOGY.md`
* `FILTERING_FINDINGS.md`
* `CHANNEL_SELECTION_PROTOCOL.md`
* prompt/tarefa inicial de disentanglement, se existir em `docs/tasks/discord_disentanglement_neo4j.md`

Objetivo desta rodada:
Evoluir o pipeline atual de conversation disentanglement para uma versão mais robusta, mantendo compatibilidade com a v1 já implementada.

Escopo:

* Focar exclusivamente em conversation disentanglement.
* Não implementar toxicidade, incivilidade, SCD, derailment ou moderação.
* Não exigir anotação manual.
* Não usar `thread_id` como feature direta de predição.
* Usar `thread_id`, quando disponível, apenas como referência estrutural/silver label para avaliação.
* Preservar privacidade: interface e relatórios devem continuar usando conteúdo normalizado e usuários anonimizados.
* Preservar auditabilidade: cada vínculo inferido deve continuar tendo score, método e evidências legíveis.

Estado atual conhecido:
O pipeline já possui:

* leitura de JSON, CSV e Parquet;
* filtragem por guild/canal;
* normalização de conteúdo;
* anonimização de autores e menções;
* extração de edges explícitos;
* geração de candidatos anteriores por mensagem;
* score heurístico auditável;
* construção de grafo com NetworkX;
* extração de threads como componentes conectados;
* exportação para CSV, JSON, GraphML, HTML e Neo4j;
* relatório HTML estático para inspeção;
* testes sintéticos para casos como reply explícito, menção, mensagem curta e conversas intercaladas.

A evolução deve respeitar esse desenho:
mensagem atual → mensagem anterior candidata → score/evidências → aresta → grafo → thread candidata

Não substituir isso por clustering semântico global.

==================================================

1. Auditoria inicial obrigatória
   ==================================================

Primeiro, faça uma auditoria do código atual e gere um pequeno relatório em:

`reports/development/disentanglement_upgrade_audit.md`

O relatório deve listar:

* módulos existentes;
* comandos CLI existentes;
* artefatos atualmente gerados;
* testes existentes;
* pontos onde o pipeline já faz normalização;
* pontos onde extrai explicit replies;
* pontos onde gera candidatos;
* pontos onde calcula score;
* pontos onde constrói grafo;
* pontos onde gera HTML;
* pontos onde exporta para Neo4j;
* riscos de quebrar compatibilidade.

Depois implemente mudanças incrementais, preservando os comandos existentes.

==================================================
2. Configuração
===============

Criar ou atualizar um arquivo:

`configs/disentanglement_default.yaml`

Adicionar parâmetros sem quebrar o comportamento atual:

embeddings:
enabled: true
provider: sentence_transformers
model_name: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
fallback_to_tfidf: true
batch_size: 64
normalize: true
cache: true

candidate_generation:
max_previous_messages: 50
max_time_delta_minutes: 1440
same_channel_only: true
include_explicit_replies: true
include_temporal_candidates: true
include_semantic_candidates: true
semantic_top_k: 20
min_semantic_similarity: 0.25
max_candidates_per_message: 80

link_scoring:
mode: hybrid
threshold: 0.50
explicit_reply_score: 1.0
uncertain_margin: 0.08
weights:
semantic_similarity: 0.30
temporal_score: 0.20
mention_score: 0.15
lexical_overlap: 0.10
question_answer_score: 0.10
same_native_thread_score: 0.10
participant_continuity_score: 0.05

evaluation:
enabled: true
use_thread_id_as_silver_reference: true
use_explicit_replies_as_reference: true
compute_link_metrics: true
compute_cluster_metrics: true
compute_stability_metrics: true
thresholds: [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]

interface:
mode: static_html
generate_thread_pages: true
generate_overview: true
show_evidence: true
show_alternative_parents: true
show_ambiguity: true
show_timeline: true
preserve_offline_compatibility: true

neo4j_export:
enabled: true
message_label: Message
conversation_label: PredictedConversation
predicted_reply_relationship: PREDICTED_REPLIES_TO
belongs_to_predicted_relationship: BELONGS_TO_PREDICTED_CONVERSATION
generate_aura_notes: true

random_seed: 42

Se o projeto já usa outro formato de configuração, integre esses campos ao padrão existente.

==================================================
3. Embeddings semânticos opcionais
==================================

Adicionar um módulo incremental, sem remover TF-IDF:

`discord_disentanglement/embeddings.py`

Requisitos:

* usar `sentence-transformers` quando instalado;
* modelo default: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`;
* gerar embeddings para `content_normalized`;
* normalizar embeddings para cosine similarity;
* cachear embeddings em arquivo `.npy`;
* gerar índice `message_id -> embedding_index`;
* se `sentence-transformers` não estiver disponível, usar o TF-IDF atual sem quebrar o pipeline;
* registrar nos logs se o pipeline está usando embeddings reais ou fallback TF-IDF.

Artefatos:

* `message_embeddings.npy`
* `message_embedding_index.csv`
* `embedding_metadata.json`

Não baixar modelo silenciosamente sem log. O usuário precisa saber qual modelo foi usado.

==================================================
4. Candidate generation híbrido
===============================

Evoluir a geração de candidatos sem remover as estratégias atuais.

Para cada mensagem source, gerar candidatos target anteriores por:

1. janela temporal;
2. últimas N mensagens;
3. explicit replies obrigatórios;
4. menções e continuidade de participante;
5. similaridade textual TF-IDF;
6. similaridade por embeddings, quando disponível;
7. tokens técnicos compartilhados;
8. URLs, código ou erro compartilhado.

Regras:

* target deve sempre ser anterior ao source, exceto se já houver explicit reply documentado em sentido diferente;
* menção não cria edge automaticamente;
* `thread_id` não pode ser usado para criar candidato obrigatório, exceto se for uma thread nativa explicitamente reconhecida já tratada pelo pipeline;
* limitar candidatos por mensagem para evitar explosão combinatória.

Atualizar ou gerar:

`candidate_pairs.csv`

Colunas mínimas:

* source_message_id
* target_message_id
* candidate_sources
* source_timestamp
* target_timestamp
* delta_seconds
* same_channel
* same_author
* explicit_reply_exists
* semantic_similarity
* tfidf_similarity
* candidate_rank_by_time
* candidate_rank_by_semantic_similarity

==================================================
5. Features por par
===================

Atualizar o cálculo de features por par em um módulo claro.

Gerar ou atualizar:

`candidate_features.csv`

Features obrigatórias:

* delta_seconds
* log_delta_seconds
* temporal_score
* same_burst
* same_author
* source_mentions_target_author
* target_mentions_source_author
* author_participated_recently
* participant_continuity_score
* lexical_overlap
* jaccard_token_overlap
* tfidf_similarity
* semantic_similarity
* shared_technical_tokens
* shared_url_marker
* shared_code_or_error_marker
* target_has_question
* source_is_probable_answer
* question_answer_score
* explicit_reply_exists
* same_channel
* same_native_thread, se existir de forma nativa
* score_gap_to_second_best
* number_of_close_candidates

Preservar compatibilidade com as features antigas.

==================================================
6. Link scoring híbrido
=======================

Evoluir o score atual para modo híbrido, preservando o score heurístico.

O score final deve combinar:

* score heurístico atual;
* similaridade por embeddings, se disponível;
* TF-IDF, como fallback ou sinal auxiliar;
* força de explicit reply;
* continuidade temporal;
* continuidade de participantes;
* pergunta-resposta;
* sinais técnicos compartilhados.

Regras:

* explicit reply deve continuar recebendo score 1.0;
* mensagens curtas não devem ser penalizadas apenas por baixa similaridade textual;
* mensagens curtas devem depender mais de tempo, menção, participação e contexto;
* similaridade semântica isolada não deve criar link forte se tempo e participantes não sustentarem a relação;
* candidatos com scores próximos devem ser marcados como ambíguos/uncertain;
* se nenhum candidato atingir o threshold, a mensagem deve iniciar nova thread.

Gerar ou atualizar:

`edges_inferred.csv`

Colunas:

* source_message_id
* target_message_id
* confidence
* method
* edge_type
* semantic_similarity
* tfidf_similarity
* time_delta_seconds
* score_heuristic
* score_final
* evidence_json
* alternative_parents_json
* model_version

Tipos de edge:

* explicit_reply
* inferred_reply
* uncertain_reply

==================================================
7. Extração de threads
======================

Preservar WCC/componentes conectados como baseline principal, mas adicionar pós-processamento mais explícito.

Gerar:

* `threads.csv`
* `thread_messages.csv`
* `threads.json`
* `thread_summaries.csv`

Cada thread deve conter:

* thread_id ou predicted_thread_id
* root_message_id
* title
* status
* start_timestamp
* end_timestamp
* duration_seconds
* message_count
* participant_count
* avg_confidence
* min_confidence
* explicit_edge_count
* inferred_edge_count
* uncertain_edge_count
* channel_name
* keywords
* conversation_shape
* needs_review_reason

Cada linha de `thread_messages.csv` deve conter:

* thread_id
* message_id
* parent_message_id
* position_in_thread
* author_id_anonymized
* timestamp
* content_normalized
* confidence_to_parent
* edge_type_to_parent
* method_to_parent
* evidence_json
* alternative_parents_json
* is_root

Critérios para status:

* ok
* ambiguous
* needs_review

Marcar `needs_review` quando:

* confiança média baixa;
* muitos links incertos;
* muitos candidatos alternativos próximos;
* grande lacuna temporal interna;
* thread grande demais;
* possível over-merge;
* possível over-split.

==================================================
8. Avaliação sem anotação manual
================================

Como não há classificação manual, implementar avaliação estrutural e diagnóstica, não avaliação como gold standard definitivo.

Gerar:

`reports/metrics/disentanglement_metrics.json`
`reports/metrics/disentanglement_metrics.csv`
`reports/metrics/threshold_sensitivity.csv`
`reports/metrics/ablation_results.csv`
`reports/errors/ambiguous_edges.csv`
`reports/errors/low_confidence_threads.csv`
`reports/errors/possible_overmerged_threads.csv`
`reports/errors/possible_oversplit_threads.csv`

Métricas de link prediction, usando explicit replies como referência quando disponíveis:

* coverage;
* explicit_reply_recovery_rate;
* precision@1 contra explicit replies;
* recall@1 contra explicit replies;
* top_k_recall, se alternative_parents_json existir.

Métricas estruturais, usando thread_id apenas como silver reference quando existir:

* número de threads previstas;
* tamanho médio e mediano;
* distribuição de tamanhos;
* fragmentation;
* mixing;
* pairwise precision;
* pairwise recall;
* pairwise F1;
* ARI;
* NMI;
* purity.

Métricas de estabilidade:

* rodar ou simular avaliação com thresholds 0.40, 0.45, 0.50, 0.55, 0.60, 0.65;
* registrar número de threads, singletons, média de confiança, fragmentation e mixing para cada threshold.

A documentação deve deixar claro:

* sem anotação manual, essas métricas não provam verdade conversacional definitiva;
* elas servem para diagnóstico, comparação de configurações e robustez estrutural;
* explicit replies e thread_id são referências fracas ou estruturais.

==================================================
9. Interface própria de inspeção de conversas
=============================================

Melhorar a interface existente sem perder o modo HTML estático.

A interface principal deve continuar funcionando offline, sem Neo4j, sem internet e sem CDN.

Atualizar:

`reports/neo4j_threads.html`

A interface deve ter:

1. Overview:

* total de mensagens;
* total de threads;
* total de singletons;
* média/mediana de mensagens por thread;
* contagem de explicit/inferred/uncertain edges;
* confiança média;
* distribuição de tamanho;
* distribuição de status;
* canais processados.

2. Lista de threads:

* filtro por status;
* filtro por tamanho mínimo/máximo;
* filtro por confiança;
* filtro por canal;
* busca textual;
* filtro por links incertos;
* ordenação por tamanho, confiança, duração e status.

3. Thread detail:
   Mostrar mensagens em ordem temporal:

* autor anonimizado;
* timestamp;
* conteúdo normalizado;
* badge root/explicit/inferred/uncertain;
* parent escolhido;
* confiança do vínculo;
* método;
* evidências compactas;
* candidatos alternativos.

4. Evidence inspector:
   Ao selecionar uma mensagem/edge, mostrar:

* source message;
* target message;
* delta_seconds;
* semantic_similarity;
* tfidf_similarity;
* temporal_score;
* lexical_overlap;
* mention_score;
* question_answer_score;
* participant_continuity_score;
* score_final;
* alternative parents;
* evidence_json formatado.

5. Ambiguity view:
   Mostrar automaticamente:

* threads com baixa confiança;
* links incertos;
* mensagens com múltiplos pais próximos;
* grandes lacunas temporais;
* possíveis merges ruins;
* possíveis splits excessivos;
* singletons suspeitos.

6. Timeline:
   Adicionar uma visualização simples em HTML/JS local:

* pontos por mensagem ao longo do tempo;
* cor por thread/status;
* destaque para lacunas temporais;
* não depender de bibliotecas externas via CDN.

As páginas individuais em `reports/thread_graphs/*.html` podem continuar textuais, mas devem mostrar:

* resumo da thread;
* mensagens ordenadas;
* parent de cada mensagem;
* evidências;
* links para voltar ao relatório principal.

Não expor IDs reais de usuários.

==================================================
10. Exportação para Neo4j
=========================

Preservar export atual, mas adicionar artefatos mais úteis para análise no Neo4j.

Gerar em `exports/`:

1. `neo4j_users.csv`
2. `neo4j_messages.csv`
3. `neo4j_threads.csv`
4. `neo4j_authored_relationships.csv`
5. `neo4j_belongs_to_relationships.csv`
6. `neo4j_replies_to_relationships.csv`
7. `neo4j_predicted_conversations.csv`
8. `neo4j_message_belongs_to_predicted_conversation.csv`
9. `neo4j_predicted_replies_to_relationships.csv`
10. `neo4j_message_disentanglement_properties.csv`
11. `neo4j_import.cypher`
12. `neo4j_import_disentanglement.cypher`
13. `README_NEO4J_IMPORT.md`

Modelo final desejado no Neo4j:

(:User)-[:AUTHORED]->(:Message)

(:Message)-[:REPLIES_TO]->(:Message)
// relação original ou extraída explicitamente

(:Message)-[:PREDICTED_REPLIES_TO]->(:Message)
// relação inferida pelo pipeline

(:Message)-[:BELONGS_TO]->(:Thread)
// thread candidata antiga ou original, quando existir

(:Message)-[:BELONGS_TO_PREDICTED_CONVERSATION]->(:PredictedConversation)

(:PredictedConversation)
// nó agregado da conversa reconstruída

`neo4j_predicted_conversations.csv`:

* predicted_conversation_id
* root_message_id
* title
* status
* method
* size
* participant_count
* start_timestamp
* end_timestamp
* duration_seconds
* avg_confidence
* min_confidence
* explicit_edge_count
* inferred_edge_count
* uncertain_edge_count
* channel_name
* guild_name
* keywords
* conversation_shape
* needs_review_reason

`neo4j_message_belongs_to_predicted_conversation.csv`:

* message_id
* predicted_conversation_id
* confidence
* method
* position_in_thread
* is_root

`neo4j_predicted_replies_to_relationships.csv`:

* source_message_id
* target_message_id
* confidence
* method
* edge_type
* semantic_similarity
* tfidf_similarity
* time_delta_seconds
* evidence_json
* model_version

`neo4j_message_disentanglement_properties.csv`:

* message_id
* predicted_conversation_id
* predicted_parent_id
* disentanglement_confidence
* disentanglement_method
* is_conversation_root
* thread_position
* thread_status

O Cypher deve:

* criar constraint para `PredictedConversation.id`;
* atualizar propriedades de `Message`;
* criar relações `PREDICTED_REPLIES_TO`;
* criar relações `BELONGS_TO_PREDICTED_CONVERSATION`;
* ser compatível com importação local via `file:///`;
* documentar no README que, no Neo4j Aura, os arquivos devem ser importados via Data Importer ou URLs HTTPS.

==================================================
11. CLI
=======

Preservar o comando atual:

python -m discord_disentanglement run ...

Adicionar ou documentar comandos incrementais, se a arquitetura permitir:

python -m discord_disentanglement validate ...
python -m discord_disentanglement embed ...
python -m discord_disentanglement evaluate ...
python -m discord_disentanglement export-neo4j ...

O comando principal `run` deve continuar executando de ponta a ponta.

Adicionar flags:

* `--config`
* `--use-embeddings`
* `--no-embeddings`
* `--threshold`
* `--export-neo4j`
* `--generate-report`

Não quebrar a chamada antiga documentada:

uv run python -m discord_disentanglement run `  --input data/processed/software_messages.parquet`
--guild-name Neo4j `  --out data/processed/neo4j_threads`
--threshold 0.50

==================================================
12. Testes
==========

Atualizar testes existentes e adicionar novos testes para:

* preservar explicit reply com score 1.0;
* garantir que menção não vira edge automaticamente;
* manter mensagens curtas;
* filtrar guild/canal antes da inferência;
* gerar embeddings ou usar fallback TF-IDF;
* incluir candidatos por similaridade;
* calcular semantic_similarity;
* gerar candidate_features.csv;
* marcar uncertain quando scores forem próximos;
* extrair threads;
* marcar needs_review;
* gerar métricas;
* gerar HTML principal;
* gerar export Neo4j com PredictedConversation;
* não usar thread_id como feature direta;
* garantir que nenhum ID real de usuário apareça nos relatórios HTML.

Criar ou manter fixture com:

* duas conversas intercaladas;
* uma reply explícita;
* uma menção;
* uma mensagem curta;
* uma resposta tardia;
* uma mensagem que inicia nova thread;
* uma conversa técnica com código;
* uma conversa com URL inválida;
* um caso ambíguo com dois pais possíveis.

==================================================
13. Documentação
================

Atualizar documentação sem apagar o histórico.

Criar ou atualizar:

`docs/methodology/DISENTANGLEMENT_V2_METHOD.md`

Esse documento deve explicar:

* o que mudou em relação à v1;
* por que embeddings foram adicionados;
* por que o método continua inferindo mensagem→mensagem;
* por que não usamos clustering semântico global como método principal;
* como explicit replies são usados;
* como candidatos são gerados;
* como score híbrido é calculado;
* como threads são extraídas;
* como a avaliação funciona sem anotação manual;
* como interpretar métricas silver-label;
* como abrir a interface;
* como importar no Neo4j;
* limitações.

Deixar claro:

* o pipeline não faz incivilidade;
* o pipeline não faz toxicidade;
* o pipeline não afirma produzir ground truth definitivo;
* sem anotação manual, a avaliação é estrutural, diagnóstica e comparativa;
* o Neo4j é usado como camada de grafo para exploração posterior;
* a interface própria é usada para observar as mensagens nas threads.

==================================================
14. Critérios de aceitação
==========================

A tarefa estará concluída quando:

1. O comando antigo continuar funcionando.
2. O pipeline gerar os artefatos antigos.
3. O pipeline gerar embeddings ou cair corretamente para TF-IDF.
4. O candidate generation incluir sinais temporais, participantes, TF-IDF e embeddings.
5. O score final preservar evidence_json.
6. Explicit replies continuarem vencendo a heurística.
7. Menções não criarem aresta automaticamente.
8. Mensagens curtas forem preservadas.
9. Threads forem extraídas e marcadas com status.
10. Métricas estruturais forem geradas.
11. Sensibilidade por threshold for gerada.
12. O HTML principal permitir observar conversas reconstruídas.
13. A interface mostrar mensagens, pais, scores, evidências e ambiguidades.
14. Artefatos Neo4j enriquecidos forem gerados.
15. Testes principais passarem.
16. A documentação explicar a v2 e suas limitações.

Implemente essa evolução incremental agora.
