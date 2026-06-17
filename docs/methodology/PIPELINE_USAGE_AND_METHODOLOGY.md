# Guia de uso do pipeline e metodologia científica

Este documento descreve como executar o pipeline de seleção de servidores e canais de software no dataset Discord Unveiled, como visualizar os canais resultantes e qual metodologia científica sustenta a classificação.

O objetivo do pipeline é produzir uma amostra de canais textuais de Discord relacionados à engenharia de software e open source para posterior análise de incivilidade.

## Visão geral

A unidade final de seleção da pesquisa é:

> servidor válido de SE/OSS + canal textual válido de software dentro desse servidor.

Isso é importante porque um servidor pode ser claramente relacionado a software, mas conter canais que não devem entrar na análise principal, como `#memes`, `#off-topic`, `#rules`, `#roles`, logs de bots, canais de voz ou vagas.

O pipeline executa cinco etapas principais:

1. Filtra servidores candidatos por metadados.
2. Extrai mensagens dos servidores selecionados.
3. Remove ou marca mensagens de bots, conforme configuração.
4. Pontua e classifica canais com base em evidências técnicas.
5. Cria views DuckDB para consulta, revisão e análise.

Há uma distinção importante entre o pipeline operacional atual e a metodologia final recomendada para a dissertação:

| Elemento                 | Status atual no pipeline                                         | Status recomendado para a dissertação                                      |
| ------------------------ | ---------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Filtro de servidores     | Implementado por metadados, termos positivos e negativos         | Usado apenas para gerar candidatos, seguido de revisão de falsos positivos |
| Filtro por nome de canal | Disponível como opção operacional                                | Usado somente em testes, não como critério final de seleção                |
| Score de canais          | Implementado com metadados, evidências lexicais e evidências OSS | Mantido como triagem objetiva e calibrado com validação manual             |
| SemanticTopicScore       | Ainda não implementado                                           | Implementar com SBERT/BERTopic antes de usar na fórmula final              |
| Validação manual         | Documentada como etapa metodológica                              | Obrigatória para definir a amostra final                                   |

## Arquivos principais

| Arquivo                                             | Função                                                   |
| --------------------------------------------------- | -------------------------------------------------------- |
| `main.py`                                           | CLI principal do pipeline                                |
| `pipeline_api.py`                                   | API programática usada pelo script                       |
| `scripts/run_programmatic_pipeline.py`              | Script completo com paths e parâmetros fixados em código |
| `docs/methodology/CHANNEL_SELECTION_PROTOCOL.md`    | Protocolo metodológico detalhado para seleção de canais  |
| `data/processed/software_servers_software.parquet`  | Servidores candidatos selecionados                       |
| `data/processed/software_messages_software.parquet` | Mensagens extraídas dos servidores candidatos            |
| `data/processed/software_channels_software.parquet` | Canais pontuados e classificados                         |
| `data/processed/software_channels_software.json`    | Versão legível para revisão manual dos canais            |
| `data/duckdb/discord_unveiled_software.duckdb`      | Banco DuckDB com views de análise                        |

## Pré-requisitos

Execute os comandos a partir da raiz do repositório:

```powershell
cd C:\Users\thiag\OneDrive\Documentos\Toxicity\Toxicity-OSS
```

Ative o ambiente virtual, se necessário:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Você pode usar `python` diretamente da `.venv`:

```powershell
.\.venv\Scripts\python.exe main.py --help
```

Ou usar `uv`, se ele estiver disponível:

```powershell
.\.venv\Scripts\python.exe main.py --help
```

## Execução rápida com dados já extraídos

Se `data/processed/software_messages_software.parquet` já existe, não é necessário baixar nem percorrer o dataset remoto novamente para testar a classificação dos canais.

Gere a pontuação dos canais:

```powershell
.\.venv\Scripts\python.exe main.py score-channels `
  --messages-parquet data/processed/software_messages_software.parquet `
  --output-parquet data/processed/software_channels_software.parquet `
  --output-json data/processed/software_channels_software.json `
  --min-messages 50
```

Recrie o DuckDB com a view `software_channels`:

```powershell
.\.venv\Scripts\python.exe main.py init-duckdb `
  --messages-parquet data/processed/software_messages_software.parquet `
  --servers-parquet data/processed/software_servers_software.parquet `
  --channels-parquet data/processed/software_channels_software.parquet `
  --database-path data/duckdb/discord_unveiled_software.duckdb
```

Esse é o melhor caminho para validar a etapa de canais sem repetir a extração pesada.

## Execução completa pelo script programático

O script [scripts/run_programmatic_pipeline.py](scripts/run_programmatic_pipeline.py) executa o fluxo completo:

1. `select_servers`
2. `extract_messages_remote`
3. `score_channels`
4. `init_duckdb`

Execute:

```powershell
.\.venv\Scripts\python.exe scripts\run_programmatic_pipeline.py
```

Atenção: essa execução chama `extract_messages_remote`, que percorre o arquivo remoto `dataset.zst`. O dataset completo tem aproximadamente 118 GB. O comando não salva esse arquivo inteiro localmente, mas ainda precisa percorrer o stream remoto para encontrar os servidores selecionados.

No script atual, a extração não usa `include_channel_regex` por padrão. Essa escolha é intencional: filtros por nome são úteis para testes rápidos, mas podem excluir canais tecnicamente relevantes chamados `general`, `python-general` ou nomes equivalentes. Para a versão principal da pesquisa, a recomendação metodológica é extrair os canais textuais dos servidores candidatos de forma mais ampla, remover bots e deixar o comando `score-channels` fazer a triagem temática no nível de canal.

Portanto, filtros por nome de canal devem ser descritos como recurso de teste operacional. Na metodologia final, a extração deve privilegiar cobertura ampla dos canais textuais dos servidores candidatos, e a inclusão ou exclusão deve ocorrer depois, por score de canais, modelagem semântica e validação manual.

## Execução passo a passo pela CLI

### 1. Baixar metadados dos servidores

```powershell
.\.venv\Scripts\python.exe main.py download-metadata
```

Saída esperada:

```text
data/raw/server_metadata/servers_metadata.txt
```

### 2. Selecionar servidores candidatos de software

```powershell
.\.venv\Scripts\python.exe main.py select-servers `
  --profile software `
  --min-positive-score 8 `
  --min-score-margin 2 `
  --max-negative-score 2 `
  --output-parquet data/processed/software_servers_software.parquet `
  --output-json data/processed/software_servers_software.json
```

Essa etapa usa metadados como nome, descrição, keywords, locale e vanity URL. O resultado ainda é uma lista de servidores candidatos, não a amostra final de canais.

### 3. Extrair mensagens dos servidores candidatos

```powershell
.\.venv\Scripts\python.exe main.py extract-messages-remote `
  --selected-servers-path data/processed/software_servers_software.parquet `
  --output-parquet data/processed/software_messages_software.parquet `
  --exclude-bots
```

Para uma extração experimental mais restrita:

```powershell
.\.venv\Scripts\python.exe main.py extract-messages-remote `
  --selected-servers-path data/processed/software_servers_software.parquet `
  --output-parquet data/processed/software_messages_software.parquet `
  --exclude-bots `
  --include-channel-regex "dev|help|code|backend|frontend" `
  --exclude-channel-regex "off-topic|meme|music"
```

Use a versão restrita apenas como teste operacional. Para a metodologia final, ela pode reduzir recall.

### 4. Pontuar e classificar canais

```powershell
.\.venv\Scripts\python.exe main.py score-channels `
  --messages-parquet data/processed/software_messages_software.parquet `
  --output-parquet data/processed/software_channels_software.parquet `
  --output-json data/processed/software_channels_software.json `
  --min-messages 50
```

O comando classifica canais em quatro classes:

| Classe | Interpretação                                  | Uso recomendado                      |
| ------ | ---------------------------------------------- | ------------------------------------ |
| A      | Canal técnico central                          | Entra na análise principal           |
| B      | Canal técnico periférico ou ambíguo            | Revisão manual ou análise secundária |
| C      | Canal social/comunitário                       | Excluir da análise principal         |
| D      | Canal administrativo, bot, regras, logs ou voz | Excluir da análise principal         |

### 5. Criar banco DuckDB

```powershell
.\.venv\Scripts\python.exe main.py init-duckdb `
  --messages-parquet data/processed/software_messages_software.parquet `
  --servers-parquet data/processed/software_servers_software.parquet `
  --channels-parquet data/processed/software_channels_software.parquet `
  --database-path data/duckdb/discord_unveiled_software.duckdb
```

Views criadas:

| View                   | Conteúdo                              |
| ---------------------- | ------------------------------------- |
| `software_servers`     | servidores selecionados por metadados |
| `software_messages`    | mensagens extraídas                   |
| `server_message_stats` | estatísticas agregadas por servidor   |
| `software_channels`    | canais pontuados e classificados      |

## Como visualizar os canais

Abra o banco:

```powershell
duckdb data/duckdb/discord_unveiled_software.duckdb
```

Resumo por classe:

```sql
SELECT channel_class, COUNT(*) AS channels, SUM(n_messages) AS messages
FROM software_channels
GROUP BY 1
ORDER BY 1;
```

Canais da análise principal:

```sql
SELECT guild_name, channel_name, software_channel_score, n_messages, n_users
FROM software_channels
WHERE channel_class = 'A'
ORDER BY software_channel_score DESC, n_messages DESC;
```

Canais que precisam de revisão manual:

```sql
SELECT
    guild_name,
    channel_name,
    channel_class,
    software_channel_score,
    lexical_evidence_score,
    oss_evidence_score,
    n_messages,
    n_users
FROM software_channels
WHERE manual_review_required
ORDER BY software_channel_score DESC, n_messages DESC;
```

Mensagens de um canal específico, para inspeção qualitativa:

```sql
SELECT timestamp, guild_name, channel_name, left(content, 240) AS content_preview
FROM software_messages
WHERE guild_name = 'Neo4j'
  AND channel_name = 'app-dev'
ORDER BY timestamp
LIMIT 50;
```

Exportar uma planilha de revisão de canais:

```sql
COPY (
    SELECT
        guild_name,
        channel_name,
        channel_class,
        software_channel_score,
        metadata_score,
        lexical_evidence_score,
        oss_evidence_score,
        n_messages,
        n_users,
        manual_review_required
    FROM software_channels
    ORDER BY software_channel_score DESC, n_messages DESC
) TO 'data/processed/channel_review.csv' (HEADER, DELIMITER ',');
```

## Metodologia científica utilizada

### Fonte dos dados

O pipeline usa o dataset Discord Unveiled, especificamente:

- `server_metadata/servers_metadata.txt`, para metadados dos servidores;
- `dataset.zst`, para mensagens organizadas por servidor.

A seleção começa no nível de servidores, mas a amostra científica é refinada no nível de canais.

### Etapa 1: filtro de servidores candidatos

Os servidores são classificados por heurísticas de termos positivos e negativos.

Sinais positivos incluem termos como:

- `software engineering`
- `software development`
- `open source`
- `programming`
- `coding`
- `developer`
- `devops`
- `github`
- `gitlab`
- `python`
- `javascript`
- `typescript`
- `rust`
- `docker`
- `kubernetes`

Sinais negativos incluem termos como:

- `nsfw`
- `crypto`
- `nft`
- `forex`
- `dating`
- `giveaway`
- `roleplay`
- nomes de jogos ou ecossistemas com alto risco de ruído temático

O objetivo dessa etapa é obter recall suficiente para encontrar comunidades candidatas, não decidir a amostra final.

O cálculo é feito por matching lexical com expressões regulares ponderadas. Para cada servidor, o pipeline concatena metadados textuais:

```text
search_text = name + description + vanity_url_code + preferred_locale + keywords
```

Depois calcula:

```text
positive_score = soma dos pesos dos padrões positivos encontrados
negative_score = soma dos pesos dos padrões negativos encontrados
score_margin = positive_score - negative_score
```

A seleção operacional usa:

```text
is_selected =
  positive_score >= min_positive_score
  AND score_margin >= min_score_margin
  AND negative_score <= max_negative_score
  AND nenhum termo negativo bloqueado foi encontrado
```

No perfil `software`, os valores padrão são `min_positive_score = 8`, `min_score_margin = 2` e `max_negative_score = 2`. Esses parâmetros implementam um corte conservador de candidatos de SE/OSS. Mesmo assim, a revisão posterior é parte do método, não uma etapa opcional.

Para a amostra principal, os servidores devem ser priorizados com critérios mais restritos:

1. `positive_score >= 8`;
2. `negative_score < 3`;
3. evidência manual de vínculo com software, preferencialmente open source;
4. existência de canais textuais classificados como técnicos centrais.

Servidores de projeto OSS, frameworks, linguagens, ferramentas e ecossistemas OSS são mais defensáveis para a análise principal. Comunidades amplas de tecnologia ou programação só devem entrar se os canais selecionados mostrarem evidência clara de desenvolvimento, manutenção, suporte ou contribuição em software. Servidores com foco em crypto, gaming, hosting promocional ou comunidades genéricas devem ser excluídos ou tratados como casos limítrofes que exigem justificativa explícita.

### Etapa 2: extração de mensagens

Após a seleção dos servidores, o pipeline extrai mensagens do dataset principal e salva um Parquet com campos principais, como:

| Campo                   | Descrição                            |
| ----------------------- | ------------------------------------ |
| `guild_id`              | identificador do servidor            |
| `guild_name`            | nome do servidor                     |
| `message_id`            | identificador da mensagem            |
| `channel_id`            | identificador do canal               |
| `channel_name`          | nome do canal                        |
| `author_id`             | identificador do autor               |
| `timestamp`             | data e hora da mensagem              |
| `content`               | conteúdo textual                     |
| `is_bot`                | indica mensagem de bot               |
| `attachment_count`      | número de anexos                     |
| `embed_count`           | número de embeds                     |
| `referenced_message_id` | mensagem referenciada, quando existe |

Para fins de documentação e publicação, recomenda-se evitar redistribuir texto bruto de mensagens. Use agregações, contagens, exemplos anonimizados ou trechos minimizados quando necessário.

### Etapa 3: classificação de canais

Um canal de software é definido como um canal textual cuja finalidade predominante é apoiar desenvolvimento, manutenção, uso, evolução, suporte, documentação, depuração, contribuição ou governança de software, especialmente em projetos, ferramentas, linguagens, frameworks ou ecossistemas open source.

O comando `score-channels` calcula três componentes operacionais:

| Componente               | O que mede                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------ |
| `metadata_score`         | evidências no nome do canal, como `help`, `dev`, `bug`, `api`, `docs`, `release`                 |
| `lexical_evidence_score` | evidências técnicas no conteúdo, como comandos, erros, código, extensões e termos de programação |
| `oss_evidence_score`     | evidências de open source e repositórios, como GitHub, GitLab, issue, PR, commit e release       |

Do ponto de vista metodológico, esses três componentes não foram escolhidos apenas por conveniência de implementação. Eles representam uma tentativa de operacionalizar um construto latente: a centralidade do canal para a prática de engenharia de software.

O `metadata_score` aproxima a finalidade declarada do canal. Nomes como `help`, `development`, `api`, `docs` ou `bug-reports` funcionam como sinais de intenção organizacional da comunidade. Esse componente é útil como prior fraco, mas não pode decidir sozinho, porque nomes de canais podem ser genéricos ou enganosos.

O `lexical_evidence_score` aproxima a prática discursiva efetivamente observada no canal. Por ser derivado do conteúdo trocado entre participantes, ele é a evidência mais próxima do construto de interesse. É esse componente que melhor responde à pergunta metodológica: este canal é usado predominantemente para discutir, manter, depurar, configurar ou evoluir software?

O `oss_evidence_score` aproxima o vínculo do canal com artefatos, fluxos e ecossistemas reais de desenvolvimento, especialmente open source. Menções a repositórios, issues, PRs, commits, branches e releases ajudam a diferenciar um canal tecnicamente central de um canal apenas superficialmente técnico.

Na versão operacional atual, o score é:

```text
software_channel_score =
    0.20 * metadata_score +
    0.60 * lexical_evidence_score +
    0.20 * oss_evidence_score
```

Essa distribuição de pesos tem uma justificativa metodológica explícita. O `lexical_evidence_score` recebe peso `0.60` porque o conteúdo observado é a evidência mais direta da atividade desempenhada no canal. O método privilegia, portanto, validade de conteúdo sobre rotulação superficial.

O `metadata_score` recebe peso `0.20` porque nomes e descrições ainda são informativos, mas entram apenas como evidência complementar. Isso reduz o risco de falso positivo em canais com nomes tecnicamente atraentes, mas conteúdo pouco relevante.

O `oss_evidence_score` recebe peso `0.20` porque o vínculo com GitHub, GitLab, issues, PRs e releases reforça que o canal participa de uma ecologia sociotécnica de software, mas não basta por si só para definir centralidade temática.

Dentro do `lexical_evidence_score`, os sinais também são ponderados de forma desigual porque não possuem o mesmo poder discriminativo. Termos de programação e comandos têm mais peso do que termos de manutenção porque indicam atividade técnica mais diretamente observável. Logs, erros e extensões de arquivos ajudam a diferenciar troubleshooting e suporte técnico de conversa geral. Já manutenção e roadmap aparecem também em canais periféricos, por isso recebem peso menor.

Os contadores são normalizados por saturação, em vez de usados como frequência absoluta. Isso tem uma justificativa importante: impedir que canais muito grandes ou repetitivos recebam score alto apenas por volume bruto. O objetivo não é medir intensidade absoluta de atividade, mas predominância relativa de evidência técnica.

Em resumo, a regra atual deve ser lida como uma heurística teoricamente orientada: mais peso para o que é observado no conteúdo, peso complementar para o que é declarado no nome e para o que evidencia ligação concreta com o ecossistema de software.

#### Como o score operacional é calculado

O cálculo implementado no pipeline segue uma lógica transparente e reprodutível.

Primeiro, o nome do canal é avaliado por padrões positivos e negativos. O score de metadados é calculado assim:

```text
metadata_raw = metadata_positive_score - metadata_negative_score
metadata_score = min(max(metadata_raw, 0) / 8, 1)
```

Esse cálculo garante que sinais negativos no nome do canal reduzam o score e que o resultado final fique entre `0` e `1`.

Segundo, o conteúdo do canal é agregado por `guild_id` e `channel_id`. Para cada canal, o pipeline conta mensagens contendo sete tipos de evidência técnica:

| Sinal                           | Peso interno |         Saturação | Interpretação                                          |
| ------------------------------- | -----------: | ----------------: | ------------------------------------------------------ |
| Links para repositórios         |         0.15 |  2% das mensagens | Evidência forte de ligação com artefatos de software   |
| Issues, PRs, commits e branches |         0.15 |  5% das mensagens | Evidência de fluxo de manutenção e colaboração         |
| Termos de programação           |         0.25 | 15% das mensagens | Evidência ampla de discussão técnica                   |
| Código ou comandos              |         0.20 |  8% das mensagens | Evidência direta de prática técnica                    |
| Extensões de arquivos           |         0.10 |  4% das mensagens | Evidência de menção a artefatos de código/configuração |
| Logs e erros                    |         0.10 |  4% das mensagens | Evidência de debugging e troubleshooting               |
| Manutenção/release              |         0.05 |  5% das mensagens | Evidência de evolução, release ou roadmap              |

Cada sinal é normalizado por saturação:

```text
bounded_signal_score = min(signal_count / (n_messages * saturation_ratio), 1)
```

Depois, os sinais normalizados são combinados:

```text
lexical_evidence_score =
  0.15 * repository_link_score +
  0.15 * issue_pr_score +
  0.25 * programming_term_score +
  0.20 * code_command_score +
  0.10 * file_extension_score +
  0.10 * log_error_score +
  0.05 * maintenance_score
```

Terceiro, o score OSS combina links diretos para repositórios e termos ligados a open source:

```text
oss_evidence_score =
  min(0.60 * repository_link_score + 0.40 * oss_term_score, 1)
```

Links diretos para repositórios recebem maior peso porque são evidência mais específica do que termos genéricos como `repo`, `issue` ou `release`.

Por fim, o score operacional do canal é calculado pela fórmula:

```text
software_channel_score =
  0.20 * metadata_score +
  0.60 * lexical_evidence_score +
  0.20 * oss_evidence_score
```

Essa lógica combina três princípios algorítmicos simples: matching lexical com expressões regulares, agregação por canal e normalização por saturação. O matching lexical identifica evidências observáveis; a agregação por canal transforma mensagens individuais em indicadores do canal; a saturação evita que volume bruto substitua predominância temática.

Resumo da lógica algorítmica usada:

| Etapa algorítmica                 | Lógica                                                                          | Papel metodológico                                                  |
| --------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Matching por expressões regulares | Busca padrões positivos e negativos em metadados, nomes de canais e conteúdo    | Transforma evidências textuais observáveis em variáveis mensuráveis |
| Soma ponderada                    | Soma sinais com pesos diferentes conforme poder discriminativo                  | Permite combinar evidências heterogêneas em um índice único         |
| Agregação por canal               | Agrupa mensagens por `guild_id` e `channel_id`                                  | Muda a unidade de decisão de mensagem individual para canal         |
| Normalização por saturação        | Usa `min(valor observado / limiar de saturação, 1)`                             | Evita que canais grandes recebam score alto apenas por volume       |
| Classificador baseado em regras   | Aplica limiares e regras para A/B/C/D                                           | Garante interpretabilidade e auditabilidade da seleção              |
| SBERT + BERTopic                  | Gera embeddings, agrupa documentos semanticamente e extrai tópicos com c-TF-IDF | Etapa semântica planejada para reduzir dependência de keywords      |

O uso de um classificador baseado em regras, em vez de um modelo supervisionado opaco nesta etapa, é intencional: a seleção de corpus precisa ser auditável, explicável e fácil de validar manualmente. A etapa supervisionada pode ser mais adequada depois, para detecção de incivilidade, quando houver rótulos anotados.

#### Como a classe do canal é atribuída

A classificação usa o score global, a densidade lexical e sinais negativos no nome do canal.

```text
se houver sinal administrativo forte
   e lexical_evidence_score < 0.30
   e oss_evidence_score < 0.20:
     classe D

senão, se houver sinal social forte
   e lexical_evidence_score < 0.35:
     classe C

senão, se software_channel_score >= 0.70
   e lexical_evidence_score >= 0.30:
     classe A

senão, se software_channel_score >= 0.50
   ou (lexical_evidence_score >= 0.45 e oss_evidence_score >= 0.20):
     classe B

senão, se houver sinal administrativo:
     classe D

senão:
     classe C
```

Essa regra cria uma hierarquia metodológica: primeiro remove canais cuja função é claramente administrativa ou social, depois identifica canais técnicos centrais, depois preserva casos ambíguos como classe B, e por fim exclui canais com baixa evidência técnica.

### Etapa 4: modelagem semântica recomendada para a dissertação

A etapa atual é uma triagem lexical e estrutural. O `SemanticTopicScore` ainda não está implementado no pipeline atual, portanto não deve ser apresentado como resultado já produzido. Para a dissertação, ele deve ser tratado como próxima etapa metodológica ou implementado antes de ser usado na fórmula final.

A recomendação é complementar a triagem atual com embeddings e topic modeling neural:

```text
Canal -> blocos de mensagens -> SBERT -> clusterização -> BERTopic -> tópicos predominantes -> validação do rótulo
```

Nesse desenho completo, o índice metodológico pode ser descrito como:

```text
SoftwareChannelScore =
    0.25 * MetadataScore +
    0.25 * LexicalEvidenceScore +
    0.35 * SemanticTopicScore +
    0.15 * OSSEvidenceScore
```

Critério sugerido:

|       Score | Decisão                                |
| ----------: | -------------------------------------- |
|   `>= 0.70` | canal técnico de software              |
| `0.50-0.69` | canal ambíguo, exige validação manual  |
|    `< 0.50` | não classificar como canal de software |

Esses limiares representam zonas metodologicamente distintas de decisão. A faixa `>= 0.70` corresponde a alta confiança de centralidade técnica e é adequada para compor a amostra principal. A faixa `0.50-0.69` representa ambiguidade substantiva: há evidência técnica, mas não suficiente para inclusão automática sem validação. Abaixo de `0.50`, a evidência é considerada insuficiente para sustentar a classificação como canal de software.

As classes A, B, C e D devem ser interpretadas como estratos analíticos, e não apenas como rótulos numéricos. A classe A representa canais técnicos centrais com maior confiança para análise principal. A classe B preserva recall e reúne canais periféricos, mistos ou ambíguos para revisão manual. A classe C representa irrelevância temática para o objetivo principal. A classe D representa irrelevância funcional: canais administrativos, automatizados, normativos ou não conversacionais, mesmo quando termos técnicos aparecem incidentalmente.

Na implementação atual, a classe A exige não apenas score global alto, mas também densidade lexical mínima. Essa decisão evita que um canal seja promovido à amostra principal apenas por nome técnico ou por poucas referências a OSS. O canal precisa apresentar evidência técnica consistente no conteúdo.

Os pesos podem ser ajustados depois de um piloto, desde que a regra final seja reportada de forma explícita. O procedimento metodologicamente mais defensável é calibrar pesos e limiares com base em uma amostra manualmente anotada, comparar precisão, recall e F1 para cada classe e reportar análise de sensibilidade ou ablação dos componentes.

Só use essa fórmula completa no texto final se a etapa semântica for efetivamente implementada e validada. Caso contrário, descreva a fórmula atual como versão operacional e o `SemanticTopicScore` como extensão planejada.

### Etapa 5: validação manual

Para tornar a seleção defensável cientificamente, a validação manual deve ser tratada como etapa obrigatória, não apenas recomendada. A classificação automática dos canais não deve ser assumida como verdade final.

Procedimento mínimo:

1. Selecionar uma amostra estratificada de canais A, B, C e D.
2. Ter dois avaliadores independentes classificando os canais.
3. Calcular concordância entre avaliadores.
4. Resolver divergências por consenso.
5. Reportar desempenho da classificação automática contra a validação manual.

Métricas recomendadas:

- Cohen's Kappa
- percentual de concordância
- precisão
- recall
- F1-score

Formulação recomendada para a dissertação:

> A classificação automática dos canais não será assumida como verdade final. Uma amostra estratificada de canais das classes A, B, C e D será avaliada manualmente por dois anotadores independentes. A concordância será medida por Cohen's Kappa, e divergências serão resolvidas por consenso. A partir dessa validação, serão reportadas precisão, recall e F1-score da classificação automática, especialmente para a classe A.

### Fluxo metodológico final recomendado

Para a versão final da dissertação, o desenho mais defensável é:

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

### Papel do disentanglement

O disentanglement não é obrigatório para selecionar canais. Para essa etapa, agregações por canal, blocos temporais ou blocos de N mensagens são suficientes.

O disentanglement se torna mais importante na análise posterior de incivilidade, quando for necessário reconstruir conversas e medir contexto, escalada, abandono, resposta a newcomers ou impacto sobre resolução.

## Exemplos reais dos dados atuais

Os exemplos abaixo foram obtidos a partir de `data/duckdb/discord_unveiled_software.duckdb`. Eles mostram agregações e metadados; conteúdo bruto de mensagens não é reproduzido aqui por minimização de dados.

### Tamanho atual do corpus extraído

| Métrica                 |   Valor |
| ----------------------- | ------: |
| Servidores selecionados |      25 |
| Canais pontuados        |      30 |
| Mensagens extraídas     | 857.232 |

### Distribuição dos canais por classe

| Classe | Canais | Mensagens |
| ------ | -----: | --------: |
| A      |      7 |    45.883 |
| B      |     11 |   474.012 |
| C      |     12 |   337.312 |

### Exemplos de servidores selecionados

| Servidor                         | Positive score | Negative score | Score margin | Membros aprox. |
| -------------------------------- | -------------: | -------------: | -----------: | -------------: |
| `/g/ - technology: CIA edition`  |             19 |              0 |           19 |          2.442 |
| `Fermyon`                        |             19 |              0 |           19 |          1.409 |
| `Neo4j`                          |             17 |              0 |           17 |          8.579 |
| `Ouckah Lair`                    |             16 |              0 |           16 |          1.899 |
| `Sapphire - Imagine a framework` |             14 |              0 |           14 |          2.224 |
| `LuaCore Framework`              |             14 |              0 |           14 |          1.887 |
| `Rectify11 Community`            |             13 |              0 |           13 |          7.166 |
| `Docker`                         |             12 |              0 |           12 |         12.661 |

### Exemplos de canais classificados como A ou B

| Servidor                         | Canal                       | Classe | Score | Mensagens | Usuários |
| -------------------------------- | --------------------------- | ------ | ----: | --------: | -------: |
| `Neo4j`                          | `app-dev`                   | A      | 0.835 |     1.981 |      366 |
| `Neo4j`                          | `dev-ops`                   | A      | 0.830 |     1.162 |      246 |
| `Sapphire - Imagine a framework` | `framework-development`     | A      | 0.797 |    16.655 |      184 |
| `Sapphire - Imagine a framework` | `pieces-development`        | A      | 0.759 |     1.358 |       36 |
| `Sapphire - Imagine a framework` | `shapeshift-development-⚡` | A      | 0.740 |     2.137 |       32 |
| `Sapphire - Imagine a framework` | `utilities-development`     | A      | 0.729 |    13.177 |      100 |
| `Sapphire - Imagine a framework` | `plugins-development`       | A      | 0.721 |     9.413 |       92 |
| `Kavita`                         | `development`               | B      | 0.697 |     2.609 |       66 |
| `Sapphire - Imagine a framework` | `website-development`       | B      | 0.681 |     5.917 |       68 |
| `OpenMW`                         | `development-lua`           | B      | 0.681 |     3.675 |       78 |
| `Seattle Indies`                 | `🕸︱web-game-dev`          | B      | 0.671 |       455 |       50 |
| `OpenMW`                         | `development-main`          | B      | 0.662 |   140.568 |      719 |

## Interpretação dos resultados

Os canais de classe A são a amostra mais limpa para a análise principal de incivilidade em engenharia de software. Eles combinam nome técnico, evidências lexicais fortes e sinais de OSS ou desenvolvimento.

Os canais de classe B devem ser revisados manualmente. Alguns podem ser técnicos, mas periféricos; outros podem misturar desenvolvimento, comunidade e suporte. Eles são bons candidatos para análise secundária ou para calibrar o limiar do classificador.

Os canais de classe C e D devem ficar fora da análise principal, salvo se uma pergunta de pesquisa futura incluir sociabilidade geral, moderação, onboarding, regras, eventos ou mercado de trabalho.

## Checklist de uso recomendado

Antes da análise de incivilidade:

1. Revisar `data/processed/software_servers_software.json` para remover falsos positivos de servidores.
2. Rodar ou rerodar a extração de mensagens.
3. Rodar `score-channels`.
4. Revisar `data/processed/software_channels_software.json`.
5. Confirmar manualmente canais A e B.
6. Documentar critérios de inclusão e exclusão.
7. Criar uma amostra estratificada para validação manual.
8. Só então aplicar detecção/anotação de incivilidade.

## Limitações

- O filtro de servidores é uma heurística de candidatos, não uma verdade final.
- O score atual de canais ainda não usa BERTopic; ele é uma versão operacional inicial baseada em metadados, evidências lexicais e OSS.
- Canais chamados `general` podem ser técnicos e não devem ser excluídos automaticamente.
- Canais com nomes técnicos podem conter conteúdo social ou periférico.
- A extração remota percorre um arquivo grande e pode levar bastante tempo.
- A validação manual continua necessária para sustentar a classificação metodologicamente.

## Próximo passo metodológico

Para aproximar o pipeline da versão final da dissertação, o próximo avanço recomendado é adicionar uma etapa de `SemanticTopicScore` com SBERT + BERTopic sobre blocos temporais ou blocos de N mensagens por canal. Essa etapa deve ser comparada contra a validação manual para medir ganho de precisão e recall na seleção de canais técnicos de software.
