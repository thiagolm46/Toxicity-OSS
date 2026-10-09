# Amostragem para o Dataset de Conversas Desentrelaçadas

## Etapa 3: objetivo

Este documento define a etapa de amostragem para construir um dataset anotado de
conversas Discord desentrelaçadas. Ela ocorre depois da filtragem de servidores
de engenharia de software e dos canais relevantes para conversas, descritas em
[DISCORD_UNVEILED_FILTERING.md](DISCORD_UNVEILED_FILTERING.md). Seu objetivo e
selecionar intervalos em todos os canais considerados relevantes, preservando
variabilidade temporal e uma justificativa estatistica para a quantidade de
mensagens-alvo anotadas.

O objetivo nao e estimar toxicidade. A amostra deve representar, dentro dos
canais selecionados, a estrutura conversacional que sera anotada manualmente:
mensagens que respondem a antecedentes anteriores, mensagens sem resposta,
antecedentes fora do contexto e inicios de novas conversas.

A unidade anotada e a mensagem-alvo. Para cada mensagem-alvo, o anotador pode
registrar zero ou mais arestas semanticas para mensagens anteriores visiveis.
A mensagem-alvo e apresentada em uma janela continua para preservar o contexto;
essa separacao entre unidade de analise e unidade de apresentacao e essencial.

## Populacao e quadro amostral

A populacao de interesse e formada por mensagens nao-bot de canais relevantes
nos servidores selecionados. O quadro amostral deve ser congelado antes do
sorteio e conter, para cada canal:

- `guild_id`, `channel_id` e `channel_name`;
- intervalo temporal coberto pelo export;
- numero de mensagens nao-bot;
- classe do canal, escore e status de elegibilidade;
- identificadores e timestamps das mensagens em ordem cronologica.

A fila inicial de anotacao usa canais de classe A com
`conversation_suitable = true` e `eligibility_status = eligible`. A classe A
mede relevancia tecnica; a adequacao conversacional exige autores humanos,
interacao por reply/mencao, alternancia de autores, baixa concentracao de um
unico autor e baixa proporcao de bots. Canais B, e canais A que falharem nessa
adequacao, devem passar por revisao manual antes de entrar no quadro. Canais C
e D podem ser amostrados como controle de calibracao, mas nao sao o foco da
primeira rodada. Canais com poucos dados sao inconclusivos: nao devem ser
interpretados como irrelevantes somente por terem baixo volume.

## Caracterizacao inicial dos canais mantidos

Antes de sortear janelas, execute a caracterizacao da populacao congelada:

```powershell
python -m discord_disentanglement.population
```

O padrao le o Parquet da Etapa 2 com sufixo
`excluded_channels_min500_interacting5` e escreve em
`data/processed/disentanglement/population_payload_v2`. Os artefatos iniciais
em `data/processed/disentanglement/population` preservam a definicao anterior.
Para outro corpus:

```powershell
python -m discord_disentanglement.population `
   --input <mensagens_mantidas.parquet> `
   --output <diretorio_novo> `
   --memory-limit 2GB
```

A rotina usa DuckDB em disco, nao altera a entrada e recusa substituir
relatorios existentes. Reserve espaco para o banco temporario e seus arquivos
de spill, que podem ser maiores que o Parquet comprimido. O limite informado
controla a memoria do DuckDB, nao toda a memoria do processo Python.

O documento detalhado [POPULATION_CHARACTERIZATION.md](POPULATION_CHARACTERIZATION.md)
e gerado a partir desses artefatos por um segundo arquivo Python executavel.
Todos os calculos adicionais, tabelas e interpretacoes numericas estao no
gerador, que verifica os hashes das entradas antes de escrever:

```powershell
python -m discord_disentanglement.population_report
```

Use `--overwrite` para regenerar explicitamente um documento existente.
O gerador aceita `--input-dir` e `--output` e cria um manifesto adjacente ao MD.

| Artefato | Conteudo |
| --- | --- |
| `channels.csv` | Volume, autores humanos distintos, cobertura temporal, dias ativos, replies e flags de qualidade por canal. |
| `servers.csv` | As mesmas medidas por servidor; autores distintos sao recalculados, nao somados entre canais. |
| `temporal_activity.csv` | Atividade mensal, por dia da semana ISO (1=segunda, 7=domingo) e hora, em UTC, por canal; separa registros totais de mensagens humanas utilizaveis. |
| `reply_distances.csv` | Replies por canal, utilizabilidade da origem e status do antecedente; quantis posicionais e temporais e contagens ate 10/100/200 registros. |
| `concentration.csv` | Canais e servidores ordenados por volume, participacao individual e acumulada; apresenta separadamente todos os registros e mensagens humanas utilizaveis. |
| `summary.json` | Totais globais, autores distintos no corpus, status dos antecedentes e quantidade de canais/servidores necessarios para atingir 80% do volume. |
| `manifest.json` | Hashes da entrada, da implementacao, do manifesto da entrada quando disponivel e dos relatorios; parametros e definicoes operacionais. |

Uma mensagem humana tem `is_bot = false`; valor ausente nao e tratado como
humano. Pela definicao `payload_v2`, nao utilizavel significa exclusivamente
registro sem texto nao vazio e sem anexo, embed ou sticker registrado. Havendo
conteudo, todos os tipos Discord sao utilizaveis nesta caracterizacao.
`usable_human_messages` exige conteudo e autor explicitamente nao-bot.
Bots com conteudo nao sao chamados de nao utilizaveis, mas ficam fora da
populacao humana. Utilizabilidade nao substitui revisao de relevancia ou
elegibilidade dos canais.

IDs ausentes, timestamps invalidos e duplicatas sao flags estruturais separadas,
nao motivos de nao utilizabilidade. A contagem
`human_messages_with_structural_issues` identifica mensagens humanas com
conteudo e algum desses problemas. Elas permanecem no volume utilizavel,
mas as distancias exigem uma base ordenavel com IDs unicos e timestamp valido.
As restricoes tecnicas do quadro amostral definitivo devem ser revisadas e
congeladas antes do sorteio de janelas.

As proporcoes de bots e registros nao utilizaveis usam todos os registros como
denominador. A proporcao de native replies e apresentada tanto nesse denominador
quanto nas mensagens humanas utilizaveis. As flags descritivas podem se
sobrepor e nao devem ser somadas para definir nao utilizabilidade:
`unusable_records` conta apenas ausencia simultanea de texto e midia.
Texto vazio sozinho nao prova mensagem ausente: mensagens com midia sao
utilizaveis. Falhas de timestamp incluem valores ausentes ou invalidos;
nao impedem utilizabilidade por conteudo, mas impedem agrupamento temporal.

Native reply significa `message_type = 19` com `referenced_message_id` nao vazio.
Referencias de outros tipos e replies sem ID do antecedente recebem contagens
separadas. A ausencia de native reply nao e evidencia de ausencia de resposta
semantica. Para cada reply com origem ordenavel, o antecedente e buscado por
servidor e ID. Sao separados `resolved`, `parent_not_found`, `different_channel`
e `not_preceding`; origens nao ordenaveis aparecem no resumo. Antecedente nao
encontrado pode estar fora do export, sem timestamp valido ou com ID duplicado;
nao demonstra que a mensagem foi apagada.

Distancias so sao calculadas para antecedentes anteriores no mesmo canal.
A distancia posicional e a posicao da origem menos a do antecedente na ordem
UTC/ID dos registros identificaveis, unicos e com timestamp valido, incluindo
bots e tipos de sistema. Uma distancia 1 indica mensagens adjacentes. Ha uma
segunda distancia posicional no quadro humano utilizavel, apenas para pares
em que ambos sao utilizaveis. A distancia temporal e dada em segundos.
As listas de quantis correspondem a 25%, 50%, 75%, 90%, 95% e 99%.
As contagens ate 10/100/200 usam a primeira ordem, nao o quadro humano.

A atividade temporal inclui somente buckets observados: meses sem registros
nao aparecem como linhas. O periodo coberto e o minimo/maximo observado, nao
uma garantia de completude do historico nem a data de criacao do canal.
Mensagens ausentes do proprio export nao podem ser quantificadas sem uma fonte
externa; a rotina mede campos ausentes, payload indisponivel e antecedentes
nao localizados no corpus.

### Definicao operacional de autores interagentes

Nao confundir tres medidas:

- `distinct_human_authors`: autores distintos com pelo menos um registro
   explicitamente nao-bot, mesmo que esse registro nao seja utilizavel;
- `distinct_usable_human_authors`: autores distintos no quadro utilizavel;
- `native_reply_interacting_authors`: autores distintos de mensagens humanas
   utilizaveis que enviaram ao menos um native reply a mensagem anterior
   utilizavel de **outro autor**, no mesmo servidor e canal. Conta emissores;
   nao conta destinatarios apenas por receberem reply, nem mencoes, replies a si
   proprio ou antecedentes fora do corpus.

A ultima e uma definicao nova, explicita e conservadora, nao uma reconstituicao
da coluna historica `interacting_authors` da Etapa 2. O manifesto historico
declara apenas `interaction_scope = human_messages`; a implementacao de
`profile-channels` que produziu aquela tabela nao esta disponivel no codigo nem
no historico Git consultado. Portanto, ainda nao e verificavel se aquela coluna
contava emissores ou destinatarios, mencoes, autorrespostas e replies nao
resolvidos. A rotina atual de scoring tem outra coluna,
`interacting_human_user_count`, e conta emissores com reply a ID humano anterior
ou `mention_count > 0`; isso nao prova equivalencia com a estatistica historica.
O criterio 500/5 da Etapa 2 nao e alterado nem reaplicado nesta caracterizacao.

Use a concentracao da populacao `usable_human` para avaliar a alocacao de
janelas. Se poucos canais acumularem 80% das mensagens, a alocacao proporcional
privilegiara esses canais. Isso nao e vies para estimar uma media entre
mensagens, mas pode fornecer cobertura insuficiente para comparacoes entre
canais. Uma cota minima por canal combinada com alocacao proporcional do
restante pode preservar cobertura; registre as probabilidades de inclusao e
os pesos quando o desenho for definido. Esta rotina descreve a populacao;
nao sorteia janelas nem modifica sua selecao.

## Qual parametro a amostra estima

O tamanho de amostra somente tem significado depois de declarar a quantidade a
ser estimada. Para o dataset de desentrelaçamento, uma quantidade primária
adequada e:

$$
p = \Pr(\text{uma mensagem-alvo possui pelo menos uma resposta semantica})
$$

A classificacao humana considera que uma mensagem possui resposta semantica
quando recebe ao menos uma aresta humana `reply`. Os estados `no_reply`,
`outside_context`, `ambiguous` e `new_conversation` tambem devem ser contados e
publicados, pois descrevem cobertura e incerteza da anotacao.

Outras estatisticas relevantes, a serem relatadas com intervalos de confianca,
sao a taxa de multiplos antecedentes, a distancia temporal/posicional para o
antecedente, a frequencia de replies nativos e a taxa de ambiguidade. A formula
para proporcoes abaixo e apropriada para cada uma dessas medidas binarias.

## Tamanho nominal por canal

Para estimar uma proporcao em um canal com confianca de 95% e margem de erro
absoluta $e$, sob amostragem aleatoria simples de mensagens independentes, use:

$$
n_0 = \frac{z^2p(1-p)}{e^2}
$$

com $z = 1{,}96$. Quando a proporcao real ainda e desconhecida, use $p = 0{,}5$.
Esse e o caso conservador porque maximiza a variancia e, portanto, o tamanho
necessario.

| Margem de erro | Tamanho nominal $n_0$ a 95% |
| --- | ---: |
| $\pm 7$ pontos percentuais | 196 |
| $\pm 6$ pontos percentuais | 267 |
| $\pm 5$ pontos percentuais | 385 |

Portanto, 267 mensagens-alvo por canal e uma meta nominal defensavel para
estimar uma proporcao conversacional com 95% de confianca e erro aproximado de
$\pm6$ pontos percentuais. Tres intervalos de 100 mensagens produzem 300
mensagens-alvo e ultrapassam esse numero nominal.

Para um canal com populacao finita de $N$ mensagens nao-bot, aplique a correcao
de populacao finita antes de definir a meta:

$$
n = \left\lceil \frac{Nn_0}{N+n_0-1} \right\rceil
$$

Para $n_0 = 267$, exemplos de metas por canal sao:

| Mensagens nao-bot no canal ($N$) | Meta corrigida ($n$) |
| --- | ---: |
| 300 | 142 |
| 500 | 175 |
| 1.000 | 211 |
| 5.000 | 254 |
| Muito grande | 267 |

Se a meta corrigida for proxima do total do canal, anotar o censo do canal e
mais simples e metodologicamente superior a sortear quase todas as mensagens.

## Janelas e dependencia temporal

A formula anterior assume observacoes independentes. Mensagens consecutivas em
Discord nao sao independentes: pertencem a uma mesma conversa, evento ou grupo
de participantes. Isso e desejavel para anotacao de conversas, pois a janela
precisa preservar contexto, mas impede interpretar 300 mensagens contiguas como
300 observacoes aleatorias independentes.

Se cada janela tiver $m$ mensagens-alvo e a correlacao intraclasse aproximada
for $\rho$, uma aproximacao para o efeito de desenho e:

$$
DEFF = 1 + (m - 1)\rho
$$

O tamanho efetivo aproximado e $n_{efetivo} = n / DEFF$. Por exemplo, tres
janelas de 100 mensagens fornecem 300 mensagens-alvo, mas com $\rho = 0{,}01$
o tamanho efetivo seria aproximadamente 151; com $\rho = 0{,}02$, cerca de
101. Esses valores sao ilustrativos: $\rho$ deve ser estimado no piloto, nao
assumido como resultado do dataset.

Consequentemente, tres janelas de 100 sao uma boa meta operacional inicial de
cobertura, mas nao devem ser apresentadas como garantia de precisao de
$\pm6$ pontos percentuais. A precisao deve ser estimada depois, por bootstrap
agrupado por janela ou por canal.

## Desenho recomendado dos intervalos

Para cada canal A com adequacao conversacional e elegibilidade:

1. determine a meta nominal com a correcao de populacao finita;
2. divida o periodo do export em estratos temporais de tamanho semelhante, por
   exemplo tercis ou meses;
3. sorteie pelo menos uma janela em cada estrato, sem sobrepor mensagens-alvo;
4. distribua a meta entre os estratos de forma aproximadamente proporcional;
5. preserve uma semente, o quadro amostral congelado e os IDs das mensagens
   inicialmente selecionadas;
6. acrescente mensagens anteriores como contexto, sem contá-las como mensagens
   anotadas da amostra.

Para a primeira rodada, tres janelas de 100 mensagens-alvo em tempos distintos
sao apropriadas quando a meta for aproximadamente 267. Quando for necessario
sustentar uma inferencia mais precisa, prefira mais janelas menores e
espacadas, como 6 a 10 janelas de 30 a 50 mensagens-alvo. Isso reduz a
correlacao dentro de cada intervalo e aumenta a cobertura de diferentes
periodos de atividade.

As janelas devem ser selecionadas por tempo, nao apenas pelas primeiras
mensagens do canal. Amostrar somente o inicio do historico favorece uma fase
particular da comunidade; amostrar somente o fim favorece eventos recentes.
A estratificacao temporal reduz esse vies sem destruir o contexto local que a
anotacao de conversas exige.

## Relacao com a ferramenta de anotacao

O comando `discord-disentangle gold-standard` produz janelas continuas por
canal. Por padrao, cada janela contem 100 mensagens-alvo (`annotated_window_size`)
e ate 200 mensagens anteriores de contexto (`context_message_count`). Apenas as
mensagens-alvo exigem anotacao; o contexto pode receber arestas como
antecedente, mas nao aumenta o tamanho da amostra.

```powershell
discord-disentangle gold-standard `
  --input <mensagens.parquet> `
  --output <diretorio_de_janelas> `
  --guild-id <guild_id> `
  --channel-id <channel_id> `
  --annotated-window-size 100 `
  --context-message-count 200
```

A implementacao atual particiona todos os canais do escopo em janelas
cronologicas sucessivas. Para aplicar o desenho estatistico acima, a selecao
das janelas deve ser registrada antes da anotacao: gerar o conjunto de janelas,
escolher as janelas sorteadas conforme seus timestamps e encaminhar somente
essas janelas para a anotacao. O arquivo de selecao deve preservar IDs de
janela, estrato temporal, semente e justificativa para qualquer substituicao.

## Piloto, recalibracao e relato

Antes da coleta final, anote um piloto temporalmente estratificado. O piloto
deve estimar: proporcao de mensagens com aresta semantica, taxa de ambiguidade,
taxa de antecedentes fora do contexto, distribuicao do tamanho das conversas e
correlacao entre mensagens de uma mesma janela. Esses resultados permitem
recalcular o tamanho de amostra com uma estimativa de $p$ menos conservadora e
um efeito de desenho observado.

O relatorio final deve informar o canal, seu tamanho populacional $N$, classe,
periodo coberto, meta nominal, correcao finita, numero de janelas, mensagens
alvo anotadas, mensagens de contexto, distribuicao temporal, criterios de
substituicao e taxa de conclusao. Para estimativas agregadas entre canais, use
pesos proporcionais ao tamanho do canal ou declare explicitamente que a analise
estima a media entre canais, nao a media entre mensagens do corpus.

O resultado esperado e um dataset com contexto suficiente para anotar arestas
semanticas e com justificativa estatistica transparente para a quantidade e a
distribuicao das mensagens classificadas.

## Etapa 4: codebook e classificacao piloto

Depois de selecionar os intervalos, a proxima etapa define e calibra o
codebook por meio de classificacao piloto. O piloto verifica se as regras para
`reply`, `no_reply`, `outside_context`, `ambiguous` e `new_conversation` sao
aplicaveis de forma consistente antes da anotacao em escala. Consulte
[ANNOTATION_CODEBOOK.md](ANNOTATION_CODEBOOK.md) para a unidade de anotacao,
os estados de decisao e o protocolo de revisao.
