# Estrutura do vault

## Pastas

| Pasta | Conteúdo | Quem escreve |
| --- | --- | --- |
| `00-Sistema/` | `Inicio` (painel), `LEIA-ME`, `Perfil`, `config`, `Paineis/*.base`, `Templates/`, `Relatorios/`, `Exemplos/` | Você |
| `01-Inbox/` | Capturas brutas `C-XXXXX` | Agentes e você; você tria |
| `02-Sessoes/` | Sessões sem projeto `S-XXXXX` | Agentes |
| `10-Projetos/<slug>/` | `<slug>.md` (hub), `<slug> - Estado.md`, `Fatos/`, `Decisoes/`, `Sessoes/`, `Specs/` | Agentes (via MCP) e você |
| `20-Missoes/` | Missões `M-XXXXX` | Agentes e você |
| `30-Conhecimento/` | `Fatos/` e `Decisoes/` globais (máquina, ferramentas, conhecimento geral); `Instrucoes/` com as seções do seu AGENTS.md levadas para o vault | Agentes, você e `cofre agents-md` |
| `40-Clientes/` | Hub por cliente (modelo `Cliente`) | Você |
| `50-Fontes/` | Material externo; `NotebookLM/` com respostas importadas `N-XXXXX` | Você e agentes |
| `60-Skills/` | Skills no formato Agent Skills (`<categoria>/<skill>/SKILL.md`); `sistema/` tem as do cofre | Você, o instalador (`sistema/`) e o Hermes ao aprender skills (com sua aprovação) |
| `90-Arquivo/` | Projetos encerrados; `Exportacoes-NotebookLM/` (não indexado) | Você / `cofre exportar-notebooklm` |

Nomes de pasta são ASCII de propósito: agentes e shells de Windows lidam mal com acentos em caminhos. Títulos de notas podem ter acento.

## Identificadores

`F-` fato, `D-` decisão, `S-` sessão, `M-` missão, `C-` captura, `N-` fonte, `E-` spec, seguidos de 5 caracteres do alfabeto Crockford (sem I, L, O, U, para não confundir). O arquivo se chama `<ID> <slug-da-afirmação>.md` e o ID também vai em `aliases`. Agentes citam só o ID; o motor resolve.

## Propriedades por tipo

### Fato (`tipo: fato`)

| Propriedade | Exemplo |
| --- | --- |
| `id` | `F-1D69S` |
| `afirmacao` | `O banco de dados do projeto é PostgreSQL 16` |
| `status` | `hipotese` / `verificado` / `contestado` / `refutado` / `obsoleto` |
| `fonte` | `arquivo` / `execucao` / `documentacao` / `usuario` / `nota` / `inferencia` |
| `evidencia` | `- "arquivo :: /home/u/loja/docker-compose.yml:3 :: image: postgres:16"` |
| `evidencia_contraria` | Evidências de contestação/refutação |
| `projeto` | `"[[loja-acme]]"` (vazio = global) |
| `tags`, `criticidade` | `criticidade: alta` = sempre no contexto |
| `registrado_por`, `registrado_em` | `opencode/glm-4.6`, `2026-10-10` |
| `verificado_por`, `verificado_em`, `revisar_em` | Preenchidos ao verificar |
| `motivo`, `refutado_em`, `contestado_em`, `obsoleto_em` | Preenchidos nas mudanças de status |
| `substitui`, `substituido_por` | Ligação entre o fato errado e o correto |

Corpo: título, callout com o status, `## Evidência`, `## Contexto`, `## Histórico` (cada mudança com data e autor). Seções extras que você escrever são preservadas.

### Decisão (`tipo: decisao`)
`id`, `titulo`, `status` (`proposta`, `aceita`, `substituida`, `rejeitada`), `projeto`, `decidido_em`, `citacao_usuario`, `substitui`/`substituida_por`. Corpo: Decisão, Contexto, Alternativas consideradas, Consequências, Histórico.

### Estado (`tipo: estado`)
Um por projeto. `atualizado`, `atualizado_por`, `ultima_sessao`. Corpo: Foco atual, Próximos passos (checklist), Bloqueios, Último checkpoint. Reescrito a cada checkpoint.

### Sessão (`tipo: sessao`)
`id`, `projeto`, `agente`, `sessao_externa` (ID da sessão do OpenCode, quando disponível), `iniciada`, `atualizada`, `fatos`, `decisoes`. Corpo: checkpoints em ordem (`### HH:MM`).

### Projeto (`tipo: projeto`)
`nome`, `status`, `cliente`, `caminhos` (pastas locais; é isso que liga o diretório ao projeto), `repos` (remotos git normalizados, ex.: `github.com/org/repo`), `stack`, `criado`. Corpo com `![[Projeto.base]]`, que mostra hipóteses, verificados, armadilhas, decisões e sessões do projeto.

### Missão (`tipo: missao`)
`id`, `titulo`, `status` (`ativa`, `pausada`, `concluida`, `cancelada`), `projetos`, `criada`, `atualizada`. Corpo: Objetivo, Critérios de pronto, Passos (checklist), Log.

### Spec (`tipo: spec`)
`id`, `titulo`, `status` (`rascunho`, `aprovada`, `em_execucao`, `concluida`, `cancelada`), `projeto`, `aprovada_em`, `citacao_usuario`, `hash_aprovado`. Corpo: Objetivo, Requisitos (`- R1: ...`), Fora de escopo, Perguntas em aberto (`- [ ] P1: ...`), Plano, Tarefas (``- [ ] T1: descrição · cobre: R1 · verificar: `comando` ``; `[/]` em andamento, `[x]` concluída, `[!]` bloqueada, `[-]` cancelada), Histórico. Edite pelas ferramentas ou pelo terminal; mudar requisitos ou tarefas à mão depois da aprovação pede nova aprovação. Detalhes em [08-specs-e-harness.md](08-specs-e-harness.md).

### Instrução (`tipo: instrucao`)
Seção do seu AGENTS.md levada para o vault por `cofre agents-md dividir`: `titulo`, `origem`, `tags`, `aliases`. Aparece para a IA como "instrução sua" quando o assunto surge.

### Outras
`captura` (inbox, `status: pendente`), `fonte` (`origem`, `confiabilidade`), `perfil`, `config`. Notas sem `tipo` (como os `LEIA-ME`) são ignoradas pelo motor.

## Skills (`60-Skills/`)

Cada skill é uma pasta com `SKILL.md` (frontmatter `name`, igual ao nome da pasta, e `description`) e, se precisar, `references/` e `scripts/`. Uma pasta de categoria no meio é opcional. O motor não indexa essas pastas como notas; elas são lidas pelos agentes:

| Agente | Como lê |
| --- | --- |
| Hermes | `skills.create_dir` = `60-Skills` (lê tudo e cria as skills novas aqui) |
| OpenCode V2 | `"skills": ["<vault>/60-Skills"]` no `opencode.json` |
| OpenCode V1 | Cópia achatada em `~/.config/opencode/skills/<id>/` feita pelo plugin a cada início (marcada com `.cofre-sync`; skills suas nessa pasta não são tocadas) |

Comandos: `cofre skills listar`, `cofre skills verificar`, `cofre skills sincronizar`. O painel `Skills.base` lista todas.

## Notas livres e busca por relevância

Qualquer nota Markdown fora de `00-Sistema/` entra na busca, mesmo sem `tipo` nem frontmatter: suas anotações em `30-Conhecimento`, `40-Clientes`, `50-Fontes` etc. A cada mensagem, os plugins procuram ali o que tem a ver com o assunto e apontam para a IA (detalhes em [01-arquitetura.md](01-arquitetura.md)). Para uma nota ser achada:

- título descritivo (o título pesa 3x o corpo);
- `tags` e `aliases` com os nomes que você usa para o assunto, inclusive em outro idioma ou abreviado (ex.: `aliases: [teste de intrusão, pentest, pentesting]`), porque a busca é por palavras, não por sinônimos;
- um assunto por nota funciona melhor que uma nota gigante.

O índice fica em `.cofre/indice.json` (pasta oculta, ignorada pelo Obsidian e pelo git). Pode apagar à vontade; ele é refeito.

## Painéis (Bases)

Bases é plugin nativo do Obsidian (sem plugins da comunidade). Os arquivos `.base` ficam em `00-Sistema/Paineis/` e excluem `00-Sistema/` dos resultados globais.

| Base | Visões |
| --- | --- |
| `Fatos.base` | Hipóteses abertas, Verificados, Revisão vencida, Contestados, Armadilhas (refutados), Por status (kanban) |
| `Projeto.base` | Embutido no hub de cada projeto (`this.file`): Hipóteses, Verificados, Contestados e armadilhas, Decisões, Sessões, Specs |
| `Projetos.base` | Tabela e cartões |
| `Decisoes.base` | Propostas aguardando você, Aceitas, Todas |
| `Missoes.base` | Quadro (kanban por status), Tabela |
| `Specs.base` | Quadro (kanban por status: rascunho, aprovada, em execução, concluída), Tabela |
| `Sessoes.base` | Recentes (14 dias), Todas |
| `Inbox.base` | Capturas pendentes |
| `Skills.base` | Skills em `60-Skills` (nome, quando usar, pasta) |

`00-Sistema/Inicio.md` junta as visões que pedem ação sua. Ordenação pode ser ajustada pelo menu Sort de cada visão (fica salva no `.base`).

## Configuração do vault

`00-Sistema/config.md` (propriedades editáveis pelo Obsidian): `politica_verificacao`, `validade_padrao_dias`, `hipotese_antiga_dias`, `ancora_a_cada_turnos`, `lembrar_checkpoint_apos_turnos`, `git_autocommit`, `contexto_max_chars`, `contexto_sistema_max_chars`, `fatos_verificados_no_contexto`. A própria nota explica cada uma.

## Git no vault

Recomendado (`--git` no instalador). Com `git_autocommit: true`, cada escrita de agente vira um commit `cofre: fato F-XXXXX (verificado) por opencode/glm-4.6`. Para desfazer o que um agente gravou: `git log` e `git revert <commit>`. O `.gitignore` do template ignora `workspace*.json` do Obsidian, a lixeira, o lock e as exportações.

Evite deixar o vault dentro do OneDrive/iCloud sincronizando em tempo real: conflitos de sincronização e latência de leitura atrapalham agentes. Prefira git (ou Obsidian Sync) para levar o vault a outra máquina.

## Exemplos

`00-Sistema/Exemplos/exemplo-loja/` tem um projeto fictício gerado pelo próprio motor (fato verificado, hipótese, refutado com correção, contestado, decisão aceita e proposta, estado, sessão e missão). As notas têm `exemplo: true`, então agentes e painéis globais as ignoram. Apague quando quiser.
