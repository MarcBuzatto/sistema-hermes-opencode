# Specs (SDD) e harness

Modelos fracos falham de um jeito previsível em trabalho longo: fazem coisa demais de uma vez, perdem o fio entre uma resposta e outra, dizem que terminaram sem testar e, quando o teste falha, mexem no teste. O cofre junta duas ideias para atacar isso:

- **Spec-Driven Development (SDD)**: antes de codar, escrever o que o sistema deve fazer, quebrar em tarefas e ter a aprovação do usuário (o fluxo do [GitHub Spec Kit](https://github.com/github/spec-kit): constitution, specify, plan, tasks, implement; e o formato de requisito EARS do Kiro, "QUANDO ..., O SISTEMA DEVE ...").
- **Harness engineering**: o que fica em volta do modelo (ferramentas, estado, verificações) é o que garante o resultado, não o prompt. Do artigo da Anthropic [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents): lista de funcionalidades com status que só muda depois de verificado, uma funcionalidade por vez, arquivo de progresso, teste de ponta a ponta. Da OpenAI ("harness engineering" com o Codex): AGENTS.md curto, como mapa, com o resto em documentos carregados quando precisa.

## O que foi implementado

| Problema | Mecanismo no cofre |
| --- | --- |
| Começa a codar sem entender | `cofre_spec`: objetivo, requisitos QUANDO/DEVE, fora de escopo, perguntas. Não dá para executar tarefa de spec em rascunho |
| Supõe em vez de perguntar | Perguntas em aberto bloqueiam a aprovação até serem respondidas |
| "Aprovação" inventada | Aprovar exige a citação literal do usuário (ou `--humano` no terminal), igual às decisões |
| Muda o escopo no meio | Requisitos e tarefas são congelados por hash na aprovação; mudou (pela ferramenta ou editando a nota), volta para rascunho |
| Faz tudo de uma vez | Uma tarefa em andamento por vez; iniciar outra é recusado |
| Perde o fio | Linha **AGORA** em toda chamada: spec, tarefa atual, comando de verificação e o próximo passo |
| Diz que terminou sem testar | `cofre_tarefa(acao='concluir')` roda o comando de verificação; a tarefa só fica pronta com código 0 |
| Quebra o que já funcionava | Na última tarefa, todas as verificações rodam de novo (regressão); a que quebrou é reaberta |
| Insiste no mesmo erro | 3 falhas seguidas bloqueiam a tarefa e a resposta manda parar e chamar o usuário |
| Marca pronto editando a nota | `cofre revisar` aponta tarefa marcada sem a verificação no histórico, e spec "concluída" com tarefa aberta |
| Esquece de salvar o progresso | Lembrete depois de N mensagens sem `cofre_checkpoint` (Hermes e OpenCode) |
| AGENTS.md grande demais | `cofre agents-md` divide em núcleo curto + instruções por assunto no vault |

## Agente `spec` (OpenCode) e personality `spec` (Hermes)

Escolhi **um** agente que cobre as duas ideias, porque no cofre elas são o mesmo laço: a spec é a lista de funcionalidades do harness, e as verificações são o que impede o modelo de mentir sobre o progresso.

- **OpenCode**: agente `spec` (Tab para trocar) e os comandos `/spec <o que construir>` e `/proxima`. O arquivo do agente não tem prompt próprio de propósito: na V2 o prompt de um agente substitui o prompt base do OpenCode (orientações de ferramentas e ajustes por modelo), o que piora modelos fracos. O plugin do cofre acrescenta as instruções do modo spec quando esse agente está ativo.
- **Hermes**: `/personality spec`. Personalities no Hermes são acrescentadas ao prompt, sem substituir nada. A skill `cofre-sdd` também fica disponível como `/cofre-sdd`.
- **Fora do modo spec**: as ferramentas e a linha AGORA funcionam com qualquer agente. Se houver spec aprovada no projeto, o modelo vê o próximo passo em toda chamada.

## Fluxo

```
/spec cupom de desconto no checkout
  -> IA lê o código, cria a spec (rascunho) com requisitos, tarefas e perguntas
  -> você responde as perguntas e diz "aprovado"
  -> IA: cofre_spec(acao='aprovar', citacao_usuario='aprovado')
/proxima
  -> cofre_tarefa(acao='proxima')       T1 em andamento
  -> IA implementa T1 e roda o teste
  -> cofre_tarefa(acao='concluir')      o cofre roda `npm test -- cupom`
       código 0 -> T1 concluída          código != 0 -> continua, saída do erro volta para a IA
/proxima ... até a última tarefa -> regressão -> spec concluída
```

A spec fica em `10-Projetos/<projeto>/Specs/E-XXXXX <título>.md`, legível no Obsidian, com o quadro em `00-Sistema/Inicio` (Kanban do Bases, Obsidian 1.14+) e a aba "Specs" no painel do projeto.

Pelo terminal:

```bash
cofre spec criar "Exportar relatório" --objetivo "Baixar CSV dos pedidos" \
  --requisito "QUANDO clicar em exportar, O SISTEMA DEVE baixar um CSV com os pedidos do filtro" \
  --tarefa "Rota GET /pedidos.csv | verificar: npm test -- exportar | cobre: R1"
cofre spec ver
cofre spec aprovar --humano
cofre tarefa proxima
cofre tarefa concluir
```

## Comandos de verificação: o que o cofre executa

O cofre roda o comando **sem shell**, na pasta do projeto, com `CI=1` e tempo máximo de `verificacao_timeout` (padrão 300 s). Executa sozinho:

- testes, lint, typecheck e build conhecidos: `npm test`, `npm run test:*|lint|typecheck|build|e2e|check...`, `pnpm`/`yarn`/`bun` equivalentes, `npx vitest|jest|tsc|eslint|playwright...`, `pytest`, `python -m pytest|unittest|mypy|ruff`, `uv run ...`, `go test|vet|build`, `cargo test|check|clippy|build`, `php artisan test`, `vendor/bin/phpunit`, `./gradlew test|check|build|lint`, `mvn test|verify`, `dotnet test|build`, `flutter test|analyze`, `make <alvo>`/`just <alvo>`;
- scripts do próprio projeto por caminho relativo (`./scripts/test.sh`, `python scripts/check.py`).

Recusa (vira verificação manual, que exige a confirmação do usuário): qualquer coisa com `;`, `|`, `&`, `>`, `<`, `` ` ``, `$`; `python -c`/`node -e`; pacote desconhecido via `npx`; caminho fora do projeto; scripts e alvos com nome de deploy, publish, release, migrate, seed, install, start, dev, watch etc. Comandos extras você libera em `verificacao_comandos` no `00-Sistema/config.md` (prefixo exato, ex.: `docker compose run --rm api pytest`).

**Risco que você precisa saber:** a verificação roda pelo servidor MCP do cofre, então não passa pelo pedido de permissão de bash do OpenCode/Hermes. Os comandos ficam congelados na aprovação da spec (você vê cada um antes de aprovar), mas o conteúdo de um teste ou script do projeto pode mudar depois; um agente com permissão de editar arquivos poderia, em tese, usar isso para executar código. É o mesmo nível de confiança de deixar o agente editar e rodar testes, mas sem o pedido de confirmação. Se isso não servir para algum projeto, use só `manual` nas tarefas dele.

## Timeouts dos clientes

Concluir uma tarefa pode levar minutos (verificação + regressão). O instalador ajusta o tempo máximo de chamada de ferramenta do servidor `cofre`:

| Cliente | Ajuste |
| --- | --- |
| Hermes | `mcp_servers.cofre.timeout: 1200` (o padrão do Hermes é 300 s) |
| OpenCode V2 | nada: o padrão de execução já é 12 h. Não use a chave `timeout` estilo V1 aqui: ela é migrada e reduz o limite |
| OpenCode V1 | `mcp.cofre.timeout: 1200000` (ms) |
| Codex CLI | `tool_timeout_sec = 1200` |
| Claude Code CLI | variável de ambiente `MCP_TOOL_TIMEOUT` (ms), se precisar |

A regressão tem limite próprio de 2x `verificacao_timeout`; se não terminar, a spec continua em execução e `cofre_tarefa(acao='regressao')` roda o que faltou.

## Por que Markdown e não JSON

O artigo da Anthropic usa JSON para a lista de funcionalidades porque o modelo reescreve JSON indevidamente com menos frequência que Markdown. Aqui a spec é Markdown para você ler e editar no Obsidian. A troca é compensada em código: definições congeladas por hash, status de tarefa mudando só pelas ferramentas (com o resultado da verificação no histórico) e a revisão apontando o que foi marcado à mão.

## AGENTS.md grande

```bash
cofre agents-md analisar                    # ~/.config/opencode/AGENTS.md ou ./AGENTS.md
cofre agents-md dividir                     # mostra o que faria
cofre agents-md dividir --aplicar --manter "Pentest"
```

As seções gerais e curtas (regras, estilo, idioma, git, até 12 linhas sem bloco de código) ficam no núcleo. As específicas viram notas `tipo: instrucao` em `30-Conhecimento/Instrucoes/`, que a busca por relevância entrega como "instrução sua: ..." quando o assunto aparece na conversa. A proposta de AGENTS.md enxuto vai para `00-Sistema/Relatorios/AGENTS-enxuto <data>.md`; o arquivo original nunca é alterado. Se você aplicar a proposta, as instruções específicas deixam de chegar aos apps que não usam o cofre (o que, no seu caso, é o desejado para o Claude e o ChatGPT nos apps oficiais).
