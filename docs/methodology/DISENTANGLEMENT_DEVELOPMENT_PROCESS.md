# Processo de desenvolvimento da funcionalidade de disentanglement

Este documento registra como a funcionalidade de conversation disentanglement foi
evoluindo no projeto ate o estado atual. O foco aqui nao e apenas descrever o pipeline
final, mas mostrar o caminho de desenvolvimento, os exemplos iniciais usados para validar
o comportamento e as decisoes de implementacao que surgiram desses exemplos.

Para a especificacao inicial da tarefa, ver
[docs/tasks/discord_disentanglement_neo4j.md](../tasks/discord_disentanglement_neo4j.md).
Para a metodologia consolidada do pipeline e da interface de inspecao, ver
[NEO4J_DISENTANGLEMENT_INTERFACE_METHODOLOGY.md](./NEO4J_DISENTANGLEMENT_INTERFACE_METHODOLOGY.md).

## 1. Ponto de partida

O desenvolvimento comecou com um objetivo bem restrito:

- transformar mensagens brutas do Discord em threads candidatas;
- manter o processo auditavel, sem depender de clustering semantico opaco;
- preservar privacidade na visualizacao;
- gerar artefatos que pudessem ser revisados por humanos.

Desde o inicio, o problema foi modelado como grafo conversacional:

- no = mensagem;
- aresta = relacao explicita ou inferida entre mensagens;
- componente conectado = thread candidata.

Essa decisao aparece cedo na especificacao em
[docs/tasks/discord_disentanglement_neo4j.md](../tasks/discord_disentanglement_neo4j.md), e foi
mantida durante toda a implementacao. O projeto nao seguiu o caminho de agrupar mensagens por
topico de forma global. Em vez disso, a unidade de inferencia escolhida foi sempre a relacao
mensagem atual -> mensagem anterior candidata.

## 2. Primeiro exemplo controlado

Antes de validar em dados reais do servidor Neo4j, o projeto ganhou um conjunto pequeno de
mensagens sinteticas em
[tests/test_discord_disentanglement.py](../../tests/test_discord_disentanglement.py). Esse
conjunto funciona como um caso minimo reproduzivel para varias situacoes que o pipeline precisa
tratar.

As mensagens sinteticas iniciais sao estas:

```text
m_001  USER_001  "Como faco relacionamento many-to-many no Neo4J?"
m_002  USER_003  "Meu docker do Neo4J nao sobe na porta 7474"
m_003  USER_002  "<@u1> voce pode criar um no intermediario com duas relationships"
m_004  USER_004  "<@u3> tenta docker compose logs porque parece erro de binding"
m_005  USER_001  "isso?"
m_006  USER_003  "valeu"
m_007  USER_002  "sobre cypher, match retorna outro plano agora"
m_008  USER_005  "Alguem sabe criar index composto no Neo4J?"
```

Esse conjunto foi desenhado para cobrir comportamentos diferentes ao mesmo tempo:

- `m_001` representa uma pergunta tecnica inicial;
- `m_003` representa uma resposta com mencao e reply explicito para `m_001`;
- `m_002` e `m_004` formam um segundo mini-dialogo tecnico, sem depender apenas de reply nativo;
- `m_005` representa resposta curtissima, que nao pode ser descartada so por ter pouco texto;
- `m_006` representa um fechamento social curto, util para testar continuacao apos ajuda tecnica;
- `m_007` e `m_008` representam mensagens posteriores, fora do burst inicial, para forcar o
  pipeline a nao colapsar tudo em uma unica conversa;
- `m_999` existe no fixture para validar filtragem por guild/canal e nao deve entrar no escopo
  `Neo4j`.

## 3. O que os exemplos iniciais provaram

Os testes sinteticos nao serviram apenas para cobrir IO. Eles definiram o comportamento-base do
pipeline. Alguns pontos importantes surgiram diretamente desses exemplos.

### 3.1 Reply explicito precisa vencer heuristica

O caso `m_003 -> m_001` mostrou que, quando o Discord ja oferece uma relacao explicita de reply,
o pipeline nao deve tentar reinventar esse vinculo. Por isso, a implementacao primeiro extrai
edges explicitos e so depois gera inferencias.

Consequencia no pipeline:

- `explicit_reply` recebe confianca `1.0`;
- `message_reference` e campos equivalentes sao preservados;
- o score heuristico curto-circuita para `1.0` quando ha reply explicito.

### 3.2 Mencao nao vira aresta automaticamente

O caso `m_004` foi importante para separar duas coisas que parecem iguais, mas nao sao:

- mencao textual a um usuario;
- evidencia suficiente para afirmar dependencia conversacional.

No desenho atual, mencao ajuda a pontuar candidatos, mas nao cria uma aresta sozinha. Isso evita
ligacoes artificiais em canais movimentados, onde usuarios se mencionam por motivos laterais.

### 3.3 Mensagens curtas precisam ser mantidas

O caso `m_005 = "isso?"` foi decisivo para evitar uma limpeza agressiva de texto. Em conversa de
chat, mensagens curtas podem ser semanticamente fracas, mas discursivamente fortes. Uma confirmacao,
uma pergunta de follow-up ou um agradecimento pode depender fortemente do contexto anterior.

Consequencia no pipeline:

- mensagens curtas nao sao removidas;
- o score delas depende mais de tempo, reply, mencao e continuidade de participantes do que de
  similaridade lexical isolada.

### 3.4 O escopo precisa ser filtrado cedo

O caso `m_999` mostrou que o pipeline precisava filtrar por guild e canal antes da normalizacao e
da construcao do grafo. Essa decisao evitou poluir a inferencia com mensagens de fora do escopo.

## 4. Primeira fase de implementacao

A primeira fase do desenvolvimento consolidou um pipeline minimo e reproduzivel no pacote
[discord_disentanglement](../../discord_disentanglement).

Essa fase cobriu:

1. leitura de JSON, CSV e Parquet;
2. filtragem por `guild_name`, `guild_id`, `channel_name` e `channel_id`;
3. normalizacao de conteudo;
4. anonimização de autores e mencoes;
5. extracao de edges explicitos;
6. geracao de candidatos anteriores por mensagem;
7. score heuristico auditavel;
8. construcao de grafo com `networkx`;
9. extracao de threads como componentes conectados;
10. exportacao para CSV, JSON e HTML.

O ganho dessa etapa foi sair de uma especificacao abstrata e chegar a um baseline testavel de ponta
a ponta.

## 5. Como o baseline heuristico foi surgindo

O baseline atual nao nasceu como um modelo fechado. Ele foi sendo composto para atender aos casos
minimos acima sem depender de embeddings obrigatorios ou de treino supervisionado.

As features escolhidas apareceram por necessidade pratica:

- tempo entre mensagens, para separar bursts de conversacao;
- mencoes, para reforcar continuidade dirigida a um participante;
- overlap lexical e similaridade TF-IDF, para capturar reuso de termos;
- tokens tecnicos, para dar peso a linguagem de software;
- sinais discursivos de pergunta e resposta;
- continuidade de participantes, para evitar links semanticamente parecidos mas socialmente implausiveis.

O principio foi sempre o mesmo: cada relacao inferida precisa ser explicavel com evidencias legiveis
em CSV e HTML, e nao apenas com um score numerico opaco.

## 6. Consolidacao das saidas de revisao

Depois que o baseline passou a funcionar com os exemplos sinteticos, o projeto ganhou uma camada de
inspecao humana. As saidas principais passaram a incluir:

- `messages_normalized.csv`;
- `edges_explicit.csv`;
- `candidate_pairs.csv`;
- `edges_inferred.csv`;
- `graph_edges.csv`;
- `threads.csv`;
- `threads.json`;
- `thread_messages.csv`;
- `thread_summaries.csv`;
- `annotation_review.csv`;
- `reports/neo4j_threads.html`;
- `reports/thread_graphs/*.html`.

Essa parte foi importante porque mudou a forma de validar a funcionalidade. O desenvolvimento deixou
de depender apenas de asserts em teste e passou a ter uma interface de auditoria manual.

## 7. Passagem do experimento sintetico para o caso Neo4j real

Com a base pronta, o pipeline foi aplicado ao recorte real do servidor Neo4j. A entrada operacional
atual vem do Parquet gerado pelo pipeline anterior de filtragem de servidores e mensagens:

```text
data/processed/software_messages.parquet
```

O comando de uso consolidado ficou:

```powershell
uv run python -m discord_disentanglement run `
  --input data/processed/software_messages.parquet `
  --guild-name Neo4j `
  --out data/processed/neo4j_threads `
  --threshold 0.50
```

Essa transicao mostrou que o pipeline precisava ser robusto nao apenas para os casos pensados no
fixture, mas tambem para ruido real de texto, links, anexos e formatos incompletos.

## 8. Endurecimento do pipeline durante o uso real

Um exemplo concreto dessa fase foi o tratamento de URLs malformadas. Durante a execucao em dados
reais, o pipeline encontrou uma string que fazia `urlparse()` levantar `ValueError` com a mensagem
`Invalid IPv6 URL`.

Isso levou a uma correcao pequena, mas importante:

- `extract_url_hosts()` passou a ignorar URLs invalidas em vez de abortar o processamento inteiro;
- foi adicionado um teste de regressao para garantir que um texto com URL valida e URL quebrada
  continue retornando apenas o host valido.

Esse ajuste representa bem a fase atual do desenvolvimento: menos mudanca conceitual grande, mais
endurecimento para suportar dados reais sem perder auditabilidade.

## 9. Evolucao da exportacao de grafos para Neo4j

No inicio, os artefatos de grafo eram suficientes para inspeção local:

- `graph.graphml`;
- `graph.json`;
- `graph_edges.csv`.

Esses formatos ajudam, mas nao entregam sozinhos a experiencia de explorar o grafo dentro do Neo4j.
Por isso, a funcionalidade evoluiu para gerar um pacote explicitamente importavel no banco.

Hoje, a pasta `exports/` inclui:

- `neo4j_users.csv`;
- `neo4j_threads.csv`;
- `neo4j_messages.csv`;
- `neo4j_authored_relationships.csv`;
- `neo4j_belongs_to_relationships.csv`;
- `neo4j_replies_to_relationships.csv`;
- `neo4j_import.cypher`.

O objetivo dessa mudanca foi sair de um grafo apenas exportado para um grafo realmente carregavel no
Neo4j Browser/Bloom, com nos `:User`, `:Message`, `:Thread` e relacoes `:AUTHORED`, `:BELONGS_TO`
e `:REPLIES_TO`.

## 10. Estado atual da funcionalidade

Neste ponto do desenvolvimento, a funcionalidade de disentanglement ja entrega:

- leitura de multiplos formatos de entrada;
- filtro por escopo de guild/canal;
- protecao basica de privacidade via anonimização;
- preservacao de links explicitos do Discord;
- inferencia heuristica auditavel de relacoes;
- extracao de threads e sumarizacao basica;
- interface HTML estatica para revisao;
- pacote de importacao para Neo4j;
- cobertura de teste para carga, normalizacao, scoring, exportacao e regressao de URL malformada.

Ainda nao entrega:

- classificacao real de incivilidade, toxicidade ou derailment;
- avaliacao quantitativa formal contra gold standard anotado;
- importacao automatica direta no Neo4j sem passo manual de copia para `import/`;
- uso obrigatorio de embeddings ou modelo supervisionado.

## 11. Como ler este historico junto com o resto da documentacao

Os documentos do projeto agora cumprem papeis diferentes:

- [docs/tasks/discord_disentanglement_neo4j.md](../tasks/discord_disentanglement_neo4j.md)
  registra a intencao inicial e o contrato desejado da funcionalidade;
- [NEO4J_DISENTANGLEMENT_INTERFACE_METHODOLOGY.md](./NEO4J_DISENTANGLEMENT_INTERFACE_METHODOLOGY.md)
  descreve a metodologia operacional consolidada;
- este arquivo registra o caminho incremental de desenvolvimento, os exemplos iniciais e as
  decisoes que transformaram a especificacao em implementacao.

Lidos em conjunto, esses tres artefatos mostram a evolucao completa: problema proposto, baseline
construido e estado atual da funcionalidade.