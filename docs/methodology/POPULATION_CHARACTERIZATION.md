# Caracterizacao da populacao de canais mantidos

## 1. Escopo, fontes e reproducibilidade

Este documento descreve o corpus apos a selecao de canais da Etapa 2, antes do sorteio das janelas da Etapa 3. As estatisticas sao descritivas do export observado, nao estimativas de todas as mensagens das comunidades nem resultados de classificacao semantica ou toxicidade.

Extracao das estatisticas: `2026-10-09T18:14:49.391240+00:00`. Todos os horarios e agrupamentos temporais usam UTC.

Entrada congelada: `messages_2026-10-07_excluded_channels_min500_interacting5.parquet`.

Os calculos deste documento sao executados por `discord_disentanglement/population_report.py`, sobre os CSVs e o resumo produzidos por `discord_disentanglement/population.py`. O gerador verifica os hashes dos artefatos e a reconciliacao dos totais antes de escrever. Nao precisa reler os milhoes de mensagens para gerar o texto.

```powershell
python -m discord_disentanglement.population_report
```

Para regenerar explicitamente ou usar outros artefatos:

```powershell
python -m discord_disentanglement.population_report `
  --input-dir data/processed/disentanglement/population_payload_v2 `
  --output docs/methodology/POPULATION_CHARACTERIZATION.md `
  --overwrite
```

O Markdown tem um manifesto adjacente com hashes dos artefatos utilizados, do gerador e do documento. A validacao de hashes cobre os relatorios; o Parquet original nao e relido por este gerador. Valores sao formatados com ponto para milhares e virgula para decimais; NA indica denominador nulo ou medida indisponivel. Arredondamento ocorre apenas na apresentacao.

## 2. Populacao observada e quadro utilizavel

| Medida | Valor |
| --- | --- |
| Servidores com registros | 31 |
| Canais com registros | 407 |
| Registros totais | 11.918.028 |
| Registros explicitamente humanos | 11.918.028 |
| Registros com texto ou midia (qualquer autor) | 11.884.832 |
| Mensagens humanas utilizaveis | 11.884.832 |
| Nao utilizaveis: sem texto nem midia registrada | 33.196 |
| Mensagens humanas com conteudo e problemas estruturais | 0 |
| Autores humanos distintos no corpus | 160.795 |
| Autores humanos distintos no quadro utilizavel | 146.848 |
| Primeiro timestamp observado (UTC) | 2017-01-15 18:56:22.736+00 |
| Ultimo timestamp observado (UTC) | 2025-01-12 20:49:00.939+00 |
| Dias com atividade observada no corpus | 2.892 |

Neste projeto, nao utilizavel significa exclusivamente um registro sem texto nao vazio e sem anexo, embed ou sticker registrado. Texto composto apenas por espacos e considerado vazio. Havendo texto ou midia, o registro e utilizavel nesta caracterizacao, independentemente do tipo Discord. Uma mensagem humana utilizavel tem conteudo registrado e `is_bot = false`; status de bot ausente nao e presumido humano. Bots com conteudo nao sao classificados como nao utilizaveis, mas nao pertencem a populacao humana.

IDs ausentes, timestamp invalido e chave duplicada sao problemas estruturais separados, nao motivos de nao utilizabilidade pela definicao adotada. Registros com conteudo e essas flags permanecem no volume utilizavel; calculos que exigem identificacao e ordem cronologica precisam exclui-los de sua base especifica. Todos os tipos de mensagem sao aceitos para volume quando ha conteudo. Utilizabilidade nao garante relevancia tematica ou elegibilidade final para anotacao. O quadro amostral definitivo ainda deve ser congelado apos revisar as restricoes tecnicas das janelas.

Autores sao deduplicados globalmente por ID no resumo. A soma de autores distintos por canal/servidor nao e uma contagem global, pois a mesma pessoa pode aparecer em varios canais. Dias ativos globais tambem nao sao somas dos dias ativos dos canais.

Registros com texto ou midia representam 99,72% do total; 0,28% nao possuem conteudo registrado. Mensagens humanas utilizaveis representam 99,72% do total. Dos autores humanos observados, 91,33% possuem ao menos uma mensagem utilizavel. A diferenca entre autores observados e autores do quadro decorre da disponibilidade de conteudo em suas mensagens, nao do tipo Discord.

A definicao `payload_v2` substitui a regra inicial que tambem rejeitava tipos diferentes de 0/19 e problemas estruturais. Os artefatos anteriores permanecem em `data/processed/disentanglement/population`; as estatisticas abaixo foram recalculadas pela nova regra. Mensagens totalmente ausentes do export continuam sendo uma perda desconhecida, distinta de registros presentes sem conteudo.

## 3. Distribuicao de volume e concentracao

### 3.1. Distribuicao entre canais e servidores

| Unidade | Medida | Min | Q25 | Mediana | Media | Q75 | Q90 | Q95 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Canal | Registros | 19,00 | 439,00 | 2.213,00 | 29.282,62 | 15.384,50 | 59.549,00 | 135.535,60 | 790.223,00 |
| Canal | Mensagens utilizaveis | 2,00 | 417,50 | 2.204,00 | 29.201,06 | 15.365,00 | 59.520,00 | 135.516,10 | 790.141,00 |
| Canal | Autores humanos distintos | 7,00 | 39,00 | 105,00 | 597,09 | 322,50 | 1.109,20 | 1.950,20 | 57.005,00 |
| Servidor | Registros | 141,00 | 19.903,00 | 190.506,00 | 384.452,52 | 530.673,50 | 960.197,00 | 1.297.544,50 | 2.441.256,00 |
| Servidor | Mensagens utilizaveis | 141,00 | 19.826,00 | 190.068,00 | 383.381,68 | 530.558,00 | 958.406,00 | 1.296.886,00 | 2.440.261,00 |
| Servidor | Autores humanos distintos | 124,00 | 598,50 | 2.106,00 | 5.214,52 | 3.707,50 | 8.041,00 | 22.579,00 | 57.465,00 |

Os quantis acima sao entre unidades: cada canal ou servidor tem peso um. Usam interpolacao linear (`pandas.Series.quantile`). Nao sao quantis entre mensagens.

### 3.2. Concentracao acumulada

| Unidade | Populacao | Meta de volume | Unidades necessarias | % das unidades | Volume efetivamente coberto |
| --- | --- | --- | --- | --- | --- |
| channel | all_records | 50,00% | 14 | 3,44% | 51,58% |
| channel | all_records | 80,00% | 46 | 11,30% | 80,20% |
| channel | all_records | 90,00% | 82 | 20,15% | 90,09% |
| channel | all_records | 95,00% | 120 | 29,48% | 95,05% |
| channel | usable_human | 50,00% | 14 | 3,44% | 51,60% |
| channel | usable_human | 80,00% | 46 | 11,30% | 80,28% |
| channel | usable_human | 90,00% | 82 | 20,15% | 90,17% |
| channel | usable_human | 95,00% | 119 | 29,24% | 95,04% |
| server | all_records | 50,00% | 4 | 12,90% | 50,31% |
| server | all_records | 80,00% | 9 | 29,03% | 80,72% |
| server | all_records | 90,00% | 13 | 41,94% | 90,63% |
| server | all_records | 95,00% | 16 | 51,61% | 95,92% |
| server | usable_human | 50,00% | 4 | 12,90% | 50,42% |
| server | usable_human | 80,00% | 9 | 29,03% | 80,83% |
| server | usable_human | 90,00% | 13 | 41,94% | 90,73% |
| server | usable_human | 95,00% | 16 | 51,61% | 96,04% |

As unidades sao ordenadas por volume decrescente. O limiar e o menor numero de unidades cuja soma atinge a meta; a participacao efetiva pode exceder a meta devido a indivisibilidade dos canais. `all_records` usa todos os registros; `usable_human` usa o quadro utilizavel.

| Unidade | Populacao | Gini | HHI | Numero efetivo de unidades |
| --- | --- | --- | --- | --- |
| channel | all_records | 0,8530 | 0,0253 | 39,46 |
| channel | usable_human | 0,8537 | 0,0254 | 39,38 |
| server | all_records | 0,6574 | 0,0955 | 10,47 |
| server | usable_human | 0,6586 | 0,0958 | 10,43 |

Gini mede desigualdade de volume (0 indica volumes iguais). HHI e a soma dos quadrados das participacoes, na escala 0 a 1; seu inverso e o numero de unidades de igual volume com concentracao equivalente. Estes indices descrevem volume, nao qualidade ou importancia cientifica.

$$G = \frac{2\sum_{i=1}^{k} i x_{(i)}}{k\sum_{i=1}^{k}x_i}-\frac{k+1}{k}, \qquad HHI=\sum_{i=1}^{k}s_i^2, \qquad k_{efetivo}=\frac{1}{HHI}$$

Na formula de Gini, os volumes sao ordenados de forma crescente; $s_i=x_i/\sum_jx_j$.

| Unidade | Populacao | Maiores unidades | % das mensagens |
| --- | --- | --- | --- |
| channel | all_records | 1 | 6,63% |
| channel | all_records | 5 | 26,60% |
| channel | all_records | 10 | 42,77% |
| channel | all_records | 20 | 60,98% |
| channel | all_records | 50 | 81,72% |
| channel | usable_human | 1 | 6,65% |
| channel | usable_human | 5 | 26,65% |
| channel | usable_human | 10 | 42,76% |
| channel | usable_human | 20 | 61,02% |
| channel | usable_human | 50 | 81,80% |
| server | all_records | 1 | 20,48% |
| server | all_records | 5 | 58,19% |
| server | all_records | 10 | 83,31% |
| server | all_records | 20 | 98,96% |
| server | all_records | 31 | 100,00% |
| server | usable_human | 1 | 20,53% |
| server | usable_human | 5 | 58,32% |
| server | usable_human | 10 | 83,42% |
| server | usable_human | 20 | 98,97% |
| server | usable_human | 31 | 100,00% |

Na populacao utilizavel, 46 de 407 canais (11,30%) atingem 80% do volume, cobrindo efetivamente 80,28%. A unidade de maior volume concentra 6,65% das mensagens utilizaveis.

Na populacao utilizavel, 9 de 31 servidores (29,03%) atingem 80% do volume, cobrindo efetivamente 80,83%. A unidade de maior volume concentra 20,53% das mensagens utilizaveis.

### 3.3. Faixas de tamanho dos canais

| Mensagens utilizaveis por canal | Canais | % dos canais | Mensagens | % das mensagens |
| --- | --- | --- | --- | --- |
| 0 a 499 | 111 | 27,27% | 19.986 | 0,17% |
| 500 a 999 | 40 | 9,83% | 28.171 | 0,24% |
| 1.000 a 4.999 | 97 | 23,83% | 230.001 | 1,94% |
| 5.000 a 9.999 | 34 | 8,35% | 246.544 | 2,07% |
| 10.000 a 49.999 | 81 | 19,90% | 1.913.029 | 16,10% |
| 50.000 a 99.999 | 15 | 3,69% | 1.118.881 | 9,41% |
| 100.000 ou mais | 29 | 7,13% | 8.328.220 | 70,07% |

As faixas usam mensagens utilizaveis, nao o volume bruto empregado na Etapa 2. Canais abaixo de 500 podem permanecer porque a exclusao historica combinava volume e autores interagentes com AND, nao OR.

### 3.4. Todos os servidores, por volume utilizavel

| Servidor | guild_id | Canais | Registros | Utilizaveis | % do quadro | Autores humanos | Primeiro UTC | Ultimo UTC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cyberpunk 2077 Modding Community | 717692382849663036 | 57 | 2.441.256 | 2.440.261 | 20,53% | 32.732 | 2020-12-09 07:17:00.54+00 | 2025-01-07 02:22:06.002+00 |
| MonoGame Discord | 355231098122272778 | 14 | 1.313.022 | 1.312.785 | 11,05% | 3.685 | 2017-09-07 08:39:49.32+00 | 2024-12-25 02:35:41.416+00 |
| Kindred Games Community | 398282199788552193 | 15 | 1.282.067 | 1.280.987 | 10,78% | 5.618 | 2018-01-04 01:50:57.564+00 | 2025-01-06 19:56:45.864+00 |
| Sapphire - Imagine a framework | 737141877803057244 | 21 | 960.197 | 958.406 | 8,06% | 2.106 | 2020-07-27 23:21:46.246+00 | 2025-01-01 19:33:32.725+00 |
| Tech Haven | 455345206481518593 | 14 | 938.522 | 938.437 | 7,90% | 3.806 | 2019-06-16 00:36:16.581+00 | 2024-12-21 23:42:36.655+00 |
| Touhou Game Dev | 933089313405685760 | 35 | 849.862 | 849.453 | 7,15% | 853 | 2022-01-18 20:27:23.069+00 | 2025-01-07 08:50:23.073+00 |
| ImperialPlugins\.com | 284399832385191936 | 8 | 773.600 | 764.683 | 6,43% | 5.854 | 2017-02-23 19:18:59.741+00 | 2025-01-07 03:04:56.565+00 |
| Rectify11 Community | 1077324213142175744 | 15 | 663.341 | 663.200 | 5,58% | 2.306 | 2023-02-28 23:11:31.147+00 | 2024-12-19 04:19:39.637+00 |
| Return Community | 1080829289412432032 | 13 | 398.006 | 397.916 | 3,35% | 3.204 | 2023-06-30 13:40:10.092+00 | 2024-12-28 17:00:44.496+00 |
| OpenRCT2 | 264137540670324737 | 10 | 308.562 | 308.504 | 2,60% | 3.195 | 2020-03-24 21:48:02.745+00 | 2025-01-11 05:05:01.437+00 |
| Docker | 460871933748183040 | 9 | 299.330 | 299.181 | 2,52% | 8.041 | 2018-06-25 18:25:07.59+00 | 2025-01-09 02:15:34.443+00 |
| L'Ordre des Devs | 706640777450881114 | 5 | 289.687 | 286.700 | 2,41% | 2.535 | 2020-05-04 21:52:31.273+00 | 2025-01-04 22:47:11.578+00 |
| Shardeum | 933959587462254612 | 2 | 283.322 | 282.792 | 2,38% | 57.465 | 2022-01-21 05:46:57.828+00 | 2025-01-08 16:27:40.895+00 |
| Terasology | 270264625419911192 | 32 | 229.222 | 229.130 | 1,93% | 892 | 2017-01-15 18:56:22.736+00 | 2025-01-07 04:44:05.86+00 |
| OpenVic - Community | 1062018115275325480 | 16 | 211.471 | 211.435 | 1,78% | 1.653 | 2023-01-09 17:01:43.292+00 | 2025-01-11 04:53:01.239+00 |
| Kavita | 821879810934439936 | 12 | 190.506 | 190.068 | 1,60% | 2.284 | 2021-03-20 16:22:40.316+00 | 2024-12-22 03:55:00.556+00 |
| TheScostumati | 516564332440584221 | 8 | 107.899 | 107.865 | 0,91% | 338 | 2019-01-22 17:25:06.815+00 | 2025-01-08 20:16:27.496+00 |
| Andy’s Development | 857672921912836116 | 3 | 94.345 | 94.269 | 0,79% | 3.730 | 2021-06-25 01:15:46.636+00 | 2025-01-12 20:49:00.939+00 |
| WWebJS | 698610475432411196 | 12 | 98.203 | 83.740 | 0,70% | 12.426 | 2020-04-11 19:36:54.376+00 | 2025-01-08 23:49:21.539+00 |
| 💻 Ouckah Lair | 519640186167099402 | 13 | 62.240 | 62.227 | 0,52% | 1.024 | 2023-04-05 18:12:51.796+00 | 2025-01-09 02:45:44.216+00 |
| GameDevSG | 558680594498977792 | 12 | 36.203 | 35.846 | 0,30% | 1.112 | 2019-04-07 07:29:16.051+00 | 2024-12-19 16:46:26.402+00 |
| Neo4j | 787399249741479977 | 25 | 32.716 | 32.664 | 0,27% | 2.841 | 2021-03-03 11:44:33.057+00 | 2024-12-24 16:07:50.037+00 |
| Penusbmic's Server | 894976658229063731 | 18 | 32.008 | 31.910 | 0,27% | 898 | 2021-10-08 18:54:51.003+00 | 2025-01-06 18:00:25.479+00 |
| Fermyon | 926888690310053918 | 14 | 7.798 | 7.742 | 0,07% | 465 | 2022-01-01 17:25:48.352+00 | 2025-01-08 10:18:49.792+00 |
| CodingWallah | 1056895641676152852 | 8 | 5.214 | 5.212 | 0,04% | 528 | 2022-12-26 11:26:35.28+00 | 2024-12-21 09:14:16.058+00 |
| Montano Community | 561997286087852118 | 1 | 2.772 | 2.772 | 0,02% | 367 | 2020-04-28 18:17:10.218+00 | 2024-11-20 06:13:19.91+00 |
| Oxylabs | 1128239127687598080 | 6 | 2.735 | 2.730 | 0,02% | 588 | 2023-07-28 08:19:19.071+00 | 2025-01-05 19:33:43.405+00 |
| TikTok Shop Developer Hub | 1204537856870191114 | 3 | 2.132 | 2.127 | 0,02% | 609 | 2024-02-06 21:27:58.8+00 | 2024-12-27 09:15:47.151+00 |
| Rosebud AI | 773712199729414144 | 2 | 970 | 970 | 0,01% | 158 | 2021-04-13 03:49:35.372+00 | 2024-12-03 09:18:05.716+00 |
| LuaCore Framework | 1078542362793492490 | 3 | 679 | 679 | 0,01% | 213 | 2023-02-27 08:32:48.682+00 | 2024-12-12 20:23:32.41+00 |
| Evolution Software Inc | 806713690182385695 | 1 | 141 | 141 | 0,00% | 124 | 2021-03-12 12:06:29.636+00 | 2025-01-07 19:48:22.244+00 |

### 3.5. Os 20 canais de maior volume utilizavel

| Servidor | Canal | channel_id | Utilizaveis | % do quadro | % acumulado | Autores humanos |
| --- | --- | --- | --- | --- | --- | --- |
| Tech Haven | general | 593063949067485204 | 790.141 | 6,65% | 6,65% | 2.734 |
| Sapphire - Imagine a framework | off-topic | 737142209639350343 | 675.805 | 5,69% | 12,33% | 1.740 |
| Rectify11 Community | casual-chat | 1080264228247719977 | 584.267 | 4,92% | 17,25% | 1.352 |
| Cyberpunk 2077 Modding Community | general-chat | 789711087158820864 | 569.877 | 4,79% | 22,05% | 11.967 |
| Kindred Games Community | general-chat | 398282200287543297 | 547.581 | 4,61% | 26,65% | 3.073 |
| Cyberpunk 2077 Modding Community | game-chat | 727800569158434827 | 496.443 | 4,18% | 30,83% | 8.836 |
| MonoGame Discord | off-topic | 357384790158213120 | 478.591 | 4,03% | 34,86% | 800 |
| ImperialPlugins\.com | general | 284399832385191936 | 364.467 | 3,07% | 37,92% | 5.792 |
| Cyberpunk 2077 Modding Community | mod-dev-chat | 727800260486758410 | 290.874 | 2,45% | 40,37% | 6.528 |
| L'Ordre des Devs | discussion | 706642662937067580 | 284.011 | 2,39% | 42,76% | 2.532 |
| Shardeum | 💬・general | 933959587462254615 | 278.422 | 2,34% | 45,10% | 57.005 |
| MonoGame Discord | help | 402546044274999299 | 276.211 | 2,32% | 47,43% | 2.499 |
| MonoGame Discord | monogame-discussion | 355231098122272779 | 251.205 | 2,11% | 49,54% | 1.785 |
| Touhou Game Dev | touhou | 933089316547219558 | 244.327 | 2,06% | 51,60% | 313 |
| MonoGame Discord | programming | 402546188198608897 | 224.841 | 1,89% | 53,49% | 1.246 |
| Kindred Games Community | swords-n-magic-and-chat | 632274671370502145 | 220.230 | 1,85% | 55,34% | 2.660 |
| Return Community | 💬┇chat-here | 1136202840499572736 | 215.679 | 1,81% | 57,16% | 2.363 |
| Return Community | 🔨┇creations | 1124314155990667396 | 167.746 | 1,41% | 58,57% | 1.152 |
| Touhou Game Dev | general | 933089314965970991 | 150.740 | 1,27% | 59,84% | 484 |
| OpenVic - Community | 💬general | 1062021872545447936 | 140.820 | 1,18% | 61,02% | 1.282 |

## 4. Autores e definicao de interacao

`distinct_human_authors` conta autores com pelo menos um registro explicitamente nao-bot; `distinct_usable_human_authors` exige pelo menos uma mensagem utilizavel. `native_reply_interacting_authors` conta autores distintos que enviaram ao menos um native reply utilizavel a mensagem humana utilizavel anterior de outro autor no mesmo servidor/canal. Conta emissores, nao destinatarios apenas por receberem reply. Nao inclui mencoes, autorrespostas nem antecedentes ausentes.

| Medida por canal | Min | Q25 | Mediana | Media | Q75 | Q90 | Q95 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| distinct_human_authors | 7,00 | 39,00 | 105,00 | 597,09 | 322,50 | 1.109,20 | 1.950,20 | 57.005,00 |
| distinct_usable_human_authors | 2,00 | 38,00 | 104,00 | 552,14 | 318,50 | 922,20 | 1.768,00 | 56.846,00 |
| native_reply_interacting_authors | 0,00 | 15,00 | 46,00 | 214,91 | 141,00 | 423,20 | 852,70 | 14.273,00 |

Canais sem emissores de reply humano resolvido: 8; canais com menos de cinco: 27. Esses numeros usam a nova definicao e nao reconstituem a regra historica.

A definicao original de `interacting_authors` da Etapa 2 permanece nao verificavel: o manifesto declara apenas `interaction_scope = human_messages`, sem o predicado, e a rotina original `profile-channels` nao foi localizada. O pacote `annotations/channel_selection_2026-10-07` preserva a tabela historica, a lista, os manifestos e os valores/decisoes por canal, com auditoria executavel dos corpora. Ele permite replay da decisao sobre os valores congelados, nao recalculo da metrica a partir das mensagens; a etapa historica nao e inteiramente reproduzivel nesse sentido. A inspecao exploratoria 552 mensagens/3 autores unicos nao foi uma mascara anterior a regra final 500 AND 5, e nao foi recuperada justificativa estatistica para essa mudanca. A coluna atual de scoring `interacting_human_user_count` conta emissores com reply a ID humano anterior ou `mention_count > 0`, mas isso nao prova equivalencia com a tabela historica. A nova medida tem nome distinto e nao altera a selecao 500/5. Consulte `docs/methodology/CHANNEL_SELECTION_STAGE.md` para o escopo do replay e suas limitacoes.

Nao ha contagens por autor nos artefatos agregados; portanto este documento nao estima distribuicao individual de produtividade, participacao do autor dominante ou concentracao entre autores.

## 5. Cobertura e distribuicao temporal

### 5.1. Cobertura por canal

| Medida por canal | Min | Q25 | Mediana | Media | Q75 | Q90 | Q95 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Amplitude em dias calendario (inclusive) | 1,00 | 530,00 | 1.037,00 | 1.065,68 | 1.510,50 | 1.989,40 | 2.291,80 | 2.910,00 |
| Dias ativos (todos os registros) | 1,00 | 62,50 | 223,00 | 444,05 | 625,50 | 1.226,60 | 1.681,20 | 2.853,00 |
| Dias ativos (quadro utilizavel) | 1,00 | 61,50 | 218,00 | 440,54 | 622,00 | 1.226,60 | 1.650,10 | 2.783,00 |
| Mensagens utilizaveis por dia ativo | 1,00 | 5,04 | 12,75 | 37,39 | 30,90 | 82,94 | 149,07 | 883,91 |

Amplitude e diferenca entre as datas UTC extremas mais um dia; nao garante coleta continua. Mensagens por dia ativo divide o volume utilizavel pelos dias com ao menos uma mensagem utilizavel no canal. Nao e media por dia calendario nem intensidade corrigida pela disponibilidade do export.

### 5.2. Atividade por ano

| Ano UTC | Registros | % dos registros | Utilizaveis | % do quadro |
| --- | --- | --- | --- | --- |
| 2017 | 96.193 | 0,81% | 96.072 | 0,81% |
| 2018 | 228.622 | 1,92% | 227.145 | 1,91% |
| 2019 | 428.653 | 3,60% | 427.201 | 3,59% |
| 2020 | 1.863.553 | 15,64% | 1.860.276 | 15,65% |
| 2021 | 1.943.263 | 16,31% | 1.936.958 | 16,30% |
| 2022 | 1.678.231 | 14,08% | 1.673.731 | 14,08% |
| 2023 | 2.727.670 | 22,89% | 2.722.377 | 22,91% |
| 2024 | 2.908.079 | 24,40% | 2.897.433 | 24,38% |
| 2025 | 43.764 | 0,37% | 43.639 | 0,37% |

Anos e meses nas extremidades podem ser parciais. Contagens anuais nao sao taxas anualizadas; diferencas podem refletir cobertura do export, entrada/saida de canais ou mudancas reais de atividade.

### 5.3. Dez meses de maior volume utilizavel

| Mes UTC | Registros | Utilizaveis | % do quadro |
| --- | --- | --- | --- |
| 2024-01 | 374.716 | 374.186 | 3,15% |
| 2023-10 | 324.101 | 323.540 | 2,72% |
| 2020-12 | 319.029 | 318.629 | 2,68% |
| 2023-09 | 284.972 | 284.482 | 2,39% |
| 2023-04 | 259.797 | 259.450 | 2,18% |
| 2024-04 | 259.113 | 257.707 | 2,17% |
| 2021-01 | 250.984 | 250.604 | 2,11% |
| 2024-03 | 251.049 | 250.234 | 2,11% |
| 2024-02 | 248.717 | 248.154 | 2,09% |
| 2024-05 | 248.398 | 247.308 | 2,08% |

### 5.4. Atividade por dia da semana

| Periodo UTC | Registros | Utilizaveis | % do quadro |
| --- | --- | --- | --- |
| Segunda | 1.673.561 | 1.668.755 | 14,04% |
| Terca | 1.768.763 | 1.763.762 | 14,84% |
| Quarta | 1.796.993 | 1.791.779 | 15,08% |
| Quinta | 1.756.063 | 1.751.036 | 14,73% |
| Sexta | 1.740.283 | 1.735.584 | 14,60% |
| Sabado | 1.590.942 | 1.586.595 | 13,35% |
| Domingo | 1.591.423 | 1.587.321 | 13,36% |

### 5.5. Atividade por hora UTC

| Periodo UTC | Registros | Utilizaveis | % do quadro |
| --- | --- | --- | --- |
| 00:00 a 00:59 | 446.047 | 444.889 | 3,74% |
| 01:00 a 01:59 | 402.476 | 401.351 | 3,38% |
| 02:00 a 02:59 | 365.670 | 364.574 | 3,07% |
| 03:00 a 03:59 | 330.952 | 329.916 | 2,78% |
| 04:00 a 04:59 | 300.551 | 299.642 | 2,52% |
| 05:00 a 05:59 | 285.843 | 284.987 | 2,40% |
| 06:00 a 06:59 | 293.093 | 292.159 | 2,46% |
| 07:00 a 07:59 | 299.268 | 298.278 | 2,51% |
| 08:00 a 08:59 | 306.740 | 305.688 | 2,57% |
| 09:00 a 09:59 | 326.063 | 324.949 | 2,73% |
| 10:00 a 10:59 | 340.795 | 339.657 | 2,86% |
| 11:00 a 11:59 | 377.648 | 376.177 | 3,17% |
| 12:00 a 12:59 | 434.876 | 433.436 | 3,65% |
| 13:00 a 13:59 | 516.327 | 514.678 | 4,33% |
| 14:00 a 14:59 | 586.650 | 584.889 | 4,92% |
| 15:00 a 15:59 | 667.967 | 666.181 | 5,61% |
| 16:00 a 16:59 | 724.946 | 723.087 | 6,08% |
| 17:00 a 17:59 | 736.307 | 734.473 | 6,18% |
| 18:00 a 18:59 | 762.467 | 760.629 | 6,40% |
| 19:00 a 19:59 | 772.684 | 770.783 | 6,49% |
| 20:00 a 20:59 | 778.570 | 776.753 | 6,54% |
| 21:00 a 21:59 | 714.778 | 713.106 | 6,00% |
| 22:00 a 22:59 | 629.595 | 628.101 | 5,28% |
| 23:00 a 23:59 | 517.715 | 516.449 | 4,35% |

Dias da semana e horas agregam todos os periodos e canais. As participacoes nao sao corrigidas pelo numero de ocorrencias de cada dia no historico, nem pelo fuso local dos participantes. A rotina original exporta apenas buckets observados; dias da semana/horas ausentes sao preenchidos com zero nesta apresentacao, sem supor completude da coleta. Mensagens com timestamp ausente/invalido nao podem ser agrupadas temporalmente, mesmo se tiverem conteudo; as participacoes usam todo o volume como denominador.

## 6. Native replies, antecedentes e distancias

### 6.1. Frequencia e denominadores

| Medida | Contagem | Denominador | Proporcao |
| --- | --- | --- | --- |
| Native replies | 1.708.622 | Todos os registros | 14,34% |
| Native replies utilizaveis | 1.708.616 | Mensagens utilizaveis | 14,38% |
| Qualquer referencia nativa | 1.711.050 | Todos os registros | 14,36% |
| Reply sem ID do antecedente | 0 | Todos os registros | 0,00% |

Native reply exige tipo Discord 19 e ID de referencia nao vazio. Referencias de outros tipos nao sao incluidas como replies. Ausencia de reply nativo nao significa ausencia de resposta semantica.

### 6.2. Resolucao de antecedentes

| Populacao de replies | Status | Replies | Denominador | Proporcao |
| --- | --- | --- | --- | --- |
| Todas as origens ordenaveis | parent_not_found | 30.149 | 1.708.622 | 1,76% |
| Todas as origens ordenaveis | resolved | 1.678.473 | 1.708.622 | 98,24% |
| Origens utilizaveis | parent_not_found | 30.149 | 1.708.616 | 1,76% |
| Origens utilizaveis | resolved | 1.678.467 | 1.708.616 | 98,24% |

Replies com origem nao ordenavel, fora da tabela de distancias: 0.

`resolved`: antecedente identificado, unico, com timestamp valido e anterior no mesmo canal; `parent_not_found`: nao localizado na base ordenavel; `different_channel`: encontrado em outro canal; `not_preceding`: origem igual ao antecedente ou antecedente posterior na ordem. Nao encontrado nao demonstra exclusao: pode ser mensagem fora do export ou registro nao ordenavel.

### 6.3. Alcance posicional agregado

Todas as origens: 1.671.310 pares com origem e antecedente utilizaveis entre 1.678.473 replies resolvidos (99,57%).

Origens utilizaveis: 1.671.310 pares com origem e antecedente utilizaveis entre 1.678.467 replies resolvidos (99,57%).

| Populacao | Distancia ate (registros) | Replies cobertos | Replies resolvidos | Cobertura |
| --- | --- | --- | --- | --- |
| Todas as origens | 10 | 1.448.773 | 1.678.473 | 86,31% |
| Todas as origens | 100 | 1.658.573 | 1.678.473 | 98,81% |
| Todas as origens | 200 | 1.667.877 | 1.678.473 | 99,37% |
| Origens utilizaveis | 10 | 1.448.767 | 1.678.467 | 86,31% |
| Origens utilizaveis | 100 | 1.658.567 | 1.678.467 | 98,81% |
| Origens utilizaveis | 200 | 1.667.871 | 1.678.467 | 99,37% |

Estas proporcoes globais sao calculadas pela soma das contagens dos canais dividida pela soma dos replies resolvidos, nao pela media das proporcoes. A distancia e posicao da origem menos posicao do antecedente; 1 indica adjacencia. A ordem inclui todos os registros unicos e identificaveis com timestamp valido, incluindo bots e tipos de sistema. Ha uma ordem alternativa somente de mensagens utilizaveis para pares utilizaveis.

Cobertura ate 200 registros e um diagnostico de alcance dos native replies, nao garantia de contexto suficiente para arestas semanticas. A posicao da mensagem-alvo dentro da janela e a ordem usada na geracao de janelas tambem alteram o contexto disponivel.

### 6.4. Quantis por canal de maior volume

| Servidor | Canal | channel_id | Replies resolvidos utilizaveis | Mediana posicional | Q95 posicional | Mediana temporal (min) | Q95 temporal (h) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tech Haven | general | 593063949067485204 | 83.192 | 3,00 | 30,00 | 1,24 | 2,38 |
| Sapphire - Imagine a framework | off-topic | 737142209639350343 | 96.646 | 3,00 | 33,00 | 1,23 | 2,14 |
| Rectify11 Community | casual-chat | 1080264228247719977 | 149.189 | 3,00 | 32,00 | 0,66 | 1,04 |
| Cyberpunk 2077 Modding Community | general-chat | 789711087158820864 | 138.670 | 3,00 | 19,00 | 0,90 | 0,87 |
| Kindred Games Community | general-chat | 398282200287543297 | 11.596 | 3,00 | 25,00 | 4,78 | 6,61 |
| Cyberpunk 2077 Modding Community | game-chat | 727800569158434827 | 75.819 | 3,00 | 25,00 | 1,15 | 2,19 |
| MonoGame Discord | off-topic | 357384790158213120 | 60.063 | 3,00 | 30,00 | 1,46 | 2,87 |
| ImperialPlugins\.com | general | 284399832385191936 | 13.069 | 3,00 | 31,00 | 2,64 | 9,16 |
| Cyberpunk 2077 Modding Community | mod-dev-chat | 727800260486758410 | 42.528 | 3,00 | 33,00 | 2,74 | 4,93 |
| L'Ordre des Devs | discussion | 706642662937067580 | 52.536 | 3,00 | 21,00 | 0,72 | 1,01 |
| Shardeum | 💬・general | 933959587462254615 | 108.224 | 3,00 | 29,00 | 2,89 | 2,86 |
| MonoGame Discord | help | 402546044274999299 | 21.970 | 2,00 | 31,00 | 3,39 | 6,81 |
| MonoGame Discord | monogame-discussion | 355231098122272779 | 17.332 | 3,00 | 30,00 | 2,75 | 8,26 |
| Touhou Game Dev | touhou | 933089316547219558 | 34.958 | 5,00 | 41,00 | 1,40 | 3,41 |
| MonoGame Discord | programming | 402546188198608897 | 18.626 | 3,00 | 30,00 | 2,05 | 7,10 |
| Kindred Games Community | swords-n-magic-and-chat | 632274671370502145 | 17.435 | 3,00 | 28,00 | 4,39 | 7,00 |
| Return Community | 💬┇chat-here | 1136202840499572736 | 53.311 | 3,00 | 20,00 | 0,37 | 0,78 |
| Return Community | 🔨┇creations | 1124314155990667396 | 55.703 | 2,00 | 30,00 | 0,71 | 3,26 |
| Touhou Game Dev | general | 933089314965970991 | 20.662 | 4,00 | 37,00 | 1,27 | 3,96 |
| OpenVic - Community | 💬general | 1062021872545447936 | 31.870 | 3,00 | 30,00 | 1,30 | 4,40 |

Quantis sao calculados sobre replies de origem utilizavel resolvidos no respectivo canal. O antecedente pode nao ser utilizavel. Minutos e horas sao conversoes de segundos por divisao por 60 e 3.600. O CSV original preserva Q25, Q50, Q75, Q90, Q95 e Q99, inclusive na ordem alternativa utilizavel. Nao e possivel recuperar quantis globais exatos apenas desses quantis por canal; este documento nao os inventa nem calcula medias de quantis.

## 7. Bots, campos ausentes e registros nao utilizaveis

| Flag | Registros | % de todos os registros |
| --- | --- | --- |
| Bots registrados | 0 | 0,00% |
| Status de bot ausente | 0 | 0,00% |
| ID da mensagem ausente | 0 | 0,00% |
| ID do autor ausente | 0 | 0,00% |
| Servidor/canal ausente | 0 | 0,00% |
| Timestamp ausente/invalido | 0 | 0,00% |
| Registros com chave duplicada | 0 | 0,00% |
| Texto vazio ou ausente | 318.541 | 2,67% |
| Mensagens humanas com conteudo e problemas estruturais | 0 | 0,00% |
| Tipo diferente de 0/19 ou ausente (nao implica nao utilizabilidade) | 36.124 | 0,30% |
| Nao utilizaveis: sem texto nem midia registrada | 33.196 | 0,28% |

As flags sao descritivas, podem se sobrepor e nao devem ser somadas. Somente a ausencia simultanea de texto e midia define nao utilizabilidade. Tipos diferentes de 0/19, bots e problemas estruturais nao sao incluidos nessa contagem pelo simples fato de apresentarem essas caracteristicas. Texto vazio sozinho nao torna uma mensagem inutilizavel quando ha anexo, embed ou sticker. Nao se presume que a disponibilidade de midia significa que seu conteudo foi baixado ou sera visivel ao anotador.

Uma proporcao zero de bots descreve apenas a entrada analisada, que pode ter passado por exclusao previa de bots. Nao demonstra que os servidores nao possuem bots. Mensagens completamente ausentes do export nao podem ser contadas sem fonte externa; antecedentes nao localizados e campos ausentes sao indicadores diferentes dessa perda desconhecida.

## 8. Implicacoes para a construcao de janelas

A concentracao deve ser avaliada sobre `usable_human` ao planejar mensagens-alvo. A amostragem proporcional ao volume favorece canais grandes. Isso e coerente para estimar uma media entre mensagens, mas pode deixar poucos exemplos dos canais pequenos para comparacoes entre canais. Uma media entre canais e uma media entre mensagens sao estimandos distintos.

Uma alternativa a avaliar e estabelecer cobertura minima por canal e distribuir o restante proporcionalmente ao volume. As probabilidades de inclusao e os pesos precisam ser registrados quando o desenho for definido. Esta caracterizacao nao determina tamanho amostral, nao estima efeito de desenho e nao sorteia janelas.

Estratificar temporalmente dentro de cada canal evita selecionar apenas inicio/fim do historico ou meses de maior atividade. O volume global por ano nao deve substituir a avaliacao do periodo disponivel de cada canal. Periodos sem registros nao provam inatividade nem falha de coleta.

O piloto deve confrontar alcance posicional dos native replies com antecedentes semanticos anotados, registrar casos fora do contexto e verificar mensagens de midia. Nao interpretar ausencia de reply nativo como rotulo negativo, nem autores interagentes como medida completa de sociabilidade.

## 9. Inventario completo dos canais

Uma linha por par `(guild_id, channel_id)`, ordenada pelo volume utilizavel. Autores H sao distintos humanos; autores U sao distintos no quadro utilizavel; emissores R usam a definicao conservadora de interacao por reply. A taxa R divide native replies utilizaveis por mensagens utilizaveis do canal. Flags detalhadas e quantis adicionais permanecem nos CSVs.

| Servidor | guild_id | Canal | channel_id | Registros | Utilizaveis | % do quadro | Autores H | Autores U | Emissores R | Taxa R | Dias ativos U | Primeiro UTC | Ultimo UTC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tech Haven | 455345206481518593 | general | 593063949067485204 | 790.223 | 790.141 | 6,65% | 2.734 | 2.734 | 859 | 10,81% | 2.007 | 2019-06-25 13:15:53.231+00 | 2024-12-21 22:43:13.07+00 |
| Sapphire - Imagine a framework | 737141877803057244 | off-topic | 737142209639350343 | 677.544 | 675.805 | 5,69% | 1.740 | 914 | 463 | 14,45% | 1.620 | 2020-07-27 23:21:51.218+00 | 2025-01-01 19:33:32.725+00 |
| Rectify11 Community | 1077324213142175744 | casual-chat | 1080264228247719977 | 584.378 | 584.267 | 4,92% | 1.352 | 1.352 | 899 | 25,91% | 661 | 2023-02-28 23:11:31.147+00 | 2024-12-19 04:19:39.637+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | general-chat | 789711087158820864 | 569.915 | 569.877 | 4,79% | 11.967 | 11.967 | 6.175 | 24,76% | 1.458 | 2020-12-19 04:30:10.299+00 | 2025-01-07 00:36:38.602+00 |
| Kindred Games Community | 398282199788552193 | general-chat | 398282200287543297 | 548.515 | 547.581 | 4,61% | 3.073 | 2.616 | 386 | 2,13% | 2.497 | 2018-01-04 04:18:51.301+00 | 2025-01-06 19:27:35.474+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | game-chat | 727800569158434827 | 496.477 | 496.443 | 4,18% | 8.836 | 8.836 | 4.418 | 15,60% | 1.488 | 2020-12-09 07:17:00.54+00 | 2025-01-06 22:41:06.838+00 |
| MonoGame Discord | 355231098122272778 | off-topic | 357384790158213120 | 478.631 | 478.591 | 4,03% | 800 | 800 | 420 | 13,11% | 2.379 | 2018-01-11 16:34:39.926+00 | 2024-12-25 01:28:11.539+00 |
| ImperialPlugins\.com | 284399832385191936 | general | 284399832385191936 | 373.307 | 364.467 | 3,07% | 5.792 | 2.217 | 634 | 3,63% | 2.783 | 2017-02-23 19:18:59.741+00 | 2025-01-06 23:25:10.929+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | mod-dev-chat | 727800260486758410 | 290.922 | 290.874 | 2,45% | 6.528 | 6.528 | 3.003 | 14,84% | 1.464 | 2020-12-10 08:19:11.786+00 | 2025-01-06 23:17:55.481+00 |
| L'Ordre des Devs | 706640777450881114 | discussion | 706642662937067580 | 286.996 | 284.011 | 2,39% | 2.532 | 1.783 | 976 | 19,23% | 1.066 | 2020-05-04 21:52:31.273+00 | 2025-01-04 22:47:11.578+00 |
| Shardeum | 933959587462254612 | 💬・general | 933959587462254615 | 278.951 | 278.422 | 2,34% | 57.005 | 56.846 | 14.273 | 39,85% | 1.074 | 2022-01-21 05:46:57.828+00 | 2025-01-08 16:27:40.895+00 |
| MonoGame Discord | 355231098122272778 | help | 402546044274999299 | 276.231 | 276.211 | 2,32% | 2.499 | 2.499 | 1.205 | 8,08% | 2.421 | 2018-01-20 20:39:37.883+00 | 2024-12-24 22:43:41.149+00 |
| MonoGame Discord | 355231098122272778 | monogame-discussion | 355231098122272779 | 251.367 | 251.205 | 2,11% | 1.785 | 1.725 | 739 | 7,04% | 2.477 | 2017-09-07 08:39:49.32+00 | 2024-12-24 13:45:01.848+00 |
| Touhou Game Dev | 933089313405685760 | touhou | 933089316547219558 | 244.413 | 244.327 | 2,06% | 313 | 313 | 236 | 14,34% | 1.081 | 2022-01-18 20:31:53.073+00 | 2025-01-07 08:50:23.073+00 |
| MonoGame Discord | 355231098122272778 | programming | 402546188198608897 | 224.847 | 224.841 | 1,89% | 1.246 | 1.246 | 621 | 8,35% | 2.076 | 2018-02-06 20:05:46.427+00 | 2024-12-24 21:39:01.262+00 |
| Kindred Games Community | 398282199788552193 | swords-n-magic-and-chat | 632274671370502145 | 220.277 | 220.230 | 1,85% | 2.660 | 2.660 | 772 | 7,95% | 1.818 | 2019-10-11 17:55:12.368+00 | 2025-01-06 19:56:45.864+00 |
| Return Community | 1080829289412432032 | 💬┇chat-here | 1136202840499572736 | 215.720 | 215.679 | 1,81% | 2.363 | 2.362 | 1.091 | 25,52% | 352 | 2024-01-07 02:23:26.117+00 | 2024-12-28 16:04:20.632+00 |
| Return Community | 1080829289412432032 | 🔨┇creations | 1124314155990667396 | 167.772 | 167.746 | 1,41% | 1.152 | 1.151 | 782 | 34,06% | 527 | 2023-06-30 13:40:10.092+00 | 2024-12-28 16:32:13.812+00 |
| Touhou Game Dev | 933089313405685760 | general | 933089314965970991 | 150.807 | 150.740 | 1,27% | 484 | 484 | 299 | 13,74% | 1.040 | 2022-01-18 20:27:23.069+00 | 2025-01-07 05:43:00.511+00 |
| OpenVic - Community | 1062018115275325480 | 💬general | 1062021872545447936 | 140.849 | 140.820 | 1,18% | 1.282 | 1.282 | 838 | 22,75% | 733 | 2023-01-09 17:01:43.292+00 | 2025-01-11 03:59:51.909+00 |
| ImperialPlugins\.com | 284399832385191936 | dev | 663524633563103233 | 138.319 | 138.295 | 1,16% | 550 | 550 | 259 | 11,62% | 1.689 | 2020-01-07 17:47:23.354+00 | 2025-01-07 03:04:56.565+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | spoilers-chat | 790730432437157898 | 129.041 | 129.032 | 1,09% | 1.690 | 1.689 | 976 | 13,36% | 1.186 | 2020-12-22 00:00:36.352+00 | 2025-01-06 23:30:02.931+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | textures-and-models | 786891742829215745 | 122.357 | 122.314 | 1,03% | 1.733 | 1.733 | 941 | 14,94% | 1.340 | 2020-12-11 14:04:21.465+00 | 2025-01-06 21:39:29.296+00 |
| Docker | 460871933748183040 | docker | 460871933748183042 | 120.796 | 120.651 | 1,02% | 4.682 | 4.638 | 1.837 | 19,19% | 2.248 | 2018-06-25 18:25:07.59+00 | 2025-01-08 23:28:32.017+00 |
| Kindred Games Community | 398282199788552193 | spoiler-chat | 753173823406342175 | 118.870 | 118.846 | 1,00% | 1.377 | 1.377 | 576 | 8,55% | 1.263 | 2020-09-09 08:43:59.646+00 | 2025-01-06 05:53:46.117+00 |
| ImperialPlugins\.com | 284399832385191936 | unturned-support | 284402775071260672 | 117.993 | 117.974 | 0,99% | 1.104 | 1.104 | 377 | 4,09% | 2.596 | 2017-02-24 20:01:07.892+00 | 2025-01-03 16:56:30.419+00 |
| OpenRCT2 | 264137540670324737 | openrct2-talk | 691736850980667514 | 117.247 | 117.231 | 0,99% | 2.012 | 2.012 | 859 | 12,25% | 1.726 | 2020-03-28 11:08:42.427+00 | 2025-01-11 03:21:37.202+00 |
| Touhou Game Dev | 933089313405685760 | jam-discussion | 933089316035506242 | 107.434 | 107.393 | 0,90% | 399 | 399 | 281 | 13,55% | 712 | 2022-01-18 21:32:24.75+00 | 2025-01-07 04:17:34.159+00 |
| Terasology | 270264625419911192 | terasology | 270264625419911192 | 104.219 | 104.206 | 0,88% | 616 | 616 | 100 | 1,74% | 1.766 | 2017-01-15 18:56:22.736+00 | 2025-01-02 12:56:42.273+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | cet-troubleshooting | 795037292955172895 | 97.244 | 97.197 | 0,82% | 9.256 | 9.256 | 3.463 | 17,15% | 1.455 | 2021-01-02 21:24:01.967+00 | 2025-01-07 01:39:22.282+00 |
| Andy’s Development | 857672921912836116 | general-support | 857802803229360138 | 92.500 | 92.446 | 0,78% | 3.694 | 3.694 | 1.804 | 20,27% | 1.262 | 2021-06-25 02:03:15.941+00 | 2025-01-12 20:41:07.048+00 |
| Sapphire - Imagine a framework | 737141877803057244 | old-coding-den | 737142325217722478 | 91.209 | 91.199 | 0,77% | 320 | 320 | 203 | 11,71% | 819 | 2020-07-27 23:21:46.246+00 | 2022-12-12 17:39:02.389+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | wolvenkit-dev | 717720094196760760 | 89.091 | 88.916 | 0,75% | 123 | 123 | 92 | 11,20% | 1.217 | 2020-12-11 09:16:18.748+00 | 2025-01-06 17:50:31.549+00 |
| Docker | 460871933748183040 | docker-compose | 581537102244610058 | 80.347 | 80.347 | 0,68% | 2.503 | 2.503 | 1.239 | 20,87% | 1.716 | 2019-05-24 17:42:34.228+00 | 2025-01-09 01:41:02.39+00 |
| Touhou Game Dev | 933089313405685760 | gaming | 933089316547219559 | 79.913 | 79.901 | 0,67% | 211 | 211 | 151 | 10,83% | 1.032 | 2022-01-18 20:41:55.541+00 | 2025-01-07 07:30:30.194+00 |
| Kavita | 821879810934439936 | support | 840693141082341406 | 74.929 | 74.927 | 0,63% | 1.626 | 1.626 | 914 | 12,25% | 1.219 | 2021-05-11 19:53:48.073+00 | 2024-12-22 03:55:00.556+00 |
| Sapphire - Imagine a framework | 737141877803057244 | old-sapphire-support | 737142503043498015 | 73.479 | 73.468 | 0,62% | 684 | 684 | 441 | 14,42% | 716 | 2020-07-27 23:22:45.027+00 | 2022-11-28 17:09:17.44+00 |
| ImperialPlugins\.com | 284399832385191936 | unturned-help | 572969584127377419 | 73.423 | 73.414 | 0,62% | 1.629 | 1.629 | 618 | 8,60% | 1.904 | 2019-05-01 02:27:53.944+00 | 2025-01-07 02:54:48.516+00 |
| Kindred Games Community | 398282199788552193 | off-topic-n-stuff | 400191665119428608 | 71.944 | 71.941 | 0,61% | 740 | 740 | 116 | 1,82% | 1.737 | 2018-01-23 08:36:04.435+00 | 2025-01-04 18:13:57.977+00 |
| Kindred Games Community | 398282199788552193 | showcase | 399153251141812235 | 68.619 | 68.618 | 0,58% | 885 | 885 | 162 | 2,77% | 2.012 | 2018-01-06 10:56:42.089+00 | 2025-01-06 01:57:18.909+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | wolvenkit-support | 808086068023918603 | 60.503 | 60.450 | 0,51% | 1.806 | 1.806 | 932 | 18,33% | 1.245 | 2021-02-07 21:52:39.981+00 | 2025-01-07 01:07:28.833+00 |
| 💻 Ouckah Lair | 519640186167099402 | ╮general | 1092864102440906803 | 58.913 | 58.900 | 0,50% | 758 | 758 | 472 | 21,63% | 620 | 2023-04-08 19:41:28.033+00 | 2025-01-09 02:45:44.216+00 |
| TheScostumati | 516564332440584221 | 🙊vocal-chat | 765144707696689152 | 54.841 | 54.828 | 0,46% | 194 | 194 | 99 | 5,13% | 1.334 | 2020-10-12 09:33:42.827+00 | 2025-01-08 13:31:52.815+00 |
| Kindred Games Community | 398282199788552193 | game-dev-chat | 447512313378111509 | 52.335 | 52.329 | 0,44% | 803 | 803 | 167 | 3,97% | 1.663 | 2018-05-19 21:35:33.456+00 | 2025-01-06 19:38:50.09+00 |
| Touhou Game Dev | 933089313405685760 | voice-text | 933089316547219563 | 47.573 | 47.540 | 0,40% | 159 | 159 | 90 | 6,15% | 345 | 2022-04-18 15:43:58.837+00 | 2025-01-06 07:41:15.574+00 |
| OpenRCT2 | 264137540670324737 | development | 691735032531779684 | 46.938 | 46.916 | 0,39% | 679 | 666 | 304 | 9,50% | 1.450 | 2020-03-24 21:48:02.745+00 | 2025-01-10 03:41:48.977+00 |
| Kindred Games Community | 398282199788552193 | gaming | 508238138209075201 | 45.918 | 45.906 | 0,39% | 451 | 451 | 82 | 2,18% | 1.312 | 2018-11-03 11:17:32.801+00 | 2025-01-04 15:33:59.644+00 |
| Touhou Game Dev | 933089313405685760 | jam-games-discussion | 933089316035506243 | 45.458 | 45.446 | 0,38% | 274 | 274 | 213 | 12,79% | 424 | 2022-01-19 01:27:40.958+00 | 2025-01-04 21:13:42.707+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | lore-talk | 889600112492437594 | 45.223 | 45.209 | 0,38% | 887 | 887 | 517 | 14,17% | 924 | 2021-09-20 19:53:35.606+00 | 2025-01-07 00:07:53.058+00 |
| Kindred Games Community | 398282199788552193 | ideas | 398288504066670602 | 44.169 | 44.165 | 0,37% | 1.211 | 1.211 | 263 | 7,43% | 1.446 | 2018-01-04 01:50:57.564+00 | 2024-12-26 00:08:42.144+00 |
| ImperialPlugins\.com | 284399832385191936 | memes | 407952543835226137 | 43.828 | 43.809 | 0,37% | 398 | 397 | 111 | 2,72% | 1.706 | 2018-01-30 17:38:58.509+00 | 2025-01-04 11:43:51.215+00 |
| Rectify11 Community | 1077324213142175744 | rectify11-chat | 1077324214555656194 | 41.921 | 41.907 | 0,35% | 1.439 | 1.439 | 795 | 26,26% | 652 | 2023-02-28 23:54:16.225+00 | 2024-12-19 02:52:02.045+00 |
| WWebJS | 698610475432411196 | general | 698610475931271249 | 43.898 | 41.599 | 0,35% | 4.444 | 2.970 | 1.466 | 30,99% | 1.601 | 2020-04-11 19:36:54.376+00 | 2025-01-08 18:28:58.621+00 |
| Kavita | 821879810934439936 | lounge | 842537562363134003 | 41.323 | 41.321 | 0,35% | 237 | 237 | 149 | 7,36% | 824 | 2021-05-13 23:29:57.147+00 | 2024-12-22 03:21:02.652+00 |
| Docker | 460871933748183040 | discussion | 669474776393187328 | 41.318 | 41.318 | 0,35% | 2.105 | 2.105 | 821 | 22,52% | 1.505 | 2020-01-22 09:40:17.654+00 | 2025-01-08 22:11:01.096+00 |
| Kavita | 821879810934439936 | general | 821879810934439939 | 40.817 | 40.432 | 0,34% | 1.114 | 919 | 410 | 9,52% | 1.136 | 2021-03-20 16:22:40.316+00 | 2024-12-18 15:31:28.853+00 |
| OpenRCT2 | 264137540670324737 | open-graphics | 691752238057783356 | 38.362 | 38.355 | 0,32% | 308 | 308 | 158 | 13,25% | 859 | 2020-03-26 12:32:54.082+00 | 2025-01-10 18:42:04.229+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | cet-lua-scripting | 795037494106128434 | 38.166 | 38.139 | 0,32% | 886 | 886 | 402 | 16,07% | 1.238 | 2021-01-02 21:22:09.313+00 | 2025-01-07 00:30:00.977+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | redscript-scripting | 804399334246187038 | 36.015 | 35.992 | 0,30% | 566 | 566 | 306 | 18,70% | 1.007 | 2021-01-28 17:17:45.421+00 | 2025-01-06 22:45:26.096+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | archived-cet-scripting | 794613856948322344 | 34.663 | 34.652 | 0,29% | 127 | 127 | 72 | 6,01% | 347 | 2021-01-01 17:14:52.845+00 | 2023-08-28 10:44:50.706+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | texture-modding | 717721370519142573 | 32.463 | 32.430 | 0,27% | 711 | 711 | 287 | 8,79% | 418 | 2020-12-10 03:12:40.693+00 | 2022-06-20 07:33:34.612+00 |
| WWebJS | 698610475432411196 | help-archive | 698612530985173002 | 32.234 | 32.232 | 0,27% | 1.106 | 1.106 | 554 | 24,48% | 862 | 2020-04-12 05:29:10.868+00 | 2022-09-25 21:49:26.929+00 |
| OpenVic - Community | 1062018115275325480 | 📚history | 1084770470685052938 | 31.930 | 31.929 | 0,27% | 204 | 204 | 156 | 19,06% | 344 | 2023-03-13 09:35:35.264+00 | 2025-01-09 04:21:46.102+00 |
| Kindred Games Community | 398282199788552193 | bots | 632280302781464595 | 31.780 | 31.776 | 0,27% | 1.363 | 1.363 | 21 | 0,22% | 1.187 | 2019-10-11 18:16:50.39+00 | 2024-12-18 04:56:27.955+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | animations | 813768799358156880 | 31.623 | 31.583 | 0,27% | 342 | 342 | 222 | 17,78% | 841 | 2021-02-23 13:46:51.326+00 | 2025-01-05 15:58:44.335+00 |
| Tech Haven | 455345206481518593 | political | 736661899936137246 | 29.292 | 29.291 | 0,25% | 141 | 141 | 77 | 10,98% | 1.145 | 2020-07-25 19:13:54.076+00 | 2024-12-18 03:28:05.391+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | cyanidex-mods | 1198976262765564018 | 28.161 | 28.151 | 0,24% | 310 | 310 | 223 | 17,13% | 333 | 2024-01-22 18:54:34.309+00 | 2025-01-07 02:00:21.446+00 |
| OpenVic - Community | 1062018115275325480 | 🤣memes | 1062140718791004301 | 28.013 | 28.009 | 0,24% | 685 | 685 | 428 | 28,64% | 734 | 2023-01-09 22:48:53.44+00 | 2025-01-11 04:53:01.239+00 |
| MonoGame Discord | 355231098122272778 | showcase-discussion | 502292592789028874 | 27.908 | 27.908 | 0,23% | 304 | 304 | 98 | 3,32% | 769 | 2018-10-18 01:46:56.357+00 | 2022-01-04 18:31:02.938+00 |
| OpenRCT2 | 264137540670324737 | off-topic | 736534008296505344 | 27.600 | 27.599 | 0,23% | 604 | 604 | 273 | 9,25% | 1.253 | 2020-07-25 10:44:13.635+00 | 2025-01-11 05:05:01.437+00 |
| TheScostumati | 516564332440584221 | 💥game-news | 537315904908820490 | 27.302 | 27.296 | 0,23% | 146 | 146 | 85 | 4,83% | 1.480 | 2019-01-22 17:25:06.815+00 | 2025-01-08 20:16:27.496+00 |
| Touhou Game Dev | 933089313405685760 | dev-touhou | 933089315297312880 | 26.985 | 26.972 | 0,23% | 236 | 235 | 156 | 11,33% | 799 | 2022-01-18 20:55:40.001+00 | 2025-01-07 02:58:58.35+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | save-editing | 789565732726767636 | 26.491 | 26.459 | 0,22% | 1.613 | 1.613 | 674 | 13,20% | 713 | 2020-12-18 19:03:37.414+00 | 2025-01-06 23:02:51.396+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | red4ext-support | 1015378649547026462 | 25.557 | 25.552 | 0,21% | 2.634 | 2.633 | 1.118 | 21,69% | 670 | 2022-09-02 21:52:20.349+00 | 2025-01-07 00:39:20.175+00 |
| ImperialPlugins\.com | 284399832385191936 | waywo | 636284605166649344 | 25.419 | 25.414 | 0,21% | 226 | 226 | 132 | 9,32% | 966 | 2019-10-22 19:39:20.354+00 | 2025-01-06 20:44:31.375+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | redscript-support | 867329707787550751 | 25.137 | 25.132 | 0,21% | 2.093 | 2.092 | 872 | 19,76% | 945 | 2021-07-21 12:25:29.479+00 | 2025-01-06 22:46:45.202+00 |
| OpenRCT2 | 264137540670324737 | help | 875468371884380210 | 24.889 | 24.885 | 0,21% | 1.375 | 1.375 | 594 | 13,26% | 1.122 | 2021-08-12 20:01:17.844+00 | 2025-01-11 02:11:41.489+00 |
| Terasology | 270264625419911192 | destination-sol | 389093174921920512 | 24.810 | 24.798 | 0,21% | 152 | 152 | 30 | 4,17% | 971 | 2017-12-09 16:37:27.547+00 | 2025-01-07 01:21:44.571+00 |
| Tech Haven | 455345206481518593 | general-it-chat | 594961464603705365 | 23.752 | 23.752 | 0,20% | 803 | 803 | 190 | 8,30% | 1.089 | 2019-07-02 03:21:56.513+00 | 2024-12-10 19:57:30.971+00 |
| Kindred Games Community | 398282199788552193 | game-jams | 508238341058199562 | 23.447 | 23.423 | 0,20% | 544 | 544 | 120 | 4,09% | 595 | 2018-11-03 11:18:52.12+00 | 2025-01-05 00:36:44.039+00 |
| Tech Haven | 455345206481518593 | memes | 589611193665191936 | 21.943 | 21.943 | 0,18% | 298 | 298 | 109 | 12,88% | 1.870 | 2019-06-16 00:36:16.581+00 | 2024-12-21 23:42:36.655+00 |
| Touhou Game Dev | 933089313405685760 | art | 933089315737731114 | 20.766 | 20.727 | 0,17% | 317 | 317 | 168 | 12,99% | 1.067 | 2022-01-18 20:50:30.034+00 | 2025-01-07 05:21:32.236+00 |
| Sapphire - Imagine a framework | 737141877803057244 | old-gaming-den | 878754511483723826 | 20.329 | 20.328 | 0,17% | 67 | 67 | 47 | 12,05% | 440 | 2021-08-21 21:39:14.039+00 | 2022-12-05 17:21:16.826+00 |
| Kindred Games Community | 398282199788552193 | food | 564536484942708736 | 19.993 | 19.993 | 0,17% | 331 | 331 | 53 | 2,53% | 881 | 2019-04-07 19:54:48.135+00 | 2025-01-06 14:42:39.172+00 |
| Rectify11 Community | 1077324213142175744 | desktops-and-setups | 1077324214555656199 | 19.928 | 19.928 | 0,17% | 637 | 637 | 464 | 32,03% | 639 | 2023-03-01 00:28:38.896+00 | 2024-12-19 00:34:55.798+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | audio | 789391457282031616 | 19.487 | 19.450 | 0,16% | 741 | 740 | 353 | 14,48% | 846 | 2020-12-18 07:23:14.979+00 | 2025-01-06 19:12:07.653+00 |
| MonoGame Discord | 355231098122272778 | libraries-discussion | 424621790363648021 | 18.590 | 18.588 | 0,16% | 487 | 487 | 196 | 10,93% | 976 | 2018-03-17 17:36:04.025+00 | 2024-12-24 11:54:27.319+00 |
| Kavita | 821879810934439936 | nightly-testing | 851515194185744464 | 18.475 | 18.473 | 0,16% | 123 | 123 | 78 | 6,93% | 720 | 2021-09-08 19:19:19.596+00 | 2024-12-17 14:03:03.701+00 |
| OpenRCT2 | 264137540670324737 | plugin | 696130778618396683 | 18.107 | 18.105 | 0,15% | 325 | 325 | 145 | 11,16% | 926 | 2020-04-16 00:59:52.096+00 | 2025-01-10 20:11:00.829+00 |
| Kindred Games Community | 398282199788552193 | fan-content | 650215395890036746 | 17.904 | 17.889 | 0,15% | 429 | 429 | 80 | 3,29% | 607 | 2019-11-30 06:04:38.206+00 | 2024-11-15 18:28:57.503+00 |
| Tech Haven | 455345206481518593 | nsfw | 638477563324268553 | 17.417 | 17.416 | 0,15% | 174 | 174 | 77 | 15,42% | 1.338 | 2019-10-30 01:15:47.994+00 | 2024-12-19 02:10:51.901+00 |
| OpenRCT2 | 264137540670324737 | additional-content | 992015068197814272 | 17.241 | 17.238 | 0,15% | 196 | 196 | 141 | 23,65% | 335 | 2022-06-30 10:36:35.034+00 | 2025-01-11 03:48:15.104+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | quests-and-scenes | 803201431657250857 | 17.102 | 17.024 | 0,14% | 213 | 213 | 132 | 15,32% | 503 | 2021-01-25 09:57:53.899+00 | 2025-01-07 01:48:16.636+00 |
| Docker | 460871933748183040 | reverse-proxy | 478468481386545171 | 16.998 | 16.997 | 0,14% | 466 | 466 | 217 | 16,61% | 786 | 2018-10-04 13:13:31.95+00 | 2025-01-08 23:51:18.67+00 |
| Docker | 460871933748183040 | kubernetes | 478470860806815745 | 16.805 | 16.805 | 0,14% | 607 | 607 | 259 | 24,33% | 939 | 2018-08-29 22:27:58.915+00 | 2025-01-09 00:18:49.45+00 |
| Sapphire - Imagine a framework | 737141877803057244 | framework-development | 737142774738190377 | 16.655 | 16.652 | 0,14% | 184 | 184 | 96 | 6,40% | 530 | 2020-07-27 23:22:36.998+00 | 2024-12-29 15:37:33.364+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | tweakdb-modding | 953004282142163014 | 16.316 | 16.310 | 0,14% | 423 | 423 | 236 | 15,54% | 546 | 2022-03-14 18:59:37.163+00 | 2025-01-06 03:32:29.94+00 |
| GameDevSG | 558680594498977792 | ♦👥main-hangout-chat♦ | 558680594498977795 | 16.416 | 16.172 | 0,14% | 716 | 556 | 180 | 6,17% | 996 | 2019-04-07 07:29:16.051+00 | 2024-12-19 05:09:12.633+00 |
| Touhou Game Dev | 933089313405685760 | jam-wip-sharing | 933089316035506245 | 16.051 | 16.023 | 0,13% | 249 | 249 | 160 | 11,98% | 234 | 2022-04-14 19:46:02.218+00 | 2024-11-05 11:19:42.6+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | blender-add-on | 1033120509216444550 | 15.863 | 15.847 | 0,13% | 350 | 350 | 222 | 18,99% | 519 | 2022-10-21 20:52:44.895+00 | 2025-01-06 21:36:38.796+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | red4ext-cpp | 839400251680227339 | 15.807 | 15.800 | 0,13% | 137 | 137 | 86 | 13,84% | 557 | 2021-05-05 12:52:09.223+00 | 2025-01-07 00:50:52.137+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | world-editing | 814064062815141909 | 15.637 | 15.599 | 0,13% | 197 | 197 | 134 | 21,77% | 431 | 2021-02-24 09:22:00.59+00 | 2025-01-07 00:10:38.193+00 |
| Terasology | 270264625419911192 | off-topic | 503491338465968138 | 15.132 | 15.131 | 0,13% | 182 | 182 | 44 | 4,35% | 1.155 | 2018-10-26 14:24:31.654+00 | 2025-01-01 05:26:12.786+00 |
| Touhou Game Dev | 933089313405685760 | technology | 933089316547219560 | 15.035 | 15.032 | 0,13% | 117 | 117 | 73 | 10,26% | 621 | 2022-01-18 20:34:31.428+00 | 2025-01-07 04:50:11.07+00 |
| Docker | 460871933748183040 | docker-desktop | 502736293810274305 | 15.000 | 15.000 | 0,13% | 927 | 927 | 367 | 22,71% | 965 | 2018-10-19 07:33:53.19+00 | 2025-01-09 02:15:34.443+00 |
| MonoGame Discord | 355231098122272778 | showcase | 402545804776046592 | 14.170 | 14.169 | 0,12% | 678 | 678 | 10 | 0,18% | 2.035 | 2018-01-26 05:29:52.946+00 | 2024-12-25 02:35:41.416+00 |
| Touhou Game Dev | 933089313405685760 | general-advice | 933089315737731118 | 14.071 | 14.068 | 0,12% | 149 | 149 | 93 | 11,36% | 352 | 2022-01-18 20:56:52.962+00 | 2025-01-07 03:52:03.354+00 |
| Sapphire - Imagine a framework | 737141877803057244 | old-technology-den | 914235414041202758 | 13.970 | 13.970 | 0,12% | 59 | 59 | 42 | 13,55% | 288 | 2021-11-27 19:25:17.633+00 | 2022-12-05 17:41:29.865+00 |
| Kindred Games Community | 398282199788552193 | bug-support | 941584884403675177 | 13.908 | 13.904 | 0,12% | 570 | 570 | 284 | 20,49% | 623 | 2022-02-11 06:47:49.866+00 | 2025-01-06 13:36:25.704+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | vortex-extension-support | 946698855976681473 | 13.748 | 13.733 | 0,12% | 849 | 849 | 354 | 19,29% | 748 | 2022-02-25 09:58:33.433+00 | 2025-01-07 01:28:16.126+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | pc-tech-talk | 1244690869756498020 | 13.603 | 13.597 | 0,11% | 330 | 330 | 202 | 19,73% | 177 | 2024-05-27 16:40:07.608+00 | 2025-01-07 02:22:06.002+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | psiberstuff | 1171003964200853594 | 13.311 | 13.305 | 0,11% | 88 | 88 | 80 | 21,06% | 327 | 2023-11-06 08:50:59.919+00 | 2025-01-07 01:52:10.94+00 |
| Touhou Game Dev | 933089313405685760 | unity | 933089315737731119 | 13.301 | 13.295 | 0,11% | 104 | 104 | 62 | 10,77% | 460 | 2022-01-18 20:49:37.066+00 | 2025-01-06 21:33:00.429+00 |
| Sapphire - Imagine a framework | 737141877803057244 | utilities-development | 759750007087431721 | 13.177 | 13.175 | 0,11% | 100 | 100 | 52 | 8,02% | 444 | 2020-09-27 12:15:20.297+00 | 2024-12-18 15:06:44.864+00 |
| TheScostumati | 516564332440584221 | 🍕master-chef | 712650717789421648 | 12.504 | 12.495 | 0,11% | 124 | 124 | 74 | 9,10% | 853 | 2020-05-20 13:02:21.631+00 | 2025-01-02 00:56:38.376+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | scripting | 717721316186390528 | 12.388 | 12.382 | 0,10% | 110 | 110 | 53 | 3,21% | 45 | 2020-12-10 11:09:03.292+00 | 2021-04-15 14:17:45.941+00 |
| Terasology | 270264625419911192 | logistics | 633681387995660303 | 11.637 | 11.625 | 0,10% | 39 | 39 | 20 | 6,34% | 675 | 2019-10-15 15:44:07.905+00 | 2024-12-30 04:51:37.942+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | archive-xl | 955663052903178270 | 11.631 | 11.610 | 0,10% | 369 | 369 | 198 | 17,63% | 514 | 2022-03-22 03:04:31.506+00 | 2025-01-06 21:54:48.276+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | mod-troubleshooting | 788213273530335233 | 11.376 | 11.373 | 0,10% | 754 | 754 | 411 | 34,41% | 16 | 2024-12-23 17:20:15.492+00 | 2025-01-07 00:44:18.578+00 |
| Terasology | 270264625419911192 | stabilization | 696830442065625118 | 11.297 | 11.273 | 0,09% | 38 | 38 | 17 | 7,94% | 482 | 2020-04-06 21:23:03.511+00 | 2024-11-17 15:32:29.291+00 |
| Tech Haven | 455345206481518593 | linux_unix-chat | 719555554321629186 | 11.243 | 11.243 | 0,09% | 358 | 358 | 132 | 10,26% | 612 | 2020-06-08 14:20:38.575+00 | 2024-10-19 09:20:40.87+00 |
| Touhou Game Dev | 933089313405685760 | dev-other | 933089315297312881 | 10.739 | 10.739 | 0,09% | 150 | 150 | 93 | 9,34% | 560 | 2022-01-18 21:10:55.327+00 | 2025-01-06 19:30:16.616+00 |
| Penusbmic's Server | 894976658229063731 | general-chat | 1132134739856334898 | 10.507 | 10.502 | 0,09% | 375 | 375 | 200 | 22,86% | 451 | 2023-07-22 02:19:51.736+00 | 2025-01-05 19:13:55.485+00 |
| Sapphire - Imagine a framework | 737141877803057244 | mature-chat | 792132881903386664 | 10.453 | 10.451 | 0,09% | 123 | 123 | 77 | 17,37% | 662 | 2020-12-25 20:53:20.79+00 | 2024-12-20 11:24:05.289+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | reverse-engineering | 786134713227935785 | 10.365 | 10.353 | 0,09% | 96 | 96 | 54 | 3,72% | 96 | 2020-12-09 07:39:37.632+00 | 2023-02-25 15:41:33.093+00 |
| Tech Haven | 455345206481518593 | programming-chat | 594961505380991039 | 9.984 | 9.984 | 0,08% | 406 | 406 | 108 | 7,98% | 717 | 2019-08-01 02:41:15.661+00 | 2024-12-11 17:21:51.44+00 |
| Sapphire - Imagine a framework | 737141877803057244 | old-application-commands-and-interactions | 889973175583133717 | 9.948 | 9.941 | 0,08% | 251 | 251 | 142 | 15,31% | 304 | 2021-09-21 20:41:09.651+00 | 2022-11-21 08:13:34.593+00 |
| Tech Haven | 455345206481518593 | cybersecurity-chat | 594961554701680640 | 9.675 | 9.675 | 0,08% | 500 | 500 | 140 | 10,69% | 722 | 2019-07-02 11:49:57.849+00 | 2024-11-27 12:44:51.223+00 |
| Sapphire - Imagine a framework | 737141877803057244 | plugins-development | 737142940777971773 | 9.413 | 9.412 | 0,08% | 92 | 92 | 52 | 7,72% | 334 | 2020-07-27 23:22:44.192+00 | 2024-11-05 21:33:05.905+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | cet-commands | 1157727395076391043 | 8.730 | 8.725 | 0,07% | 1.622 | 1.622 | 563 | 26,57% | 406 | 2023-09-30 17:17:43.08+00 | 2025-01-06 19:24:01.773+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | djkovrik-mods | 858635881275195401 | 8.627 | 8.624 | 0,07% | 534 | 534 | 244 | 16,49% | 628 | 2021-06-27 18:02:25.919+00 | 2025-01-06 21:28:22.813+00 |
| OpenRCT2 | 264137540670324737 | open-sound-and-music | 694586451500859469 | 8.611 | 8.610 | 0,07% | 198 | 198 | 117 | 10,59% | 581 | 2020-03-31 16:39:08.673+00 | 2025-01-11 03:40:28.068+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | redengine-research | 786902567778910229 | 8.492 | 8.482 | 0,07% | 283 | 282 | 119 | 6,59% | 190 | 2020-12-11 10:56:14.666+00 | 2024-12-02 21:40:14.362+00 |
| Neo4j | 787399249741479977 | cypher | 818578585194594334 | 8.477 | 8.476 | 0,07% | 751 | 751 | 312 | 24,49% | 944 | 2021-03-11 10:13:55.464+00 | 2024-12-24 10:29:41.533+00 |
| MonoGame Discord | 355231098122272778 | non-programming | 490325877117157392 | 8.346 | 8.345 | 0,07% | 247 | 247 | 93 | 6,04% | 475 | 2018-09-15 22:26:13.642+00 | 2024-12-24 11:57:35.956+00 |
| Tech Haven | 455345206481518593 | networking-chat | 594961585206722560 | 7.982 | 7.982 | 0,07% | 250 | 250 | 84 | 8,56% | 452 | 2019-07-10 14:03:07.296+00 | 2024-11-13 23:21:24.265+00 |
| MonoGame Discord | 355231098122272778 | gaming | 484428606542577674 | 7.842 | 7.842 | 0,07% | 163 | 163 | 59 | 5,88% | 468 | 2018-08-31 13:22:11.141+00 | 2024-11-07 12:33:51.613+00 |
| Touhou Game Dev | 933089313405685760 | touhou-spoilers | 1136052830260707458 | 7.640 | 7.635 | 0,06% | 52 | 52 | 42 | 11,28% | 24 | 2023-08-01 21:48:43.215+00 | 2023-08-31 03:05:26.72+00 |
| Touhou Game Dev | 933089313405685760 | anime-manga | 933089316547219557 | 7.507 | 7.506 | 0,06% | 85 | 85 | 60 | 12,64% | 357 | 2022-01-18 20:33:37.405+00 | 2025-01-05 09:24:54.807+00 |
| Docker | 460871933748183040 | offtopic | 532556917432647685 | 7.412 | 7.410 | 0,06% | 444 | 444 | 146 | 21,13% | 675 | 2019-01-09 13:52:51.543+00 | 2025-01-07 16:06:08.035+00 |
| WWebJS | 698610475432411196 | off-topic | 698622612523188285 | 7.391 | 7.390 | 0,06% | 255 | 255 | 141 | 24,84% | 543 | 2020-06-05 19:17:35.764+00 | 2024-12-25 00:45:26.217+00 |
| OpenRCT2 | 264137540670324737 | open-scenarios | 1093263778814116022 | 7.212 | 7.211 | 0,06% | 105 | 105 | 76 | 15,02% | 223 | 2023-04-05 20:05:06.844+00 | 2025-01-10 22:02:24.383+00 |
| Terasology | 270264625419911192 | web-stuff | 559240070062800906 | 7.204 | 7.198 | 0,06% | 44 | 44 | 13 | 8,02% | 360 | 2019-03-24 05:00:35.021+00 | 2024-05-15 19:50:31.358+00 |
| Sapphire - Imagine a framework | 737141877803057244 | old-discordjs-support | 750799332445519884 | 7.060 | 7.060 | 0,06% | 222 | 222 | 121 | 13,70% | 347 | 2020-10-21 19:23:49.55+00 | 2022-11-26 18:23:52.951+00 |
| Touhou Game Dev | 933089313405685760 | cirno-mc-chat | 1163908653091397662 | 6.965 | 6.949 | 0,06% | 34 | 34 | 23 | 5,07% | 203 | 2023-10-17 18:41:50.536+00 | 2025-01-06 12:49:41.24+00 |
| GameDevSG | 558680594498977792 | 🎨art-and-vfx | 676484825628278846 | 6.693 | 6.693 | 0,06% | 281 | 281 | 117 | 12,89% | 761 | 2020-02-10 17:52:15.893+00 | 2024-12-02 16:14:03.582+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | edgerunners | 1014540824882729000 | 6.480 | 6.479 | 0,05% | 270 | 270 | 147 | 16,02% | 106 | 2022-08-31 14:44:58.408+00 | 2023-01-28 11:07:37.797+00 |
| Touhou Game Dev | 933089313405685760 | gamemaker | 933089315737731120 | 6.448 | 6.445 | 0,05% | 71 | 71 | 47 | 7,39% | 228 | 2022-01-19 07:50:51.817+00 | 2024-12-29 17:08:47.95+00 |
| Touhou Game Dev | 933089313405685760 | godot | 933089316035506236 | 6.434 | 6.433 | 0,05% | 91 | 91 | 61 | 8,77% | 304 | 2022-01-19 01:46:25.067+00 | 2025-01-05 17:49:00.135+00 |
| Kavita | 821879810934439936 | komf | 1037456434822127717 | 6.092 | 6.076 | 0,05% | 156 | 156 | 98 | 12,11% | 367 | 2022-11-02 20:01:47.373+00 | 2024-12-20 21:52:25.036+00 |
| Return Community | 1080829289412432032 | 👑┇royal-chat | 1168556243024101516 | 5.979 | 5.976 | 0,05% | 99 | 99 | 59 | 33,17% | 345 | 2023-10-30 14:27:01.481+00 | 2024-12-28 15:31:55.309+00 |
| Neo4j | 787399249741479977 | graphql | 818578492723036210 | 5.936 | 5.926 | 0,05% | 376 | 376 | 192 | 27,89% | 787 | 2021-03-08 21:04:11.977+00 | 2024-12-20 17:27:06.949+00 |
| Sapphire - Imagine a framework | 737141877803057244 | website-development | 795723882556162058 | 5.917 | 5.911 | 0,05% | 68 | 68 | 42 | 8,68% | 228 | 2021-01-04 18:42:43.701+00 | 2024-11-16 02:03:29.762+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | mlsetup-builder | 1082772930892664943 | 5.639 | 5.630 | 0,05% | 126 | 126 | 71 | 21,10% | 268 | 2023-03-07 21:13:08.597+00 | 2025-01-05 18:43:35.922+00 |
| Penusbmic's Server | 894976658229063731 | itch-chat | 894976658229063737 | 5.539 | 5.451 | 0,05% | 306 | 288 | 145 | 21,72% | 498 | 2021-10-08 18:54:51.003+00 | 2024-12-31 15:47:09.6+00 |
| Rectify11 Community | 1077324213142175744 | shitpost-spam | 1077332778980479076 | 5.405 | 5.403 | 0,05% | 159 | 159 | 77 | 14,23% | 403 | 2023-02-28 23:12:19.123+00 | 2024-12-17 17:17:45.395+00 |
| TheScostumati | 516564332440584221 | 🎨wip-2d | 541985837265453066 | 5.359 | 5.359 | 0,05% | 120 | 120 | 42 | 3,97% | 541 | 2019-02-24 20:04:42.593+00 | 2024-05-01 15:38:06.185+00 |
| Terasology | 270264625419911192 | rendering | 591982628476026891 | 5.260 | 5.259 | 0,04% | 47 | 47 | 19 | 6,08% | 365 | 2019-06-22 13:35:28.773+00 | 2024-12-01 15:14:03.657+00 |
| Penusbmic's Server | 894976658229063731 | project-game-showcase | 917172543729844244 | 5.047 | 5.046 | 0,04% | 262 | 262 | 180 | 24,89% | 621 | 2021-12-09 19:44:43.682+00 | 2024-12-31 15:15:06.109+00 |
| Terasology | 270264625419911192 | math-n-physics | 701818347238588561 | 4.636 | 4.634 | 0,04% | 23 | 23 | 11 | 4,23% | 166 | 2020-04-20 15:37:05.732+00 | 2024-04-07 08:47:48.087+00 |
| Rectify11 Community | 1077324213142175744 | memes | 1077324214832476272 | 4.567 | 4.565 | 0,04% | 268 | 268 | 149 | 28,85% | 541 | 2023-02-28 23:42:14.143+00 | 2024-12-19 02:52:31.987+00 |
| Tech Haven | 455345206481518593 | windows-chat | 719555492757897276 | 4.539 | 4.539 | 0,04% | 155 | 155 | 60 | 9,74% | 294 | 2020-06-10 09:27:56.093+00 | 2024-10-28 05:16:08.247+00 |
| Touhou Game Dev | 933089313405685760 | jam-voice-text | 1068126758253117517 | 4.435 | 4.428 | 0,04% | 92 | 92 | 50 | 7,02% | 44 | 2023-01-26 11:30:09.685+00 | 2024-10-31 05:32:54.301+00 |
| Fermyon | 926888690310053918 | spin | 950022897160839248 | 4.389 | 4.389 | 0,04% | 303 | 303 | 147 | 19,30% | 670 | 2022-03-07 19:27:38.541+00 | 2025-01-06 22:01:51.93+00 |
| TheScostumati | 516564332440584221 | 💭movies-comics | 669239879334363170 | 4.372 | 4.372 | 0,04% | 79 | 79 | 46 | 6,38% | 659 | 2020-01-21 18:10:43.997+00 | 2025-01-07 16:20:27.06+00 |
| Shardeum | 933959587462254612 | 🤣・memes | 938397846510653440 | 4.371 | 4.370 | 0,04% | 1.416 | 1.416 | 173 | 9,73% | 801 | 2022-02-02 15:32:43.988+00 | 2025-01-08 15:21:10.258+00 |
| Terasology | 270264625419911192 | ai | 552216356364222469 | 4.289 | 4.288 | 0,04% | 33 | 33 | 12 | 3,78% | 240 | 2019-03-04 19:53:01.727+00 | 2023-05-04 20:00:13.602+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | visual-modding | 789457082712981524 | 4.137 | 4.129 | 0,03% | 191 | 191 | 79 | 8,19% | 165 | 2020-12-18 11:41:03.459+00 | 2021-10-26 10:58:38.377+00 |
| Kindred Games Community | 398282199788552193 | community-streams | 405205466910818305 | 4.099 | 4.099 | 0,03% | 317 | 317 | 24 | 2,17% | 1.488 | 2018-01-23 11:54:26.198+00 | 2024-12-29 23:08:54.139+00 |
| Terasology | 270264625419911192 | ephermeral-discussions | 1125013678966710342 | 3.988 | 3.986 | 0,03% | 14 | 14 | 13 | 22,58% | 146 | 2023-07-02 13:46:47.848+00 | 2024-12-23 03:05:07.086+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | null-morb-land | 1172804635061395456 | 3.916 | 3.908 | 0,03% | 83 | 83 | 53 | 8,75% | 181 | 2023-11-11 07:47:35.796+00 | 2025-01-06 15:43:17.844+00 |
| Terasology | 270264625419911192 | play-terasology | 713903952764207164 | 3.905 | 3.904 | 0,03% | 201 | 201 | 68 | 13,11% | 322 | 2020-06-04 21:50:36.357+00 | 2024-12-27 04:03:02.318+00 |
| Tech Haven | 455345206481518593 | pc-builds | 870388964475953182 | 3.899 | 3.899 | 0,03% | 103 | 103 | 61 | 11,34% | 240 | 2021-07-29 19:44:49.493+00 | 2024-11-04 18:58:54.876+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | cet-chat | 795037478229901322 | 3.838 | 3.837 | 0,03% | 97 | 97 | 41 | 5,68% | 110 | 2021-01-02 21:16:23.966+00 | 2022-10-23 14:54:09.466+00 |
| Terasology | 270264625419911192 | biology | 577139912474886157 | 3.793 | 3.793 | 0,03% | 26 | 26 | 5 | 0,24% | 190 | 2019-05-12 14:28:08.754+00 | 2024-01-07 02:03:34.244+00 |
| Tech Haven | 455345206481518593 | failtesters-den | 947700068729905203 | 3.688 | 3.687 | 0,03% | 57 | 57 | 33 | 9,74% | 402 | 2022-02-28 04:07:42.758+00 | 2024-12-17 04:56:55.783+00 |
| Penusbmic's Server | 894976658229063731 | feedback-and-constructive-criticism | 1017958075283542057 | 3.640 | 3.637 | 0,03% | 187 | 186 | 120 | 29,91% | 350 | 2022-09-10 07:52:37.68+00 | 2025-01-06 18:00:25.479+00 |
| Touhou Game Dev | 933089313405685760 | jam-team-forming | 933089316035506241 | 3.578 | 3.576 | 0,03% | 312 | 312 | 152 | 21,22% | 301 | 2022-03-25 14:05:48.364+00 | 2024-10-31 05:53:06.181+00 |
| GameDevSG | 558680594498977792 | 👾game-design | 676615865675808808 | 3.408 | 3.408 | 0,03% | 147 | 147 | 56 | 4,96% | 286 | 2020-02-11 15:08:44.756+00 | 2024-12-04 02:47:35.342+00 |
| Terasology | 270264625419911192 | outreach | 714188700141224036 | 3.350 | 3.347 | 0,03% | 26 | 26 | 10 | 1,14% | 160 | 2020-05-25 14:58:28.271+00 | 2025-01-07 04:44:05.86+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | deceptious-mods | 1097844044022956032 | 3.353 | 3.347 | 0,03% | 240 | 240 | 121 | 24,83% | 338 | 2023-04-18 11:20:41.67+00 | 2025-01-06 12:24:09.733+00 |
| Sapphire - Imagine a framework | 737141877803057244 | voice-context | 750105399172137011 | 3.311 | 3.311 | 0,03% | 56 | 56 | 24 | 2,87% | 123 | 2020-08-31 21:31:30.237+00 | 2022-05-19 06:06:13.907+00 |
| GameDevSG | 558680594498977792 | 🧮programming-and-tech | 676484881508859905 | 3.231 | 3.229 | 0,03% | 118 | 118 | 44 | 5,45% | 258 | 2020-02-10 17:52:31.082+00 | 2024-11-28 17:17:05.551+00 |
| Terasology | 270264625419911192 | ui-ux | 703047991430217728 | 3.228 | 3.226 | 0,03% | 30 | 30 | 18 | 4,90% | 202 | 2020-04-24 01:06:05.11+00 | 2024-05-30 20:29:28.303+00 |
| CodingWallah | 1056895641676152852 | 🎀│general-chat | 1056895642628276256 | 3.186 | 3.185 | 0,03% | 388 | 388 | 108 | 16,30% | 194 | 2022-12-26 11:26:35.28+00 | 2024-12-14 08:43:09.528+00 |
| Terasology | 270264625419911192 | architecture | 577194115725262912 | 3.164 | 3.163 | 0,03% | 28 | 28 | 15 | 8,44% | 254 | 2019-05-12 18:09:36.109+00 | 2023-05-01 10:00:44.451+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | psiberx-mods | 1171107143076806767 | 3.118 | 3.118 | 0,03% | 242 | 242 | 134 | 22,48% | 265 | 2023-11-06 17:31:24.559+00 | 2025-01-07 02:16:45.795+00 |
| TheScostumati | 516564332440584221 | 🌀inspiration | 721321990207701052 | 3.058 | 3.056 | 0,03% | 96 | 96 | 36 | 3,44% | 760 | 2020-06-13 12:41:15.627+00 | 2025-01-07 15:11:10.349+00 |
| Terasology | 270264625419911192 | world-generation | 702893102481932308 | 3.030 | 3.030 | 0,03% | 31 | 31 | 19 | 8,78% | 244 | 2020-04-23 14:48:35.577+00 | 2024-05-22 01:34:09.89+00 |
| Penusbmic's Server | 894976658229063731 | general | 1059937532479029308 | 2.804 | 2.804 | 0,02% | 181 | 181 | 80 | 19,33% | 260 | 2023-01-03 20:54:16.074+00 | 2024-11-29 14:03:07.448+00 |
| Kavita | 821879810934439936 | melvor-idle | 1292838448104734751 | 2.802 | 2.800 | 0,02% | 10 | 10 | 9 | 3,57% | 62 | 2024-10-07 13:18:39.017+00 | 2024-12-21 17:51:44.916+00 |
| Montano Community | 561997286087852118 | 📚┃english-only | 704757495100342372 | 2.772 | 2.772 | 0,02% | 367 | 367 | 82 | 6,96% | 331 | 2020-04-28 18:17:10.218+00 | 2024-11-20 06:13:19.91+00 |
| Touhou Game Dev | 933089313405685760 | toho-station-jam | 1293617429821394954 | 2.767 | 2.760 | 0,02% | 63 | 62 | 52 | 20,58% | 13 | 2024-10-09 16:54:32.715+00 | 2024-10-23 01:13:51.95+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | blender-add-on-dev | 1141547129794478080 | 2.722 | 2.716 | 0,02% | 21 | 21 | 15 | 12,52% | 139 | 2023-08-17 02:07:20.997+00 | 2025-01-06 12:42:55.163+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | rmk-mods | 858646966019817482 | 2.699 | 2.696 | 0,02% | 157 | 157 | 77 | 17,32% | 295 | 2021-06-29 01:54:47.736+00 | 2025-01-05 15:29:04.22+00 |
| Terasology | 270264625419911192 | launcher | 591979528432386068 | 2.691 | 2.691 | 0,02% | 38 | 38 | 11 | 2,97% | 216 | 2019-06-22 13:36:23.788+00 | 2024-08-29 23:36:48.729+00 |
| Tech Haven | 455345206481518593 | servers-chat | 733027648841842739 | 2.681 | 2.681 | 0,02% | 100 | 100 | 45 | 7,91% | 178 | 2020-07-15 18:34:03.434+00 | 2024-12-16 02:35:19.772+00 |
| Terasology | 270264625419911192 | gestalt | 714313228271747152 | 2.670 | 2.669 | 0,02% | 20 | 20 | 13 | 8,80% | 171 | 2020-05-25 03:11:38.965+00 | 2024-12-24 21:57:49.982+00 |
| Kavita | 821879810934439936 | development | 1009566589663850536 | 2.609 | 2.609 | 0,02% | 66 | 66 | 31 | 8,39% | 206 | 2022-08-17 22:13:10.936+00 | 2024-12-21 17:49:50.93+00 |
| Return Community | 1080829289412432032 | 🗿┇meme | 1136203088601034764 | 2.440 | 2.440 | 0,02% | 384 | 384 | 149 | 28,52% | 397 | 2023-08-05 06:45:31.11+00 | 2024-12-28 14:53:25.77+00 |
| OpenRCT2 | 264137540670324737 | localisation | 691736823378083882 | 2.355 | 2.354 | 0,02% | 113 | 113 | 49 | 7,73% | 298 | 2020-04-04 19:25:52.929+00 | 2024-12-28 20:59:41.622+00 |
| Return Community | 1080829289412432032 | 📷┇medi̇a | 1160264181233225799 | 2.320 | 2.318 | 0,02% | 378 | 378 | 152 | 26,49% | 344 | 2023-10-07 17:15:42.057+00 | 2024-12-28 15:17:42.558+00 |
| MonoGame Discord | 355231098122272778 | suggestions | 355231151272624138 | 2.213 | 2.211 | 0,02% | 157 | 157 | 59 | 9,77% | 266 | 2017-09-17 19:06:02.754+00 | 2024-11-12 21:19:47.936+00 |
| Tech Haven | 455345206481518593 | electronics-chat | 594961729889370124 | 2.204 | 2.204 | 0,02% | 100 | 100 | 27 | 5,90% | 150 | 2019-10-03 14:00:48.255+00 | 2024-12-18 16:34:57.035+00 |
| GameDevSG | 558680594498977792 | 💗emotional-support | 1075785552290398359 | 2.192 | 2.192 | 0,02% | 107 | 107 | 68 | 23,27% | 262 | 2023-02-16 15:00:20.07+00 | 2024-12-19 16:46:26.402+00 |
| Oxylabs | 1128239127687598080 | ┠💬-general | 1128324284754968637 | 2.187 | 2.183 | 0,02% | 511 | 511 | 147 | 35,04% | 358 | 2023-09-15 09:02:22.631+00 | 2025-01-04 22:27:37.992+00 |
| Sapphire - Imagine a framework | 737141877803057244 | shapeshift-development-⚡ | 934614121687687179 | 2.137 | 2.137 | 0,02% | 32 | 32 | 21 | 9,97% | 118 | 2022-01-23 15:33:47.902+00 | 2024-10-01 11:32:13.037+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | tweakdb-editing | 826506889117302875 | 2.050 | 2.046 | 0,02% | 62 | 62 | 32 | 10,36% | 90 | 2021-04-01 01:55:57.065+00 | 2022-07-17 21:22:39.597+00 |
| L'Ordre des Devs | 706640777450881114 | cmd | 1045347041909420032 | 2.017 | 2.017 | 0,02% | 61 | 61 | 32 | 11,95% | 244 | 2022-11-26 00:09:49.568+00 | 2025-01-04 21:35:50.164+00 |
| Neo4j | 787399249741479977 | app-dev | 816630778505986058 | 1.981 | 1.981 | 0,02% | 366 | 366 | 145 | 29,78% | 550 | 2021-03-24 08:57:26.664+00 | 2024-12-24 16:07:50.037+00 |
| OpenVic - Community | 1062018115275325480 | 🏅discussion | 1094718769546416278 | 1.960 | 1.960 | 0,02% | 70 | 70 | 52 | 20,56% | 141 | 2023-04-09 20:40:58.149+00 | 2024-10-10 00:20:54.791+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | wolvenkit-scripts | 1036574451237662780 | 1.913 | 1.908 | 0,02% | 57 | 57 | 35 | 21,70% | 145 | 2022-10-31 09:38:00.745+00 | 2025-01-06 22:27:41.172+00 |
| Neo4j | 787399249741479977 | data-science | 816630747136786484 | 1.904 | 1.904 | 0,02% | 222 | 222 | 86 | 25,74% | 465 | 2021-03-17 15:13:14.976+00 | 2024-12-09 04:53:18.714+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | wolvenkit-github | 717721419529584723 | 1.873 | 1.871 | 0,02% | 39 | 39 | 28 | 15,55% | 333 | 2020-12-21 23:14:09.642+00 | 2024-12-11 14:49:08.449+00 |
| Terasology | 270264625419911192 | vc-general | 710527864872632421 | 1.836 | 1.836 | 0,02% | 53 | 53 | 24 | 9,91% | 218 | 2020-05-25 17:30:41.874+00 | 2024-08-18 19:08:04.12+00 |
| Andy’s Development | 857672921912836116 | suggestions | 857791068393308170 | 1.814 | 1.792 | 0,02% | 122 | 122 | 54 | 15,68% | 206 | 2021-06-25 01:15:46.636+00 | 2023-08-31 03:37:59.825+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | modding-showcases | 796493553924440084 | 1.779 | 1.779 | 0,01% | 259 | 259 | 105 | 18,04% | 354 | 2021-01-06 21:49:35.479+00 | 2022-09-17 07:48:52.528+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | merchants-of-death | 1206340528158019634 | 1.779 | 1.778 | 0,01% | 73 | 73 | 54 | 20,92% | 142 | 2024-02-11 20:50:49.152+00 | 2025-01-03 10:47:01.177+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | manually_archived_tweak-modding | 1016766213755523213 | 1.780 | 1.772 | 0,01% | 115 | 115 | 48 | 16,37% | 74 | 2022-09-06 17:46:06.135+00 | 2022-12-25 21:54:24.985+00 |
| Neo4j | 787399249741479977 | product | 816627121732059146 | 1.721 | 1.720 | 0,01% | 423 | 423 | 111 | 25,93% | 535 | 2021-03-29 08:00:11.754+00 | 2024-12-20 11:00:35.809+00 |
| Neo4j | 787399249741479977 | graph-academy | 816956538512998440 | 1.710 | 1.708 | 0,01% | 417 | 417 | 121 | 21,66% | 516 | 2021-03-04 09:00:53.812+00 | 2024-12-24 00:59:00.189+00 |
| Sapphire - Imagine a framework | 737141877803057244 | @plugin-subcommands Chat Input support | 934916302651412512 | 1.604 | 1.602 | 0,01% | 37 | 37 | 18 | 11,30% | 58 | 2022-01-23 23:01:38.52+00 | 2022-08-12 02:29:12.154+00 |
| Touhou Game Dev | 933089313405685760 | help-wanted | 933089315297312882 | 1.602 | 1.601 | 0,01% | 116 | 116 | 57 | 13,55% | 177 | 2022-01-18 22:30:08.808+00 | 2024-12-31 20:37:22.221+00 |
| GameDevSG | 558680594498977792 | 📝writing | 677487756464619530 | 1.601 | 1.599 | 0,01% | 71 | 71 | 35 | 8,51% | 202 | 2020-02-13 14:05:46.136+00 | 2024-10-01 20:08:33.933+00 |
| Neo4j | 787399249741479977 | apoc | 831067735499866152 | 1.569 | 1.569 | 0,01% | 238 | 238 | 85 | 28,30% | 396 | 2021-04-12 07:27:48.923+00 | 2024-12-19 14:14:10.724+00 |
| Terasology | 270264625419911192 | playtest | 698959573523890197 | 1.558 | 1.555 | 0,01% | 38 | 38 | 15 | 6,43% | 49 | 2020-04-12 18:16:23.389+00 | 2024-12-26 02:41:24.265+00 |
| Return Community | 1080829289412432032 | 🎨┇art | 1162389494515900446 | 1.532 | 1.532 | 0,01% | 131 | 131 | 86 | 34,33% | 256 | 2023-10-13 14:01:00.304+00 | 2024-12-28 17:00:44.496+00 |
| OpenVic - Community | 1062018115275325480 | 🧠showcase-discussion | 1097347652510826506 | 1.521 | 1.521 | 0,01% | 144 | 144 | 90 | 29,65% | 147 | 2023-04-17 02:32:51.765+00 | 2024-11-24 18:37:27.685+00 |
| Rectify11 Community | 1077324213142175744 | installer | 1163243209384808559 | 1.457 | 1.457 | 0,01% | 224 | 224 | 108 | 36,99% | 200 | 2023-10-16 05:57:43.039+00 | 2024-12-18 00:37:00.806+00 |
| Touhou Game Dev | 933089313405685760 | resources-and-talks | 933089315297312883 | 1.469 | 1.457 | 0,01% | 77 | 77 | 37 | 7,69% | 201 | 2022-02-08 04:55:10.643+00 | 2025-01-06 02:35:34.482+00 |
| Touhou Game Dev | 933089313405685760 | rpg-maker | 933089316035506237 | 1.454 | 1.454 | 0,01% | 57 | 57 | 30 | 6,26% | 83 | 2022-01-27 02:30:58.799+00 | 2024-12-23 22:39:36.21+00 |
| GameDevSG | 558680594498977792 | ⏳animation | 676484919303864343 | 1.425 | 1.425 | 0,01% | 121 | 121 | 35 | 6,18% | 247 | 2020-02-10 17:53:07.164+00 | 2024-10-31 09:12:38.807+00 |
| Rectify11 Community | 1077324213142175744 | theme | 1077324214832476275 | 1.392 | 1.390 | 0,01% | 96 | 96 | 65 | 31,01% | 144 | 2023-03-01 11:45:41.348+00 | 2024-12-05 21:29:03.983+00 |
| Terasology | 270264625419911192 | play-ark | 409116216322686976 | 1.385 | 1.383 | 0,01% | 19 | 19 | 5 | 1,16% | 117 | 2018-02-03 03:30:12.947+00 | 2022-08-27 04:30:15.597+00 |
| Terasology | 270264625419911192 | lost | 708801708545015809 | 1.369 | 1.368 | 0,01% | 18 | 18 | 4 | 0,73% | 59 | 2020-05-09 22:05:57.294+00 | 2021-12-10 09:13:13.982+00 |
| Sapphire - Imagine a framework | 737141877803057244 | pieces-development | 737142871622156369 | 1.358 | 1.357 | 0,01% | 36 | 36 | 17 | 5,75% | 84 | 2020-07-27 23:22:42.07+00 | 2024-07-24 20:52:27.032+00 |
| MonoGame Discord | 355231098122272778 | voice-general | 775019135121227797 | 1.338 | 1.338 | 0,01% | 73 | 73 | 17 | 2,99% | 60 | 2020-11-08 16:24:29.652+00 | 2024-11-15 07:32:00.816+00 |
| Touhou Game Dev | 933089313405685760 | films-and-games | 1311998626515390525 | 1.340 | 1.336 | 0,01% | 35 | 35 | 22 | 7,11% | 24 | 2024-11-29 10:15:16.24+00 | 2024-12-29 20:26:49.975+00 |
| CodingWallah | 1056895641676152852 | 😊chat-room | 1271778126275543040 | 1.329 | 1.329 | 0,01% | 138 | 138 | 54 | 18,74% | 88 | 2024-08-10 13:58:40.307+00 | 2024-12-15 15:49:33.655+00 |
| Rectify11 Community | 1077324213142175744 | startify | 1163242529471336539 | 1.322 | 1.319 | 0,01% | 97 | 97 | 68 | 32,22% | 131 | 2023-10-15 22:38:29.569+00 | 2024-12-18 00:54:25.924+00 |
| Neo4j | 787399249741479977 | 🌞banter | 788809846949412878 | 1.277 | 1.274 | 0,01% | 226 | 226 | 63 | 22,53% | 443 | 2021-03-09 09:07:19.707+00 | 2024-12-24 09:26:25+00 |
| OpenVic - Community | 1062018115275325480 | 🤖dev-diary-discussion | 1074055648687435796 | 1.232 | 1.232 | 0,01% | 125 | 125 | 71 | 24,27% | 109 | 2023-02-11 19:56:37.723+00 | 2025-01-10 06:49:23.379+00 |
| OpenVic - Community | 1062018115275325480 | 🏆submissions | 1094714102569517207 | 1.184 | 1.184 | 0,01% | 158 | 158 | 7 | 1,69% | 171 | 2023-04-09 20:37:45.581+00 | 2024-10-28 14:29:13.599+00 |
| Neo4j | 787399249741479977 | dev-ops | 854675261635428353 | 1.162 | 1.162 | 0,01% | 246 | 246 | 85 | 27,80% | 381 | 2021-06-16 16:18:30.832+00 | 2024-12-16 09:44:49.049+00 |
| Sapphire - Imagine a framework | 737141877803057244 | cli-development | 1249350647443361803 | 1.127 | 1.126 | 0,01% | 16 | 16 | 12 | 20,60% | 20 | 2024-06-09 13:13:32.907+00 | 2024-11-24 04:51:00.881+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | _server-competition-discussion | 1123223580675670026 | 1.119 | 1.105 | 0,01% | 16 | 16 | 13 | 13,39% | 27 | 2023-06-27 12:10:17.041+00 | 2023-08-08 11:09:12.097+00 |
| Rectify11 Community | 1077324213142175744 | your-art | 1095818717327282298 | 1.106 | 1.102 | 0,01% | 138 | 138 | 93 | 36,03% | 192 | 2023-04-12 21:14:47.656+00 | 2024-12-19 00:41:42.723+00 |
| Neo4j | 787399249741479977 | aura | 854674503668990032 | 1.094 | 1.093 | 0,01% | 221 | 221 | 80 | 25,25% | 386 | 2021-06-17 12:35:51.402+00 | 2024-12-21 13:33:26.117+00 |
| OpenVic - Community | 1062018115275325480 | submissions-general | 1093214935066095686 | 1.083 | 1.082 | 0,01% | 62 | 62 | 40 | 24,31% | 74 | 2023-04-05 16:54:15.091+00 | 2024-09-25 11:08:06.272+00 |
| OpenVic - Community | 1062018115275325480 | 🖥technical-discussion | 1105124380612247582 | 1.066 | 1.065 | 0,01% | 51 | 51 | 32 | 22,63% | 72 | 2023-05-08 13:33:24.215+00 | 2024-10-23 12:02:27.878+00 |
| TikTok Shop Developer Hub | 1204537856870191114 | general | 1204537856870191117 | 1.068 | 1.063 | 0,01% | 404 | 400 | 168 | 40,36% | 224 | 2024-02-06 21:27:58.8+00 | 2024-12-27 09:15:47.151+00 |
| Rectify11 Community | 1077324213142175744 | bootlegs | 1099322850147586099 | 1.061 | 1.059 | 0,01% | 83 | 83 | 46 | 26,35% | 130 | 2023-04-22 13:17:10.255+00 | 2024-12-15 06:37:19.482+00 |
| OpenVic - Community | 1062018115275325480 | openvic-discussion | 1288761356127961149 | 1.047 | 1.047 | 0,01% | 50 | 50 | 28 | 20,73% | 58 | 2024-09-26 09:07:50.716+00 | 2025-01-10 02:21:09.225+00 |
| TikTok Shop Developer Hub | 1204537856870191114 | general-discussions | 1209061602796634132 | 1.022 | 1.022 | 0,01% | 315 | 315 | 137 | 44,62% | 207 | 2024-02-28 17:41:54.202+00 | 2024-12-21 09:05:26.22+00 |
| Kavita | 821879810934439936 | media-suggest | 973964508374638672 | 1.021 | 1.021 | 0,01% | 61 | 61 | 31 | 11,26% | 127 | 2022-05-11 15:09:01.461+00 | 2024-12-22 01:42:55.946+00 |
| Fermyon | 926888690310053918 | general | 926888690310053921 | 1.058 | 1.003 | 0,01% | 199 | 171 | 61 | 23,93% | 284 | 2022-01-01 17:25:48.352+00 | 2025-01-08 10:18:49.792+00 |
| Neo4j | 787399249741479977 | graphrag | 1161686426476351530 | 997 | 997 | 0,01% | 131 | 131 | 66 | 28,99% | 213 | 2023-10-11 15:59:01.999+00 | 2024-12-23 09:09:18.669+00 |
| Return Community | 1080829289412432032 | 💼┇hiring | 1253401749235044393 | 938 | 937 | 0,01% | 242 | 242 | 46 | 13,45% | 183 | 2024-06-20 17:31:13.872+00 | 2024-12-28 15:26:40.952+00 |
| Touhou Game Dev | 933089313405685760 | 3d-works | 1231377195956572210 | 936 | 936 | 0,01% | 34 | 34 | 20 | 8,01% | 54 | 2024-04-20 22:53:36.275+00 | 2024-12-24 12:55:09.946+00 |
| Kavita | 821879810934439936 | share-your-own | 933858494560481360 | 933 | 912 | 0,01% | 98 | 98 | 50 | 16,45% | 159 | 2022-01-23 15:16:34.81+00 | 2024-12-12 22:58:33.847+00 |
| Kavita | 821879810934439936 | show-off-your-server | 936974355777327114 | 885 | 885 | 0,01% | 102 | 102 | 49 | 13,67% | 144 | 2022-01-29 16:47:07.971+00 | 2024-12-15 00:32:38.963+00 |
| ImperialPlugins\.com | 284399832385191936 | rust-support | 741451835193163867 | 874 | 873 | 0,01% | 64 | 64 | 26 | 13,52% | 129 | 2020-11-16 15:17:44.97+00 | 2024-03-16 17:21:18.166+00 |
| 💻 Ouckah Lair | 519640186167099402 | 》code | 1092906566379896982 | 843 | 843 | 0,01% | 61 | 61 | 30 | 19,22% | 74 | 2023-04-05 23:06:31.702+00 | 2024-09-07 18:05:35.159+00 |
| OpenVic - Community | 1062018115275325480 | 💻tech-support | 1104094378550632538 | 824 | 824 | 0,01% | 52 | 52 | 33 | 18,93% | 61 | 2023-05-05 17:35:44.178+00 | 2025-01-05 15:20:37.804+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | krat0es-mods | 984010932013371393 | 822 | 820 | 0,01% | 79 | 79 | 35 | 15,12% | 114 | 2022-06-08 08:29:48.621+00 | 2025-01-07 01:31:47.263+00 |
| Terasology | 270264625419911192 | game-lobby | 411879557247795201 | 811 | 810 | 0,01% | 38 | 38 | 0 | 0,00% | 78 | 2018-02-12 09:04:26.328+00 | 2021-12-19 15:09:00.88+00 |
| Neo4j | 787399249741479977 | visualization | 859317168851779604 | 806 | 805 | 0,01% | 156 | 156 | 49 | 25,84% | 300 | 2021-06-30 10:13:44.337+00 | 2024-11-29 13:26:08.795+00 |
| MonoGame Discord | 355231098122272778 | hobby | 487351382987243541 | 803 | 803 | 0,01% | 103 | 103 | 31 | 10,09% | 121 | 2018-09-06 20:28:40.666+00 | 2024-12-11 14:42:41.095+00 |
| Neo4j | 787399249741479977 | data-models | 872013648707588136 | 801 | 801 | 0,01% | 206 | 206 | 58 | 22,85% | 289 | 2021-08-03 07:16:29.941+00 | 2024-12-16 11:06:44.284+00 |
| Terasology | 270264625419911192 | artwork | 736668510582734940 | 795 | 795 | 0,01% | 27 | 27 | 12 | 2,89% | 83 | 2020-07-25 19:39:42.388+00 | 2024-04-07 16:10:32.491+00 |
| Penusbmic's Server | 894976658229063731 | creative-ideas | 1060558407024775188 | 765 | 765 | 0,01% | 52 | 52 | 16 | 20,26% | 133 | 2023-01-07 15:56:25.494+00 | 2024-08-14 13:43:29.776+00 |
| Neo4j | 787399249741479977 | error | 930032449679925278 | 758 | 758 | 0,01% | 265 | 265 | 42 | 15,17% | 310 | 2022-01-19 20:50:26.459+00 | 2024-12-21 20:36:12.185+00 |
| 💻 Ouckah Lair | 519640186167099402 | 》questions | 1093313287824879647 | 744 | 744 | 0,01% | 111 | 111 | 41 | 17,74% | 98 | 2023-04-23 05:44:01.317+00 | 2024-12-17 15:43:55.304+00 |
| Touhou Game Dev | 933089313405685760 | showcase-committee | 1301095373628248074 | 744 | 741 | 0,01% | 29 | 29 | 17 | 13,90% | 10 | 2024-10-30 08:08:35.822+00 | 2025-01-02 11:00:49.965+00 |
| Penusbmic's Server | 894976658229063731 | highscores | 1090600226110324756 | 726 | 726 | 0,01% | 38 | 38 | 19 | 15,70% | 76 | 2023-05-06 10:07:43.809+00 | 2024-12-23 22:28:33.588+00 |
| Touhou Game Dev | 933089313405685760 | music-links | 1287449658364268676 | 702 | 700 | 0,01% | 48 | 47 | 19 | 8,29% | 96 | 2024-09-22 16:25:44.752+00 | 2025-01-06 23:47:39.59+00 |
| Terasology | 270264625419911192 | play-valheim | 811692749292175380 | 698 | 697 | 0,01% | 13 | 13 | 7 | 5,31% | 68 | 2021-02-17 20:20:24.885+00 | 2023-09-25 05:00:18.016+00 |
| Terasology | 270264625419911192 | play-dest-sol | 713904031562727445 | 679 | 679 | 0,01% | 36 | 36 | 15 | 18,85% | 84 | 2020-08-17 13:58:06.622+00 | 2024-12-30 13:08:10.03+00 |
| GameDevSG | 558680594498977792 | 🎙audio | 676737759674630144 | 668 | 668 | 0,01% | 72 | 72 | 23 | 10,78% | 206 | 2020-02-11 15:27:35.332+00 | 2024-12-14 17:31:23.01+00 |
| Sapphire - Imagine a framework | 737141877803057244 | sapphire-esm-only | 1012413247011422409 | 650 | 649 | 0,01% | 92 | 92 | 40 | 28,97% | 5 | 2022-08-25 17:29:36.595+00 | 2022-08-29 08:58:34.376+00 |
| MonoGame Discord | 355231098122272778 | commercial | 453768164476715010 | 645 | 645 | 0,01% | 100 | 100 | 23 | 8,84% | 94 | 2018-06-28 11:39:26.977+00 | 2024-09-21 11:08:21.819+00 |
| Touhou Game Dev | 933089313405685760 | shame | 1224130852469084221 | 624 | 624 | 0,01% | 57 | 57 | 0 | 0,00% | 3 | 2024-03-31 23:00:03.19+00 | 2024-07-13 19:43:04.974+00 |
| Touhou Game Dev | 933089313405685760 | jam-submission-help | 1193629430166339624 | 606 | 604 | 0,01% | 58 | 58 | 25 | 10,26% | 17 | 2024-01-07 18:58:04.403+00 | 2024-11-05 20:20:26.972+00 |
| Touhou Game Dev | 933089313405685760 | renpy | 933089316035506238 | 598 | 598 | 0,01% | 28 | 28 | 15 | 7,53% | 38 | 2022-02-27 09:09:04.073+00 | 2024-12-28 03:55:34.638+00 |
| Terasology | 270264625419911192 | performance | 882575244215341097 | 594 | 594 | 0,00% | 18 | 18 | 12 | 23,74% | 45 | 2021-09-01 10:43:06.517+00 | 2024-07-14 17:39:57.171+00 |
| Neo4j | 787399249741479977 | 💌suggestions | 819928762107822100 | 591 | 584 | 0,00% | 153 | 153 | 41 | 26,20% | 228 | 2021-03-12 14:10:10.914+00 | 2024-12-23 17:04:31.009+00 |
| Sapphire - Imagine a framework | 737141877803057244 | sapphire-v4-only-djs-v14-or-more | 1021836029520515152 | 583 | 582 | 0,00% | 40 | 40 | 25 | 15,98% | 11 | 2022-09-21 17:03:02.044+00 | 2022-10-01 15:20:51.265+00 |
| Touhou Game Dev | 933089313405685760 | jam-game-release | 933089316035506244 | 563 | 563 | 0,00% | 196 | 196 | 12 | 6,22% | 145 | 2022-04-18 00:01:37.237+00 | 2024-12-05 11:05:35.26+00 |
| Penusbmic's Server | 894976658229063731 | bugs-and-crashes | 1059947040794230945 | 560 | 560 | 0,00% | 56 | 56 | 23 | 19,64% | 88 | 2023-01-03 21:43:01.125+00 | 2024-12-31 13:37:55.382+00 |
| Touhou Game Dev | 933089313405685760 | unreal | 933089315737731121 | 543 | 543 | 0,00% | 41 | 41 | 13 | 6,08% | 40 | 2022-01-19 00:40:47.337+00 | 2024-09-03 08:04:35.715+00 |
| 💻 Ouckah Lair | 519640186167099402 | ：introductions | 1092866443609124892 | 535 | 535 | 0,00% | 344 | 344 | 31 | 15,51% | 172 | 2023-04-05 18:12:51.796+00 | 2024-12-17 18:16:46.521+00 |
| Penusbmic's Server | 894976658229063731 | upcoming-pack-ideas-and-feedback | 894976658711400500 | 528 | 528 | 0,00% | 61 | 61 | 28 | 19,70% | 96 | 2021-12-21 15:15:10.701+00 | 2024-10-30 15:49:34.896+00 |
| Rosebud AI | 773712199729414144 | 🗣┃tokkingheads | 945756857706885181 | 519 | 519 | 0,00% | 105 | 105 | 32 | 31,98% | 187 | 2022-03-09 04:00:31.609+00 | 2024-12-03 09:18:05.716+00 |
| WWebJS | 698610475432411196 | suggestions | 698618511798567014 | 515 | 515 | 0,00% | 133 | 133 | 35 | 24,47% | 243 | 2020-04-14 16:35:50.408+00 | 2024-11-27 19:36:10.932+00 |
| WWebJS | 698610475432411196 | hebrew | 995711591905513602 | 509 | 509 | 0,00% | 58 | 58 | 27 | 28,09% | 104 | 2022-07-11 20:35:07.869+00 | 2025-01-05 11:16:57.381+00 |
| Fermyon | 926888690310053918 | cloud | 1024646765149950022 | 500 | 500 | 0,00% | 94 | 94 | 45 | 24,40% | 164 | 2022-10-24 13:36:58.958+00 | 2024-11-29 14:45:56.935+00 |
| Penusbmic's Server | 894976658229063731 | social-media-posts | 1207350303079538730 | 499 | 499 | 0,00% | 34 | 34 | 19 | 31,26% | 103 | 2024-02-14 21:31:15.473+00 | 2024-12-10 13:57:24.434+00 |
| Fermyon | 926888690310053918 | random | 950023151578923028 | 479 | 479 | 0,00% | 78 | 78 | 32 | 16,08% | 164 | 2022-03-12 21:44:26.26+00 | 2024-12-03 08:45:25.953+00 |
| LuaCore Framework | 1078542362793492490 | 📚〡إقتراحات-الأعضاء | 1079682322372251718 | 473 | 473 | 0,00% | 168 | 168 | 93 | 42,28% | 106 | 2023-02-27 08:32:48.682+00 | 2024-11-14 11:19:10.168+00 |
| WWebJS | 698610475432411196 | german | 923304514189148240 | 466 | 466 | 0,00% | 24 | 24 | 11 | 25,97% | 62 | 2021-12-22 22:09:30.934+00 | 2024-07-04 19:12:36.621+00 |
| WWebJS | 698610475432411196 | showcase | 744945758649843734 | 466 | 464 | 0,00% | 173 | 173 | 90 | 43,97% | 228 | 2020-08-18 06:41:18.17+00 | 2024-12-26 22:51:35.908+00 |
| Kavita | 821879810934439936 | how-you-found-us | 928748255871918190 | 471 | 463 | 0,00% | 337 | 335 | 29 | 14,47% | 263 | 2022-01-06 20:42:18.498+00 | 2024-12-12 11:02:50.947+00 |
| Rosebud AI | 773712199729414144 | 👾┃tokking-bugs | 819923707114815498 | 451 | 451 | 0,00% | 76 | 76 | 31 | 35,25% | 156 | 2021-04-13 03:49:35.372+00 | 2024-11-21 11:27:43.838+00 |
| Return Community | 1080829289412432032 | 🎥┇content | 1150688654319157298 | 441 | 441 | 0,00% | 16 | 16 | 14 | 24,04% | 98 | 2023-10-02 12:37:25.339+00 | 2024-12-24 09:36:37.649+00 |
| ImperialPlugins\.com | 284399832385191936 | news | 525649215146295297 | 437 | 437 | 0,00% | 52 | 52 | 0 | 1,37% | 338 | 2018-12-21 13:22:38.676+00 | 2025-01-01 03:16:19.395+00 |
| Terasology | 270264625419911192 | documentation | 822117930501799956 | 398 | 398 | 0,00% | 17 | 17 | 11 | 14,82% | 70 | 2021-03-18 14:45:35.057+00 | 2024-10-03 21:35:47.025+00 |
| 💻 Ouckah Lair | 519640186167099402 | ╮process | 1303115560753561730 | 397 | 397 | 0,00% | 27 | 27 | 8 | 9,07% | 35 | 2024-11-04 22:01:32.971+00 | 2025-01-09 00:45:22.493+00 |
| Neo4j | 787399249741479977 | 💾release-notes | 816628571387985934 | 393 | 372 | 0,00% | 41 | 41 | 9 | 3,76% | 230 | 2021-03-03 11:44:33.057+00 | 2024-11-29 17:19:09.556+00 |
| Docker | 460871933748183040 | articles-and-links | 496964738706702356 | 349 | 348 | 0,00% | 92 | 92 | 16 | 18,97% | 144 | 2019-01-16 13:13:00.734+00 | 2024-12-25 09:12:42.654+00 |
| Rectify11 Community | 1077324213142175744 | controlpanel | 1139903652069388338 | 330 | 330 | 0,00% | 60 | 60 | 41 | 35,45% | 54 | 2023-08-12 12:50:42.12+00 | 2024-10-06 17:13:27.532+00 |
| Return Community | 1080829289412432032 | 👥┇staff-post | 1168333389703688305 | 326 | 324 | 0,00% | 15 | 15 | 12 | 19,14% | 70 | 2023-10-29 23:40:55.393+00 | 2024-12-27 14:51:27.477+00 |
| Neo4j | 787399249741479977 | integration | 898138274898538506 | 322 | 322 | 0,00% | 103 | 103 | 23 | 27,33% | 146 | 2021-11-17 23:11:15.976+00 | 2024-11-14 22:51:03.306+00 |
| Penusbmic's Server | 894976658229063731 | asset-packs | 1007266137513398342 | 320 | 319 | 0,00% | 39 | 39 | 30 | 28,21% | 54 | 2023-04-08 10:59:33.551+00 | 2025-01-03 17:18:46.066+00 |
| Docker | 460871933748183040 | repositories | 577916066349580348 | 305 | 305 | 0,00% | 84 | 84 | 24 | 26,23% | 105 | 2019-05-14 17:56:41.044+00 | 2024-10-10 13:50:19.818+00 |
| Oxylabs | 1128239127687598080 | ┠💬-event-chat | 1128323960589783131 | 305 | 304 | 0,00% | 60 | 60 | 18 | 36,18% | 39 | 2023-07-28 08:19:19.071+00 | 2024-11-11 01:59:46.427+00 |
| Penusbmic's Server | 894976658229063731 | memes-channel | 1157031822128070706 | 293 | 293 | 0,00% | 38 | 38 | 20 | 18,09% | 93 | 2023-09-28 19:12:08.578+00 | 2024-12-17 07:04:37.819+00 |
| Touhou Game Dev | 933089313405685760 | joonuary | 1324069636894883870 | 292 | 292 | 0,00% | 37 | 37 | 17 | 14,38% | 7 | 2025-01-01 17:40:07.753+00 | 2025-01-07 07:38:21.165+00 |
| Kindred Games Community | 398282199788552193 | arcane-toybox-chat | 1157026109322436648 | 289 | 287 | 0,00% | 18 | 18 | 9 | 14,98% | 25 | 2023-09-28 20:58:17.309+00 | 2024-11-28 23:14:24.474+00 |
| Terasology | 270264625419911192 | review-hotlist | 914642216922804244 | 285 | 284 | 0,00% | 13 | 13 | 6 | 17,25% | 139 | 2021-11-28 22:24:20.714+00 | 2024-12-26 09:16:15.528+00 |
| Neo4j | 787399249741479977 | drivers | 1052516552517357588 | 284 | 284 | 0,00% | 100 | 100 | 25 | 13,03% | 123 | 2022-12-14 09:43:37.335+00 | 2024-12-20 08:16:09.901+00 |
| Fermyon | 926888690310053918 | bartholomew | 950022927468855336 | 282 | 282 | 0,00% | 29 | 29 | 18 | 16,67% | 55 | 2022-03-09 22:57:54.359+00 | 2024-06-25 19:25:22.845+00 |
| Neo4j | 787399249741479977 | hackathon | 829976721490837504 | 276 | 276 | 0,00% | 78 | 78 | 33 | 25,72% | 97 | 2021-04-15 18:56:26.415+00 | 2024-08-23 14:59:43.831+00 |
| CodingWallah | 1056895641676152852 | ❓doubt-room | 1271778820462088212 | 273 | 273 | 0,00% | 48 | 48 | 23 | 19,78% | 35 | 2024-08-10 14:51:52.201+00 | 2024-12-02 06:01:04.102+00 |
| L'Ordre des Devs | 706640777450881114 | anecdotes | 1063977461873917952 | 273 | 272 | 0,00% | 46 | 46 | 23 | 20,96% | 120 | 2023-01-15 15:51:10.323+00 | 2024-12-31 16:40:39.763+00 |
| TheScostumati | 516564332440584221 | 🚀reviews | 761512712713928715 | 265 | 264 | 0,00% | 61 | 61 | 11 | 5,30% | 40 | 2020-10-02 09:08:33.566+00 | 2024-06-07 19:22:45.151+00 |
| Fermyon | 926888690310053918 | platform | 989284094724681820 | 257 | 256 | 0,00% | 37 | 37 | 18 | 25,39% | 49 | 2022-06-22 21:45:24.992+00 | 2024-01-05 19:04:49.33+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | redscript-snippets | 867332475553054740 | 253 | 253 | 0,00% | 41 | 41 | 18 | 15,02% | 50 | 2021-07-21 09:57:03.585+00 | 2024-01-01 00:15:30.606+00 |
| Terasology | 270264625419911192 | metal-renegades-multi | 577194054022856714 | 251 | 250 | 0,00% | 13 | 13 | 0 | 0,00% | 21 | 2019-05-20 20:15:29.842+00 | 2020-04-04 14:23:07.036+00 |
| OpenVic - Community | 1062018115275325480 | 🎶music | 1146182275822784592 | 246 | 246 | 0,00% | 37 | 37 | 17 | 18,29% | 78 | 2023-08-29 20:42:24.185+00 | 2024-12-29 17:02:46.422+00 |
| Rectify11 Community | 1077324213142175744 | directui | 1106722967234302012 | 236 | 236 | 0,00% | 49 | 49 | 32 | 32,20% | 66 | 2023-05-13 02:23:33.992+00 | 2024-10-18 07:23:16.492+00 |
| GameDevSG | 558680594498977792 | 🚀everything-else | 676616420737679360 | 236 | 236 | 0,00% | 47 | 47 | 12 | 7,63% | 81 | 2020-02-11 20:18:09.387+00 | 2024-12-01 18:13:49.936+00 |
| L'Ordre des Devs | 706640777450881114 | présentation | 1045346613050220564 | 228 | 227 | 0,00% | 216 | 216 | 1 | 1,32% | 176 | 2022-11-26 11:40:10.823+00 | 2025-01-03 16:51:25.489+00 |
| WWebJS | 698610475432411196 | arabic | 892257829237440522 | 226 | 226 | 0,00% | 65 | 65 | 24 | 36,73% | 97 | 2021-09-28 11:22:12.405+00 | 2025-01-08 02:59:12.073+00 |
| Neo4j | 787399249741479977 | nodes | 787958964607254558 | 216 | 214 | 0,00% | 49 | 49 | 14 | 12,15% | 50 | 2021-03-16 19:05:35.903+00 | 2024-11-26 10:08:55.8+00 |
| CodingWallah | 1056895641676152852 | 🤪│memes | 1120944537699897394 | 212 | 212 | 0,00% | 25 | 25 | 8 | 7,08% | 149 | 2023-06-21 09:57:05.899+00 | 2024-12-21 09:14:16.058+00 |
| Penusbmic's Server | 894976658229063731 | quality-of-life-improvements | 1060558489170235503 | 212 | 212 | 0,00% | 33 | 33 | 10 | 24,53% | 40 | 2023-01-05 15:53:59.721+00 | 2024-07-11 18:45:14.756+00 |
| 💻 Ouckah Lair | 519640186167099402 | 》project-showcase | 1092906671489159218 | 203 | 203 | 0,00% | 49 | 49 | 25 | 23,65% | 49 | 2023-04-08 18:17:15.325+00 | 2025-01-06 21:44:44.443+00 |
| TheScostumati | 516564332440584221 | 📢annunci | 531448181318483988 | 198 | 195 | 0,00% | 10 | 9 | 0 | 0,00% | 165 | 2019-02-21 10:42:35.707+00 | 2024-12-31 12:09:19.749+00 |
| OpenVic - Community | 1062018115275325480 | voting-discussion | 1107087508451369112 | 192 | 192 | 0,00% | 19 | 19 | 13 | 27,60% | 23 | 2023-05-13 23:43:03.739+00 | 2023-11-15 00:17:16.647+00 |
| Neo4j | 787399249741479977 | ❓help-others | 819843342397079562 | 192 | 190 | 0,00% | 63 | 63 | 20 | 33,68% | 49 | 2021-03-12 09:33:56.442+00 | 2024-08-14 20:54:01.669+00 |
| LuaCore Framework | 1078542362793492490 | 💳〡تحويلات-الخدمة | 1078684154012643389 | 187 | 187 | 0,00% | 51 | 51 | 6 | 5,88% | 63 | 2023-03-01 12:10:29.2+00 | 2024-11-23 15:18:20.233+00 |
| Terasology | 270264625419911192 | lotr-module | 541408595577929729 | 174 | 174 | 0,00% | 10 | 10 | 0 | 0,00% | 7 | 2019-02-03 00:05:00.852+00 | 2019-10-16 14:39:28.225+00 |
| L'Ordre des Devs | 706640777450881114 | suggestions | 1045847765017690212 | 173 | 173 | 0,00% | 27 | 27 | 13 | 17,34% | 60 | 2022-12-13 10:09:31.912+00 | 2024-12-10 18:11:50.89+00 |
| Return Community | 1080829289412432032 | 💸┇paid | 1178931250950578277 | 172 | 172 | 0,00% | 50 | 50 | 22 | 34,88% | 81 | 2023-11-28 11:08:40.433+00 | 2024-12-27 17:28:42.348+00 |
| Sapphire - Imagine a framework | 737141877803057244 | old-music-den | 1049324190026702848 | 167 | 167 | 0,00% | 7 | 7 | 5 | 16,17% | 1 | 2022-12-05 14:10:14.472+00 | 2022-12-05 14:35:35.968+00 |
| WWebJS | 698610475432411196 | turkish | 906316230967820328 | 164 | 164 | 0,00% | 49 | 49 | 16 | 14,63% | 51 | 2021-11-05 23:01:07.469+00 | 2024-12-10 08:33:57.379+00 |
| 💻 Ouckah Lair | 519640186167099402 | ╮rank | 1094432919029817437 | 163 | 163 | 0,00% | 27 | 27 | 2 | 5,52% | 38 | 2023-04-09 01:44:57.288+00 | 2024-12-12 01:41:28.416+00 |
| Penusbmic's Server | 894976658229063731 | upcoming-tutorial-ideas | 930478264693166130 | 157 | 157 | 0,00% | 40 | 40 | 14 | 19,75% | 46 | 2022-01-11 15:15:38.485+00 | 2024-11-26 14:20:04.74+00 |
| Fermyon | 926888690310053918 | show-and-tell | 971988031286444092 | 157 | 157 | 0,00% | 44 | 44 | 16 | 21,02% | 72 | 2022-06-27 03:21:39.435+00 | 2025-01-03 17:05:29.208+00 |
| Kavita | 821879810934439936 | android-dev | 1011961005930184744 | 149 | 149 | 0,00% | 26 | 26 | 10 | 14,77% | 28 | 2022-08-24 12:09:10.475+00 | 2024-09-25 20:42:12.317+00 |
| Return Community | 1080829289412432032 | 📊┇polls | 1168399276255219802 | 163 | 148 | 0,00% | 8 | 8 | 3 | 19,59% | 26 | 2023-10-30 04:02:40.446+00 | 2024-12-27 13:18:26.223+00 |
| Fermyon | 926888690310053918 | sqlite | 1133472877224665178 | 147 | 147 | 0,00% | 22 | 22 | 12 | 16,33% | 59 | 2023-07-27 11:53:10.475+00 | 2024-11-16 17:55:41.32+00 |
| Fermyon | 926888690310053918 | serverless-ai | 1148522244277014568 | 142 | 142 | 0,00% | 36 | 36 | 13 | 15,49% | 51 | 2023-09-05 11:48:09.363+00 | 2024-12-02 13:14:01.677+00 |
| OpenVic - Community | 1062018115275325480 | 😊emoji-suggestions | 1068341812143608009 | 141 | 141 | 0,00% | 50 | 50 | 14 | 21,28% | 45 | 2023-01-27 01:30:20.808+00 | 2024-12-11 21:10:47.547+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | redscript-bot-spam | 1193294894547083424 | 141 | 141 | 0,00% | 28 | 28 | 5 | 7,09% | 32 | 2024-01-06 20:48:20.543+00 | 2025-01-05 21:51:08.94+00 |
| Evolution Software Inc | 806713690182385695 | 💯┊ꜰᴇᴇᴅʙᴀᴄᴋ | 806713690605748242 | 141 | 141 | 0,00% | 124 | 124 | 0 | 0,00% | 113 | 2021-03-12 12:06:29.636+00 | 2025-01-07 19:48:22.244+00 |
| OpenVic - Community | 1062018115275325480 | community-showcase | 1098029818186039356 | 132 | 132 | 0,00% | 42 | 42 | 25 | 37,12% | 33 | 2023-04-19 01:15:12.535+00 | 2024-09-21 10:09:23.012+00 |
| Fermyon | 926888690310053918 | spin-maintenance | 1246118121828253746 | 132 | 132 | 0,00% | 14 | 14 | 11 | 22,73% | 36 | 2024-05-31 15:08:41.862+00 | 2024-11-18 15:40:25.407+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | carbine-mods | 933162454836461618 | 125 | 125 | 0,00% | 21 | 21 | 13 | 16,00% | 43 | 2022-01-19 12:28:30.686+00 | 2023-07-28 13:53:10.756+00 |
| CodingWallah | 1056895641676152852 | 🖲│bot-command | 1108963727543386184 | 118 | 118 | 0,00% | 48 | 48 | 3 | 2,54% | 23 | 2023-05-19 03:51:57.967+00 | 2024-03-15 16:37:32.17+00 |
| WWebJS | 698610475432411196 | italian | 1024686092940759050 | 118 | 118 | 0,00% | 21 | 21 | 10 | 29,66% | 51 | 2022-09-28 14:16:56.548+00 | 2024-12-10 13:28:51.773+00 |
| Penusbmic's Server | 894976658229063731 | balancing-upgrades-guns-feedback | 1061997224638296165 | 109 | 109 | 0,00% | 19 | 19 | 10 | 27,52% | 21 | 2023-01-09 13:21:16.019+00 | 2024-04-07 13:00:00.698+00 |
| Return Community | 1080829289412432032 | ✅┇vouch | 1178931689054023700 | 107 | 107 | 0,00% | 56 | 56 | 17 | 31,78% | 65 | 2023-11-28 10:23:19.529+00 | 2024-11-02 15:27:45.539+00 |
| Rectify11 Community | 1077324213142175744 | server-feedback | 1231696905122222200 | 104 | 104 | 0,00% | 16 | 16 | 7 | 14,42% | 20 | 2024-04-21 20:07:06.483+00 | 2024-12-19 00:14:27.684+00 |
| Oxylabs | 1128239127687598080 | ┠🌐-scraping | 1296723586354253905 | 103 | 103 | 0,00% | 43 | 43 | 18 | 38,83% | 40 | 2024-10-18 11:50:12.798+00 | 2025-01-04 22:27:41.497+00 |
| 💻 Ouckah Lair | 519640186167099402 | 》memes | 1092940560714702989 | 103 | 103 | 0,00% | 27 | 27 | 6 | 14,56% | 33 | 2023-04-06 17:34:04.554+00 | 2024-09-20 10:43:58.648+00 |
| Sapphire - Imagine a framework | 737141877803057244 | paginated-messages-v2 | 1191448052226068503 | 106 | 103 | 0,00% | 11 | 11 | 6 | 13,59% | 5 | 2024-01-01 18:34:01.266+00 | 2024-03-21 07:40:53.87+00 |
| Penusbmic's Server | 894976658229063731 | coding-chat | 1299679273992589312 | 102 | 102 | 0,00% | 12 | 12 | 9 | 37,25% | 8 | 2024-10-26 10:39:25.966+00 | 2024-11-23 22:43:56.116+00 |
| Penusbmic's Server | 894976658229063731 | event-chat | 1141713551422132254 | 101 | 101 | 0,00% | 23 | 23 | 4 | 11,88% | 20 | 2023-08-18 13:56:18.185+00 | 2024-10-08 08:37:03.867+00 |
| Penusbmic's Server | 894976658229063731 | ranks-and-levels | 939199936870908014 | 99 | 99 | 0,00% | 25 | 25 | 3 | 7,07% | 33 | 2022-02-04 16:46:55.689+00 | 2024-11-12 10:32:39.101+00 |
| Return Community | 1080829289412432032 | 🏅┇levels | 1171733817590030366 | 96 | 96 | 0,00% | 33 | 33 | 2 | 18,75% | 18 | 2023-11-08 10:00:15.34+00 | 2024-05-06 19:56:52.206+00 |
| Fermyon | 926888690310053918 | spin-plugins | 1109140856600023213 | 95 | 95 | 0,00% | 18 | 18 | 10 | 33,68% | 27 | 2023-05-19 15:30:14.421+00 | 2024-11-15 05:12:39.557+00 |
| 💻 Ouckah Lair | 519640186167099402 | 》connecting | 1093215366685134930 | 91 | 91 | 0,00% | 57 | 57 | 10 | 17,58% | 47 | 2023-04-19 21:33:49.402+00 | 2024-12-26 01:51:53.216+00 |
| Neo4j | 787399249741479977 | 🎆share-your-graph | 864549789164765184 | 91 | 91 | 0,00% | 36 | 36 | 18 | 30,77% | 52 | 2021-07-13 16:56:18.071+00 | 2024-07-30 06:02:49.238+00 |
| MonoGame Discord | 355231098122272778 | assets | 1225987443308761119 | 91 | 88 | 0,00% | 21 | 21 | 8 | 22,73% | 15 | 2024-04-06 02:51:51.73+00 | 2024-10-30 13:46:13.337+00 |
| 💻 Ouckah Lair | 519640186167099402 | ╮fitness | 1283614411738710108 | 87 | 87 | 0,00% | 9 | 9 | 6 | 16,09% | 7 | 2024-09-12 02:34:01.765+00 | 2024-12-20 19:57:32.262+00 |
| Terasology | 270264625419911192 | discuss-git-workflow | 800117138895142913 | 86 | 86 | 0,00% | 8 | 8 | 5 | 10,47% | 20 | 2021-01-16 21:46:35.869+00 | 2022-09-13 21:18:40.977+00 |
| Rectify11 Community | 1077324213142175744 | rectifypad | 1194904976271626341 | 79 | 79 | 0,00% | 16 | 16 | 5 | 24,05% | 23 | 2024-01-11 07:26:25.671+00 | 2024-11-05 17:51:52.521+00 |
| 💻 Ouckah Lair | 519640186167099402 | ╮gaming | 1092865627993149440 | 77 | 77 | 0,00% | 10 | 10 | 4 | 14,29% | 11 | 2023-05-02 23:06:52.128+00 | 2024-12-09 01:07:17.895+00 |
| GameDevSG | 558680594498977792 | 🖥the-matrix | 681915090290737219 | 185 | 76 | 0,00% | 117 | 24 | 1 | 6,58% | 48 | 2020-06-11 18:27:17.871+00 | 2024-08-27 04:01:03.794+00 |
| GameDevSG | 558680594498977792 | 🤝career-advice🤝 | 1245868774612013086 | 75 | 75 | 0,00% | 17 | 17 | 9 | 26,67% | 16 | 2024-06-06 00:56:40.582+00 | 2024-10-20 00:02:30.66+00 |
| GameDevSG | 558680594498977792 | ✋critiques-and-feedback | 1259501865868066948 | 73 | 73 | 0,00% | 13 | 13 | 7 | 30,14% | 23 | 2024-07-07 23:50:56.044+00 | 2024-11-08 08:20:31.635+00 |
| Oxylabs | 1128239127687598080 | ┠💻-looking-for-dev | 1296723200436338728 | 71 | 71 | 0,00% | 44 | 44 | 11 | 25,35% | 40 | 2024-10-25 11:12:36.474+00 | 2025-01-05 19:33:43.405+00 |
| Neo4j | 787399249741479977 | hello | 858987162035683329 | 72 | 71 | 0,00% | 40 | 40 | 8 | 25,35% | 44 | 2021-06-28 14:55:46.272+00 | 2024-09-23 08:41:12.975+00 |
| Touhou Game Dev | 933089313405685760 | jam-retrospective-showcase | 1215864272802812026 | 69 | 69 | 0,00% | 37 | 37 | 7 | 23,19% | 12 | 2024-03-09 03:41:30.76+00 | 2024-04-19 15:01:27.227+00 |
| Fermyon | 926888690310053918 | k8s | 1174022324144590981 | 67 | 67 | 0,00% | 20 | 20 | 7 | 14,93% | 16 | 2023-11-14 16:26:52.464+00 | 2024-12-09 11:18:42.091+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | kwek-mods | 1084570298881413120 | 67 | 66 | 0,00% | 22 | 22 | 7 | 19,70% | 24 | 2023-03-12 20:15:43.705+00 | 2023-07-28 13:51:48.123+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | cybercat-dev | 1156328948351905863 | 66 | 66 | 0,00% | 11 | 11 | 5 | 15,15% | 9 | 2023-09-26 20:39:08.846+00 | 2024-03-31 00:23:18.846+00 |
| WWebJS | 698610475432411196 | french | 891518457705811968 | 55 | 55 | 0,00% | 24 | 24 | 5 | 10,91% | 35 | 2021-09-26 03:22:20.252+00 | 2024-10-26 17:52:46.243+00 |
| Cyberpunk 2077 Modding Community | 717692382849663036 | cet-snippets | 807165519018459156 | 55 | 55 | 0,00% | 17 | 17 | 2 | 3,64% | 37 | 2021-02-05 08:29:46.753+00 | 2023-10-21 19:02:22.163+00 |
| Neo4j | 787399249741479977 | graphconnect | 968481001162543165 | 55 | 55 | 0,00% | 16 | 16 | 10 | 34,55% | 27 | 2022-04-26 12:25:51.604+00 | 2024-08-14 08:02:55.997+00 |
| Rectify11 Community | 1077324213142175744 | eol-gadgets | 1259411007219044455 | 55 | 54 | 0,00% | 14 | 14 | 7 | 44,44% | 16 | 2024-07-07 07:32:47.904+00 | 2024-11-11 10:36:11.315+00 |
| Fermyon | 926888690310053918 | bindle | 954140964379828234 | 53 | 53 | 0,00% | 11 | 11 | 5 | 11,32% | 24 | 2022-04-27 19:08:31.777+00 | 2023-04-07 20:56:43.196+00 |
| OpenVic - Community | 1062018115275325480 | 🔨moderation-corner | 1289270823621754933 | 51 | 51 | 0,00% | 11 | 11 | 4 | 15,69% | 10 | 2024-09-27 20:40:15.86+00 | 2025-01-07 19:44:25.222+00 |
| 💻 Ouckah Lair | 519640186167099402 | 》new-coders-resources | 1109970799441498143 | 51 | 51 | 0,00% | 25 | 25 | 6 | 17,65% | 23 | 2023-05-21 22:28:47.27+00 | 2024-12-24 03:42:45.369+00 |
| CodingWallah | 1056895641676152852 | 🖥│setup-related-issue | 1113728120365776947 | 49 | 48 | 0,00% | 18 | 18 | 3 | 12,50% | 11 | 2023-06-01 07:22:00.151+00 | 2024-01-30 09:06:49.229+00 |
| TikTok Shop Developer Hub | 1204537856870191114 | market-trends | 1210271935016075284 | 42 | 42 | 0,00% | 30 | 30 | 6 | 16,67% | 22 | 2024-03-21 11:12:28.042+00 | 2024-12-16 17:43:47.29+00 |
| Fermyon | 926888690310053918 | hippo | 950447584546283580 | 40 | 40 | 0,00% | 13 | 13 | 3 | 12,50% | 6 | 2022-03-17 14:02:33.908+00 | 2022-10-14 19:50:48.367+00 |
| Oxylabs | 1128239127687598080 | ┠🐭-ai-mouse | 1288476244618510356 | 36 | 36 | 0,00% | 11 | 11 | 5 | 16,67% | 17 | 2024-09-25 12:40:37.886+00 | 2025-01-04 22:28:14.622+00 |
| Oxylabs | 1128239127687598080 | ┠❔-support | 1298910783257972758 | 33 | 33 | 0,00% | 14 | 14 | 3 | 15,15% | 11 | 2024-10-27 07:27:58.603+00 | 2025-01-04 22:27:58.303+00 |
| 💻 Ouckah Lair | 519640186167099402 | ╮setups | 1092864502510399488 | 33 | 33 | 0,00% | 16 | 16 | 6 | 24,24% | 14 | 2023-04-08 19:51:30.274+00 | 2024-12-28 00:26:44.814+00 |
| Neo4j | 787399249741479977 | neo4j-arrows | 1110514116428308501 | 31 | 31 | 0,00% | 12 | 12 | 6 | 25,81% | 18 | 2023-05-24 13:12:40.367+00 | 2024-07-15 08:08:20.919+00 |
| Andy’s Development | 857672921912836116 | general-chat | 1327805405119774720 | 31 | 31 | 0,00% | 15 | 15 | 4 | 12,90% | 1 | 2025-01-12 01:04:51.616+00 | 2025-01-12 20:49:00.939+00 |
| CodingWallah | 1056895641676152852 | ask-from-mentor | 1113774254803144715 | 27 | 27 | 0,00% | 14 | 14 | 1 | 7,41% | 11 | 2023-06-01 10:34:24.88+00 | 2023-08-06 10:51:30.301+00 |
| CodingWallah | 1056895641676152852 | 📷│media | 1104734004315439214 | 20 | 20 | 0,00% | 16 | 16 | 1 | 5,00% | 14 | 2023-05-13 14:59:54.546+00 | 2024-10-19 14:24:31.009+00 |
| LuaCore Framework | 1078542362793492490 | ⭐〡اراء-العملاء | 1218713254323421226 | 19 | 19 | 0,00% | 16 | 16 | 3 | 15,79% | 9 | 2024-03-17 00:12:28.287+00 | 2024-12-12 20:23:32.41+00 |
| WWebJS | 698610475432411196 | wwebjs | 904443786548113488 | 12.161 | 2 | 0,00% | 10.426 | 2 | 0 | 0,00% | 2 | 2021-10-31 22:56:57.594+00 | 2025-01-08 23:49:21.539+00 |

## 10. Fontes auditaveis

Os arquivos de entrada deste documento estao em `data/processed/disentanglement/population_payload_v2`.

| Arquivo | SHA-256 |
| --- | --- |
| channels.csv | `937a2d019b4fef8f4cee17702811c094921e881333087384d029586c221dbe93` |
| servers.csv | `46ff61f2392f25682cab65725f163ff4d22e9be7ae981d0114fe7e7fc5b3e252` |
| temporal_activity.csv | `80ae0e34eca44111cb921a0bbe871967d566463606be96f045875bc85ec83777` |
| reply_distances.csv | `6790288a0c81d76aaa10719a2fb2d2d875430683278b53d550bd80a3e92f577c` |
| concentration.csv | `d50f9373fddf56a4ca0a39a86da14ce1c065ddd7c4cb02140ec4892e62a1ace7` |
| summary.json | `4c252b7debc71d72982399957e1ba069f87af428391896326f6b67fdc78dfc25` |

Os numeradores, denominadores, agrupamentos, faixas e formulas adicionais estao no gerador Python. A extracao original, suas definicoes e a proveniencia do Parquet estao no manifesto da populacao. Nao foram adicionados calculos manuais fora desses arquivos executaveis.
