# Toxicity-OSS: Pipeline de Dados de Engenharia de Software

Preparacao auditavel de dados Discord para futura anotacao de relacoes
conversacionais em comunidades de Engenharia de Software. O repositorio cobre
aquisicao, selecao de servidores e canais, caracterizacao da populacao,
amostragem probabilistica, auditoria e preparacao de tabelas para anotacao.

Nao contem treinamento, inferencia, checkpoints, avaliacao de modelos de
disentanglement ou a pesquisa de comunidades de jogos. O resultado atual e
material preparado para anotacao, nao um benchmark humano concluido.

## Instalacao

```powershell
uv sync
```

Comandos instalados: `discord-data`, `discord-filter` e `discord-prepare`.
Sem instalacao dos entry points, use `python -m discord_data`,
`python -m discord_filtering` e `python -m discord_disentanglement`.

O nome interno `discord_disentanglement` permanece para nao invalidar imports,
comandos por modulo e registros de proveniencia existentes; ele agora contem
somente preparacao e auditoria dos dados.

## Etapas Atuais

| Etapa | Implementacao | Registro metodologico |
| --- | --- | --- |
| Aquisicao e extracao | [discord_data](discord_data/__main__.py) | [Servidores](docs/methodology/SERVER_FILTERING_STAGE.md) |
| Selecao de servidores | [discord_filtering](discord_filtering/cli.py), perfis de software | [Etapa 1](docs/methodology/SERVER_FILTERING_STAGE.md) |
| Selecao por participantes | [channel_selection.py](discord_filtering/channel_selection.py) | [Etapa 2](docs/methodology/CHANNEL_SELECTION_STAGE.md) |
| Caracterizacao da populacao | [population.py](discord_disentanglement/population.py) e [population_report.py](discord_disentanglement/population_report.py) | [Relatorio](docs/methodology/POPULATION_CHARACTERIZATION.md) |
| Quadro e sorteio de janelas | [sampling.py](discord_disentanglement/sampling.py) | [Desenho](docs/methodology/DISENTANGLEMENT_SAMPLING.md) |
| Auditoria da amostra | [sampling_audit.py](discord_disentanglement/sampling_audit.py) | [Auditoria](docs/methodology/SAMPLING_DESIGN_AUDIT.md) |
| Preparacao para anotacao | [annotation_bundle.py](discord_disentanglement/annotation_bundle.py) | [Codebook](docs/methodology/ANNOTATION_CODEBOOK.md) |

O detalhamento do fluxo esta em
[DISENTANGLEMENT_DATASET_PIPELINE.md](docs/methodology/DISENTANGLEMENT_DATASET_PIPELINE.md).

## Corpus e Proveniencia

O corpus atual e
`data/processed/filtering/software/participants_v2/messages.parquet`:
29 servidores, 297 canais e 11.897.859 registros.
A selecao recalcula as estatisticas diretamente da fonte original e exige
**pelo menos 500 registros brutos E cinco autores humanos distintos por canal**,
alem de aplicar a lista manual de exclusao. Participacao nao exige reply,
mencao ou conversa inferida. Os limites sao requisitos operacionais, nao uma
garantia estatistica de qualidade.

```powershell
python -m discord_filtering.channel_selection select --output <nova_selecao>
python -m discord_filtering.channel_selection verify <nova_selecao>
```

Fonte, decisoes, contagens e hashes estao no manifesto da selecao. Os corpora
e pacotes anteriores permanecem apenas como arquivo historico e nao alimentam
a pipeline vigente. Nao sobrescreva essas execucoes.

As mensagens brutas nao sao distribuidas pelo repositorio. Acesso e eventual
redistribuicao devem respeitar os termos do dataset-fonte.

## Caracterizacao, Sorteio e Auditoria

Os comandos abaixo gravam novos artefatos; diretorios de execucao existentes
nao sao substituidos silenciosamente. Para uma demonstracao, informe caminhos
novos com `--output`.

```powershell
discord-prepare population --output <nova_populacao>
discord-prepare population-report --input-dir <nova_populacao> --output <relatorio.md>
discord-prepare prepare-frame --channels <nova_populacao>/channels.csv --output <quadro.csv>
discord-prepare draw --frame <quadro.csv> --output <nova_amostra> --seed 20261014
discord-prepare audit-sampling --sample <nova_amostra> --output <nova_auditoria> --report <auditoria.md>
```

Consulte `discord-prepare <etapa> --help` para parametros e caminhos padrao.
O quadro e provisorio; os estados de elegibilidade devem ser revisados antes
de uma coleta definitiva. Somente registros sem texto e sem anexo, embed ou
sticker registrado sao chamados de nao utilizaveis. As restricoes tecnicas de
identificacao e ordenacao para janelas sao tratadas separadamente.

A execucao atual esta em `data/processed/disentanglement/sampling_participants_v2`;
a auditoria vigente esta em `data/processed/disentanglement/sampling_participants_audit_v2`.
O novo sorteio produziu 107 canais, 317 janelas e 17.921 mensagens-alvo.
Resultados de sensibilidade da auditoria nao sao experimentos de modelos.

## Preparacao para Anotacao

```powershell
discord-prepare build-annotation-bundle `
  --annotation-windows <nova_amostra>/annotation_windows.csv `
  --output <novo_bundle>
```

O pacote separa mensagens canonicas, pertencimento alvo/contexto, arestas
humanas e estados das fontes. Replies nativos sao evidencia silver observada;
sua ausencia nunca e um rotulo semantico negativo. O anotador registra arestas,
nao uma conversa prevista por algoritmo.

`publish-annotation-dataset` publica um bundle, codebook e uma tabela explicita
de arestas nativas fornecida por `--native-reply-edges`. O comando nao infere
arestas nem treina modelos. Sua ajuda lista os insumos obrigatorios.

## Testes e Manutencao

```powershell
python -m pytest tests -q
```

A limpeza de resultados antigos e caches dos modulos removidos e auditavel:

```powershell
python scripts/cleanup_legacy.py
python scripts/cleanup_legacy.py --apply --report data/maintenance/legacy_cleanup.json
```

Sem `--apply`, o script apenas apresenta o plano. Ele usa uma lista fechada de
caminhos legados e verifica referencias nos manifestos preservados. Os corpora,
o pacote historico, a populacao, a amostra atual, o artigo, as notas de pesquisa
e a auditoria vigente nao sao alvos de exclusao.