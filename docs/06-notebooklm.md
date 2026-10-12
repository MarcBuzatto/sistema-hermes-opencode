# NotebookLM

> Status: revisado com a sua pesquisa ([`docs/pesquisa/respostas-notebooklm.md`](pesquisa/respostas-notebooklm.md), resposta 10 para o fluxo pesquisa -> skill). Limites do NotebookLM mudam: confirme na ajuda oficial.

## Papel de cada ferramenta

| | Obsidian (Cofre) | NotebookLM |
| --- | --- | --- |
| Função | Fonte de verdade, memória das IAs, edição | Análise, síntese e perguntas sobre um conjunto fechado de fontes, com citações |
| Quem escreve | Você e os agentes (com regras) | Ninguém escreve "verdade" ali; ele gera respostas, resumos, guias, mapas mentais, áudio |
| Confiabilidade do que sai | Depende do status de cada nota | Síntese externa: útil para orientar, não é fonte primária |

Regra central: **o que volta do NotebookLM nunca entra como fato verificado**. Entra como fonte (`tipo: fonte`, `confiabilidade: sintese-externa`) e, se virar fato, nasce como hipótese citando a fonte, até ser conferido no código, na documentação oficial ou com você.

## Exportar do cofre para o NotebookLM

```bash
cofre exportar-notebooklm loja-acme
cofre exportar-notebooklm loja-acme --hipoteses   # inclui arquivo separado e rotulado de hipóteses
```

Gera em `90-Arquivo/Exportacoes-NotebookLM/<data>-<projeto>/` (pasta não indexada pelo motor nem pela busca do Obsidian):

| Arquivo | Conteúdo |
| --- | --- |
| `01 Visao geral` | Hub do projeto, estado atual, missões |
| `02 Fatos verificados` | Cada fato com evidência, contexto e datas |
| `03 Decisoes` | Decisões aceitas e substituídas |
| `04 Diario de sessoes` | Checkpoints em ordem cronológica (marcado como escrito por agentes) |
| `05 Armadilhas e conflitos` | Refutados (com o correto), contestados e obsoletos |
| `06 HIPOTESES NAO VERIFICADAS` | Só com `--hipoteses` |

Cada arquivo começa com a legenda de status e a instrução para citar o status ao responder. A consolidação existe porque o NotebookLM limita fontes por notebook; um projeto vira 5 ou 6 fontes. Cada arquivo é recusado acima de 400 mil palavras.

Fluxo sugerido: um notebook por projeto (ou por cliente). Ao reexportar, apague as fontes antigas do notebook e envie as novas, para não misturar versões.

Limites citados em guias de 2026 (confirme na ajuda oficial, eles mudam): 50 fontes por notebook no plano gratuito, mais em planos pagos; cada fonte até cerca de 500 mil palavras ou 200 MB; Markdown e texto puro aceitos como upload.

## Importar do NotebookLM para o cofre

Copie a resposta/briefing do NotebookLM e:

```bash
cofre importar-notebooklm resposta.md --titulo "Briefing de arquitetura" --projeto loja-acme --notebook "Loja Acme"
# ou colando no stdin:
cofre importar-notebooklm - --titulo "Riscos do checkout" --projeto loja-acme
```

Cria `50-Fontes/NotebookLM/N-XXXXX <data> <título>.md`. Depois, para cada afirmação útil, peça a um agente (skill `cofre-notebooklm`) para registrar como hipótese com evidência `nota :: N-XXXXX :: <trecho>`, e verificar na origem antes de promover.

## Por que não automatizar o NotebookLM

O NotebookLM de consumidor não tem API pública oficial; as integrações "MCP para NotebookLM" que circulam usam automação de navegador sobre a sua conta, o que é frágil e pode violar os termos de uso. Existe API no NotebookLM Enterprise (Google Cloud), que faria sentido se você tiver esse plano. Por isso o fluxo aqui é manual e controlado: exportação gerada pelo cofre, importação explícita.

## Pesquisa -> conhecimento validado -> skill

Separação que a sua pesquisa recomenda (literatura vs. conclusões testadas), no formato do cofre:

| Etapa | Onde fica | Status |
| --- | --- | --- |
| Pesquisa bruta (resposta do NotebookLM, guia, artigo) | `50-Fontes/` (`tipo: fonte`, `N-XXXXX`), reflete a visão da fonte | Referência, nunca fato |
| Cada afirmação útil | Fato `F-XXXXX` com evidência `nota :: N-XXXXX :: <trecho>` | `hipotese` |
| Afirmação conferida (doc oficial, comando, código, você) | O mesmo fato, promovido com evidência `url`/`comando`/`arquivo`/`usuario` | `verificado` |
| Procedimento reutilizável | Skill em `60-Skills/<categoria>/<nome>/SKILL.md` com `status` e `fontes` | `rascunho` até os passos principais terem bloco "Comprovado" |

Na skill, cada passo separa o que foi testado (`> [!check] Comprovado`, citando o F-XXXXX) do que só a fonte diz (`> [!quote] Recomendação da fonte`, citando o N-XXXXX). Skill em `rascunho` aparece marcada no bloco de relevância e a IA avisa você antes de seguir; `cofre skills verificar` reclama de skill `verificada` sem `fontes`. O formato completo está em `60-Skills/LEIA-ME.md` e a IA o segue pela skill `cofre-notebooklm` ("transforma a pesquisa N-XXXXX numa skill").

Material longo (fichamento, relatório) pode ficar inteiro na fonte: ponha títulos `##` e a IA lê só a seção que precisa (`cofre_ler` com `secao`).

## Ainda em aberto

- Ajustar a divisão em arquivos ao que funcionar melhor nas suas perguntas (por tema, por período, por cliente).
- Avaliar formatos de saída do NotebookLM que valem guardar (guias de estudo, FAQ, linha do tempo, mapas mentais) e um modelo de nota para cada.
- Definir se notebooks transversais (conhecimento técnico, não projeto) devem ter exportação própria a partir de `30-Conhecimento`.
