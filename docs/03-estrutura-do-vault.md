# Estrutura do vault

## Pastas

| Pasta | Conteúdo | Quem escreve |
| --- | --- | --- |
| `00-Sistema/` | `Inicio` (painel), `LEIA-ME`, `Perfil`, `config`, `Paineis/*.base`, `Templates/`, `Relatorios/`, `Exemplos/` | Você |
| `01-Inbox/` | Capturas brutas `C-XXXXX` | Agentes e você; você tria |
| `02-Sessoes/` | Sessões sem projeto `S-XXXXX` | Agentes |
| `10-Projetos/<slug>/` | `<slug>.md` (hub), `<slug> - Estado.md`, `Fatos/`, `Decisoes/`, `Sessoes/`, `Specs/` | Agentes (via MCP) e você |
| `20-Missoes/` | Missões `M-XXXXX` | Agentes e você |
| `30-Conhecimento/` | `Fatos/` e `Decisoes/` globais; `Instrucoes/` (seções do AGENTS.md levadas ao vault); `Recursos/` (sites/ferramentas externas) | Agentes e você |
| `40-Clientes/` | Hub por cliente (modelo `Cliente`) | Você |
| `50-Fontes/` | Material externo; `NotebookLM/` com respostas importadas `N-XXXXX` | Você e agentes |
| `60-Skills/` | Skills no formato Agent Skills (`<categoria>/<skill>/SKILL.md`); `sistema/` tem as do cofre | Você, o instalador (`sistema/`) e o Hermes ao aprender skills (com sua aprovação) |
| `80-Anexos/` | Imagens, PDFs e outros binários (o Obsidian salva aqui o que você cola) | Você |
| `90-Arquivo/` | Projetos encerrados; `Exportacoes-NotebookLM/` (não indexado) | Você / `cofre exportar-notebooklm` |
| `99-Privado/` | O que nenhuma IA deve receber pelo cofre; fora do git do vault | Você |

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

### Recurso (`tipo: recurso`)
Site, API ou ferramenta externa que a IA deve abrir/usar quando o assunto aparecer (não é fato nem evidência): `titulo`, `url` (link ou comando), `quando_usar`, `tags`, `projeto` (opcional). Ficam em `30-Conhecimento/Recursos/` (geral) ou `10-Projetos/<slug>/Recursos/` (do projeto). Crie pelo modelo `Recurso`, por `cofre recurso "<nome>" --url ... --quando "..."`, ou peça à IA ("guarda esse site"); a busca por relevância mostra o recurso sozinha e a IA abre o link só quando servir.

### Instrução (`tipo: instrucao`)
Seção do seu AGENTS.md levada para o vault por `cofre agents-md dividir`: `titulo`, `origem`, `tags`, `aliases`. Aparece para a IA como "instrução sua" quando o assunto surge.

### Outras
`moc` (mapa do assunto: lista de links para as notas de um tema), `captura` (inbox, `status: pendente`), `fonte` (`origem`, `confiabilidade`), `perfil`, `config`. Notas sem `tipo` (como os `LEIA-ME`) são ignoradas pelo motor.

## Skills (`60-Skills/`)

Cada skill é uma pasta com `SKILL.md` (frontmatter `name`, igual ao nome da pasta, e `description`) e, se precisar, `references/` e `scripts/`. Uma pasta de categoria no meio é opcional. O motor não indexa essas pastas como notas; elas são lidas pelos agentes:

| Agente | Como lê |
| --- | --- |
| Hermes | `skills.create_dir` = `60-Skills` (lê tudo e cria as skills novas aqui) |
| OpenCode V2 | `"skills": ["<vault>/60-Skills"]` no `opencode.json` |
| OpenCode V1 | Cópia achatada em `~/.config/opencode/skills/<id>/` feita pelo plugin a cada início (marcada com `.cofre-sync`; skills suas nessa pasta não são tocadas) |

Comandos: `cofre skills listar`, `cofre skills verificar`, `cofre skills sincronizar`. O painel `Skills.base` lista todas.

## Notas livres e busca por relevância

### Como escrever notas que a IA acha (resumo da sua pesquisa)

- **Título**: uma frase que diz a ideia ("Tailwind liga o tema escuro pela classe dark"), sem ID no nome. Atalhos e siglas vão em `aliases`, que a busca também usa.
- **`description`**: uma linha dizendo do que a nota trata. É ela que a IA recebe como resumo do ponteiro, em vez da primeira linha do texto. `description` é uma propriedade que o próprio Obsidian reconhece; `resumo` também funciona.
- **Tags**: de 2 a 5, planas (`#pentest`, `#frontend`). Use aninhadas só para estado (`#status/rascunho`). Mais de 5 tags indica que a nota trata de várias coisas e vale dividir.
- **MOC (mapa do assunto)**: com 3 ou mais notas sobre um tema, crie um MOC pelo modelo `MOC` (ou ponha a tag `moc`). Quando o assunto aparece, a IA recebe primeiro o mapa e abre só o que servir, o que gasta menos tokens que vários ponteiros soltos.
- **Propriedades**: nomes minúsculos sem espaço (`quando_usar`), sempre do mesmo tipo em todo o vault, sem YAML aninhado e com links entre aspas (`projeto: "[[loja]]"`).
- **Arquivo morto**: o que está em `90-Arquivo/` não entra na busca automática por mensagem, mas `cofre_buscar` ainda encontra.
- **Renomear e mover**: faça no Obsidian, que atualiza os links. Pelo terminal (`mv`) os links quebram.
- **Um assunto por nota** (algumas centenas de palavras), com pelo menos um `[[link]]` para outra nota ou para o MOC do tema. Nota longa não é proibida (fichamento, relatório), mas ponha títulos `##`: `cofre_ler` de nota com mais de `ler_max_chars` (6000 caracteres) devolve o começo e a lista de seções, e a IA pede só a seção útil (`secao='Etapa 3'`). Sem títulos, ela só consegue ler inteira.
- **Inbox**: capture sem formatar e trie depois de um ou dois dias; o que sobrar vira nota em `30-Conhecimento/` reescrita com as suas palavras.
- **Anexos**: PDF/imagem não é lido pela IA. Crie uma fonte em `50-Fontes/` (template Fonte) com `anexo: "[[arquivo.pdf]]"`, `description` e os trechos importantes em texto.

O `cofre revisar` aponta o que foge disso: notas sem nenhum link, temas com 3 ou mais notas sem MOC, notas muito longas ou longas sem títulos e itens parados na inbox.

As notas que o cofre cria (fatos, decisões, specs) continuam com o ID no nome (`F-7K3PQ ...`). Os agentes citam esses IDs, e eles garantem nome único quando um fato refutado e a correção dele têm textos parecidos. Você vê essas notas pelos painéis, que mostram a afirmação e não o nome do arquivo.

Qualquer nota Markdown fora de `00-Sistema/` entra na busca, mesmo sem `tipo` nem frontmatter: suas anotações em `30-Conhecimento`, `40-Clientes`, `50-Fontes` etc. A cada mensagem, os plugins procuram ali o que tem a ver com o assunto e apontam para a IA (detalhes em [01-arquitetura.md](01-arquitetura.md)). Para uma nota ser achada:

- título descritivo (o título pesa 3x o corpo);
- `tags` e `aliases` com os nomes que você usa para o assunto, inclusive em outro idioma ou abreviado (ex.: `aliases: [teste de intrusão, pentest, pentesting]`), porque a busca é por palavras, não por sinônimos;
- um assunto por nota funciona melhor que uma nota gigante.

O índice fica em `.cofre/indice.json` (pasta oculta, ignorada pelo Obsidian e pelo git). Pode apagar à vontade; ele é refeito.

## Painéis (Bases)

Bases é plugin nativo do Obsidian (sem plugins da comunidade). Os arquivos `.base` ficam em `00-Sistema/Paineis/` e excluem `00-Sistema/` dos resultados globais. Todas começam com um filtro por `tipo` ou pasta, para não varrer o vault inteiro quando ele crescer.

| Base | Visões |
| --- | --- |
| `Fatos.base` | Hipóteses abertas, Verificados, Revisão vencida, Contestados, Armadilhas (refutados), Por status (kanban) |
| `Projeto.base` | Embutido no hub de cada projeto (`this.file`): Hipóteses, Verificados, Contestados e armadilhas, Decisões, Sessões, Specs |
| `Projetos.base` | Tabela e cartões |
| `Decisoes.base` | Propostas aguardando você, Aceitas, Todas |
| `Missoes.base` | Quadro (kanban por status), Tabela |
| `Specs.base` | Quadro (kanban por status: rascunho, aprovada, em execução, concluída), Tabela |
| `Recursos.base` | Sites, APIs e ferramentas externas (título, quando usar, url) |
| `Sessoes.base` | Recentes (14 dias), Todas |
| `Inbox.base` | Para triar (capturas das IAs), Tudo na inbox (inclui as suas) |
| `Skills.base` | Skills em `60-Skills` (nome, status, quando usar, fontes, pasta) |

`00-Sistema/Inicio.md` junta as visões que pedem ação sua. Ordenação pode ser ajustada pelo menu Sort de cada visão (fica salva no `.base`).

## Configuração do vault

`00-Sistema/config.md` (propriedades editáveis pelo Obsidian): `politica_verificacao`, `validade_padrao_dias`, `hipotese_antiga_dias`, `ancora_a_cada_turnos`, `lembrar_checkpoint_apos_turnos`, `git_autocommit`, `contexto_max_chars`, `contexto_sistema_max_chars`, `fatos_verificados_no_contexto`, `ler_max_chars`, `pastas_privadas` e as de relevância e specs. A própria nota explica cada uma.

## Pasta privada e dados sensíveis

`99-Privado/` (e as pastas listadas em `pastas_privadas` no `config.md`) é para o que você quer no Obsidian mas não quer entregar a nenhuma IA: dados de clientes, contratos, anotações pessoais.

| Camada | O que acontece |
| --- | --- |
| Cofre (Hermes e OpenCode) | Fora do índice, da busca, do bloco de relevância, do contexto, da revisão e da exportação para o NotebookLM. `cofre_ler` recusa o caminho. |
| Plugin do OpenCode (hooks V1) | Bloqueia `read`, `edit`, `glob`, `grep`, `list`, `bash` e demais ferramentas cujos argumentos apontem para a pasta; tira as linhas com o caminho dela da saída de `glob`/`grep`/`list`/`bash`. |
| Git do vault | `99-Privado/` está no `.gitignore` do template (`cofre init` acrescenta a linha em vaults antigos). O `cofre revisar` dá erro se uma pasta privada estiver versionada ou fora do `.gitignore`. |
| Hermes | O plugin não bloqueia ferramentas de arquivo/terminal; vale a exclusão do cofre e a regra no protocolo. |

Não é criptografia: um agente com terminal livre ainda pode ler o disco por caminhos que nenhuma regra prevê. Senhas, tokens e chaves não ficam nem aqui: use um gerenciador de senhas e registre no vault só onde a credencial fica (o cofre bloqueia credenciais nas escritas e o `cofre revisar` procura nas notas).

Sincronização e backup (da sua pesquisa, resposta 13; confirme preços e recursos atuais nos sites oficiais):

- **Obsidian Sync** tem criptografia ponta a ponta e permite excluir pastas da sincronização (deixe `99-Privado/` fora dos dispositivos móveis se quiser).
- **Git** é texto puro: o `.gitignore` resolve as pastas privadas; para um remoto no GitHub/GitLab, repositório privado e, se precisar, `git-crypt`.
- **iCloud/Drive/Dropbox** sincronizando o vault em tempo real: evite (conflitos, arquivos descarregados, sem criptografia por arquivo).
- **Sincronizar não é backup**: apagou num lugar, apaga em todos. Tenha uma cópia versionada fora da máquina, por exemplo `rclone` com remoto `crypt` (cifra conteúdo e nomes) e `--backup-dir` para guardar versões alteradas ou apagadas.

## Git no vault

Recomendado (`--git` no instalador). Com `git_autocommit: true`, cada escrita de agente vira um commit `cofre: fato F-XXXXX (verificado) por opencode/glm-4.6`; o commit inclui só os arquivos que o cofre gravou (anexos e notas suas entram quando você mesmo commitar). Para desfazer o que um agente gravou: `git log` e `git revert <commit>`. O `.gitignore` do template ignora `workspace*.json` do Obsidian, a lixeira, o lock, as exportações e `99-Privado/`.

Evite deixar o vault dentro do OneDrive/iCloud sincronizando em tempo real: conflitos de sincronização e latência de leitura atrapalham agentes. Prefira git (ou Obsidian Sync) para levar o vault a outra máquina.

## Exemplos

`00-Sistema/Exemplos/exemplo-loja/` tem um projeto fictício gerado pelo próprio motor (fato verificado, hipótese, refutado com correção, contestado, decisão aceita e proposta, estado, sessão e missão). As notas têm `exemplo: true`, então agentes e painéis globais as ignoram. Apague quando quiser.
