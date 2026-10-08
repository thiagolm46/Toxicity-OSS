# Etapa 2 - Selecao e Limpeza de Canais

## 1. Objetivo e escopo

Esta etapa reduziu o conjunto de canais extraidos para a pesquisa de software antes da preparacao do material destinado a analise conversacional. Foram combinadas duas fontes de decisao:

1. uma lista manual de nomes de canais a excluir;
2. estatisticas por canal, usadas para excluir canais simultaneamente pequenos em volume e em participacao de autores interagentes.

A unidade de decisao foi o canal. Quando um canal foi excluido, todas as mensagens associadas ao seu `channel_id` foram retiradas do Parquet de saida. Nenhuma mensagem foi classificada individualmente nesta operacao.

Este documento registra a execucao concluida no diretorio `affinity_v2`. Ela nao deve ser confundida com o scoring generico de relevancia tecnica A-D descrito em [DISCORD_UNVEILED_FILTERING.md](DISCORD_UNVEILED_FILTERING.md): o artefato final desta execucao foi produzido pela combinacao da lista manual e dos limites de atividade abaixo.

## 2. Posicao no pipeline

A etapa foi executada depois da selecao de servidores e da extracao das mensagens correspondentes. As estatisticas foram calculadas sobre esse arquivo de mensagens e serviram para apoiar a decisao sobre canais. O Parquet final e o corpus limpo para as etapas seguintes, como amostragem e preparacao de anotacao.

O processo preservou os arquivos de origem. A filtragem gravou uma nova versao do corpus, acompanhada de manifesto; nao houve sobrescrita do Parquet de mensagens original.

## 3. Entradas e artefatos

Todos os arquivos desta execucao estao em [`data/processed/filtering/software/affinity_v2`](../../data/processed/filtering/software/affinity_v2):

| Artefato | Papel na etapa |
| --- | --- |
| [`messages_2026-09-21.parquet`](../../data/processed/filtering/software/affinity_v2/messages_2026-09-21.parquet) | Corpus de mensagens de entrada, com 13.275.074 linhas. |
| [`channel_statistics_2026-09-21.parquet`](../../data/processed/filtering/software/affinity_v2/channel_statistics_2026-09-21.parquet) | Uma linha por canal; contem `channel_id`, `channel_name`, `guild_name`, `total_messages` e `interacting_authors`, entre outras estatisticas. |
| [`channel_statistics_2026-09-21.parquet.manifest.json`](../../data/processed/filtering/software/affinity_v2/channel_statistics_2026-09-21.parquet.manifest.json) | Registra 13.275.074 mensagens de entrada, 689 canais, escopo de interacao `human_messages`, timezone UTC para dias ativos e hashes de entrada e saida. |
| [`canais_a_excluir.txt`](../../data/processed/filtering/software/affinity_v2/canais_a_excluir.txt) | Lista manual de nomes de canais. Cada linha nao vazia e um nome usado na correspondencia exata com `channel_name`. |
| [`messages_2026-10-07_excluded_channels_min500_interacting5.parquet`](../../data/processed/filtering/software/affinity_v2/messages_2026-10-07_excluded_channels_min500_interacting5.parquet) | Corpus resultante da aplicacao conjunta dos dois criterios de exclusao. |
| [`messages_2026-10-07_excluded_channels_min500_interacting5.parquet.manifest.json`](../../data/processed/filtering/software/affinity_v2/messages_2026-10-07_excluded_channels_min500_interacting5.parquet.manifest.json) | Registro de proveniencia, parametros, contagens e SHA-256 do resultado final. |

O arquivo [`messages_2026-10-07_excluded_channels.parquet`](../../data/processed/filtering/software/affinity_v2/messages_2026-10-07_excluded_channels.parquet) e seu manifesto correspondem a um resultado intermediario, produzido somente com a lista manual. Ele nao e o resultado final da regra combinada documentada aqui.

## 4. Estatisticas utilizadas

O arquivo de estatisticas tem 689 linhas, uma por canal. Para a decisao automatica foram lidos dois campos:

- `total_messages`: volume de mensagens associado ao canal;
- `interacting_authors`: quantidade de autores interagentes registrada na tabela de estatisticas.

O manifesto das estatisticas declara `interaction_scope: human_messages`. A definicao operacional completa de quando um autor conta como interagente nao esta registrada nesse manifesto nem no script de remocao; portanto, a interpretacao desta variavel deve permanecer limitada ao valor calculado no artefato de estatisticas. Os limites desta etapa nao recalculam interacoes a partir das mensagens.

## 5. Regras de exclusao

### 5.1 Exclusao manual por nome

O conteudo de `canais_a_excluir.txt` foi lido como UTF-8. Linhas vazias foram ignoradas e as demais foram comparadas exatamente, sem normalizacao, com `channel_name` na tabela de estatisticas. A comparacao nao diferencia uma decisao por servidor: se o mesmo nome aparece em mais de um servidor, todas as linhas correspondentes sao marcadas para exclusao.

O arquivo contem 47 nomes distintos. Eles corresponderam a 66 canais na tabela de estatisticas. Todos os 47 nomes encontraram correspondencia; nao houve nome sem correspondencia.

A lista preserva as decisoes de exclusao, mas nao contem codigos de motivo, anotador, data da decisao ou justificativa por canal. Nomes como `welcome`, `introductions`, `bot-commands`, `music` e `art-showcase` sugerem tipos de canal, mas esses rotulos nao foram registrados como motivos formais e nao devem ser apresentados como tais.

### 5.2 Exclusao por baixa atividade

Um canal foi considerado de baixa atividade quando as duas condicoes abaixo eram verdadeiras ao mesmo tempo:

$$
\text{total\_messages} < 500
\quad\land\quad
\text{interacting\_authors} < 5
$$

Os limites sao estritos: um canal com exatamente 500 mensagens ou exatamente 5 autores interagentes nao e removido por este criterio, embora ainda possa ser removido pela lista manual.

Esse criterio marcou 221 canais. Ele foi aplicado como uma regra operacional de limpeza, nao como uma medida de irrelevancia tematica: um canal pequeno pode conter material pertinente, mas foi excluido quando tambem nao alcancou o minimo de autores interagentes definido para esta execucao.

### 5.3 Combinacao dos criterios

Um canal foi excluido se satisfizesse pelo menos um dos criterios. Os cinco canais que satisfizeram os dois criterios foram contados uma unica vez:

| Resultado na tabela de canais | Canais |
| --- | ---: |
| Correspondentes a nomes da lista manual | 66 |
| Abaixo dos dois limites de atividade | 221 |
| Presentes nos dois criterios | 5 |
| Excluidos pela uniao dos criterios | 282 |
| Mantidos | 407 |

Assim, 282 dos 689 canais foram removidos (40,93%) e 407 foram mantidos (59,07%). A contagem de removidos e da uniao, nao a soma simples de 66 e 221.

## 6. Aplicacao ao Parquet de mensagens

O script [`remove_channel.py`](../../discord_filtering/remove_channel.py) converteu os IDs dos 282 canais selecionados para um conjunto de `channel_id` e percorreu o Parquet de entrada em lotes de 100.000 linhas. Para cada lote, removeu as linhas cujo `channel_id` estava nesse conjunto e escreveu as demais mantendo o schema da origem, com compressao Zstandard.

O resultado da execucao final foi:

| Mensagens | Quantidade |
| --- | ---: |
| Na entrada | 13.275.074 |
| Removidas com os canais excluidos | 1.357.046 |
| Mantidas no corpus final | 11.918.028 |

As mensagens removidas representam aproximadamente 10,22% da entrada; 89,78% foram mantidas. Essas contagens sao de linhas no Parquet, nao de usuarios, conversas ou mensagens unicas deduplicadas.

O script grava primeiro em um arquivo temporario e publica a saida sem substituir um arquivo preexistente. O manifesto registra os hashes SHA-256 dos tres insumos (mensagens, estatisticas e lista), os parametros de execucao, as contagens e o hash da saida. O valor `source_data_policy: read_only_immutable` documenta que as fontes devem ser tratadas como imutaveis.

## 7. Reproducao e seguranca dos artefatos

Na raiz do repositorio, a execucao e iniciada com:

```powershell
.\.venv\Scripts\python.exe -m discord_filtering.remove_channel
```

O script usa caminhos e limites definidos no proprio modulo. Ele interrompe a execucao se o Parquet final ou o manifesto ja existir; nao sobrescreva os artefatos finalizados. Para uma nova rodada metodologica, preserve esta execucao e grave os novos insumos e resultados em um diretorio/versionamento distintos, atualizando explicitamente os caminhos e registrando uma nova versao do procedimento.

Para verificar o resultado registrado, compare as contagens e hashes do manifesto final com os artefatos presentes. O Parquet final esperado e `messages_2026-10-07_excluded_channels_min500_interacting5.parquet`; o Parquet sem o criterio de baixa atividade e somente intermediario.

## 8. Lista manual aplicada

A lista abaixo reproduz os nomes nao vazios de `canais_a_excluir.txt`. A presenca nesta lista e a regra efetiva; as categorias aparentes nos nomes nao substituem justificativas individuais que nao foram registradas.

```text
welcome
👋┇welcome
┠👋-introductions
introduction
introductions
introduce-yourself
👋introduce-yourself
Welcome New Members
👋┃new-members
🙋introduce-yourself
bot-commands
🤖┇commands
bot-playground
bot-cmds
bot-spam
a-scheena-bot
#! /bot-commands
💬〡الشات-العام
🤖〡شات-الأوامر
🟥〡الاشتراكات
💻〡الإستفسارات-العامة
🌏┇general-🇹🇭
nederlands
🍆scostumatezze-random
💲consigli-per-gli-acquisti
💬┃geral
💵┃vagas
russian
portuguese
spanish
indonesian
🌗・gm-gn
🚰・faucet
💬・referral
🔍┇next-giveaway-sneak-peek
🔊music
music
music-audio
🎮now-playing
🐈pet-photos
old-pets-animals-den
wallpapers
screenshots
gallery
fan-art
art-showcase
animation-showcase
```

## 9. Limites e interpretacao

1. A lista e baseada em nomes de canal, nao em pares `(guild_id, channel_id)`. Nomes repetidos em servidores diferentes geram exclusao de todas as correspondencias encontradas.
2. A lista nao registra justificativa individual nem historico de revisao. Uma revisao futura deve preservar a lista atual e registrar autor, data, motivo e decisao anterior/nova.
3. O significado exato de `interacting_authors` nao pode ser reconstruido apenas pelo manifesto da estatistica e pelo script de remocao. Isso deve ser esclarecido na documentacao da rotina que produziu `channel_statistics_2026-09-21.parquet` antes de alterar ou generalizar o limite.
4. Os limites 500/5 sao especificos desta execucao. Nao representam um limiar universal de relevancia, qualidade ou representatividade.
5. A remocao por canal pode excluir mensagens tecnicamente relevantes de canais com pouca atividade. As analises resultantes se referem ao corpus apos essa regra e nao incluem os 282 canais removidos.
6. A remocao foi feita por `channel_id` e nao por conteudo da mensagem; todos os registros dos canais mantidos permaneceram elegiveis, inclusive mensagens de bot, salvo filtragem posterior.