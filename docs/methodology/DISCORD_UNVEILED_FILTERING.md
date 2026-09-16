# Curadoria do Discord Unveiled

## Finalidade

Este processo prepara dados do Discord Unveiled para classificacao manual. A
curadoria ocorre em duas etapas: primeiro seleciona servidores relacionados a
engenharia de software; depois classifica seus canais em uma escala de
relevancia. A segunda etapa prioriza a revisao humana, mas nao a substitui.

Neo4j e apenas um exemplo de execucao. O perfil
[`software.v1.json`](../../configs/filtering/software.v1.json) define regras,
pesos e limiares. Cada execucao gera Parquet e manifesto com hashes,
parametros e contagens para auditoria e reproducao.

## Etapa 1: servidores de engenharia de software

A selecao examina `name`, `description`, `about`, `reasons_to_join`, `slug`,
`vanity_url_code` e `keywords` do catalogo
[`servers_metadata.txt`](../../data/raw/server_metadata/servers_metadata.txt).
Os textos sao normalizados em Unicode NFKC, comparados sem diferenciar
maiusculas de minusculas, e valores ausentes nao contam como evidencia.

Sinais positivos incluem desenvolvimento de software, programacao,
desenvolvedores, DevOps/SRE, ciencia da computacao, desenvolvimento web, APIs,
bibliotecas, GitHub/GitLab, bancos de dados, linguagens e infraestrutura.
`open source` e `oss` sao sinais fortes, mas nao sao obrigatorios. Sinais de
NSFW, cripto, namoro, sorteios, roleplay, jogos, entretenimento e memes
reduzem ou bloqueiam a selecao.

Cada regra tem peso e grupo semantico. Em um mesmo grupo, somente a regra de
maior peso recebe credito (`max_per_group`); outras ocorrencias ficam na
auditoria sem inflar o escore. Por isso, `programming` e `coding` juntos valem
4, nao 8.

Sejam $P$ o escore positivo, $N$ o negativo e $M = P - N$ a margem. O servidor
e selecionado se $P \geq 7$, $M \geq 2$, $N \leq 3$ e nao houver os bloqueios
`nsfw`, `finance/crypto` ou `game title`.

`servers_audit.parquet` contem aprovados e rejeitados, escores, termos
encontrados, bloqueios e `server_evidence_json`. `servers_selected.parquet`
contem somente registros com `is_selected = true`. Na execucao historica de
25 de agosto de 2026, 38 de 3.167 servidores foram selecionados (1,20%). Os
artefatos estao em
[`discord_unveiled_2026-08-25`](../../data/processed/filtering/software/discord_unveiled_2026-08-25).

## Etapa 2: classificacao de canais

As mensagens dos servidores selecionados sao agrupadas por `guild_id` e
`channel_id`. Cada canal recebe tres componentes, normalizados entre 0 e 1:

| Componente | Peso | Evidencia usada |
| --- | ---: | --- |
| Metadados ($E_m$) | 0,20 | Nome, categoria, descricao e topico. |
| Lexical ($E_l$) | 0,60 | Frequencia de sinais tecnicos nas mensagens. |
| Dominio ($E_d$) | 0,20 | Praticas e artefatos de engenharia/OSS. |

O escore composto e:

$$
S = \min(0{,}20E_m + 0{,}60E_l + 0{,}20E_d, 1)
$$

A evidencia lexical recebe o maior peso. Um canal com nome tecnico, mas sem
conteudo tecnico, portanto, nao deve receber classificacao alta.

### Metadados

Sinais positivos incluem suporte/perguntas, bugs, desenvolvimento,
APIs/SDK/CLI, documentacao, releases, instalacao, bibliotecas, Git/OSS,
linguagens, backend, frontend, banco de dados e DevOps. Sinais negativos
incluem off-topic, memes, apresentacoes, administracao, bots/logs, voz,
spam/sorteios, empregos e marketplace.

O escore de metadados usa o saldo entre regras positivas e negativas, tambem
com `max_per_group`:

$$
E_m = \min\left(\frac{\max(P_m - N_m, 0)}{8}, 1\right)
$$

Assim, `rules` e `bot-logs` tendem a ter relevancia baixa mesmo em um servidor
tecnico.

### Mensagens

O conteudo e avaliado em oito familias: links de repositorio; issue, PR,
commit, merge, branch, bug e fix; termos de programacao; codigo e comandos;
extensoes de arquivos; logs e erros; manutencao/releases; e fluxo OSS. Cada
familia e saturada para evitar que repeticoes de um unico termo dominem o
resultado. Para contagem $c_i$, total de mensagens $T$ e saturacao $q_i$:

$$
C_i = \min\left(\frac{c_i}{Tq_i}, 1\right)
$$

As contribuicoes ponderadas formam $E_l$ e $E_d$. Ate cinco exemplos por
familia sao preservados com o ID da mensagem, para revisao humana.

Mensagens de bot (`is_bot = true`) sao registradas em `n_bot_messages`, mas
nao entram na contagem nem nas evidencias do perfil atual. Isso impede que
avisos e comandos automatizados elevem a classificacao. Ainda nao ha exclusao
por proporcao de bots; isso pode ser adicionado em uma versao futura voltada a
canais predominantemente automatizados ou promocionais.

## Escala para curadoria manual

As regras sao aplicadas na seguinte ordem:

| Classe | Criterio | Acao |
| --- | --- | --- |
| D | Sinal administrativo, bot/log, voz ou spam com pouca evidencia tecnica | Fora da fila inicial. |
| C | Sinal social com pouca evidencia tecnica, ou escore insuficiente | Baixa prioridade. |
| A | $S \geq 0{,}70$ e $E_l \geq 0{,}30$ | Alta prioridade; entra na fila principal. |
| B | $S \geq 0{,}50$, ou $E_l \geq 0{,}45$ e $E_d \geq 0{,}20$ | Revisar antes de incluir. |

D e C tem precedencia se houver sinais administrativos ou sociais sem
evidencia tecnica suficiente. A exige escore alto e conteudo tecnico real. B
reune canais plausiveis, mas inconclusivos; os demais recebem C.

Por padrao, A define `include_in_main_analysis = true` e B define
`manual_review_required = true`. O canal tambem precisa ter pelo menos 50
mensagens nao-bot para `eligibility_status = eligible`. Abaixo disso, escore e
classe continuam visiveis, mas a inclusao automatica e removida e a revisao se
torna obrigatoria.

## Aplicacao na anotacao

Use A como inicio da fila, revise B antes de incluir, e amostre C/D para
encontrar falsos negativos ou erros sistematicos. Canais com poucos dados sao
inconclusivos, nao irrelevantes. Para cada decisao humana, registre classe,
escore, componentes, evidencias e decisao final. Essa amostra de referencia
permite calibrar uma nova versao do perfil de modo mensuravel.

## Exemplo: Neo4j

Em 1 de setembro de 2026, o exemplo Neo4j pontuou 37 canais com 35.787
mensagens: 27 elegiveis e 10 com dados insuficientes. A distribuicao foi 9 A,
11 B, 16 C e 1 D. Os 9 A foram incluidos automaticamente; 20 foram marcados
para revisao por serem B, terem pouco volume ou ambos.

Os resultados estao em
[`neo4j_channels.parquet`](../../data/processed/filtering/software/discord_unveiled_rich_2026-09-01/neo4j_channels.parquet)
e no
[`manifesto do exemplo`](../../data/processed/filtering/software/discord_unveiled_rich_2026-09-01/neo4j_channels.parquet.manifest.json).
Use `channel_score`, `lexical_evidence_score`, `domain_evidence_score`,
`channel_class`, `eligibility_status`, `include_in_main_analysis` e
`manual_review_required` para organizar a fila.

## Reproducao

```powershell
python -m discord_filtering select-servers `
  --profile configs/filtering/software.v1.json `
  --input data/raw/server_metadata/servers_metadata.txt `
  --output data/processed/filtering/software/<execucao>/servers_audit.parquet `
  --include-rejected
```

```powershell
python -m discord_filtering score-channels `
  --profile configs/filtering/software.v1.json `
  --input <mensagens.parquet> `
  --output data/processed/filtering/software/<execucao>/channels.parquet `
  --guild-id <guild_id> `
  --min-messages 50
```

Para canais, escolha exatamente um escopo: `--guild-id`, `--guild-name` ou
`--all-guilds`. Grave cada execucao em um novo diretorio e mantenha os
manifestos correspondentes.
