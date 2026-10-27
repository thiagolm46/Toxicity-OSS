# Proveniencia da Selecao de Canais

O pacote [channel_selection_2026-10-07](channel_selection_2026-10-07/manifest.json)
preserva estatisticas agregadas e decisoes operacionais da selecao final de
Engenharia de Software: lista manual, valores historicos de
`interacting_authors`, manifestos originais, decisoes por canal e auditoria
contra os corpora. Nao contem texto de mensagens nem IDs de autores.

```powershell
python -m discord_filtering.channel_selection verify annotations/channel_selection_2026-10-07
```

Ele permite repetir as decisoes sobre valores congelados, nao recuperar o
calculo original de `interacting_authors`. Preserve o pacote sem sobrescrita e
inclua-o na release cientifica, com hash do manifesto publicado externamente.

O inventario exploratorio Neo4j com todas as decisoes `pending` foi retirado:
nao era o registro de selecao do corpus atual nem continha revisoes humanas.
As tabelas de futura anotacao sao geradas a partir das janelas amostradas,
conforme o [codebook](../docs/methodology/ANNOTATION_CODEBOOK.md).

Consulte [a documentacao da Etapa 2](../docs/methodology/CHANNEL_SELECTION_STAGE.md)
para a diferenca entre a triagem exploratoria 552/3 e a regra final 500 AND 5.