# Achados da Filtragem de Servidores

## Escopo

Este relatório resume os achados da filtragem aplicada sobre `server_metadata/servers_metadata.txt` do dataset `SaisExperiments/Discord-Unveiled-Compressed`, com foco em servidores relacionados a:

- programação
- desenvolvimento de software
- engenharia de software
- ferramentas open source

A seleção foi feita com heurísticas de termos positivos e negativos sobre `name`, `description`, `keywords`, `vanity_url_code` e `preferred_locale`.

## Atualização Metodológica: Servidor não é Canal

Os resultados abaixo devem ser lidos como uma filtragem de **servidores candidatos**, não como a amostra final de análise. Um servidor pode ser relacionado a software e ainda conter canais irrelevantes para engenharia de software, como `#memes`, `#off-topic`, `#rules`, `#roles`, logs de bots, voz ou vagas.

A unidade recomendada para a próxima etapa é:

> servidor válido de SE/OSS + canal textual válido de software dentro desse servidor.

Assim, o conjunto de servidores selecionados deve ser seguido por uma classificação de canais. No pipeline atual, essa etapa é apoiada pelo comando `score-channels`, que calcula evidências técnicas no conteúdo e sugere classes A/B/C/D para revisão manual.

## Resumo Executivo

- Foram selecionados `107` servidores de um total de `3.167`, o equivalente a aproximadamente `3,4%` do universo avaliado.
- A soma dos `approximate_member_count` dos servidores selecionados foi `1.401.303`.
- A soma dos `approximate_presence_count` foi `142.113`.
- A pontuação positiva variou de `4` a `19`, com mediana `6`.
- A maior parte dos servidores selecionados está em `en-US`: `94` de `107` servidores.
- O conjunto contém um núcleo de alta confiança, mas ainda inclui uma cauda considerável de casos limítrofes.

## Nível de Confiança da Seleção

- Alta confiança, com `positive_score >= 8`: `34` servidores.
- Confiança intermediária, com `positive_score` entre `6` e `7`: `27` servidores.
- Baixa confiança, com `positive_score` entre `4` e `5`: `46` servidores.
- Servidores com algum sinal negativo (`negative_score > 0`): `46`.
- Servidores com sinal negativo forte (`negative_score >= 3`): `44`.

Leitura prática:

- O conjunto mais sólido está nos `34` servidores com score `>= 8`.
- Os `46` servidores com score `4` ou `5` são os mais prováveis candidatos a falso positivo.
- Como `44` servidores carregam sinais negativos relevantes, a revisão manual ainda é necessária antes da extração definitiva das mensagens.

## Distribuição de Pontuação

| Positive Score | Quantidade |
| -------------- | ---------: |
| 4              |         41 |
| 5              |          5 |
| 6              |         21 |
| 7              |          6 |
| 8              |         14 |
| 9              |          4 |
| 10             |          5 |
| 11             |          2 |
| 12             |          1 |
| 13             |          2 |
| 14             |          2 |
| 16             |          1 |
| 17             |          1 |
| 19             |          2 |

Achado importante:

- A distribuição é fortemente concentrada em scores baixos. Isso indica que a heurística atual é útil para recuperar candidatos, mas ainda está mais próxima de uma filtragem de recall alto do que de precisão alta.

## Principais Termos que Explicaram a Seleção

Os termos positivos mais frequentes foram:

| Termo       | Frequência |
| ----------- | ---------: |
| developer   |         45 |
| programming |         40 |
| dev         |         31 |
| coding      |         22 |
| open source |         21 |
| github      |         10 |
| linux       |         10 |
| java        |          8 |
| javascript  |          7 |
| python      |          4 |
| framework   |          4 |
| rust        |          3 |

Achados importantes:

- `developer`, `programming` e `dev` dominam a seleção.
- `dev` é útil para capturar comunidades técnicas, mas também aumenta a chance de falso positivo quando aparece em contextos como `game development`, `hosting`, `development` genérico ou naming promocional.
- `open source`, `github`, `linux`, `python`, `javascript` e `rust` funcionam como bons sinais de precisão.

## Distribuição por Locale

| Locale | Quantidade |
| ------ | ---------: |
| en-US  |         94 |
| NA     |          3 |
| pt-BR  |          2 |
| uk     |          2 |
| es-ES  |          1 |
| vi     |          1 |
| hr     |          1 |
| tr     |          1 |
| de     |          1 |
| ru     |          1 |

Achados importantes:

- O conjunto filtrado é majoritariamente anglófono.
- Há alguma diversidade linguística, mas pequena.
- Se o objetivo for ampliar a cobertura de comunidades técnicas em português ou espanhol, a heurística pode ser enriquecida com termos positivos nesses idiomas.

## Servidores Mais Fortes na Filtragem

Os exemplos abaixo são os melhores candidatos a comunidades realmente relacionadas a software, com base na combinação de score alto e sinais positivos claros:

| Servidor                       | Score | Membros | Sinais positivos                                            |
| ------------------------------ | ----: | ------: | ----------------------------------------------------------- |
| /g/ - technology: CIA edition  |    19 |   2.442 | open source, programming, coding, github, javascript, linux |
| Fermyon                        |    19 |   1.409 | open source, programming, coding, python, javascript, rust  |
| Neo4j                          |    17 |   8.579 | open source, programming, coding, python, java              |
| Ouckah Lair                    |    16 |   1.899 | programming, coding, computer science, github, javascript   |
| Sapphire - Imagine a framework |    14 |   2.224 | programming, coding, framework, javascript, typescript      |
| LuaCore Framework              |    14 |   1.887 | programming, coding, framework, github, linux               |
| Rectify11 Community            |    13 |   7.166 | open source, programming, dev, github                       |
| Docker                         |    12 |  12.661 | developer, devops, docker, kubernetes                       |
| Montano Community              |    11 |  10.983 | open source, github, javascript, linux                      |
| WWebJS                         |    11 |   9.978 | open source, programming, library                           |

Leitura prática:

- Esses servidores formam o melhor ponto de partida para uma extração inicial de mensagens com menor risco de ruído temático.
- O servidor `Docker` se destaca como comunidade de ferramenta técnica, mesmo sem muitas palavras clássicas como `programming` ou `open source` na combinação final.

## Maiores Servidores Selecionados

Os maiores servidores por `approximate_member_count` dentro do conjunto filtrado foram:

| Servidor               |        Membros |  Score | Negative Score |
| ---------------------- | -------------: | -----: | -------------: | --- |
| Shardeum               |        699.562 |     13 |              4 |
| Roblox UGC Community   |         31.108 |      6 |              3 |
| Static Shift Racing    |         29.036 |      4 |              0 |
| VPS CHEAP \\           | HN Gaming 2024 | 28.621 |              4 | 3   |
| RoVFX                  |         25.497 |      6 |              3 |
| Railway                |         24.228 |      4 |              0 |
| GraalOnline (Official) |         22.711 |      6 |              0 |
| Headstarter            |         19.314 |      8 |              0 |
| palera1n               |         17.933 |      7 |              0 |
| Roblox Developers      |         16.288 |     10 |              3 |

Achados importantes:

- Os maiores servidores não são, necessariamente, os mais confiáveis tematicamente.
- `Shardeum` domina o volume agregado, mas carrega sinal negativo de `finance/crypto`.
- Há casos de grande porte com forte chance de ruído, como `Roblox UGC Community`, `Static Shift Racing`, `VPS CHEAP | HN Gaming 2024` e `RoVFX`.
- Se esses servidores forem mantidos, eles podem contaminar a análise textual posterior com conteúdo não centrado em software open source ou desenvolvimento profissional.

## Casos Ambíguos ou Prováveis Falsos Positivos

Os seguintes servidores merecem revisão manual prioritária:

| Servidor                    | Score | Negative Score | Motivo de atenção                                                 |
| --------------------------- | ----: | -------------: | ----------------------------------------------------------------- |
| Shardeum                    |    13 |              4 | Forte componente crypto/blockchain                                |
| SagaDAO                     |     5 |              4 | Forte componente crypto                                           |
| Roblox Developers           |    10 |              3 | Mistura de desenvolvimento com ecossistema de jogo                |
| Roblox UGC Community        |     6 |              3 | Foco provável em criação dentro de jogo/plataforma                |
| Static Shift Racing         |     4 |              0 | Nome sugere comunidade de jogo, score muito baixo                 |
| VPS CHEAP \| HN Gaming 2024 |     4 |              3 | Mistura de hosting e gaming                                       |
| RoVFX                       |     6 |              3 | Sinal forte de game title                                         |
| GraalOnline (Official)      |     6 |              0 | Comunidade oficial de jogo, apesar de passar na heurística        |
| Return Community            |     8 |              3 | Indício de game title                                             |
| Andy’s Development          |     8 |              3 | O termo development pode estar sendo usado fora de software geral |

Achado importante:

- A principal fonte de ruído da filtragem atual é a sobreposição entre `development` no sentido de software e `development` dentro de ecossistemas de jogos, mods, scripting ou hosting promocional.

## O Que a Filtragem Já Entrega Bem

- Recupera bem comunidades explicitamente ligadas a open source, frameworks, linguagens e tooling.
- Encontra servidores fortemente técnicos mesmo quando a descrição é curta, desde que as `keywords` sejam ricas.
- Constrói uma boa base inicial para extrair mensagens orientadas a software sem precisar baixar todos os dados antes da triagem.

## Limitações Atuais

- A heurística ainda aceita muitos casos limítrofes com score baixo.
- O termo `dev` está amplo demais e puxa comunidades não centradas em engenharia de software.
- A soma de membros não representa usuários únicos, porque uma mesma pessoa pode estar em vários servidores.
- `approximate_member_count` e `approximate_presence_count` são métricas aproximadas do próprio metadata do Discord, não contagens verificadas pelo pipeline.

## Recomendações de Refinamento

1. Usar `positive_score >= 6` como corte inicial para uma versão mais precisa do conjunto.
2. Considerar `positive_score >= 8` como subconjunto de alta confiança para a primeira extração de mensagens.
3. Excluir automaticamente servidores com `negative_score >= 3` quando o nome ou descrição contiver sinais de `crypto`, `gaming`, `giveaway` ou `roleplay`.
4. Adicionar uma allowlist para projetos claramente técnicos, como `Docker`, `Neo4j`, `Fermyon`, `WWebJS` e `Sapphire`.
5. Adicionar uma blocklist para segmentos conhecidos de ruído, especialmente gaming, Roblox, crypto, hosting promocional e comunidades de leaks.
6. Enriquecer a heurística com termos positivos em português e espanhol se a intenção for ampliar a cobertura fora do inglês.
7. Após extrair mensagens, executar a pontuação de canais e focar a análise principal em canais de classe A.
8. Validar manualmente uma amostra estratificada de canais para estimar precisão, recall, F1 e concordância entre avaliadores.

## Arquivos Gerados

- [software_servers.json](data/processed/software_servers.json)
- [software_servers.parquet](data/processed/software_servers.parquet)
- [filter_summary.json](data/processed/filter_summary.json)

## Conclusão

O filtro atual já separa um núcleo útil de comunidades técnicas, especialmente open source, frameworks, linguagens e ferramentas de infraestrutura. O resultado mais importante é que existe um subconjunto claro de alta confiança, mas o conjunto completo de `107` servidores ainda está misturado com comunidades de gaming, crypto, hosting e casos de `development` ambíguo. Para a próxima etapa de extração das mensagens, o caminho mais seguro é usar primeiro o subconjunto com score mais alto ou revisar manualmente os casos com sinais negativos.

A partir desta revisão, a conclusão metodológica deve ser mais específica: a seleção de servidores é apenas a primeira etapa. A amostra final da dissertação deve ser composta por canais técnicos centrais dentro desses servidores, identificados por uma combinação de metadados, evidências lexicais, evidências de OSS, modelagem semântica e validação manual.
