# Pipeline do Dataset de Conversas Discord

## Visao geral

O objetivo e construir um dataset de conversas Discord desentrelaçadas em
comunidades de engenharia de software. O pipeline reduz progressivamente o
universo de dados ate chegar a janelas anotadas manualmente e a um codebook
calibrado.

## Etapa 1: selecionar servidores

**Pergunta:** quais servidores do Discord Unveiled pertencem ao dominio de
engenharia de software?

O filtro analisa metadados dos servidores, como nome, descricao e palavras-chave.
Ele procura sinais de programacao, desenvolvimento, DevOps, linguagens,
bancos de dados e ferramentas, e exclui dominios incompativeis, como jogos,
NSFW e cripto.

**Saida:** uma lista auditavel de servidores selecionados. Ela define onde os
dados serao coletados, mas ainda nao escolhe mensagens ou conversas.

Detalhes: [DISCORD_UNVEILED_FILTERING.md](DISCORD_UNVEILED_FILTERING.md).

## Etapa 2: selecionar canais conversacionais

**Pergunta:** dentro dos servidores selecionados, quais canais parecem conter
conversas tecnicas entre usuarios reais?

O filtro combina relevancia tecnica e adequacao conversacional. A relevancia
tecnica usa metadados e conteudo. A adequacao conversacional verifica se ha
participacao de varios autores humanos, interacoes por replies ou menções,
alternancia entre autores, baixa concentracao em uma unica pessoa e baixa
proporcao de bots.

**Saida:** canais priorizados para anotacao. Apenas canais tecnicamente A,
conversacionalmente adequados e com volume suficiente entram automaticamente
na fila principal; os demais podem ser revisados manualmente.

Detalhes: [DISCORD_UNVEILED_FILTERING.md](DISCORD_UNVEILED_FILTERING.md).

## Etapa 3: selecionar intervalos de anotacao

**Pergunta:** quais trechos de cada canal relevante devem ser classificados
para representar diferentes momentos da comunidade?

A amostragem seleciona janelas continuas de mensagens em pontos temporais
distintos do canal. Cada janela preserva mensagens anteriores como contexto,
mas apenas as mensagens-alvo entram na quantidade anotada. O tamanho da
amostra e justificado para estimar propriedades conversacionais, como a
proporcao de mensagens com antecedente semantico.

**Saida:** um conjunto rastreavel de intervalos temporais por canal, com meta
de mensagens-alvo, contexto, estrato temporal e semente de selecao.

Detalhes: [DISENTANGLEMENT_SAMPLING.md](DISENTANGLEMENT_SAMPLING.md).

## Etapa 4: definir o codebook e executar o piloto

**Pergunta:** como os anotadores devem decidir, de forma consistente, se uma
mensagem responde a outra ou inicia uma nova conversa?

Um piloto de classificacao aplica e aperfeicoa o codebook nas janelas
selecionadas. O piloto registra replies semanticos, ausencia de reply,
antecedentes fora do contexto, ambiguidade e inicios de conversa. As rodadas
piloto servem para comparar discordancias, consolidar regras e preparar a
anotacao em escala.

**Saida:** codebook validado, exemplos de decisoes e um protocolo consistente
para produzir arestas humanas. As conversas finais sao derivadas dessas
arestas, e nao atribuídas diretamente pelo anotador.

Detalhes: [ANNOTATION_CODEBOOK.md](ANNOTATION_CODEBOOK.md).

## Resultado esperado

O pipeline produz um dataset rastreavel: comunidades de software, canais com
interacao humana, janelas temporalmente distribuídas e anotacoes humanas de
relacoes de resposta. Cada etapa preserva seus criterios e artefatos para que
as decisoes possam ser auditadas e recalculadas.
