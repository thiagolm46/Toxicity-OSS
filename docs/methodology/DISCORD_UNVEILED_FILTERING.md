# Curadoria do Discord Unveiled para Engenharia de Software

## Escopo Atual

Este repositorio demonstra a preparacao de dados de comunidades de Engenharia
de Software. Nao executa modelos de disentanglement nem um fluxo de pesquisa
de comunidades de jogos. Mencoes a jogos ou cripto em perfis de software sao
evidencias de exclusao ou de especializacao, nao outra pipeline.

## Etapa 1: Servidores

O scoring de metadados e a revisao humana selecionaram 31 servidores. O perfil
[software.engineering.v2.json](../../configs/filtering/software.engineering.v2.json)
e dedicado a servidores e nao tem politica de scoring de canais. Os perfis
de software anteriores permanecem como configuracoes de suporte e proveniencia,
nao como resultados de pesquisa independentes.

O registro vigente, as limitacoes da revisao e os artefatos estao em
[SERVER_FILTERING_STAGE.md](SERVER_FILTERING_STAGE.md).

## Etapa 2: Canais

A selecao final usou uma lista exata de nomes a excluir e a regra historica
`total_messages < 500 AND interacting_authors < 5`. Nao foi produzida pelo
scoring generico A-D. A triagem exploratoria 552/3 nao foi uma mascara anterior
a regra final. Justificativa estatistica para essa mudanca e o predicado
original de autores interagentes nao foram recuperados.

O pacote [historico](../../annotations/channel_selection_2026-10-07/manifest.json)
preserva os valores e decisoes para replay e auditoria. Isso nao reconstitui
o calculo da metrica a partir das mensagens nem razoes humanas nao registradas.
O corpus preservado contem 407 canais e 11.918.028 registros.

Procedimento e comandos: [CHANNEL_SELECTION_STAGE.md](CHANNEL_SELECTION_STAGE.md).
O schema dos perfis reutilizados esta em
[FILTER_PROFILE_REFERENCE.md](FILTER_PROFILE_REFERENCE.md).

## Etapas Seguintes

Caracterizacao, amostragem probabilistica e auditoria:
[DISENTANGLEMENT_SAMPLING.md](DISENTANGLEMENT_SAMPLING.md).
Preparacao e calibracao da anotacao: [ANNOTATION_CODEBOOK.md](ANNOTATION_CODEBOOK.md).
Visao completa: [DISENTANGLEMENT_DATASET_PIPELINE.md](DISENTANGLEMENT_DATASET_PIPELINE.md).