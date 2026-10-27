# Quadro de Participantes e Proveniencia

O quadro atual e
[channel_frame_participants_v2.csv](channel_frame_participants_v2.csv), gerado
apos a selecao de canais com pelo menos 500 registros brutos e cinco autores
humanos distintos. Ele contem 297 canais de 29 servidores e estados provisorios
de elegibilidade; nao sao rotulos de conversas anotadas.

A fonte, as estatisticas recalculadas, as decisoes por canal e os hashes estao
em `data/processed/filtering/software/participants_v2`. Verificacao:

```powershell
python -m discord_filtering.channel_selection verify
```

O pacote `channel_selection_2026-10-07` e o cadastro anterior sao somente arquivo
historico, preservados sem sobrescrita. Nao sao insumos da selecao, do quadro
ou da amostra vigentes. O fluxo ativo nao usa contadores de autores baseados
em replies ou mencoes.

Procedimento: [CHANNEL_SELECTION_STAGE.md](../docs/methodology/CHANNEL_SELECTION_STAGE.md).
Anotacao futura: [ANNOTATION_CODEBOOK.md](../docs/methodology/ANNOTATION_CODEBOOK.md).