# Protocolo de seleção de canais de software

## Unidade de seleção

Neste projeto, a unidade final de seleção não é apenas o servidor. Um servidor pode ser relacionado a engenharia de software ou open source, mas conter canais que não são relevantes para a análise, como `#memes`, `#off-topic`, `#rules`, `#roles`, canais de voz, logs de bot ou vagas.

A unidade de inclusão recomendada é:

> servidor válido de SE/OSS + canal textual válido de software dentro desse servidor.

Isso significa que a filtragem de servidores produz candidatos, enquanto a seleção final da amostra acontece no nível de canais.

## Definição operacional

Neste trabalho, um canal de software é um canal textual de um servidor Discord cuja finalidade predominante é apoiar atividades relacionadas ao desenvolvimento, manutenção, uso, evolução, suporte, documentação, depuração, contribuição ou governança de software, especialmente em projetos, ferramentas, linguagens, frameworks ou ecossistemas open source.

Entram como candidatos fortes canais de dúvidas técnicas, bugs, instalação, configuração, APIs, desenvolvimento, contribuição, releases, documentação, suporte de ferramentas, arquitetura, revisão de código, troubleshooting e integração com GitHub/GitLab.

Ficam fora da análise principal canais de memes, off-topic, apresentações, regras, anúncios puramente sociais, bots, cargos, moderação interna, voz, spam, marketplace e vagas. Canais de vagas só devem entrar se o estudo incluir explicitamente mercado de trabalho, o que não é o foco recomendado agora.

## Por que keywords não bastam

Keywords são úteis como filtro inicial, mas são frágeis como critério final. Um canal chamado `#general` pode ser altamente técnico, como nos canais analisados pelo DISCO em comunidades de programação. Por outro lado, um canal chamado `#dev-chat` pode conter pouca discussão técnica real, dependendo da comunidade.

Por isso, o pipeline deve usar nomes de canais apenas como sinal inicial. A decisão deve considerar também o conteúdo das mensagens, evidências de open source, modelagem semântica e validação manual.

## Protocolo em cinco etapas

O protocolo abaixo descreve a versão metodológica desejada para a dissertação. O pipeline atual já implementa metadados, evidências lexicais, evidências OSS e classificação A/B/C/D. A etapa de modelagem semântica com `SemanticTopicScore` ainda deve ser implementada antes de ser tratada como resultado final.

### 1. Filtro por metadados

Coletar e manter, quando disponível:

- `server_id`
- `server_name`
- `channel_id`
- `channel_name`
- `channel_category`
- `channel_description` ou `topic`
- `n_messages`
- `n_users`
- `n_bot_messages`
- `date_range`

Aplicar termos iniciais como `help`, `support`, `dev`, `development`, `bug`, `issue`, `pr`, `pull-request`, `code`, `programming`, `api`, `docs`, `documentation`, `release`, `install`, `setup`, `framework`, `library`, `package`, `plugin`, `python`, `java`, `javascript`, `typescript`, `rust`, `go`, `linux`, `github` e `gitlab`.

Esse filtro gera candidatos; ele não fecha a seleção.

### 2. Evidências técnicas no conteúdo

Para cada canal candidato, calcular sinais objetivos no conteúdo:

| Sinal                   | Exemplos                                                        |
| ----------------------- | --------------------------------------------------------------- |
| Links para repositórios | `github.com`, `gitlab.com`, `bitbucket.org`                     |
| Issues e PRs            | `issue`, `pull request`, `PR`, `commit`, `merge`, `branch`      |
| Termos de programação   | `function`, `class`, `error`, `exception`, `API`, `dependency`  |
| Código ou comandos      | blocos Markdown, `npm install`, `pip install`, `git clone`      |
| Arquivos e extensões    | `.py`, `.js`, `.java`, `.rs`, `.go`, `.json`, `.yaml`           |
| Logs e erros            | `stack trace`, `traceback`, `TypeError`, `NullPointerException` |
| Manutenção              | `release`, `version`, `breaking change`, `deprecated`           |

No código atual, essa etapa é implementada pelo comando:

```powershell
.\.venv\Scripts\python.exe main.py score-channels --min-messages 50
```

O comando gera `data/processed/software_channels.parquet` e `data/processed/software_channels.json` com scores, contagens de evidências, classe sugerida e marcação de revisão manual.

Filtros por nome de canal, como `include_channel_regex`, devem ser usados apenas em testes operacionais ou execuções exploratórias. Na metodologia final, a extração deve ser ampla o suficiente para não excluir canais técnicos com nomes genéricos, como `general` ou `python-general`. A triagem temática deve acontecer depois, por score de canais, modelagem semântica e validação manual.

### 3. Modelagem semântica de tópicos

Para a dissertação, a etapa mais forte é complementar o score lexical com modelagem semântica. A estratégia recomendada é criar documentos por canal usando blocos temporais ou blocos de N mensagens. Conversas disentangled são melhores para contexto, mas mais caras e não são obrigatórias para classificar canais.

Esta etapa não deve ser descrita como já implementada enquanto o pipeline não calcular `SemanticTopicScore`. Até lá, o método implementado deve ser descrito como versão operacional baseada em metadados, evidências lexicais e evidências OSS.

Fluxo recomendado:

```text
Canal -> blocos de mensagens -> SBERT/sentence embeddings -> clusterização -> BERTopic -> tópicos predominantes -> rótulo do canal
```

Tópicos esperados em canais de software incluem pacotes, erros, APIs, GitHub, issues, releases, dependências, build, Docker, instalação e troubleshooting. Tópicos sociais ou administrativos incluem música, jogos, fim de semana, boas-vindas, regras, roles, memes e random.

### 4. Classificação dos canais

Classificar cada canal em quatro classes:

| Classe | Descrição                                                                                    | Entra na análise principal?     |
| ------ | -------------------------------------------------------------------------------------------- | ------------------------------- |
| A      | Canal técnico central: dúvidas, suporte, bugs, desenvolvimento, código, API, contribuição    | Sim                             |
| B      | Canal técnico periférico: releases, documentação, anúncios técnicos, roadmap ou caso ambíguo | Talvez, como análise secundária |
| C      | Canal comunitário/social: geral social, off-topic, memes, apresentações, eventos             | Não                             |
| D      | Canal administrativo/bot: logs, regras, moderação, bots, cargos, voz                         | Não                             |

Para a análise principal de incivilidade, a recomendação é focar na classe A. A classe B pode ser usada em análise secundária ou comparação.

### 5. Validação manual

A validação manual é essencial para transformar a seleção em procedimento científico e deve ser tratada como etapa obrigatória da metodologia final. A classificação automática dos canais não deve ser assumida como verdade final. Uma amostra estratificada de canais das classes A, B, C e D deve ser avaliada por dois anotadores independentes, com cálculo de concordância e resolução de divergências por consenso.

Métricas recomendadas:

- Cohen's Kappa
- percentual de concordância
- precisão da classificação automática
- recall da classificação automática
- F1-score

Formulação recomendada:

> A classificação automática dos canais não será assumida como verdade final. Uma amostra estratificada de canais das classes A, B, C e D será avaliada manualmente por dois anotadores independentes. A concordância será medida por Cohen's Kappa, e divergências serão resolvidas por consenso. A partir dessa validação, serão reportadas precisão, recall e F1-score da classificação automática, especialmente para a classe A.

## Score recomendado para a dissertação

Para o texto metodológico, o índice completo pode ser definido assim:

```text
SoftwareChannelScore =
    0.25 * MetadataScore +
    0.25 * LexicalEvidenceScore +
    0.35 * SemanticTopicScore +
    0.15 * OSSEvidenceScore
```

Critério de decisão sugerido:

|       Score | Decisão                                 |
| ----------: | --------------------------------------- |
|   `>= 0.70` | canal técnico de software               |
| `0.50-0.69` | canal ambíguo; precisa validação manual |
|    `< 0.50` | não classificar como canal de software  |

Os pesos podem ser ajustados após piloto. O importante é manter uma regra explícita e reportar como ela foi calibrada.

### Justificativa metodológica da formação do score

A formação do score deve ser apresentada como uma operacionalização de um construto latente: o grau em que um canal funciona como espaço central de prática, suporte, manutenção, coordenação ou governança de software. Como esse construto não é observável diretamente, ele é aproximado por indicadores complementares.

`MetadataScore` mede a finalidade declarada do canal por meio de nome, categoria e descrição. `LexicalEvidenceScore` mede a prática discursiva efetivamente observada no conteúdo do canal. `SemanticTopicScore` mede o tema predominante em nível semântico, reduzindo a dependência de keywords isoladas. `OSSEvidenceScore` mede o vínculo do canal com artefatos e fluxos concretos de desenvolvimento, como repositórios, issues, PRs e releases.

Essa decomposição segue uma lógica de triangulação metodológica. Em vez de depender de um único tipo de evidência, o método combina intenção declarada, uso observado, tema predominante e ligação com ecossistemas reais de software. Isso fortalece a validade de construto e reduz a probabilidade de classificação baseada em rótulos superficiais.

### Justificativa dos pesos

Os pesos refletem uma prioridade teórica: quanto mais próximo o indicador estiver da atividade efetivamente desempenhada no canal, maior deve ser sua influência no score final.

Por isso, `MetadataScore` recebe peso moderado, pois é útil, mas sujeito a ambiguidade. `LexicalEvidenceScore` recebe peso alto porque deriva do conteúdo observado. `SemanticTopicScore` recebe o maior peso na formulação final porque representa a estrutura temática predominante do canal com maior robustez semântica. `OSSEvidenceScore` recebe peso complementar porque reforça a ligação com a prática de desenvolvimento, mas não basta sozinho para definir centralidade técnica.

Em termos metodológicos, a distribuição de pesos desloca a decisão de sinais superficiais para sinais mais próximos do construto que se deseja medir.

### Justificativa dos limiares e da classificação

Os limiares `>= 0.70`, `0.50-0.69` e `< 0.50` representam, respectivamente, zonas de alta confiança, ambiguidade substantiva e baixa evidência. A existência de uma faixa intermediária é importante porque transforma a incerteza em parte explícita do método, em vez de forçar todos os casos a uma decisão binária automática.

As classes A, B, C e D têm papéis analíticos distintos. A classe A reúne canais com alta confiança de centralidade técnica e compõe a amostra principal. A classe B reúne canais tecnicamente plausíveis, mas periféricos ou ambíguos, úteis para revisão manual e análise secundária. A classe C representa irrelevância temática para o foco principal do estudo. A classe D representa irrelevância funcional, isto é, canais administrativos, automatizados, normativos ou não conversacionais.

Essa distinção entre irrelevância temática e irrelevância funcional é importante para estudos em Discord, porque alguns canais podem conter linguagem técnica ocasional, mas não funcionar como espaços reais de interação técnica entre participantes.

### Justificativa da versão operacional atual

No pipeline atual, a fórmula operacional é mais simples:

```text
software_channel_score =
    0.20 * metadata_score +
    0.60 * lexical_evidence_score +
    0.20 * oss_evidence_score
```

Essa configuração prioriza o conteúdo observado porque ela procura evitar dois erros recorrentes: excluir canais tecnicamente relevantes com nomes genéricos, como `general`, e incluir canais com nomes técnicos, mas conteúdo pouco relevante. Trata-se de uma formulação operacional inicial, adequada para triagem, mas ainda aberta a calibração empírica.

### Plano de calibração e validação

Para justificar a formação dos scores de modo plenamente defensável, recomenda-se um plano explícito de calibração:

1. construir uma amostra de canais rotulada manualmente;
2. testar combinações alternativas de pesos e limiares;
3. comparar precisão, recall e F1, sobretudo para a classe A;
4. realizar análise de sensibilidade e, quando possível, ablação dos componentes do score;
5. fixar a configuração final antes da análise principal de incivilidade.

Assim, a formação dos scores é apresentada como combinação de fundamentação teórica, operacionalização explícita e validação empírica, e não como escolha arbitrária.

O comando `score-channels` implementa uma versão operacional inicial sem `SemanticTopicScore`, usando mais peso nas evidências do conteúdo para evitar excluir canais tecnicamente relevantes chamados `#general`. A versão final da dissertação deve incorporar BERTopic ou outra modelagem semântica e registrar a validação manual.

### Lógica dos algoritmos usados

A etapa implementada atualmente é baseada em algoritmos interpretáveis:

| Algoritmo ou técnica            | Como funciona no pipeline                                                              | Por que foi escolhido                                                    |
| ------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Expressões regulares ponderadas | Identificam termos técnicos, sinais sociais, sinais administrativos, links e artefatos | São auditáveis e adequadas para triagem inicial                          |
| Soma ponderada                  | Combina componentes normalizados em `software_channel_score`                           | Permite explicitar a importância relativa de cada evidência              |
| Normalização por saturação      | Limita cada sinal ao intervalo `0-1` após atingir uma proporção mínima de mensagens    | Reduz viés de volume e enfatiza predominância temática                   |
| Regras A/B/C/D                  | Aplicam limiares e condições sobre score global, densidade lexical e sinais negativos  | Produzem classes interpretáveis para revisão manual                      |
| SBERT                           | Representa blocos de mensagens como embeddings semânticos                              | Permite comparar blocos por similaridade sem depender apenas de keywords |
| BERTopic                        | Agrupa embeddings e usa c-TF-IDF para extrair descritores de tópicos                   | Ajuda a identificar temas predominantes e interpretar canais ambíguos    |

A escolha por métodos interpretáveis na seleção do corpus é deliberada. Nesta fase, o objetivo não é maximizar performance preditiva a qualquer custo, mas construir uma amostra defensável, auditável e validável. Modelos mais complexos podem ser incorporados na etapa semântica, desde que seus resultados sejam comparados com a validação manual.

## Fluxo final recomendado

Para a versão final da dissertação, o processo completo deve ser descrito como:

1. Filtragem ampla de servidores candidatos.
2. Remoção ou revisão de falsos positivos evidentes.
3. Classificação do tipo de servidor: projeto OSS, ecossistema OSS, comunidade técnica ampla ou caso ruidoso.
4. Extração ampla de canais textuais dos servidores candidatos.
5. Remoção de bots e canais não textuais, administrativos ou evidentemente sociais.
6. Cálculo de `MetadataScore`, `LexicalEvidenceScore` e `OSSEvidenceScore`.
7. Criação de blocos de mensagens por canal.
8. Modelagem semântica de tópicos com embeddings/SBERT e BERTopic, se implementada.
9. Cálculo do `SoftwareChannelScore` final.
10. Classificação dos canais em A/B/C/D.
11. Validação manual com dois avaliadores e métricas de concordância/desempenho.
12. Definição da amostra final de canais técnicos para análise de incivilidade.

Se a etapa semântica ainda não estiver implementada, o texto deve apresentar o `SemanticTopicScore` como extensão planejada e usar a fórmula operacional atual para os resultados reportados.

## Papel do disentanglement

O disentanglement não é obrigatório para a primeira seleção de canais. Para decidir se um canal trata majoritariamente de desenvolvimento de software, blocos temporais ou blocos de N mensagens costumam ser suficientes.

Ele se torna importante depois, na análise de incivilidade em contexto, especialmente para estudar quem respondeu a quem, abandono de conversa, escalada de conflito, dúvidas técnicas que viraram conflito, respostas hostis a newcomers e efeito de incivilidade sobre resolução.

## Uso de sumarização

Sumarização automática pode apoiar avaliadores humanos, mas não deve ser o critério automático final. O uso recomendado é gerar, para cada canal, tópicos, mensagens representativas e um resumo interpretativo que ajude a confirmar o rótulo.

Formulação metodológica recomendada:

> A sumarização automática foi utilizada como apoio interpretativo, enquanto a decisão final de inclusão ou exclusão foi baseada em critérios objetivos e validação manual.

## Formulação para a metodologia

Para garantir que os canais analisados representam efetivamente espaços de discussão relacionados à engenharia de software, esta pesquisa adotará um procedimento híbrido de classificação de canais. Inicialmente, serão utilizados metadados dos servidores e canais, como nome, descrição, categoria e volume de mensagens, para identificar candidatos. Em seguida, o conteúdo textual dos canais será analisado por meio de evidências léxicas e semânticas, incluindo menções a código, erros, APIs, bibliotecas, repositórios, issues, pull requests e releases. Além disso, serão aplicadas técnicas modernas de modelagem de tópicos baseadas em embeddings, a fim de identificar os assuntos predominantes de cada canal. Por fim, os canais serão classificados em categorias como técnico central, técnico periférico, social/comunitário e administrativo, sendo a amostra final validada manualmente.

Decisão metodológica final:

> Neste trabalho, a classificação de canais será tratada como uma etapa própria da metodologia, anterior à análise de incivilidade. O objetivo dessa etapa é garantir que a análise seja realizada apenas sobre canais cujo conteúdo esteja predominantemente relacionado à prática de engenharia de software open source. Para isso, será utilizada uma abordagem híbrida baseada em metadados, evidências léxicas, modelagem semântica de tópicos e validação manual.
