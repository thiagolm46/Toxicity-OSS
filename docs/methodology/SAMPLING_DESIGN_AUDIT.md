# Desenho amostral: auditoria do piloto

Relatorio gerado por `python -m discord_disentanglement.sampling_audit`. Todos os calculos estao em `discord_disentanglement/sampling_audit.py`; os CSVs e hashes permitem conferir cada resultado. Nao houve alteracao da entrada, do cadastro ou do sorteio.

## 1. Escopo e verificacao do mecanismo

A inferencia e condicional aos servidores retidos e a elegibilidade provisoria. O mecanismo e estratificado no nivel dos canais (servidor x porte), com meses ativos e blocos sorteados nos niveis seguintes. Sortear meses nao e garantir cobertura de todos os segmentos temporais.

Resultado: **38/38 verificacoes aprovadas**. Os hashes das entradas e do corpus foram verificados antes da analise. A semente foi reexecutada e as probabilidades recalculadas independentemente do registro do sorteio.

| Medida | Valor |
| --- | --- |
| frame_channels | 407 |
| sampled_channels | 132 |
| sampled_servers | 31 |
| windows | 390 |
| target_messages | 18.012 |
| eligible_technical_targets | 11.884.832 |
| expected_windows | 389,63 |
| expected_targets | 18.627,99 |

A formula pi = (n_h/N_h)(m_c/M_c)(w_ct/W_ct) e o peso 1/pi sao validos para cada bloco e suas mensagens-alvo. A ultima janela incompleta deve continuar no quadro para manter probabilidade positiva. O produto nao transforma a amostra em autoponderada: medias brutas de mensagens nao estimam automaticamente a media do corpus.

A correspondencia entre os totais tecnicos do Parquet e os blocos tambem foi conferida. A estimativa Horvitz-Thompson do total observado na amostra nao precisa coincidir com o total conhecido em uma unica realizacao: essa diferenca nao e, isoladamente, erro de sorteio.

Como todos os tamanhos dos blocos sao conhecidos, e possivel calcular a variancia EXATA sob este desenho para essas quantidades auxiliares, sem usar rotulos humanos. A lei da variancia total e aplicada recursivamente aos tres sorteios SRS sem reposicao, incluindo as correcoes de populacao finita. Isso nao estima a variancia de toxicidade, arestas semanticas ou desempenho de modelos.

| Quantidade auxiliar | Observado | Esperanca exata | Desvio-padrao do desenho | Desvio padronizado |
| --- | --- | --- | --- | --- |
| ht_target_total | 18.888.286,00 | 11.884.832,00 | 4.760.858,14 | 1,471 |
| unweighted_target_count | 18.012,00 | 18.627,99 | 578,00 | -1,066 |
| short_window_count | 275,00 | 271,00 | 7,37 | 0,543 |

O desvio padronizado e descritivo, nao um p-valor ou teste normal: a distribuicao do estimador pode ser assimetrica. Uma discrepancia grande do total HT conhecido e alerta de instabilidade dos pesos, nao prova isolada de vies. Os componentes exatos por nivel estao em `known_total_variance.csv`.

A recursao para um sorteio de n entre N unidades com medias mu_i e variancias internas V_i usa Var(soma selecionada) = n(1-n/N) S_mu^2 + (n/N) soma V_i; para expansao HT, multiplica-se a media por N/n e a variancia por (N/n)^2. Estratos independentes sao somados.

## 2. Estratos e distribuicao resultante

Ha 75 estratos nao vazios; 27 sao censitarios no nivel dos canais. Os limites de porte sao operacionais, nao um resultado validado como otimo. Estratos preservam cobertura e probabilidades conhecidas; homogeneidade do volume nao demonstra homogeneidade dos resultados de disentanglement.

A tabela compara limites alternativos sem excluir canais nem refazer o sorteio. As cotas permanecem iguais, mas o custo esperado pode mudar. CV e apenas dispersao relativa do volume dentro de servidor x porte, nao variancia do estimador nem criterio suficiente para escolher cortes.

| Cenario | Corte pequeno | Corte medio | Canais previstos | Janelas esperadas | Alvos esperados | Fracao curta esperada | CV de volume | DP relativo HT auxiliar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frozen | 1.000,0 | 10.000,0 | 132 | 389,63 | 18.627,99 | 69,55% | 0,797 | 40,06% |
| half_cutpoints | 500,0 | 5.000,0 | 136 | 398,96 | 17.574,34 | 73,76% | 0,853 | 44,75% |
| double_cutpoints | 2.000,0 | 20.000,0 | 127 | 375,93 | 19.814,59 | 63,77% | 0,720 | 29,75% |
| volume_tertiles | 760,3 | 7.935,3 | 134 | 395,62 | 18.351,90 | 70,93% | 0,823 | 42,88% |

Distribuicao por porte; esperado significa soma das probabilidades no quadro elegivel, nao uma cota exata de mensagens:

| Porte | Alvos no quadro | Janelas esperadas | Janelas observadas | Alvos esperados | Alvos observados |
| --- | --- | --- | --- | --- | --- |
| large | 11.360.130 | 113,94 | 114 | 9.618,24 | 9.777 |
| medium | 476.545 | 131,17 | 132 | 6.538,94 | 6.045 |
| small | 48.157 | 144,52 | 144 | 2.470,82 | 2.190 |

Foram observadas 275 janelas incompletas; o desenho previa 271,00 em media. Ha 22 janelas com um alvo e 127 com ate dez. Meses uniformes e blocos finais tornam janelas curtas especialmente provaveis em canais pouco ativos; isso nao constitui falha automaticamente.

Distribuicoes completas por servidor, canal e mes estao em `allocation.csv`. A alocacao nao precisa reproduzir participacoes brutas do corpus: essa diferenca e intencional para evitar dominio dos maiores canais. Comparacoes aqui sao descritivas; proximidade ao valor esperado nao e teste de representatividade.

## 3. Adequacao das janelas ao disentanglement

Duracoes em horas; min/P25/mediana/media/P75/P90/P95/max. Mensagens singulares tem duracao zero, que nao demonstra troca rapida. Medidas abaixo descrevem somente a amostra realizada, nao estimativas ponderadas da populacao.

| Medida | Min | P25 | Mediana | Media | P75 | P90 | P95 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_count | 1,00 | 7,00 | 31,00 | 46,18 | 100,00 | 100,00 | 100,00 | 100,00 |
| target_duration_hours | 0,00 | 19,02 | 143,61 | 252,90 | 483,66 | 656,33 | 690,51 | 742,34 |
| visible_duration_hours | 0,00 | 364,07 | 1.699,24 | 4.026,21 | 5.159,10 | 10.857,06 | 17.284,89 | 36.037,56 |
| max_target_gap_hours | 0,00 | 12,44 | 76,63 | 119,91 | 188,42 | 302,03 | 398,72 | 647,42 |
| distinct_target_authors | 1,00 | 3,00 | 6,00 | 8,93 | 12,00 | 19,00 | 24,00 | 59,00 |
| largest_target_author_share | 0,07 | 0,25 | 0,38 | 0,43 | 0,51 | 0,83 | 1,00 | 1,00 |

Comparacao dos dominios completos e incompletos, sem mudar sua elegibilidade:

| Dominio | Janelas | Mediana de alvos | Duracao-alvo mediana (h) | Mediana de autores-alvo | Com proxy de entrelacamento |
| --- | --- | --- | --- | --- | --- |
| completo | 115 | 100,0 | 56,31 | 13,0 | 81,74% |
| incompleto | 275 | 13,0 | 278,05 | 5,0 | 24,73% |

283 janelas-alvo duram mais de 24 horas e 186 mais de sete dias; 35 possuem um unico autor-alvo. Sao indicadores para leitura humana, nao limiares de exclusao. Cortar por duracao ou numero de autores sem redefinir o estimando mudaria a populacao e poderia remover conversas esparsas legitimamente relevantes.

Ha sobreposicao de spans de componentes nativos distintos em 162 janelas e arestas nativas cruzadas em 133. Sao proxies observaveis de entrelacamento: componentes nativos podem fragmentar a mesma conversa semantica, e conversas reais podem nao usar replies explicitos. Ausencia do proxy nao comprova ausencia de conversas paralelas; sua presenca nao valida os rotulos semanticos.

Os componentes sao calculados com arestas nativas anteriores e visiveis; contam-se somente componentes que recebem uma aresta de fonte-alvo. Sobreposicao significa spans cronologicos intercalados; cruzamento usa pos(pai1) < pos(pai2) < pos(filho1) < pos(filho2), ou simetrico. Multiplos autores ou alta atividade sozinhos nao comprovam entrelacamento.

Uma janela operacional por contagem nao e necessariamente um episodio conversacional compacto: spans longos podem reunir trocas separadas por dias. A sobreposicao de arestas de longa duracao tambem nao comprova simultaneidade local. Portanto, nao se deve afirmar que todas as janelas sao casos uteis de entrelacamento apenas porque passaram nas restricoes tecnicas. A duracao e os silencios devem ser confrontados com leitura humana, preservando tambem casos esparsos e sem entrelacamento para avaliar a especificidade do benchmark.

### Contexto e truncamento observavel

| Status de antecedente nativo | Referencias de alvos |
| --- | --- |
| before_visible_context | 15 |
| parent_not_in_corpus | 93 |
| visible | 2.991 |

A sensibilidade abaixo mantem as mesmas fontes-alvo e varia apenas o numero de registros anteriores visiveis. O denominador de cobertura e restrito a antecedentes resolvidos, anteriores, no mesmo canal e tecnicamente ordenaveis. Nao inclui referencias ausentes do corpus, duplicadas ou de outros canais como se fossem falha de contexto.

| Registros anteriores | Referencias nativas | Resolvidas elegiveis | Visiveis | Cobertura das resolvidas |
| --- | --- | --- | --- | --- |
| 0 | 3099 | 3006 | 2801 | 93,18% |
| 50 | 3099 | 3006 | 2962 | 98,54% |
| 100 | 3099 | 3006 | 2981 | 99,17% |
| 200 | 3099 | 3006 | 2991 | 99,50% |
| 400 | 3099 | 3006 | 2993 | 99,57% |

Essa cobertura nao mede recuperacao de antecedentes semanticos desconhecidos nem determina automaticamente um contexto ideal. Aumentar contexto pode recuperar evidencia observada, mas tambem aumentar muito o custo e a duracao visivel em canais esparsos.

## 4. Ajustes necessarios e decisoes pendentes

1. **Correcoes do mecanismo:** corrigir qualquer verificacao reprovada antes de aceitar a amostra. Se todas passarem, nao ha evidencia nesta auditoria de erro de denominador, peso, cota, sobreposicao de alvos ou reproducao da semente.
2. **Estimando e pesos:** declarar se o objetivo e benchmark com cobertura entre canais, media entre canais ou media entre mensagens. Preservar as tres probabilidades e nao substituir pesos por volume bruto. Separar avaliacao do benchmark de inferencia populacional.
3. **Incerteza:** 148 meses sorteados tem uma unica janela observada apesar de multiplos blocos disponiveis. Nesse nivel nao ha replicacao para estimar diretamente a variancia dentro do mes sem suposicoes adicionais. Se intervalos design-based forem requisito, avaliar pelo menos duas janelas nos meses nao censitarios e rebalancear o orcamento antes de novo sorteio. Nao e necessario aumentar a amostra apenas para produzir um benchmark descritivo.
4. **Estratos:** manter os cortes atuais como provisao auditavel; nao adotar novos cortes apenas por parecerem mais equilibrados em volume. Comparar custo, cobertura e variacao dos resultados anotados antes de alegar eficiencia superior.
5. **Adequacao semantica:** usar o piloto humano para medir conversas simultaneas reais, antecedentes fora do contexto, ambiguidade e tempo de anotacao. Comparar blocos completos, caudas curtas e janelas de diferentes duracoes como dominios de analise, sem descarta-los antecipadamente.
6. **Elegibilidade:** a decisao sobre canais paralelos ao desenvolvimento permanece com a revisao tematica. Nao introduzir filtros por reply, autores ou duracao para resolver uma decisao de escopo.

O tamanho de Kish calculado apenas pelos pesos das mensagens e 822,99 para 18012 alvos. Nao e tamanho efetivo inferencial: ignora dependencia temporal, estratificacao e conglomerados. Bootstrap ingenuo de mensagens, ou de janelas sem respeitar os niveis do desenho, nao resolve a ausencia de replicacao.

## 5. Reproducao e artefatos

```powershell
python -m discord_disentanglement.sampling_audit
python -m pytest tests/test_sampling.py -q
```

A execucao recusa substituir a pasta de auditoria. Para repetir, use `--output <pasta_nova> --overwrite-report`; `--sample` permite auditar outro sorteio. `--report` permite escolher o documento gerado. Os artefatos incluem checks, probabilidades de todos os blocos, estratos, alocacao, sensibilidade dos cortes, diagnosticos de janelas, referencias nativas, sensibilidade de contexto, censo tecnico, resumo e manifesto.

Diretorio desta auditoria: `data\processed\disentanglement\sampling_design_audit_v3`. Semente do sorteio: `20261014`. As distribuicoes por porte e por tamanho de bloco estao em `window_distribution.csv`; cada janela pode ser inspecionada por `annotation_id` em `window_diagnostics.csv` e nos artefatos originais.

**Conclusao:** probabilidades corretas e utilidade semantica sao questoes distintas. O desenho pode ser executavel e probabilistico sem que todas as janelas mostrem entrelacamento. Esta auditoria nao certifica rotulos inexistentes e nao aplica novos filtros.
