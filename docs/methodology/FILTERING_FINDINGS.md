# Achados da Filtragem de Servidores

Este relatório descreve o critério atual de triagem de servidores candidatos no dataset `SaisExperiments/Discord-Unveiled-Compressed`, usando `server_metadata/servers_metadata.txt` como fonte inicial.

O resultado abaixo deve ser lido como **conjunto de servidores candidatos**, não como amostra final da dissertação. A unidade final de inclusão continua sendo:

> servidor válido de SE/OSS + canal textual válido de software dentro desse servidor.

## Critério Atual

Para cada servidor, o pipeline concatena metadados disponíveis (`name`, `description`, `keywords`, `vanity_url_code` e `preferred_locale`) e aplica expressões regulares positivas e negativas com pesos explícitos.

```text
positive_score = soma dos pesos positivos encontrados
negative_score = soma dos pesos negativos encontrados
score_margin = positive_score - negative_score
```

O perfil `software` usa o seguinte critério padrão:

```text
is_selected =
  positive_score >= 8
  AND score_margin >= 2
  AND negative_score <= 2
  AND nenhum termo negativo bloqueado foi encontrado
```

Termos negativos bloqueados incluem `nsfw`, `finance/crypto` e `game title`. O limite `negative_score <= 2` implementa o critério metodológico `negative_score < 3`.

## Resultado da Execução Atual

Com o critério atual, foram selecionados `25` servidores de `3.167` registros avaliados, aproximadamente `0,8%` do universo de metadados.

| Métrica                                      |   Valor |
| -------------------------------------------- | ------: |
| Servidores candidatos selecionados           |      25 |
| Soma de `approximate_member_count`           | 131.166 |
| Soma de `approximate_presence_count`         |  20.812 |
| Menor `positive_score`                       |       8 |
| Maior `positive_score`                       |      19 |
| Mediana de `positive_score`                  |      10 |
| Servidores com `negative_score > 0` no corte |       0 |

Distribuição por `preferred_locale`:

| Locale | Servidores |
| ------ | ---------: |
| en-US  |         24 |
| pt-BR  |          1 |

Distribuição de `positive_score`:

| Positive score | Servidores |
| -------------: | ---------: |
|              8 |          8 |
|              9 |          4 |
|             10 |          3 |
|             11 |          2 |
|             12 |          1 |
|             13 |          1 |
|             14 |          2 |
|             16 |          1 |
|             17 |          1 |
|             19 |          2 |

## Sinais que Mais Explicaram a Seleção

| Termo positivo   | Frequência |
| ---------------- | ---------: |
| programming      |         19 |
| coding           |         14 |
| open source      |         10 |
| github           |          5 |
| javascript       |          5 |
| linux            |          5 |
| dev              |          5 |
| framework        |          4 |
| developer        |          3 |
| python           |          2 |
| rust             |          2 |
| java             |          2 |
| computer science |          2 |

Os sinais mais fortes combinam termos de programação, open source e ecossistemas de ferramentas. O termo `dev` permanece útil, mas deve ser interpretado com cautela porque também aparece em contextos de jogos, hosting ou comunidades genéricas.

## Exemplos de Servidores Fortes

| Servidor                         | Positive score | Negative score | Score margin | Membros aprox. | Sinais positivos                                            |
| -------------------------------- | -------------: | -------------: | -----------: | -------------: | ----------------------------------------------------------- |
| `/g/ - technology: CIA edition`  |             19 |              0 |           19 |          2.442 | open source, programming, coding, GitHub, JavaScript, Linux |
| `Fermyon`                        |             19 |              0 |           19 |          1.409 | open source, programming, coding, Python, JavaScript, Rust  |
| `Neo4j`                          |             17 |              0 |           17 |          8.579 | open source, programming, coding, Python, Java              |
| `Ouckah Lair`                    |             16 |              0 |           16 |          1.899 | programming, coding, computer science, GitHub, JavaScript   |
| `Sapphire - Imagine a framework` |             14 |              0 |           14 |          2.224 | programming, coding, framework, JavaScript, TypeScript      |
| `LuaCore Framework`              |             14 |              0 |           14 |          1.887 | programming, coding, framework, GitHub, Linux               |
| `Rectify11 Community`            |             13 |              0 |           13 |          7.166 | open source, programming, dev, GitHub                       |
| `Docker`                         |             12 |              0 |           12 |         12.661 | developer, DevOps, Docker, Kubernetes                       |
| `Montano Community`              |             11 |              0 |           11 |         10.983 | open source, GitHub, JavaScript, Linux                      |
| `WWebJS`                         |             11 |              0 |           11 |          9.978 | open source, programming, library                           |

## Interpretação Metodológica

O corte atual é mais conservador do que a triagem exploratória anterior. Ele reduz falsos positivos de gaming, crypto, hosting promocional e comunidades genéricas, mas ainda não substitui validação manual.

Para a amostra principal, cada servidor candidato deve ser classificado manualmente em uma das categorias abaixo:

| Categoria de servidor                                      | Entra na análise principal?            | Justificativa                                                                                            |
| ---------------------------------------------------------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Projeto OSS específico                                     | Sim, se houver canais técnicos válidos | O servidor está diretamente ligado a um projeto e seus fluxos de suporte, manutenção e contribuição      |
| Framework, linguagem, ferramenta ou ecossistema OSS        | Sim, se houver canais técnicos válidos | O servidor representa uma comunidade de prática de software ou infraestrutura técnica                    |
| Comunidade ampla de tecnologia/programação                 | Somente após validação manual forte    | Tecnologia geral não é equivalente a comunidade open source; a inclusão depende dos canais e do conteúdo |
| Gaming, crypto, hosting promocional ou comunidade genérica | Não, salvo justificativa explícita     | Alto risco de falso positivo e ruído temático                                                            |

## Próxima Etapa

Após a seleção de servidores, a extração deve ser ampla o suficiente para não remover canais textuais com nomes genéricos. A triagem de canais deve ocorrer depois, com o comando `score-channels`, que calcula `metadata_score`, `lexical_evidence_score`, `oss_evidence_score`, `software_channel_score` e classes A/B/C/D.

A classificação automática dos canais deve ser validada manualmente. A recomendação mínima é usar amostra estratificada por classe, dois avaliadores independentes, cálculo de Cohen's Kappa e métricas de precisão, recall e F1 para a classe A.

## Arquivos Gerados

- [../../data/processed/software_servers_software.json](../../data/processed/software_servers_software.json)
- [../../data/processed/software_servers_software.parquet](../../data/processed/software_servers_software.parquet)

Esses arquivos ficam em `data/`, que é ignorado pelo Git. Para replicação, execute novamente o pipeline a partir dos comandos documentados no README e em [PIPELINE_USAGE_AND_METHODOLOGY.md](PIPELINE_USAGE_AND_METHODOLOGY.md).
