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

## 15. Evolução científica do disentanglement — schema 2.0

Em 2026-08-18 o protocolo foi ampliado sem substituir o piloto v1. Foram
adicionadas duas condições experimentais e uma avaliação que separa explicitamente
três problemas:

1. geração comum de candidatos;
2. ranking/recuperação do parent;
3. reconstrução de conversas por projeção sobre componentes silver.

Os novos métodos são `chi_zero_shot` e `irc_transfer`, ambos corretamente
classificados como `INSPIRED_BY`. A auditoria encontrou o repositório oficial de
Chi e Rudnicky no commit `ad0ef53f`, mas não encontrou licença nem checkpoint
treinado; portanto, nenhum código foi copiado. O adapter usa um checkpoint linear
auto-supervisionado em logs Ubuntu IRC sem ler annotations.

Para transferência, foi escolhido o corpus/repositório de Kummerfeld et al. no
commit `82ed04f9`, cujos dados têm licença CC-BY-4.0 e código ISC. O modelo DyNet
oficial não distribui checkpoint compatível com o ambiente atual. O adapter usa
um ranker pairwise treinado somente no IRC. O parser preserva IDs baseados nas
linhas do log, múltiplos parents e diferencia self-links, eventos de sistema e
reply edges. Os checkpoints JSON registram todos esses números e hashes.

A avaliação v2 acrescenta:

- Candidate Recall por K = 5, 10, 20 e 50;
- Recall@1/3/5/10, MRR, mean/median rank overall e conditional;
- ARI e NMI via scikit-learn;
- VI, B-Cubed, Exact Match, fragmentation e merge com testes controlados;
- intervalos bootstrap percentil agrupados por canal, 1.000 reamostragens;
- diferenças bootstrap pareadas sobre os mesmos 1.392 replies de teste;
- estratos de distância, tempo e competição;
- auditoria automática de leakage antes de qualquer `fit` ou `score`;
- interface Streamlit read-only para conversas, silver, predictions, rankings,
  divergências e casos de erro.

Definições formais, decisões de projeção e limitações estão em
`DISENTANGLEMENT_EVALUATION.md`; a proveniência de cada método está em
`DISENTANGLEMENT_METHODS.md`.

## 16. Execução integral Neo4j — piloto v2

O novo piloto foi gravado separadamente em
`data/processed/disentanglement_experiments/neo4j_pilot_v2`. A execução levou
aproximadamente 6 minutos e 20 segundos no ambiente observado, incluindo os
intervalos de confiança. O v1 permanece preservado.

| Verificação | Resultado |
|---|---:|
| mensagens treino/validação/teste | 21.472 / 7.157 / 7.158 |
| replies brutos / válidos / alvo ausente | 8.813 / 8.697 / 116 |
| pares candidatos comuns | 405.728 |
| fingerprint comum | `2c617474453bbf4f44fc6aecfe83b1ac596d42149f7494b84f26612c7c6ac892` |
| replies silver de teste | 1.392 |
| mensagens na projeção silver | 2.247 |
| links entre canais / links para o futuro | 0 / 0 nas cinco abordagens |
| leakage audit | `PASSED` nas cinco abordagens |
| bootstrap | canal, 1.000 reamostragens, 95%, seed 42 |

Candidate generation, comum aos cinco métodos:

| K | Candidate Recall | Média de candidatos | Mediana |
|---:|---:|---:|---:|
| 5 | 0,7536 | 2,8233 | 3 |
| 10 | 0,7744 | 4,0374 | 3 |
| 20 | 0,7816 | 5,3958 | 3 |
| 50 | 0,7845 | 6,8721 | 3 |

Resultados de ranking e reconstrução projetada:

| Abordagem | Tipo | R@1 overall | R@5 overall | MRR overall | MRR conditional | ARI | B-Cubed F1 | Exact | Fragmentation | Merge |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `zero_shot` | PILOT_PROXY | 0,5503 | 0,7536 | 0,6400 | 0,8158 | 0,3653 | 0,7281 | 0,1948 | 0,5451 | 0,1421 |
| `co_training` | PILOT_PROXY | 0,4986 | 0,7270 | 0,5990 | 0,7635 | 0,3483 | 0,7083 | 0,1722 | 0,5950 | 0,1461 |
| `weak_supervision` | PILOT_PROXY | 0,5733 | 0,7536 | 0,6541 | 0,8338 | 0,3631 | 0,7373 | 0,2209 | 0,4382 | 0,1785 |
| `chi_zero_shot` | INSPIRED_BY | 0,2981 | 0,6667 | 0,4521 | 0,5763 | 0,2764 | 0,6879 | 0,1508 | 0,6152 | 0,1630 |
| `irc_transfer` | INSPIRED_BY | 0,2802 | 0,5783 | 0,4096 | 0,5221 | 0,2287 | 0,6872 | 0,1413 | 0,4976 | 0,1502 |

### 16.1 Achados que podem orientar a dissertação

No recorte Neo4j, `weak_supervision` obteve o maior R@1, MRR overall, MRR
conditional, B-Cubed F1 e Exact Match. Em diferença pareada por canal contra o
baseline `zero_shot`, o ganho foi 0,0230 em R@1 (IC95% 0,0027–0,0368) e 0,0142
em MRR (IC95% 0,0029–0,0212). Isso é evidência do piloto, não prova de
superioridade universal.

As duas condições externas ficaram abaixo dos proxies internos no ranking. A
diferença `chi_zero_shot` versus `irc_transfer` possui intervalos pareados que
incluem zero tanto para R@1 quanto para MRR; este piloto não sustenta uma diferença
clara entre elas. O resultado é compatível com forte domain shift e também com a
simplificação linear dos mecanismos originais. Não deve ser interpretado como
falha dos artigos nem como avaliação de suas implementações oficiais.

Métricas locais e estruturais não escolheram exatamente a mesma configuração:
`weak_supervision` teve a menor fragmentação, mas merge maior que `zero_shot`.
Esse contraste confirma a necessidade de separar reply recovery de conversation
reconstruction.

O aumento do cap de 20 para 50 produziu ganho pequeno de Candidate Recall
(0,7816 em K=20 para 0,7845 em K=50), enquanto o custo subiu para 405.728 pares.
Isso sugere retornos decrescentes após K=20 neste servidor e deve ser reavaliado
por canal antes da expansão para outras comunidades.

### 16.2 Restrições para qualquer alegação

- os clusters são projeções sobre 2.247 mensagens cobertas por componentes de
  replies explícitos, não todas as 7.158 mensagens do teste;
- NMI alto coexistindo com ARI bem menor é plausível em partições com muitos
  clusters pequenos e não deve ser reportado isoladamente;
- thresholds compartilham uma regra de abstention, mas scores permanecem em
  escalas diferentes;
- canais do Neo4j continuam com decisão humana `pending` no artefato versionado;
- ainda falta avaliação manual com mensagens sem `direct_reply` e anotação entre
  avaliadores antes de conclusões finais da dissertação.

Comandos verificados nesta etapa:

```powershell
uv sync --extra ui
uv run pytest -q
discord-disentangle all --config configs/experiments/neo4j_pilot.json
discord-disentangle-ui
```

## 17. Correção da inspeção visual de conversas completas

A primeira versão do `Conversation Explorer` lia corretamente os artefatos de
threads, mas renderizava cada linha de `predicted_links.parquet` como um cartão
pai–filho independente. Como o pai era repetido para cada filho, a interface dava
a impressão incorreta de que a saída científica continha apenas pares, embora
`message_assignments.parquet` já atribuísse cada mensagem a um
`predicted_thread_id` completo.

O explorador passou a usar a atribuição de mensagens como unidade de apresentação:

- cada cartão corresponde agora a uma thread, com contagem de mensagens e
  participantes;
- cada mensagem aparece uma única vez, em ordem cronológica, acompanhada do pai
  previsto e do score da ligação;
- a profundidade do encadeamento é indicada visualmente, preservando ramificações;
- ao selecionar uma thread específica, a interface carrega todas as suas mensagens,
  inclusive as que estiverem fora da janela cronológica ou do split atualmente
  usado para localizar o caso;
- a referência Silver recebeu seletor próprio e o mesmo tratamento por componente;
- os seletores pesquisam todas as threads do canal e split escolhidos, não apenas as
  que aparecem na janela cronológica corrente;
- `all` permanece limitado à janela para evitar carregar simultaneamente milhares de
  conversas, mas organiza as mensagens visíveis em cartões por thread.

Foram adicionados testes para impedir regressões em três contratos: expansão da
thread prevista além da janela, ausência de duplicação pai–filho no modo `all` e
expansão do componente Silver completo. No caso real
`WEAK_SUPERVISION_5861f056533f`, no canal `graph-academy`, a interface reconstruída
carrega 14 mensagens únicas, três participantes e o intervalo de 07:00:37 a
09:41:45 UTC de 18 de agosto de 2023.

### 17.1 Comparação dirigida pela referência Direct Reply

O `direct_reply` permanece definido como evidência Silver positiva de alta
confiança, e não como anotação exaustiva: a presença do vínculo sustenta que duas
mensagens pertencem à mesma conversa, enquanto sua ausência não sustenta que elas
pertençam a conversas diferentes.

Ao selecionar um componente Silver, a interface agora localiza automaticamente
todas as threads previstas que contêm suas mensagens e informa, por abordagem:

- número de mensagens e vínculos explícitos no componente Silver;
- quantidade de threads previstas usadas para representar o componente;
- proporção das mensagens Silver preservadas na thread prevista dominante;
- recuperação exata dos pais indicados por `direct_reply`;
- quantidade de mensagens adicionais incorporadas à thread dominante.

Esse último número é diagnóstico, não falso positivo automático, pois mensagens
sem `direct_reply` continuam sem rótulo. No caso
`SILVER_5d1ae7db4c24`, `weak_supervision` e `zero_shot` preservaram as 11/11
mensagens em uma única thread e acrescentaram três mensagens. O primeiro recuperou
6/10 pais explícitos exatos e o segundo 7/10. O exemplo demonstra por que acerto do
pai e reconstrução da conversa devem ser analisados separadamente.

Os seletores de canal também passaram a mostrar `channel_name`; a chave interna com
ID só é acrescentada quando dois canais possuem o mesmo nome.

## 18. Conversation Explorer orientado pelo objetivo Silver

A revisão visual mostrou que controles de janela cronológica, posição inicial e
seleção independente de threads previstas exigiam que o pesquisador descobrisse
manualmente quais resultados correspondiam ao mesmo componente Silver. Essa
organização foi removida do `Conversation Explorer`.

O fluxo definitivo da página é orientado pela pergunta científica:

1. escolher o canal pelo nome;
2. escolher uma conversa Silver descrita por tamanho, participantes, data e trecho
   inicial;
3. visualizar o componente Silver completo como objetivo inicial;
4. comparar simultaneamente as cinco abordagens sobre esse mesmo componente;
5. abrir cada abordagem em uma visão de duas colunas: Silver à esquerda e
   reconstrução à direita.

As reconstruções mostram todas as threads previstas que interceptam o componente
Silver. Mensagens da referência são marcadas em verde; mensagens acrescentadas pelo
método, em amarelo. Cada vínculo informa se o pai de `direct_reply` foi preservado
ou qual pai alternativo foi escolhido. Se um componente foi fragmentado, todos os
fragmentos aparecem na mesma seção da abordagem.

Os vínculos da referência visual são carregados de `test_gold_outcomes.parquet`, e
não apenas dos pares presentes em `test_ranked_candidates.parquet`. Portanto, um
`direct_reply` cujo pai ficou fora do conjunto de candidatos continua visível no
objetivo Silver e é contabilizado como não reconstruído pelas abordagens. Isso evita
inflar artificialmente a proximidade ao esconder justamente os casos sem cobertura.

A tabela conjunta inclui as cinco condições (`zero_shot`, `co_training`,
`weak_supervision`, `chi_zero_shot` e `irc_transfer`) e apresenta preservação das
mensagens Silver, número de fragmentos, direct replies exatos, mensagens sugeridas e
F1 de sobreposição. Para o conjunto Silver `S` e a thread prevista dominante `P`, o
diagnóstico usa `precision = |S ∩ P| / |P|`, `recall = |S ∩ P| / |S|` e a média
harmônica das duas. Esse F1 mede semelhança de conjuntos para inspeção; não transforma
mensagens adicionais sem rótulo em falsos positivos científicos.

No caso `SILVER_5d1ae7db4c24`:

| Abordagem | Threads | Silver principal | Replies exatos | Sugeridas | F1 sobreposição |
|---|---:|---:|---:|---:|---:|
| `zero_shot` | 1 | 11/11 | 7/10 | 3 | 0,8800 |
| `co_training` | 2 | 9/11 | 2/10 | 3 | 0,7826 |
| `weak_supervision` | 1 | 11/11 | 6/10 | 3 | 0,8800 |
| `chi_zero_shot` | 1 | 11/11 | 1/10 | 3 | 0,8800 |
| `irc_transfer` | 8 | 4/11 | 0/10 | 2 | 0,4706 |

Esse exemplo deixa visíveis três fenômenos distintos: preservação do conjunto de
mensagens, recuperação do pai exato e inclusão de possíveis continuações ainda não
anotadas. A página também oferece uma matriz vínculo a vínculo com todas as
abordagens. A validação automatizada confirmou as cinco linhas, ausência dos antigos
sliders e alinhamento ao mesmo componente Silver.
