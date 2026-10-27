# Auditoria de interacting_authors

## Explicacao concisa

A hipotese principal e: quantidade de autores humanos distintos que, no canal, enviaram pelo menos uma referencia de resposta a uma mensagem humana anterior presente no mesmo canal/export, ou uma mensagem com `mention_count > 0`. Cada autor e contado uma unica vez. Conta emissores, nao destinatarios apenas por receberem resposta ou mencao. Nao mede conversas semanticas.

Resultado observado dessa hipotese: **689 de 689 canais coincidentes**, 0 divergencias e 0 decisoes finais alteradas. A comparacao cobre todos os canais da fonte historica, incluindo os excluidos.

## O que foi recuperado

Foram comparadas 7 definicoes explicitas. Candidatas com igualdade em todos os canais: `resolved_reply_or_mention_senders`.

Igualdade no corpus congelado e evidencia de compatibilidade empirica, nao prova de que a rotina original foi recuperada, nem de que outras implementacoes seriam impossiveis. A implementacao antiga continua ausente. As afirmacoes sobre o calculo estao limitadas as definicoes aqui executadas e ao snapshot identificado pelos hashes.

## Comparacao das definicoes

| Candidata | Canais iguais | Canais diferentes | Maior diferenca absoluta | Diferentes com menos de 500 mensagens | Decisoes finais alteradas |
| --- | ---: | ---: | ---: | ---: | ---: |
| `human_authors` | 28 | 661 | 211259 | 307 | 42 |
| `reply_senders` | 232 | 457 | 1144 | 136 | 18 |
| `mention_senders` | 341 | 348 | 249 | 61 | 1 |
| `reply_or_mention_senders` | 634 | 55 | 11 | 11 | 1 |
| `resolved_reply_senders` | 222 | 467 | 1455 | 145 | 23 |
| `resolved_reply_or_mention_senders` | 689 | 0 | 0 | 0 | 0 |
| `other_author_reply_or_mention_senders` | 485 | 204 | 234 | 33 | 0 |

## Predicados executados

- `human_authors`: distinct nonempty author_id with is_bot=false.

- `reply_senders`: distinct human source authors with nonempty referenced_message_id, whether resolved or not and regardless of message type.

- `mention_senders`: distinct human source authors with mention_count>0, including self/bot mentions if present.

- `reply_or_mention_senders`: distinct human source authors with referenced_message_id or mention_count>0; no semantic reply inference.

- `resolved_reply_senders`: distinct human source authors referencing a unique preceding human message in the same guild/channel; self replies allowed.

- `resolved_reply_or_mention_senders`: resolved_reply_senders union mention_senders; counts source authors, not recipients.

- `other_author_reply_or_mention_senders`: human authors replying to a unique preceding human message by another author in the same guild/channel, or with mention_count>0.

A variante principal aceita autorrespostas. A condicao de mencao usa somente `mention_count > 0`, sem exigir que o destinatario seja outro humano e sem procurar um antecedente semantico. Replies sao identificados pelo campo de referencia, nao obrigatoriamente pelo tipo Discord 19. A variante resolvida exige pai humano unico, com timestamp valido e anterior na ordem UTC/ID, no mesmo servidor e canal. Essas escolhas sao explicitas na reconstrucao; casos nao presentes no export nao permitem distinguir todas as alternativas historicas.

## Papel no filtro e impacto

A regra final exclui por baixa atividade apenas quando `total_messages < 500 AND interacting_authors < 5`; a lista manual e aplicada por uniao. Assim, a metrica serve de contrapeso ao volume em canais pequenos, nao como validacao de relevancia para Engenharia de Software ou qualidade conversacional.

A decisao historica manteve 407 canais; 110 tinham menos de 500 mensagens brutas. Substituir a metrica por autores humanos distintos mudaria 42 decisoes nesta auditoria. As comparacoes sao contrafactuais: nenhum corpus, quadro ou amostra foi alterado.

O filtro exploratorio 552 mensagens/3 autores unicos e a regra final 500 AND 5 tem papeis e medidas diferentes. A reconstrucao da metrica nao recupera a justificativa contemporanea da mudanca de limiares nem razoes humanas de exclusao que nao foram registradas.

## Reproducao e rastreabilidade

```powershell
python -m discord_filtering.interaction_audit --output <novo_diretorio>
```

O comando verifica o pacote historico e o hash da fonte, recusa saida existente e exporta `channel_comparison.csv`, `candidates.csv`, `summary.json` e `manifest.json`. O primeiro CSV preserva os valores por canal, as diferencas para cada candidata e o efeito sobre a decisao. Todos os calculos estao no arquivo Python, sem consultas ad hoc fora dele.

Para gerar novamente somente este documento a partir da auditoria existente:

```powershell
python -m discord_filtering.interaction_audit --report-only --overwrite-report
```

Use `--output` para indicar o diretorio auditado e `--report` para outro Markdown. A geracao verifica os hashes dos artefatos antes de ler o resumo. O manifesto adjacente ao documento registra a auditoria, o gerador e o Markdown.

Fonte: `C:\Users\thiag\OneDrive\Documentos\Mestrado\Toxicity-OSS\data\processed\filtering\software\affinity_v2\messages_2026-09-21.parquet`; SHA-256: `ff2097232fe9d9c57e2c470ac6e6af90ed4e474554ae91e8871967f6d6114210`.

Pacote historico: SHA-256 do manifesto `0e0ae7c9a0f33084879b09f202c28743e0f8fee8d2f2e15c9d52eb6748b9b5b6`.
