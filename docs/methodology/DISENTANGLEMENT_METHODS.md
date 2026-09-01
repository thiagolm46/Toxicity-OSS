# Métodos de conversation disentanglement

**Versão metodológica:** 2.0 — 2026-08-18  
**Escopo executado:** servidor Discord Neo4j, pesquisa de comunidades de software  
**Regra de interpretação:** `direct_reply` é referência silver parcial, não gold conversacional completo

## Quadro científico

| Approach | Referência | Implementação local | Treino | Labels Discord | Papel experimental |
|---|---|---|---|---|---|
| `zero_shot` | Chi e Rudnicky (2021), apenas como motivação | `PILOT_PROXY` | nenhum; pesos fixos | não | baseline heurístico sem treino |
| `co_training` | Liu, Shi e Zhu (2021) | `PILOT_PROXY` | pseudo-rótulos em duas visões do treino Discord | não | exploratório não supervisionado |
| `weak_supervision` | ranker local; SBERT é somente referência relacionada | `PILOT_PROXY` | `direct_reply` do primeiro 60% | sim, fracos e somente treino | adaptação ao domínio Discord |
| `chi_zero_shot` | Chi e Rudnicky (2021) | `INSPIRED_BY` | response selection auto-supervisionado em logs IRC sem annotations | não | condição zero-shot academicamente motivada |
| `irc_transfer` | Kummerfeld et al. (2019) | `INSPIRED_BY` | relações anotadas do Ubuntu IRC | não | transferência supervisionada entre domínios |

Os valores `PILOT_PROXY` e `INSPIRED_BY` são deliberados. Nenhum dos cinco
módulos é apresentado como reprodução oficial, reimplementação fiel ou resultado
SOTA.

## Contrato comum

Todas as abordagens recebem exatamente a mesma tabela de pares candidatos. Cada
par contém apenas sinais derivados do texto, autores anonimizados, tempo, posição
e canal. A interface mínima está em `approaches/base.py`: `fit`, `score`, metadados
e capabilities. Ranking, seleção de links, criação de threads, métricas e escrita
de artefatos são responsabilidades comuns fora dos métodos.

Cada `manifest.json` registra título, autores, ano, venue, tipo de implementação,
repositório e commit de origem, checkpoint, adaptações, fonte de treino e usos de
`direct_reply` em treino e teste.

## `zero_shot`

- **Método local:** combinação fixa e documentada de 12 sinais comuns, seguida de
  transformação logística.
- **Treino:** nenhum. Os pesos são congelados.
- **Links e threads:** escolhe o candidato de maior score; a regra de abstenção é
  o quantil comum de scores da validação, sem labels. Os links selecionados formam
  componentes cronológicos.
- **Limitação:** preserva apenas a ideia de response selection zero-shot; não usa
  BERT, self-supervised training nem checkpoint de Chi e Rudnicky.

## `co_training`

- **Referência relacionada:** Hui Liu, Zhan Shi e Xiaodan Zhu, *Unsupervised
  Conversation Disentanglement through Co-Training*, EMNLP 2021,
  DOI `10.18653/v1/2021.emnlp-main.181`.
- **Método local:** uma visão conversacional e uma visão temática treinam rankers
  lineares, trocando pseudo-rótulos de alta confiança por três rodadas.
- **Treino:** somente candidatos do primeiro 60%; nenhum reply explícito.
- **Limitação:** o artigo usa redes neurais, classificador de sessão e reforço; o
  módulo local não reproduz essa arquitetura.

## `weak_supervision`

- **Método local:** regressão logística pairwise sobre diferenças entre um pai
  explícito positivo e até seis candidatos negativos do mesmo source.
- **Treino:** somente `direct_reply` válido do split de treino. Validação e teste
  permanecem mascarados.
- **Interpretação do score:** utilidade monotônica pairwise, não probabilidade
  calibrada de existir um link.
- **Limitação:** um candidato sem `direct_reply` não é um negativo conhecido. O
  uso como negativo é uma aproximação de weak supervision e deve ser declarado.

## `chi_zero_shot`

### Auditoria da fonte oficial

- Artigo: Ta-Chung Chi e Alexander I. Rudnicky, *Zero-Shot Dialogue
  Disentanglement by Self-Supervised Entangled Response Selection*, EMNLP 2021,
  DOI `10.18653/v1/2021.emnlp-main.400`.
- Repositório oficial encontrado:
  `https://github.com/chijames/zero_shot_dialogue_disentanglement`.
- Commit auditado: `ad0ef53ff192fae682ce6b3826619df936e89d9a`.
- O README requer os dados DSTC8 Subtask 2, um checkpoint BERT escolhido pelo
  usuário e treinamento local. Não há checkpoint treinado distribuído.
- Não foi encontrado arquivo de licença no snapshot auditado. Por isso, o código
  oficial não foi copiado nem incorporado.
- Dependências e arquitetura do código oficial incluem PyTorch, Transformers,
  encoder BERT hierárquico e atenção sobre o contexto.

### O que foi implementado

O adapter carrega `configs/approaches/chi_zero_shot.irc_self_supervised.v1.json`.
Esse checkpoint leve foi treinado em 60.000 exemplos de seleção de resposta:
contexto cronologicamente anterior como positivo e resposta de outra sessão IRC
como negativa. Os arquivos de annotation não foram abertos. Uma agregação por
máximo de features funciona como proxy pequeno e auditável da atenção; o score
individual do par é usado no ranking comum.

Isto preserva a condição científica “sem labels Discord e sem reply labels no
treino externo”, mas troca representação, objetivo detalhado e inferência neural.
A classificação correta é, portanto, `INSPIRED_BY`, não `REIMPLEMENTATION`.

## `irc_transfer`

### Escolha da fonte

Foram considerados Kummerfeld et al. (2019) e Yu e Joty (2020). A solução de
Kummerfeld foi escolhida porque o repositório oficial fornece o corpus anotado,
formato de relações, código e licenças explícitas. O código do modelo oficial usa
DyNet antigo e não distribui checkpoint compatível com Python 3.12. O método de
Yu e Joty exige uma pointer network end-to-end; não foi identificado checkpoint
oficial reutilizável durante esta auditoria. Adicionar essa arquitetura aumentaria
o escopo sem melhorar o controle do experimento de transferência inicial.

- Artigo selecionado: Jonathan K. Kummerfeld et al., *A Large-Scale Corpus for
  Conversation Disentanglement*, ACL 2019, DOI `10.18653/v1/P19-1374`.
- Repositório: `https://github.com/jkkummerfeld/irc-disentanglement`.
- Commit auditado: `82ed04f9627a45d0d6f2ec3c8683c88eb408a0d5`.
- Licenças: dados `CC-BY-4.0`; código `ISC`.
- O corpus publicado contém 77.563 mensagens anotadas. Nesta execução foram
  lidas 153 sessões e 196.146 linhas de chat dos logs de treino, com 69.395
  annotations. O cap determinístico percorreu 41.278 annotations: preservou
  múltiplos parents, identificou 9.908 self-links como início de conversa,
  10.945 arestas com endpoint de evento de sistema não textual, 20.425 reply
  edges textuais e 20.066 dentro da janela comum. O ajuste parou no cap de
  120.000 diferenças positivo–negativo.

O adapter usa um ranker pairwise com as mesmas 12 features do protocolo Discord.
Isto é uma adaptação de representação/formato e não fine-tuning supervisionado:
nenhuma mensagem, label ou `direct_reply` Discord participa do ajuste. A mudança
de DyNet para regressão logística impede chamá-lo de implementação oficial; o
rótulo é `INSPIRED_BY`.

Self-links do IRC são registrados como raízes e não viram exemplos positivos do
ranker pai-anterior. No Discord, a possibilidade de iniciar uma conversa é
representada pela abstenção posterior ao ranking, calibrada sem labels na
validação. Essa equivalência é aproximada e faz parte do domain shift.

## Regeneração dos checkpoints externos

```powershell
git clone https://github.com/jkkummerfeld/irc-disentanglement.git external/irc-disentanglement

uv run python -m discord_disentanglement.training.external_irc `
  --irc-repository external/irc-disentanglement `
  --output-dir configs/approaches `
  --seed 42
```

Os JSONs resultantes registram hashes dos arquivos-fonte, commit, regime, número
de exemplos, seed, ordem das features, normalização, pesos e bias.

## Future / Mapped Approaches

- **Liu et al. (2021), co-training oficial/reimplementado:** substituiria o proxy
  linear por message-pair classifier, session classifier e o processo de
  co-training do artigo. Adiado por exigir uma reprodução neural separada.
- **Huang et al. (2022), Bi-CL:** acrescentaria objetivos contrastivos de nível de
  utterance e de sessão, supervisionados e não supervisionados. Adiado para manter
  cinco condições comparáveis nesta fase.
- **Li et al., DiHRL:** acrescentaria perdas hierárquicas, decodificação easy-first
  e features globais. A identidade bibliográfica e o código exatos devem ser
  novamente verificados antes de qualquer alegação de reprodução.
- **Takada e Mori (2026), DLA/DLA+SC:** testa atribuição direta a diálogos por LLM
  e uso de contexto subsequente. Não foi incluído porque quebra a restrição
  strictly-past da comparação principal e introduz custo/model versioning.
- **Takada e Mori (2026), DD-GEPA:** otimiza prompts modulares para
  disentanglement. É trabalho recente e exige um protocolo separado para modelo,
  prompt, custo e contaminação; permanece somente mapeado.

## Referências primárias

- <https://aclanthology.org/2021.emnlp-main.400/>
- <https://aclanthology.org/2021.emnlp-main.181/>
- <https://aclanthology.org/P19-1374/>
- <https://aclanthology.org/2020.emnlp-main.512/>
- <https://aclanthology.org/2022.findings-emnlp.217/>
