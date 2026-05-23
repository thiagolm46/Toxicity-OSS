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
.\.venv\Scripts\uv.exe run python main.py score-channels --min-messages 50
```

O comando gera `data/processed/software_channels.parquet` e `data/processed/software_channels.json` com scores, contagens de evidências, classe sugerida e marcação de revisão manual.

### 3. Modelagem semântica de tópicos

Para a dissertação, a etapa mais forte é complementar o score lexical com modelagem semântica. A estratégia recomendada é criar documentos por canal usando blocos temporais ou blocos de N mensagens. Conversas disentangled são melhores para contexto, mas mais caras e não são obrigatórias para classificar canais.

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

A validação manual é essencial para transformar a seleção em procedimento científico. Recomenda-se selecionar uma amostra estratificada de canais, pedir que dois avaliadores classifiquem independentemente, calcular concordância e resolver divergências por consenso.

Métricas recomendadas:

- Cohen's Kappa
- percentual de concordância
- precisão da classificação automática
- recall da classificação automática
- F1-score

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

O comando `score-channels` implementa uma versão operacional inicial sem `SemanticTopicScore`, usando mais peso nas evidências do conteúdo para evitar excluir canais tecnicamente relevantes chamados `#general`. A versão final da dissertação deve incorporar BERTopic ou outra modelagem semântica e registrar a validação manual.

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
