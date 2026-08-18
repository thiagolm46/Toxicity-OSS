# Refatoração de filtragem e protocolo de disentanglement

**Data da intervenção:** 2026-08-18  
**Escopo inicial do disentanglement:** servidor Discord `Neo4j`, `guild_id=787399249741479977`, pesquisa de software  
**Status metodológico:** infraestrutura experimental inicial; ainda não é resultado final de dissertação

## 1. Objetivo

Esta intervenção separa duas responsabilidades que estavam misturadas:

1. seleção de servidores e canais por perfis externos de regras;
2. comparação de abordagens de *conversation disentanglement* sob um protocolo comum.

O objetivo não é apenas facilitar manutenção. A separação permite registrar qual configuração gerou cada corpus e repetir uma execução sem editar Python. As pesquisas de software e de jogos são independentes: reutilizam o motor, mas não o mesmo perfil, corpus, conjunto de decisões humanas ou diretório de resultados. O Neo4j pertence somente ao piloto de software.

## 2. Estado encontrado antes da refatoração

O código de filtragem estava concentrado em `main.py`. Regex, pesos, limiares, vocabulários de software e sinais de canal estavam definidos diretamente no programa. O pipeline de disentanglement existente reunia heurística, regressão com supervisão fraca e CrossEncoder em um único score híbrido.

O diretório de trabalho também continha alterações não commitadas anteriores. Elas foram preservadas. Em particular, os módulos de ranking, relatórios, normalização, embeddings e exportação Neo4j continuam úteis como baselines e infraestrutura. Nenhuma tentativa anterior foi apagada.

Problemas metodológicos identificados:

- replies explícitos recebiam score máximo e depois eram usados na própria avaliação, produzindo vazamento de rótulo;
- a configuração de mesmo canal não era aplicada na geração de candidatos;
- modos diferentes podiam cair silenciosamente para a mesma heurística;
- métricas de cluster iguais a zero eram exibidas mesmo sem referência de cluster;
- milhões de pares eram duplicados em dois CSVs muito grandes;
- o arquivo de mensagens podia ser removido antes de uma nova extração terminar;
- não existia no Git um registro das decisões manuais de canais.

## 3. Fonte de dados congelada

O arquivo observado é:

```text
data/processed/software_messages.parquet
```

O nome `data/processed/software/_messages.parquet` citado na solicitação não existe no checkout analisado. O arquivo acima foi, portanto, tratado como a fonte indicada.

Snapshot verificado:

| Propriedade | Valor |
|---|---:|
| SHA-256 | `5fe780aeee4465e1b48419f21973e4e6b31ce33bd398a8f90b7070fae1f76f19` |
| Tamanho | 410.923.361 bytes |
| Mensagens | 7.092.851 |
| Servidores | 25 |
| Canais | 482 |
| Replies explícitos | 1.053.140 |
| Período | 2017-01-15 a 2025-01-09 |

Recorte Neo4j:

| Propriedade | Valor |
|---|---:|
| `guild_id` | `787399249741479977` |
| Mensagens | 35.787 |
| Canais | 37 |
| Autores | 3.624 |
| Replies explícitos | 8.813 no Parquet bruto |
| Período | 2020-12-14 a 2024-12-24 |

O Parquet deve ser tratado como **entrada imutável**. Novas seleções, inventários e experimentos devem ser gravados em diretórios derivados e nunca sobre esse caminho.

## 4. Validação manual de canais

Os documentos anteriores descrevem a necessidade de validação, mas não foi encontrado um artefato versionado contendo as decisões. Além disso, o Parquet inclui canais como `rules`, `banter` e `introduce-yourself`; portanto, presença no arquivo não pode ser usada como sinônimo de aprovação manual.

Foi criado `annotations/neo4j_channel_decisions.csv` com os 37 canais e estado inicial `pending`. Isso não invalida uma revisão já realizada fora do repositório: a planilha serve para importar e tornar auditáveis essas decisões. Até que essa importação ocorra, o recorte deve ser descrito como “todos os canais do servidor Neo4j, execução exploratória”, e não como corpus final validado.

## 5. Refatoração da filtragem

As regras passam a ser perfis versionados fora do código. Os perfis `software.v1` e `games.v1` são processados pelo mesmo motor. Um perfil contém:

- campos de metadados pesquisados e seus pesos;
- regras positivas e negativas, com IDs, grupos e pesos;
- regras bloqueantes;
- política para sobreposição de regras;
- sinais de conteúdo dos canais;
- limiares e classes;
- versão do schema e identificador do perfil.

Decisões importantes:

- usar JSON e a biblioteca padrão nesta versão, evitando dependência implícita de YAML;
- preservar a origem da evidência por campo;
- normalizar Unicode e aceitar `keywords` como lista, string, vazio ou `NA`;
- corrigir as fronteiras de `C++` e `C#`;
- registrar rejeitados, não apenas selecionados;
- fazer escrita atômica e impedir sobrescrita sem autorização explícita;
- registrar hash do perfil e do input em manifesto.

Separar perfis permite reutilizar o motor sem misturar os objetos de pesquisa. O
perfil `software.v1` deve ser aplicado ao corpus de software e o perfil
`games.v1` somente a um corpus de comunidades de jogos. Uma futura pesquisa de
outro domínio deve receber outro perfil versionado e outro conjunto de artefatos.

### 5.1 Verificação da seleção inicial de servidores

Os dois perfis foram executados separadamente sobre os 3.167 registros do arquivo
geral de metadados, somente para criar listas candidatas de servidores para cada
pesquisa. Esses números não comparam os domínios e não formam um corpus misto:

| Perfil | Servidores selecionados | Proporção |
|---|---:|---:|
| `software.v1` | 38 | 1,20% |
| `games.v1` | 996 | 31,45% |

A proporção maior de candidatos de jogos não deve ser interpretada como precisão.
Antes de construir `games_messages.parquet`, deve-se anotar uma amostra
estratificada de selecionados e rejeitados do perfil de jogos. A mesma calibração
deve ser feita separadamente para software. Comunidades híbridas — por exemplo,
desenvolvimento de mods ou motores de jogos — exigem uma regra de escopo explícita
em cada projeto, sem transferir decisões automaticamente entre as pesquisas.

No recorte Neo4j, o perfil de software manteve os 37 canais no inventário e
produziu 9 canais A, 11 B, 16 C e 1 D. As classes e os escores foram copiados
para `annotations/neo4j_channel_decisions.csv`; as 37 decisões humanas continuam
`pending`. O perfil de jogos **não faz parte dessa execução**. A execução indevida
`neo4j_games` foi removida depois que a separação entre as duas pesquisas foi
explicitada.

Durante essa execução foi detectado e corrigido um erro específico do Windows
na sincronização do arquivo Parquet temporário. Um teste de regressão cobre agora
a gravação atômica de Parquet nesse sistema.

## 6. As três abordagens do chat compartilhado

A recomendação final do chat compartilhado não define DiHRL e LLM como os três experimentos principais. Ela propõe três **regimes de supervisão**:

### E1 — Zero-shot

Família inspirada em Chi e Rudnicky (2021). Nenhum `direct_reply` do Neo4j pode ser usado para ajustar o modelo. A referência original treina seleção de resposta em outra tarefa/domínio e transfere o modelo para disentanglement.

### E2 — Não supervisionado no Discord

Família inspirada no co-training de Liu, Shi e Zhu (2021), ou futuramente no Bi-Level Contrastive Learning. Não recebe labels do Neo4j; usa duas visões ou pseudo-rótulos derivados do corpus não anotado.

### E3 — Supervisão fraca

Um ranker pareado aprende com `direct_reply` somente no split de treino. No teste, todo campo que revele a referência é ocultado e a mensagem-pai deve ser recuperada entre candidatos anteriores.

Referências primárias:

- Chi, T.-C.; Rudnicky, A. I. (2021). *Zero-Shot Dialogue Disentanglement by Self-Supervised Entangled Response Selection*. EMNLP. DOI `10.18653/v1/2021.emnlp-main.400`; artigo: <https://aclanthology.org/2021.emnlp-main.400/>; código oficial: <https://github.com/chijames/zero_shot_dialogue_disentanglement>.
- Liu, H.; Shi, Z.; Zhu, X. (2021). *Unsupervised Conversation Disentanglement through Co-Training*. EMNLP. DOI `10.18653/v1/2021.emnlp-main.181`; artigo: <https://aclanthology.org/2021.emnlp-main.181/>; código oficial: <https://github.com/LayneIns/Unsupervised_dialo_disentanglement>.
- Reimers, N.; Gurevych, I. (2019). *Sentence-BERT*. EMNLP-IJCNLP. DOI `10.18653/v1/D19-1410`; artigo: <https://aclanthology.org/D19-1410/>.

A identificação dos três regimes seguiu a recomendação final do chat compartilhado
na solicitação: <https://chatgpt.com/share/6a848d44-68f8-83e9-ba72-c15d5b9a0138>.

## 7. Nível de fidelidade

As implementações locais iniciais são marcadas como:

```text
fidelity = pilot_proxy
```

Elas operacionalizam os três regimes com dependências atuais e permitem testar o protocolo no Neo4j. Elas **não** devem ser chamadas de reprodução fiel dos artigos nem de SOTA. Uma reprodução fiel exige ambientes isolados, checkpoints, dados de pré-treino e arquiteturas originais. O código oficial de Chi e Rudnicky e o de Liu et al. deve ser integrado depois como adaptador adicional, mantendo o mesmo contrato de entrada, candidatos e saída.

Esse rótulo é deliberado: é cientificamente preferível um proxy declarado e reprodutível a atribuir indevidamente o nome de um método a uma heurística diferente.

## 8. Protocolo comum no Neo4j

Todas as abordagens devem usar:

- o mesmo `guild_id`, não apenas comparação textual do nome;
- as mesmas mensagens normalizadas;
- candidatos anteriores do mesmo canal;
- a mesma janela temporal e o mesmo limite de candidatos;
- split temporal 60/20/20 dos replies explícitos;
- nenhum campo de referência entregue ao scorer no teste;
- o mesmo conjunto de fontes de teste;
- outputs e manifestos separados por abordagem.

O teste silver mede recuperação de replies explícitos. Ele não representa todas as respostas implícitas. Por isso, o resultado final da dissertação também precisa de amostra manual que inclua mensagens sem `direct_reply` e, idealmente, dois anotadores.

Métricas mínimas:

- *candidate recall*;
- Accuracy/Recall@1;
- Recall@3 e Recall@5;
- MRR;
- cobertura e abstenção;
- número de links entre canais e links para o futuro, que devem ser zero por construção;
- estatísticas de tamanho, duração e singletons das conversas.

Métricas de cluster como ARI, NMI, VI, Shen-F e one-to-one overlap só devem ser reportadas quando houver referência de clusters. Ausência de referência deve aparecer como `not_available`, nunca como desempenho zero.

## 9. Interpretação dos resultados

Uma diferença entre as três abordagens pode decorrer de duas etapas:

1. recuperação de candidatos;
2. ordenação/atribuição dos candidatos.

Por isso, *candidate recall* deve ser mostrado separadamente. Se o pai verdadeiro estiver fora da janela, nenhum ranker poderá recuperá-lo. O threshold também deve ser ajustado apenas no conjunto de validação de cada abordagem.

As métricas calculadas sobre `direct_reply` devem ser chamadas de **silver evaluation**. A formulação defensável é “capacidade de recuperar respostas explícitas quando o metadado é mascarado”, não “qualidade total das conversas reconstruídas”.

## 10. Extensões planejadas

Depois de validar o protocolo no Neo4j:

1. integrar checkpoints/código oficial em ambientes isolados;
2. criar um gold set manual estratificado;
3. calibrar perfis de canal contra decisões humanas;
4. executar em outros servidores, com split por comunidade;
5. adicionar DiHRL como baseline estrutural especializado;
6. adicionar LLM DLA/DLA+SC como comparação contemporânea, registrando modelo, versão, prompt, custo e uso de contexto posterior;
7. medir como erros de disentanglement alteram a classificação posterior de incivilidade.

## 11. Regra para escrita da dissertação

Relatar sempre quatro versões separadas:

- método descrito no artigo original;
- adaptação implementada neste repositório;
- configuração exata da execução;
- limitações do silver standard e do domínio Neo4j.

Essa separação evita transformar uma adaptação exploratória em alegação de reprodução e permite que os experimentos sejam atualizados sem reescrever a história metodológica.

## 12. Implementação entregue

A filtragem ficou organizada em:

- `discord_filtering/engine.py`: funções puras de classificação;
- `discord_filtering/profile.py`: parser/validador estrito;
- `discord_filtering/service.py`: execução por arquivo e escopo de guild;
- `discord_filtering/storage.py`: escrita atômica, hashes e manifestos;
- `discord_filtering/cli.py`: comandos reproduzíveis;
- `configs/filtering/software.v1.json` e `games.v1.json`: vocabulários,
  pesos, sinais e limiares externos.

Os experimentos ficaram organizados em três módulos independentes em
`discord_disentanglement/approaches/` e em um protocolo comum em
`discord_disentanglement/experiments/`. Nenhum módulo cai silenciosamente para
outra abordagem.

Comandos usados na validação final:

```powershell
.\.venv\Scripts\python.exe -m pytest -q

.\.venv\Scripts\python.exe -m discord_filtering score-channels `
  --profile configs/filtering/software.v1.json `
  --input data/processed/software_messages.parquet `
  --output data/processed/filtering/software/neo4j_channels.parquet `
  --guild-id 787399249741479977 `
  --min-messages 50

.\.venv\Scripts\python.exe -m discord_disentanglement.experiments all `
  --config configs/experiments/neo4j_pilot.json `
  --input data/processed/software_messages.parquet `
  --output data/processed/disentanglement_experiments/neo4j_pilot_v1
```

## 13. Execução integral do piloto Neo4j

A execução final terminou em aproximadamente 58 segundos no ambiente observado.
A leitura Parquet projetou somente as colunas necessárias e aplicou o filtro do
`guild_id` antes da conversão para Pandas. Isso reduziu a leitura de 7.092.851
para 35.787 linhas.

| Verificação | Resultado |
|---|---:|
| mensagens treino/validação/teste | 21.472 / 7.157 / 7.158 |
| replies brutos | 8.813 |
| replies válidos, anteriores e no mesmo canal | 8.697 |
| referências cujo alvo não está no recorte | 116 |
| pares candidatos comuns | 283.889 |
| fingerprint comum | `ea77741f8bd43b1b8e57995da180cb5b7c5c33d594609d4a6b3a9dbee09cffda` |
| replies de teste | 1.392 |
| candidate recall/cobertura no teste | 0,7809 |
| links entre canais | 0 |
| links para o futuro | 0 |

| Abordagem | Recall@1 | Recall@3 | Recall@5 | MRR | links de teste |
|---|---:|---:|---:|---:|---:|
| zero-shot | 0,5503 | 0,7220 | 0,7529 | 0,6398 | 3.788 |
| co-training | 0,5065 | 0,6875 | 0,7349 | 0,6051 | 3.843 |
| weak supervision | 0,5797 | 0,7284 | 0,7572 | 0,6575 | 4.150 |

Os thresholds de link não são os valores absolutos arbitrários dos módulos. Cada
abordagem usa o mesmo quantil de abstention (0,25) sobre os melhores scores do
split de validação, sem consultar labels. Isso torna a regra de calibração comum,
mas não transforma scores de métodos diferentes em probabilidades calibradas.

A suíte dessa etapa continha 25 testes e passou integralmente. Além dos testes sintéticos,
a execução real confirmou o mesmo fingerprint de candidatos nas três abordagens,
zero violações temporais/de canal e isolamento dos replies de teste. Os resultados
acima continuam sendo avaliação *silver* de `direct_reply` e `pilot_proxy`.

## 14. Limpeza estrutural de 2026-08-18

Depois da validação do piloto, foi realizada uma limpeza para que somente o
protocolo vigente permanecesse operacional:

- aquisição e extração saíram do `main.py` monolítico e foram separadas em
  `discord_data/remote.py`, `extraction.py`, `database.py` e `cli.py`;
- a API programática duplicada e o script que apenas a encapsulava foram removidos;
- o pipeline híbrido anterior, sua interface HTML, rankers, embeddings, configuração,
  testes e documentação específica foram removidos porque não pertenciam às três
  abordagens comparáveis e apresentavam problemas metodológicos já registrados;
- as tentativas `neo4j_threads` e `neo4j_threads_ranktest` foram apagadas. Elas
  somavam aproximadamente 8,96 GiB, continham CSVs duplicados e não eram resultados
  válidos do protocolo atual;
- caches Python, relatórios gerados, configurações de editor e saídas antigas de
  filtragem foram removidos;
- dependências exclusivas do pipeline descartado (`torch`, `sentence-transformers`
  e `networkx`) saíram do projeto;
- os únicos resultados derivados preservados são a filtragem separada por pesquisa
  e `disentanglement_experiments/neo4j_pilot_v1`.

A limpeza não alterou nem removeu a fonte congelada
`software_messages.parquet`, os metadados brutos, os perfis versionados, as
decisões humanas ou os artefatos finais do piloto. A partir desta etapa, os três
comandos públicos são `discord-data`, `discord-filter` e `discord-disentangle`.
