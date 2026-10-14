# Desenho amostral: experimentos, testes e achados

## 1. Objetivo e escopo

Este documento registra o que foi implementado, como foi verificado e o que foi
observado nos testes de amostragem para o dataset de disentanglement.
Integra a etapa **3.2. Desenho amostral** e sintetiza as evidencias disponiveis
em 14/10/2026.

As perguntas investigadas foram:

1. O sorteador implementa corretamente os tres niveis de selecao e suas
   probabilidades de inclusao?
2. A distribuicao resultante corresponde ao mecanismo definido, especialmente
   quanto a cobertura de servidores, portes e periodos?
3. As janelas permitem observar interacoes uteis ao disentanglement?
4. Quais resultados exigem correcao e quais sao caracteristicas esperadas da
   populacao ou limitacoes que dependem de anotacao humana?

Nao foram realizados aqui experimentos de desempenho de modelos, classificacao
de toxicidade ou validacao de conversas semanticas por anotadores. Aprovacao
dos testes de software nao equivale a validacao definitiva do desenho.

## 2. Evidencias e implementacao

| Evidencia | O que foi feito | O que permite concluir |
| --- | --- | --- |
| Testes automatizados | Nove casos com dados sinteticos e resultados conhecidos. | As propriedades explicitamente exercitadas funcionam nesses cenarios. |
| Auditoria do piloto real | 38 verificacoes sobre o quadro congelado, os artefatos e o Parquet de origem. | A execucao observada e consistente com os denominadores, cotas, probabilidades e restricoes verificadas. |
| Analises de sensibilidade | Recalculo de cenarios de estratos e contexto sem alterar a amostra. | Como algumas escolhas afetam custo esperado e evidencia nativa visivel; nao identifica automaticamente uma configuracao otima. |

O sorteador esta em [sampling.py](../../discord_disentanglement/sampling.py#L1).
A auditoria e os calculos estao em
[sampling_audit.py](../../discord_disentanglement/sampling_audit.py#L1).
Os testes estao em [test_sampling.py](../../tests/test_sampling.py#L1).

O [desenho metodologico](DISENTANGLEMENT_SAMPLING.md) define a selecao; o
[relatorio numerico gerado](SAMPLING_DESIGN_AUDIT.md) apresenta as tabelas da
auditoria. Este documento explica os experimentos e a interpretacao dessas
evidencias, sem substituir os arquivos Python como fonte dos calculos.

### 2.1. O que foi implementado

- Cadastro de elegibilidade separado do Parquet, preservando os 407 canais
  como quadro provisorio da execucao original.
- Estados `provisional_eligible`, `eligible`, `pending_review` e `excluded`.
- Sorteio de canais dentro de combinacoes de servidor e porte; meses dentro
  dos canais; janelas dentro dos meses, sem reposicao em cada nivel.
- Ordenacao cronologica e particionamento mensal dos alvos em blocos nao
  sobrepostos, preservando o ultimo bloco incompleto.
- Contexto anterior e registros nao alvo dentro do intervalo visivel, sem
  atribuir a esses pertencimentos uma probabilidade de mensagem-alvo.
- Exportacao de janelas, mensagens, probabilidades, pesos, semente, contagens
  e manifestos com hashes; recusa de sobrescrita das pastas de execucao.
- Diagnosticos de duracao, autores, referencias nativas, contexto e variancia
  de totais auxiliares conhecidos, sem filtrar ou substituir janelas.

## 3. Testes automatizados

### 3.1. Inventario dos nove casos

Os nomes abaixo correspondem aos metodos executados pelo pytest. Um metodo
pode conter varias verificacoes e chamadas de integracao.

| Teste | Cenario e verificacoes principais |
| --- | --- |
| `test_probabilities_and_reproducibility` | Quotas por servidor, oito janelas, probabilidades conhecidas, peso 20, ausencia de duplicatas e reproducao apos embaralhar as entradas. |
| `test_statuses_size_coverage_and_technical_exclusions` | Exclusao do sorteio de canais pendentes, excluidos ou sem candidatos; preservacao da cobertura de portes e probabilidade 1 em estratos censitarios. |
| `test_frame_is_separate_and_refuses_overwrite` | Cadastro independente, classificacao nos limites de porte, estado provisorio inicial, preservacao dos bytes da fonte e recusa de sobrescrita. |
| `test_empty_and_invalid_frames` | Resultado vazio quando todos os canais estao excluidos; rejeicao de cota zero e estado de elegibilidade desconhecido. |
| `test_parquet_draw_short_windows_context_and_bundle` | Fluxo completo com Parquet, caudas curtas, contexto entre meses, exclusoes tecnicas, preservacao de midia, pacote de anotacao, reproducao, auditoria, hashes e regeneracao explicita do documento. |
| `test_independent_design_audit_detects_wrong_probabilities` | Reconstrucao independente das probabilidades e deteccao de um peso adulterado propositalmente. |
| `test_native_interleaving_is_only_an_observable_proxy` | Duas cadeias nativas intercaladas, componentes e arestas cruzadas, duracao conhecida e timestamps ISO com precisao mista. |
| `test_exact_known_total_variance_and_census` | Media e variancia conhecidas para sorteio de um bloco entre dois; variancia zero quando ambos sao observados. |
| `test_exact_variance_across_three_stages` | Recursao da variancia comparada com todos os resultados possiveis de um pequeno desenho com tres niveis. |

### 3.2. Experimento controlado de probabilidades

O primeiro cenario contem dois servidores, quatro canais por servidor, quatro
meses por canal e cinco janelas por mes. Todos os canais pertencem ao mesmo
porte. A configuracao sorteia dois canais por servidor, dois meses por canal
e uma janela por mes, com semente 7.

Para qualquer janela elegivel desse quadro:

$$
\pi = \frac{2}{4}\frac{2}{4}\frac{1}{5} = 0{,}05,
\qquad d = \frac{1}{\pi} = 20.
$$

O teste exige quatro canais e oito janelas selecionadas. Em seguida, embaralha
as linhas dos canais e candidatos e exige os mesmos resultados com a mesma
semente. Isso verifica a independencia em relacao a ordem de entrada, nao
uma prova empirica da frequencia de inclusao sobre muitas sementes.

Na auditoria independente, os mesmos candidatos recebem dois alvos por bloco.
O quadro possui 320 alvos; a soma de `pi * peso * tamanho_do_bloco` deve ser
320. Depois de duplicar deliberadamente o peso de uma janela selecionada,
a verificacao `design_weight_per_window` deve reprovar. Assim, o teste verifica
tambem a capacidade do auditor de detectar uma falha conhecida.

### 3.3. Elegibilidade, portes e entradas invalidas

Foram exercitados os limites 1.000 e 10.000 mensagens utilizaveis. O cadastro
classifica 1.000 como `small`, 1.001 e 10.000 como `medium`, e 10.001 como
`large`. O volume zero tambem e preservado no cadastro; disponibilidade tecnica
e elegibilidade sao decisoes separadas.

Outro cenario marca canais como `pending_review` ou `excluded` e retira os
candidatos de um terceiro canal. Nenhum deles pode ser sorteado; o canal sem
candidatos deve aparecer como `no_valid_targets`. Os portes restantes devem
continuar contemplados, sem substituir canais de um estrato por outro.

Quando todos os canais sao excluidos, o seletor em memoria retorna quadros
de periodos e janelas vazios. Cotas nao positivas e estados de elegibilidade
desconhecidos sao rejeitados nos casos exercitados. Esses testes nao constituem
uma enumeracao de todas as entradas invalidas possiveis.

### 3.4. Integracao com Parquet e anotacao

Foi construido um Parquet temporario com 12 registros, incluindo humanos,
bot, midia sem texto, payload ausente, status de bot desconhecido, timestamp
invalido, autor ausente e duas ocorrencias da mesma chave de mensagem.

Com blocos de ate dois alvos, permanecem quatro mensagens-alvo validas, com
IDs `1`, `3`, `5` e `6`. As tres janelas censitarias possuem tamanhos 1, 2 e 1.
Os casos estruturalmente invalidos nao entram no quadro tecnico; bots e outros
registros ordenaveis podem continuar visiveis como contexto.

O teste verifica especialmente:

- Contexto de janeiro visivel para uma janela de fevereiro.
- Registro com anexo e sem texto mantido como alvo utilizavel.
- Preservacao do antecedente nativo e da URL do anexo no payload exportado.
- Ausencia de probabilidade de alvo nos pertencimentos de contexto.
- Criacao de quatro estados pendentes de anotacao pelo construtor de pacote.
- Igualdade dos bytes do Parquet de origem antes e depois do sorteio.
- Igualdade do arquivo de janelas selecionadas em duas execucoes equivalentes.
- Probabilidade proporcional ao inverso do numero de janelas no mes quando
  somente um mes e uma janela sao sorteados.
- Resolucao de uma referencia nativa conhecida e sensibilidade do contexto:
  o antecedente fica invisivel com zero ou um registro anterior e visivel com
  dois ou 200.
- Execucao completa da auditoria e geracao de seu documento.
- Rejeicao de arquivos adulterados por divergencia de hash.
- Recusa de sobrescrita da amostra e da pasta de auditoria; substituicao do
  documento somente quando a opcao correspondente e explicita.

Nenhum desses testes modifica os dados reais: os arquivos artificiais sao
criados em diretorios temporarios.

### 3.5. Entrelacamento observavel

O cenario controlado tem quatro mensagens em ordem: duas de contexto e duas
alvo. A terceira responde nativamente a primeira; a quarta responde a segunda.
As arestas sao `1 -> 3` e `2 -> 4`, no sentido antecedente para resposta.

O resultado exigido e: dois componentes nativos distintos tocando alvos, um
par de componentes com spans intercalados e um par de arestas cruzadas. Os
alvos estao separados por um minuto, verificando tambem a duracao calculada.

Essas medidas capturam uma estrutura nativa observavel, nao a identidade das
conversas semanticas. Componentes nativos diferentes podem pertencer a mesma
conversa, e conversas paralelas podem ocorrer sem replies explicitos.

### 3.6. Variancia exata e censo

No exemplo com blocos de tamanhos 1 e 3, sorteia-se um bloco uniformemente.
A contagem bruta tem media 2 e variancia 1. Com expansao Horvitz-Thompson,
os resultados possiveis sao 2 e 6: media 4 e variancia 4. No censo dos dois
blocos, o total permanece 4 e a variancia deve ser zero.

O ultimo teste usa dois canais, dois periodos por canal e dois blocos por
periodo. Sorteia-se uma unidade em cada nivel. Os oito resultados possiveis
sao enumerados, cada um com probabilidade 1/8. A media e a variancia da
recursao devem coincidir com a media e a variancia dessa distribuicao finita.
A soma dos componentes de canal, periodo e janela deve recuperar a variancia
total.

Esse e um teste exato em um quadro pequeno, nao uma simulacao Monte Carlo.
Ele valida o calculo para totais conhecidos; nao fornece automaticamente
variancia para futuros rotulos humanos ou desempenho de modelos.

## 4. Experimento com o corpus real

### 4.1. Configuracao congelada

O piloto foi executado com semente `20261014`, ate dois canais por combinacao
servidor/porte, ate tres meses ativos por canal e uma janela por mes. Cada
bloco possui ate 100 mensagens-alvo e recebe ate 200 registros anteriores
validos como contexto, alem dos registros nao alvo dentro do intervalo.

Os portes usam os cortes 1.000 e 10.000 mensagens humanas utilizaveis. Os
servidores sao fixos no quadro retido; as conclusoes nao representam todos
os servidores Discord. Meses sem alvo valido nao sao unidades sorteaveis.

| Medida | Resultado |
| --- | ---: |
| Canais no cadastro provisorio | 407 |
| Estratos servidor/porte nao vazios | 75 |
| Estratos censitarios no nivel dos canais | 27 |
| Canais selecionados | 132 |
| Servidores contemplados | 31 |
| Janelas selecionadas | 390 |
| Mensagens-alvo selecionadas | 18.012 |
| Mensagens-alvo no quadro tecnico elegivel | 11.884.832 |

### 4.2. Auditoria do mecanismo

As **38 verificacoes passaram**. Foram conferidos hashes dos artefatos e da
fonte, reproducao da semente, denominadores reconstruidos independentemente,
positividade das probabilidades, cotas dos tres niveis, pesos, unicidade de
alvos, nao sobreposicao dos blocos e correspondencia de seus totais com o
censo tecnico do Parquet.

Os nove testes de software e as 38 verificacoes nao sao a mesma contagem.
Os primeiros usam cenarios artificiais; as segundas examinam uma realizacao
do piloto. Nenhuma dessas contagens deve ser apresentada como quantidade de
experimentos com anotadores ou como garantia de representatividade universal.

### 4.3. Distribuicao e caudas curtas

| Medida | Observado | Esperado pelo desenho |
| --- | ---: | ---: |
| Janelas | 390 | 389,63 |
| Mensagens-alvo | 18.012 | 18.627,99 |
| Janelas incompletas | 275 | 271,00 |

A quantidade esperada de janelas nao precisa ser inteira: depende dos canais
sorteados e de quantos meses eles possuem. O DP exato da quantidade de janelas
incompletas e 7,37; a diferenca observada corresponde a aproximadamente 0,543
DP. Esse numero e descritivo, nao um p-valor ou teste de normalidade.

Ha 22 janelas com um unico alvo e 127 com ate dez. A mediana e 31 alvos por
janela, apesar do limite maximo de 100. Canais pouco ativos produzem meses
com poucos alvos; o sorteio uniforme de meses e a manutencao das caudas tornam
esses casos esperados. Exclui-los depois do sorteio alteraria a populacao
representada e as probabilidades registradas.

### 4.4. Duracao e utilidade conversacional

| Indicador | Resultado |
| --- | ---: |
| Mediana da duracao entre primeiro e ultimo alvo | 143,61 horas |
| Janelas com alvos distribuidos por mais de 24 horas | 283 |
| Janelas com alvos distribuidos por mais de sete dias | 186 |
| Janelas com um unico autor-alvo | 35 |
| Janelas com componentes nativos intercalados | 162 |
| Janelas com arestas nativas cruzadas | 133 |

Os 115 blocos completos possuem duracao-alvo mediana de 56,31 horas; os 275
incompletos, de 278,05 horas. Portanto, bloco com poucos alvos nao significa
necessariamente intervalo curto. O calendario mensal e a baixa atividade podem
produzir o contrario.

Esses achados limitam a interpretacao das janelas como episodios conversacionais
compactos. Nem mesmo um proxy nativo de entrelacamento prova simultaneidade
local quando as arestas atravessam longos periodos. Entretanto, duracao longa,
um unico autor ou ausencia do proxy tambem nao justificam exclusao automatica:
podem ser casos relevantes para medir a especificidade do benchmark.

### 4.5. Experimento de sensibilidade do contexto

Foram encontradas 3.099 referencias nativas emitidas por mensagens-alvo.
Dessas, 93 nao tiveram antecedente localizado no corpus; 3.006 foram
resolvidas como antecedentes tecnicamente ordenaveis, anteriores e do mesmo
canal. Esse ultimo grupo e o denominador da cobertura abaixo.

| Registros anteriores disponibilizados | Antecedentes visiveis | Cobertura dos 3.006 resolvidos |
| --- | ---: | ---: |
| 0 | 2.801 | 93,18% |
| 50 | 2.962 | 98,54% |
| 100 | 2.981 | 99,17% |
| 200 | 2.991 | 99,50% |
| 400 | 2.993 | 99,57% |

Mesmo com zero registros anteriores, antecedentes podem estar dentro do proprio
intervalo-alvo. Com a configuracao atual, 15 antecedentes resolvidos ficam
antes do contexto visivel. Aumentar de 200 para 400 recuperaria apenas dois
desses casos; nao recupera as 93 referencias sem antecedente no corpus.

O experimento mantem as mesmas mensagens-alvo e recalcula apenas a visibilidade
posicional. Nao gera novas amostras nem mede o desempenho de anotadores.
A cobertura nativa nao mede recuperacao de todos os antecedentes semanticos,
que permanecem desconhecidos sem anotacao humana.

### 4.6. Experimento de sensibilidade dos estratos

Foram comparados os cortes congelados, metade e dobro desses cortes e tercis
globais do volume humano utilizavel. Os sorteios continuam estratificados por
servidor e porte. Nenhum canal foi removido e nenhuma dessas alternativas foi
aplicada ao piloto original.

| Cenario | Cortes pequeno/medio | Canais previstos | Alvos esperados | Fracao esperada de janelas curtas | DP relativo do total HT auxiliar |
| --- | --- | ---: | ---: | ---: | ---: |
| Congelado | 1.000 / 10.000 | 132 | 18.627,99 | 69,55% | 40,06% |
| Metade | 500 / 5.000 | 136 | 17.574,34 | 73,76% | 44,75% |
| Dobro | 2.000 / 20.000 | 127 | 19.814,59 | 63,77% | 29,75% |
| Tercis de volume | 760,33 / 7.935,33 | 134 | 18.351,90 | 70,93% | 42,88% |

As alternativas alteram simultaneamente custo esperado, numero de canais e
composicao. Nao sao uma comparacao sob orcamento fixo. O melhor resultado do
cenario de cortes dobrados para esse total auxiliar nao demonstra superioridade
para disentanglement, cujos resultados ainda nao foram anotados.

Homogeneidade de volume dentro dos estratos nao equivale a homogeneidade de
conversas ou de desempenho de modelos. Nao foi escolhido um novo corte como
consequencia automatica dessas tabelas.

### 4.7. Pesos e incerteza

Os pesos sao inversos das probabilidades dos tres niveis. Eles permitem
expansao para o quadro definido, mas a amostra nao e autoponderada.

Para o total auxiliar conhecido de 11.884.832 mensagens-alvo tecnicas, a
estimativa Horvitz-Thompson desta realizacao foi 18.888.286. O DP exato do
desenho foi 4.760.858,14 e a diferenca corresponde a 1,471 DP. Trata-se de
variabilidade amostral relevante, nao de prova isolada de erro ou vies.
O desvio padronizado nao foi convertido em p-valor.

O diagnostico de Kish baseado apenas nos pesos foi 822,99 para 18.012 alvos.
Nao representa tamanho efetivo inferencial completo: nao incorpora toda a
estratificacao, conglomeracao ou dependencia temporal.

Em 148 meses selecionados havia varios blocos disponiveis, mas apenas uma
janela observada. Falta replicacao para estimar diretamente a variancia dentro
desses meses a partir de futuros rotulos sem suposicoes adicionais. O calculo
exato apresentado aqui e possivel porque os tamanhos de todos os blocos sao
conhecidos, nao porque essa limitacao tenha desaparecido para resultados
semanticos desconhecidos.

## 5. Problemas tecnicos corrigidos

Durante a implementacao da auditoria foram encontrados dois problemas de
engenharia, distintos de falhas do desenho amostral:

| Problema | Correcao | Verificacao incorporada |
| --- | --- | --- |
| Timestamps ISO com e sem fracoes de segundo falhavam na conversao vetorizada do pandas. | Uso explicito de `format="ISO8601"` nas duracoes. | O cenario de entrelacamento mistura essas precisoes e exige a duracao correta. |
| A opcao de regenerar o documento nao era repassada ao gravador atomico. | Encaminhamento de `overwrite_report` para `overwrite` no gravador. | O teste de integracao regenera o documento em uma nova pasta de auditoria e exige seu manifesto final. |

As correcoes nao alteraram canais elegiveis, unidades sorteadas ou cotas. A
execucao completa de referencia e `sampling_design_audit_v3`; seus artefatos
estao separados dos resultados do sorteio `sampling_pilot_v1`.

## 6. Conclusoes e decisoes

| Classificacao | Conclusao | Acao |
| --- | --- | --- |
| Propriedade verificada | Probabilidades, pesos, cotas e reproducao passaram nos testes e na auditoria da realizacao. | Preservar os registros e utilizar os pesos compativeis com o estimando declarado. |
| Caracteristica esperada | Frequencia elevada de caudas curtas e cobertura nao proporcional ao volume bruto. | Nao filtrar esses casos como se fossem erros. |
| Limitacao de utilidade | Muitas janelas abrangem dias ou semanas; proxies nativos nao validam conversas semanticas. | Avaliar casos de diferentes tamanhos e duracoes com anotadores, mantendo tambem casos sem entrelacamento. |
| Limitacao inferencial | Pesos heterogeneos e pouca replicacao no ultimo nivel. | Definir o objetivo inferencial e avaliar mais janelas nos meses nao censitarios se intervalos design-based forem requisito. |
| Escolha ainda provisoria | Cortes de porte e escopo tematico dos canais. | Rever com justificativa substantiva e resultados do piloto humano, nao apenas por equilibrio numerico. |
| Alteracao sem suporte automatico | Aumentar contexto, descartar canais esparsos ou refazer o sorteio apenas pelas distribuicoes observadas. | Nao aplicar sem explicitar objetivo, custo e impacto no quadro/probabilidades. |

O resultado desta etapa e um mecanismo executavel e auditado, acompanhado de
evidencias sobre sua realizacao. Ainda nao e uma certificacao de que todas as
janelas sao episodios uteis de entrelacamento nem um dataset humano validado.

## 7. Reproducao

Na raiz do projeto, com o ambiente Python configurado, executar somente os
testes de sampling:

```powershell
python -m pytest tests/test_sampling.py -v
```

Resultado registrado: **9 testes aprovados**. A verificacao conjunta com a
caracterizacao e o gerador de relatorio da populacao foi:

```powershell
python -m pytest tests/test_sampling.py tests/test_population.py -v
```

Resultado registrado: **15 testes aprovados**, sendo nove de sampling e seis
da suite de populacao. Os seis adicionais nao devem ser apresentados como
novos testes exclusivos do sorteador.

Para recalcular a auditoria do piloto existente, escolher uma pasta ainda
inexistente e um documento separado, preservando a referencia atual:

```powershell
python -m discord_disentanglement.sampling_audit `
  --sample data/processed/disentanglement/sampling_pilot_v1 `
  --output data/processed/disentanglement/sampling_design_audit_reproduction `
  --report data/processed/disentanglement/sampling_design_audit_reproduction.md
```

Esse comando nao realiza novo sorteio. A pasta de reproducao deve ser nova;
para execucoes posteriores, alterar seu nome. Para substituir explicitamente
um documento existente, usar `--overwrite-report`, sem reutilizar a pasta de
artefatos da auditoria.

### 7.1. Fontes dos resultados

Os resultados numericos deste relato foram obtidos dos seguintes artefatos
locais da execucao completa. Os dados processados podem nao estar versionados
no Git; sua integridade e conferida pelos manifestos.

| Fonte | Conteudo usado neste documento |
| --- | --- |
| [Resumo](../../data/processed/disentanglement/sampling_design_audit_v3/summary.json#L1) | Totais, 38 verificacoes, tamanhos, duracoes, proxies e limitacoes inferenciais. |
| [Verificacoes](../../data/processed/disentanglement/sampling_design_audit_v3/checks.csv#L1) | Resultado individual de cada verificacao da realizacao. |
| [Distribuicoes](../../data/processed/disentanglement/sampling_design_audit_v3/window_distribution.csv#L1) | Medianas e quantis, incluindo blocos completos e incompletos. |
| [Contexto](../../data/processed/disentanglement/sampling_design_audit_v3/context_sensitivity.csv#L1) | Contagens e denominadores da sensibilidade de visibilidade. |
| [Estratos](../../data/processed/disentanglement/sampling_design_audit_v3/stratum_sensitivity.csv#L1) | Cortes alternativos, custo esperado e dispersao do total auxiliar. |
| [Variancia conhecida](../../data/processed/disentanglement/sampling_design_audit_v3/known_total_variance.csv#L1) | Esperancas e variancias exatas para quantidades auxiliares. |
| [Manifesto](../../data/processed/disentanglement/sampling_design_audit_v3/manifest.json#L1) | Origem, hashes, implementacao e arquivos de saida da auditoria. |

Este relato e uma sintese metodologica versionavel, nao o destino automatico
do gerador numerico. Se o codigo ou o piloto mudar, executar novamente os
testes e a auditoria e atualizar a sintese com a nova referencia, sem misturar
resultados de execucoes diferentes.