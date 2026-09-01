# Protocolo de avaliação de conversation disentanglement

**Schema de métricas:** 2.0  
**Unidade principal:** replies explícitos do split temporal de teste  
**Referência:** silver parcial, nunca gold conversacional completo

## 1. Split temporal

As 35.787 mensagens do Neo4j são ordenadas por `(timestamp, message_id)` e
divididas globalmente em 60% treino, 20% validação e 20% teste. O corte é fixo
para todas as abordagens. O teste é sempre held-out. `weak_supervision` pode
receber reply edges somente do treino; os outros quatro métodos não recebem
labels Discord.

## 2. Candidate generation

Para cada mensagem-fonte são elegíveis apenas mensagens:

1. do mesmo canal;
2. estritamente anteriores;
3. dentro de 24 horas;
4. entre as 50 mensagens anteriores configuradas.

A ordenação de geração intercala candidatos recentes e candidatos com maior
similaridade temática. Ela é independente do cap: cada prefixo K representa a
mesma política truncada. O piloto v2 mede K = 5, 10, 20 e 50.

Para um reply explícito `(source, parent)`:

```text
CandidateRecall@K = 1[parent pertence aos primeiros K candidatos]
```

São reportados Candidate Recall, média e mediana do número de candidatos. Esta
etapa é comum e acontece antes de qualquer abordagem.

## 3. Parent ranking

Cada método atribui score aos mesmos pares. O pai com maior score tem rank 1.

- **Overall:** todo reply explícito do teste participa. Se o pai não estiver nos
  candidatos, Reciprocal Rank e hits são zero. Mede geração + ordenação.
- **Conditional:** considera somente sources cujo pai foi gerado. Mede a ordenação
  dado que o candidato correto estava disponível.

São calculados Recall@1, @3, @5, @10, MRR, mean rank e median rank. Scores de
métodos distintos não são probabilidades calibradas e não devem ser comparados
numericamente. O threshold de link usa, em todos os métodos, o mesmo quantil de
abstenção dos melhores scores da validação sem labels.

## 4. Construção da referência silver

Cada `direct_reply` válido é uma aresta positiva observada. A união das arestas
forma componentes conexos chamados **explicit-reply silver threads**. Um
componente é incluído na avaliação de teste quando contém ao menos um source de
reply do teste. Arestas de treino ou validação podem ligar mensagens no mesmo
componente, mas nenhuma é disponibilizada ao scorer de teste.

Regras conceituais obrigatórias:

```text
direct_reply       = relação positiva observada
sem direct_reply   = relação desconhecida
silver component   != conversa gold completa
```

## 5. Projeção das conversas previstas

Clusters previstos podem conter mensagens sem anotação explícita. Penalizá-las
como falsas seria assumir incorretamente que “não observado” significa negativo.
Por isso, a avaliação intersecta cada cluster previsto com o conjunto de mensagens
pertencentes aos componentes silver avaliáveis. Somente essa projeção é comparada.

## 6. Métricas de reconstrução

- **ARI:** Adjusted Rand Index via scikit-learn.
- **NMI:** Normalized Mutual Information via scikit-learn.
- **VI:** `H(S) + H(P) - 2 I(S;P)`, em log natural; menor é melhor.
- **B-Cubed precision:** para cada mensagem, fração do cluster previsto que
  pertence ao seu cluster silver; depois média.
- **B-Cubed recall:** para cada mensagem, fração de seu cluster silver recuperada
  no cluster previsto; depois média.
- **B-Cubed F1:** média harmônica das duas médias anteriores.
- **Exact Match:** proporção de componentes silver cujo conjunto de mensagens é
  idêntico a alguma projeção prevista.
- **Fragmentation rate:** proporção de componentes silver distribuídos por mais
  de um cluster previsto.
- **Merge rate:** proporção de clusters previstos projetados que contêm mensagens
  de mais de um componente silver.

ARI/NMI vêm de biblioteca estabelecida. B-Cubed, VI e os erros estruturais têm
implementações pequenas e testes sintéticos para reconstrução perfeita,
fragmentação e merge.

## 7. Dificuldade

Os limites estão em `configs/experiments/neo4j_pilot.json`:

- parent distance: 1–2, 3–5, 6–10, 11–20, >20 mensagens;
- time gap: <30 s, 30 s–2 min, 2–5 min, 5–15 min, >=15 min;
- competição: `low` até 5 candidatos, `medium` entre 6 e 14, `high` a partir de 15.

Cada estrato registra quantidade, Candidate Recall, Recall@1 overall e MRR overall.

## 8. Incerteza estatística

O piloto usa bootstrap percentil agrupado por canal, 1.000 reamostragens, seed 42
e intervalo de 95%. São produzidos intervalos para Recall@1 overall, MRR overall,
B-Cubed F1 e ARI. O bootstrap por mensagem também está disponível em configuração,
mas não é o default porque mensagens do mesmo canal não são independentes.

`paired_bootstrap.json` reamostra os mesmos canais e os mesmos sources para cada
par de métodos, estimando diferenças pareadas de Recall@1 e MRR. Esses intervalos
não são testes de hipótese automáticos e não demonstram superioridade universal.

## 9. Leakage audit

Antes de `fit` e `score`, a auditoria rejeita colunas como `direct_reply`,
`reply_to`, `reference`, `referenced_message`, labels e IDs nativos de thread.
Também verifica:

- gold entregue a método não supervisionado;
- qualquer split diferente de treino no gold permitido;
- caches serializados ou grafos com arestas silver expostos à abordagem;
- referência do teste visível durante candidate generation ou inferência.

O `manifest.json` registra `PASSED` ou a execução falha. Os campos silver são
anexados ao ranking somente depois que todos os scores e ranks foram calculados.

## 10. Artefatos e reprodutibilidade

Cada abordagem escreve:

- `predicted_links.parquet`;
- `message_assignments.parquet`;
- `predicted_threads.parquet`;
- `test_ranked_candidates.parquet`;
- `test_gold_outcomes.parquet`;
- `silver_projection.parquet`;
- `review_sample.csv`;
- `metrics.json`;
- `manifest.json`.

O diretório comum contém `comparison.csv`, `comparison.md` e
`paired_bootstrap.json`. O manifesto registra hashes dos artefatos, dataset e
configuração, commit Git, versões de Python/numpy/pandas/pyarrow/scikit-learn/scipy,
seed, hardware, checkpoint e commit externo.

## 11. Limitações

1. `direct_reply` não representa todas as respostas do Discord.
2. Silver threads representam somente a estrutura explicitamente observável.
3. Mensagens sem reply possuem relação desconhecida, não negativa.
4. Candidate Recall impõe um teto às métricas overall de ranking.
5. Bons links locais não garantem bons clusters.
6. A transferência IRC → Discord sofre domain shift de plataforma, época,
   vocabulário, comportamento de menções e convenções de resposta.
7. O split é temporal global dentro de um único servidor; generalização para
   outros servidores ainda não foi medida.
8. O corpus inclui canais ainda marcados `pending` na decisão humana. O piloto não
   deve ser descrito como corpus final de canais validados.

