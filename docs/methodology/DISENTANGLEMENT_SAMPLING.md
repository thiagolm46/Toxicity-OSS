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
