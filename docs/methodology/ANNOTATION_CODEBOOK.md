# Codebook de anotação conversacional

**Versão:** 1.1  
**Unidade de anotação:** janela contínua de um canal Discord

## 1. Estrutura de dados

`native_reply_annotation_windows.csv` é o artefato de preparação. Antes da
anotação, ele deve ser achatado com `build-annotation-bundle` em três tabelas
Parquet. As tabelas canônicas de anotação são `messages.parquet` e
`annotations.parquet`.

### `messages.parquet`

Cada linha é uma mensagem canônica do servidor. `message_id` é único e `content`
aparece uma única vez, junto de seus metadados nativos.

```text
message_id, server_id, channel_id, author_id, timestamp, content,
native_reply_to, mentions, message_type, reaction_count, has_attachment, is_bot
```

O arquivo inclui também os metadados nativos preservados, como reactions,
attachments, embeds, thread, webhook, flags e payload de origem.

### `sample_messages.parquet`

Cada linha registra a participação de uma mensagem em uma janela de anotação:

```text
sample_id, message_id, is_context, sequence
```

Uma mensagem pode aparecer em várias amostras porque o contexto de uma janela
pode sobrepor o trecho anotado da próxima. A chave é `(sample_id, message_id)`.
`is_context=true` indica contexto anterior; `is_context=false` indica trecho
alvo. Para obter uma amostra completa, faça a junção por `message_id` entre esta
tabela e `messages.parquet`.

### `annotations.parquet`

Cada linha é uma aresta humana dirigida. A mesma `source_message_id` pode
aparecer em diversas linhas dentro de uma `sample_id`.

```text
sample_id, source_message_id, target_message_id, annotator_id, relation,
ambiguous, confidence, notes
```

No codebook inicial, `relation=reply` é a única relação materializada. Arestas
ambíguas são preservadas, mas ficam fora do gold derivado por padrão; a opção
`--include-ambiguous` as inclui explicitamente.

### `source_statuses.parquet`

Esta terceira tabela é necessária para decisões humanas sem aresta. Cada fonte
do trecho alvo possui uma linha com `source_status`; assim, a ausência de uma
linha em `annotations.parquet` nunca significa `no_reply`.

Somente participações com `is_context=false` exigem decisão. Toda mensagem
anterior visível, inclusive `is_context=true`, é um antecedente elegível.

## 2. Evidência nativa do Discord

`native_reply_to_message_id` preserva a referência explícita da plataforma.

| Situação | Interpretação obrigatória |
|---|---|
| `native_reply_to_message_id != null` | evidência positiva observada de uma aresta nativa `(source, target)` |
| `native_reply_to_message_id == null` | relação sem observação nativa; não é negativa, não é `no_reply` e não inicia uma conversa |

Em particular, a ausência de reply nativo nunca deve gerar um par negativo,
excluir um pai semântico ou separar uma conversa. `native_reply_evidence` usa
somente `positive_observed` e `unknown` por esse motivo.

As arestas em `native_reply_edges_json` são evidência silver parcial. Elas não
limitam as anotações humanas: uma mensagem sem reply nativo pode receber um pai
semântico anotado.

Exemplo: se apenas `M5` cita `M1` explicitamente, a anotação pode registrar
`M2 -> M1`, `M3 -> M1`, `M4 -> M1` e `M5 -> M1` quando o conteúdo sustentar
essas relações.

## 3. Preservação de metadados

O silver preserva identificadores, canal/servidor, autor, timestamps original e
de edição, conteúdo, tipo de mensagem, replies nativos, menções, reactions,
attachments, embeds, stickers, roles mencionados, flags, estado de bot/webhook,
fixação e thread nativa. `native_fields_json` retém campos adicionais da origem.
`native_available_fields` identifica quais campos estavam presentes na origem de
cada mensagem: um campo ausente da origem não deve ser interpretado como uma
lista vazia, valor falso ou evidência negativa.

Esses campos são evidência de anotação e material para estudo posterior. Nenhum
campo vira feature, gold ou label negativo automaticamente.

## 4. Arestas humanas primárias

O anotador não atribui `conversation_id` e não preenche um pai singular. A
unidade primária é uma linha de `annotations.parquet`. A mesma fonte pode
aparecer em uma ou mais arestas:

```json
[
  {
    "source_message_id": "M20",
    "target_message_id": "M17",
    "target_location": "context"
  },
  {
    "source_message_id": "M20",
    "target_message_id": "M18",
    "target_location": "annotated"
  }
]
```

Cada aresta afirma que a fonte responde semanticamente ao alvo. A fonte deve
estar no trecho `annotated`; o alvo deve ser uma mensagem visível, estritamente
anterior e da mesma `sample_id`. O alvo pode estar no contexto ou no trecho
anotado; sua posição é determinada por `is_context` em `messages.parquet`.

`source_statuses.parquet` contém uma decisão para cada fonte do trecho alvo,
mas não uma relação pai-filho. Valores permitidos em `source_status`:

- `pending`: anotação ainda aberta;
- `complete`: a lista de zero ou mais arestas da fonte está finalizada;
- `no_reply`: após revisão, não foi atribuída relação de resposta semântica;
- `outside_context`: há indício de antecedente anterior ao contexto visível;
- `ambiguous`: a evidência não permite decidir.
- `new_conversation`: há início claro de tópico, explicitamente julgado pelo
  anotador.

O materializador aceita arestas apenas de fontes `complete`. `no_reply`,
`outside_context` e `ambiguous` não criam arestas e não implicam que a mensagem
inicia uma conversa nova. `new_conversation` é a única decisão que cria uma
conversa singleton: somente na materialização ele vira o self-link compatível
`M30 -> M30`. Um pai fora da janela nunca é inventado.

## 5. Agrupamento conversacional

Depois de concluir as arestas, execute:

```powershell
discord-disentangle derive-annotation-components `
  --messages <messages.parquet> `
  --sample-messages <sample_messages.parquet> `
  --annotations <annotations.parquet> `
  --source-statuses <source_statuses.parquet> `
  --output <diretorio_gold_humano>
```

O comando valida as arestas e escreve `human_reply_edges.parquet` e
`human_reply_components.parquet`. O segundo arquivo calcula `conversation_id`
como componente conexo não direcionado das arestas humanas. Para as arestas
`M10 -> M4`, `M11 -> M4`, `M12 -> M7`, `M13 -> M10` e `M13 -> M11`, as mensagens
`M4`, `M10`, `M11` e `M13` pertencem ao mesmo componente; `M7` e `M12` pertencem
a outro.

`conversation_id` é, portanto, derivado e reproduzível, não um rótulo do
anotador. Somente mensagens participantes de pelo menos uma aresta humana
recebem um componente; fontes sem aresta não são convertidas em conversas
singleton automaticamente.

## 6. Regras iniciais de decisão

| Caso | Decisão |
|---|---|
| Reply explícito nativo | Forte evidência positiva; revisar e registrar a aresta humana quando semanticamente compatível. |
| `@menção` | Evidência de destinatário, não antecedente automático. |
| Resposta sem menção ou reply nativo | Permitir aresta semântica quando conteúdo e contexto a sustentarem. |
| Várias respostas para uma mensagem | Todas podem apontar para o mesmo antecedente. |
| Mensagem respondendo várias anteriores | Registrar uma linha `reply` por antecedente. |
| Início claro de tópico | Marcar `source_status=new_conversation`; não criar self-link manualmente. |
| Continuação do próprio autor | Examinar conteúdo e contexto; mesma autoria não é ligação automática. |
| "sim", "não", "obrigado" | Procurar antecedente no contexto; não assumir a mensagem imediatamente anterior. |
| Antecedente anterior ao trecho alvo | Buscar no contexto; se continuar invisível, usar `outside_context`. |
| Nenhum antecedente identificável | Usar `no_reply`; não forçar uma ligação. |
| Mensagem ou relação incerta | Usar `ambiguous=true` na aresta, ou `source_status=ambiguous` quando não houver uma aresta defensável. |

## 7. Piloto e revisão

Antes da anotação em escala, executar três rodadas piloto. Após cada rodada,
comparar discordâncias, registrar decisões de consenso e acrescentar exemplos
anônimos de casos difíceis ao codebook. Casos prioritários: perguntas repetidas,
múltiplos antecedentes, interjeições, respostas curtas, respostas sem menção e
fronteiras entre tópicos.

## 8. Revisão e privacidade

Registre identidade do anotador, data, ambiguidade e observações no registro da
janela. Conteúdo bruto e payloads de mensagens permanecem nos artefatos locais
ignorados pelo Git; não devem ser copiados para planilhas ou documentos
versionados.