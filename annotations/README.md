# Registros de validação manual

Este diretório versiona **decisões humanas**, separadas dos escores automáticos. O conteúdo bruto das mensagens não deve ser adicionado ao Git.

`neo4j_channel_decisions.csv` é o inventário auditável do recorte inicial do servidor Neo4j (`guild_id=787399249741479977`). Todas as linhas começam como `pending` porque não foi localizado no repositório um artefato com as decisões manuais anteriores. A presença de um canal em `software_messages.parquet` não é interpretada como aprovação.

As colunas `automatic_class` e `automatic_score` foram preenchidas pelo perfil
`software.v1` (`profile_version=1.0.0`, SHA-256
`aeedf8d6029b34eccbad57dd95ec9f2bf2f267f898ea9e8b431109d134aec0bc`) sobre
o snapshot abaixo, com todos os 37 canais mantidos no inventário. Elas são apoio
à triagem e nunca substituem `manual_decision`.

Valores permitidos em `manual_decision`:

- `include`: incluir no corpus final;
- `exclude`: excluir do corpus final;
- `uncertain`: requer consenso ou segunda revisão;
- `pending`: ainda não revisado.

Preencha `annotator_id`, `reviewed_at`, `reason_code` e `notes` sem incluir texto bruto das mensagens. Uma segunda planilha ou colunas adicionais podem registrar o segundo anotador; divergências devem ser resolvidas por consenso e o acordo deve ser reportado.

Para a anotação de janelas conversacionais, siga
`docs/methodology/ANNOTATION_CODEBOOK.md`. O codebook separa evidência nativa
positiva de replies explícitos da ausência de observação, que nunca é rótulo
negativo.

O hash registrado corresponde ao arquivo-fonte `data/processed/software_messages.parquet` observado em 2026-08-18:

```text
sha256:5fe780aeee4465e1b48419f21973e4e6b31ce33bd398a8f90b7070fae1f76f19
```
