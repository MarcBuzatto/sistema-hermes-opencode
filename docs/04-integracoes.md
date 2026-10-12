# Integrações

## Princípio: nenhum arquivo de instruções é editado

O cofre não escreve em `AGENTS.md`, `SOUL.md`, `CLAUDE.md` nem em nenhum outro arquivo de instruções. Esses arquivos costumam estar grandes demais para o modelo ler inteiros, e somar mais texto neles piora o problema. O protocolo chega por três canais curtos:

| Canal | Conteúdo | Tamanho |
| --- | --- | --- |
| Plugin (Hermes e OpenCode) | Pacote de contexto do projeto com 9 regras no fim, no prompt de sistema | até `contexto_sistema_max_chars` (padrão 3500 caracteres, regras incluídas) |
| Instruções do servidor MCP | Resumo das regras (para clientes sem plugin, como Claude Code e Codex) | ~900 caracteres |
| Skill `cofre-protocolo` | Protocolo completo e referência | carregada só quando o modelo precisa |

Se uma versão antiga do instalador tiver deixado um bloco `### >>> COFRE ...` nesses arquivos, o instalador atual remove só esse bloco.

## Quem usa o cofre e quem não usa

| Ferramenta | Usa o cofre? | Como |
| --- | --- | --- |
| Hermes Agent (qualquer modelo: OpenCode Zen/Go, Claude, GPT etc.) | Sim | Plugin, MCP, skills do vault, ajustes de memória |
| OpenCode (V1 >= 1.18.29 e V2) | Sim | Plugin, MCP, comandos, skills do vault |
| Claude Code CLI | Opcional (`--claude-code`) | Só o servidor MCP (escopo usuário) |
| Codex CLI | Opcional (`--codex`) | Só o servidor MCP (`config.toml`) |
| Claude Desktop (chat) | Não | Nenhum arquivo dele é alterado |
| ChatGPT app | Não | Nenhum conector ou arquivo é criado |

O isolamento é estrutural: só quem tem o servidor MCP `cofre` (e, no Hermes/OpenCode, o plugin) usa o cofre. Casos de borda:
- A aba **Code** do app Claude Desktop é o Claude Code; por isso `--claude-code` vem desligado.
- O app **Codex** compartilha `~/.codex` com o Codex CLI; mesma lógica para `--codex`.

## Hermes Agent

Linux/macOS/WSL: `~/.hermes`; Windows nativo: `%LOCALAPPDATA%\hermes`; ou `HERMES_HOME`.

| Item | O que muda | Por quê |
| --- | --- | --- |
| `plugins/cofre/` | Plugin Python | Seção estável do prompt de sistema com o contexto do projeto e as regras (preservada na compactação). No Hermes sem `register_system_prompt_section` (o 0.19.0 do PyPI não tem), o mesmo contexto vai junto da primeira mensagem e de novo depois de uma compactação; o Hermes guarda esse texto com a mensagem e o reenvia nos turnos seguintes. A cada mensagem, bloco com o que o vault tem sobre o assunto (sem repetir itens já mostrados na sessão), a linha AGORA da spec ativa (sem spec, âncora com o foco a cada N turnos) e lembrete depois de N mensagens sem checkpoint; aviso ao fechar sessão longa sem checkpoint; `pre_tool_call`/`transform_tool_result` protegem a pasta privada |
| `mcp_servers.cofre` | Servidor MCP stdio, `timeout: 1200` | As 13 ferramentas, que no Hermes se chamam `mcp__cofre__cofre_*` (o plugin avisa o modelo). O timeout cobre a verificação de tarefas de spec (padrão do Hermes: 300 s). O Hermes precisa do suporte a MCP: o instalador oficial já traz; instalado com `pip`, use `pip install "hermes-agent[mcp]"` |
| `agent.personalities.<nome>` | Uma personality por agente de `65-Agentes` (`description` + `system_prompt`) | Agentes definidos no vault, usados com `/personality nome`. O instalador e o plugin (a cada abertura, valendo na sessão seguinte) mantêm sincronizado; só as personalities que o cofre criou são atualizadas ou removidas (manifesto em `~/.config/cofre/agentes-sincronizados.json`) |
| `agent.personalities.spec` | Personality `spec` | `/personality spec` liga o modo spec (SDD com verificação). Se você já tem uma personality com esse nome, ela é mantida |
| `plugins.enabled` | `+ cofre` | Plugins do usuário são opt-in |
| `skills.create_dir` | `<vault>/60-Skills` | O Hermes lê as skills do vault e cria as que aprender lá. Se você já usa `create_dir` para outra pasta, o instalador mantém e adiciona o vault em `skills.external_dirs` |
| `skills.write_approval` | `true` | Skill criada/editada pelo agente espera sua aprovação (`/skills pending`) antes de ir para o vault |
| `skills.disabled` | `+ obsidian` (pule com `--manter-skill-obsidian`) | A skill nativa escreve no vault sem as regras do cofre |
| `memory.memory_enabled` | `false` (pule com `--manter-memoria-hermes`) | `MEMORY.md` era a principal fonte de "fatos errados persistentes" |
| `memory.write_approval` | `true` | `USER.md` só muda com sua aprovação (`/memory pending`) |

`SOUL.md` não é tocado. O instalador edita o `config.yaml` com o próprio Python do Hermes (que traz PyYAML), mesclando listas e preservando o resto. Não usa `hermes config set` para valores estruturados: até a 0.19 ele grava JSON como texto, e o MCP e o plugin ficavam inválidos (verificado no Hermes 0.19.0 real); valores deixados assim por uma instalação anterior são consertados. Sem achar o Python do Hermes, o instalador mostra o trecho YAML para colar. Antes de desligar o `MEMORY.md`, ele faz backup e leva cada entrada para `01-Inbox` como captura não verificada.

Skills do Hermes com o mesmo nome de uma skill do vault têm precedência (ordem do Hermes: projeto, `~/.hermes/skills`, `create_dir`, `external_dirs`). Skills viram comandos: `/cofre-checkpoint`, `/cofre-corrigir`, `/cofre-revisar`, `/cofre-notebooklm`, `/cofre-protocolo`, `/cofre-sdd`.

## OpenCode

Em `~/.config/opencode` (ou `OPENCODE_CONFIG_DIR`). `AGENTS.md` não é tocado.

| Item | O que muda | Por quê |
| --- | --- | --- |
| `plugins/cofre.js` | Plugin (pule com `--sem-plugin-opencode`) | V2: hook `context` (contexto, linha AGORA e regras no sistema a cada chamada, mais o bloco do que o vault tem sobre a última mensagem do usuário; instruções do modo spec quando o agente `spec` está ativo; lembrete de checkpoint) e `compaction`; V1: `experimental.chat.system.transform`, `experimental.chat.messages.transform` (lê a última mensagem e o agente) e `experimental.session.compacting`; pasta privada do vault: V1 `tool.execute.before`/`tool.execute.after`, V2 `ctx.tool.hook("execute.before"|"execute.after")`, que bloqueiam ferramentas que apontem para ela e tiram o caminho dela das respostas. Cache de 30 s, refeito quando aparece chamada nova a ferramenta do cofre. Sem o plugin, só as instruções do MCP chegam ao modelo |
| `opencode.json` > MCP | Servidor `cofre` | V2: `mcp.servers.cofre` com `codemode: false` (ferramentas direto na lista nativa, melhor para modelos fracos); sem `timeout`, porque o padrão de execução da V2 é 12 h. V1 ou versão desconhecida: `mcp.cofre` com `timeout: 1200000`. Com `opencode.jsonc`, o instalador mostra o trecho para colar |
| `agents/spec.md` | Agente `spec` | Modo spec (Tab). Sem prompt próprio: na V2 o prompt de agente substitui o prompt base; as instruções vêm do plugin. Formato V1, que a V2 migra (`permission` vira `permissions`) |
| `agents/<nome>.md` | Um arquivo por agente de `65-Agentes` (formato V1, que a V2 lê) | Agentes definidos no vault: Tab ou `@nome`. O plugin refaz a cópia a cada abertura; arquivos seus com o mesmo nome não são tocados |
| `opencode.json` > `skills` | `+ <vault>/60-Skills` (só V2) | A V2 lê skills de qualquer profundidade nessa pasta |
| `opencode.json` > `permissions` | Regras `deny` de `read`, `edit` e `external_directory` para as pastas privadas (só V2) | Bloqueio nativo, independente do plugin. Formas relativa (sessão dentro do vault) e absoluta (sessão em outro projeto). Suas regras ficam; as do cofre vão no fim da lista (a última que casa vence) e saem na desinstalação |
| `skills/` | Cópias das skills do vault (só V1 ou versão desconhecida) | A V1 só enxerga `~/.config/opencode/skills/*/SKILL.md`. O plugin refaz a cópia a cada início; as cópias têm `.cofre-sync` e skills suas nessa pasta não são tocadas |
| `commands/` | `ctx.md`, `checkpoint.md`, `corrigir.md`, `revisar-cofre.md`, `spec.md`, `proxima.md` | Comandos `/ctx`, `/checkpoint`, `/corrigir`, `/revisar-cofre`, `/spec`, `/proxima`. Arquivos seus com o mesmo nome não são sobrescritos |

O servidor MCP recebe do OpenCode o ID da sessão (`_meta["ai.opencode/sessionID"]`) e agrupa os checkpoints de uma conversa na mesma nota de sessão.

## Claude Code CLI e Codex CLI (opcionais)

- `--claude-code`: `claude mcp add -s user cofre -- <python> <app> mcp`. O Claude Code inclui as instruções do servidor MCP no contexto.
- `--codex`: entrada `[mcp_servers.cofre]` em `~/.codex/config.toml` (entre `# cofre:inicio` e `# cofre:fim`). Não verifiquei se o Codex repassa as instruções do servidor MCP ao modelo; se não repassar, o modelo vê só as descrições das ferramentas.

Nenhum dos dois recebe plugin de injeção de contexto; o modelo precisa chamar `cofre_contexto` (as instruções do MCP pedem isso).

## Windows nativo e WSL ao mesmo tempo

É comum o OpenCode rodar no Windows e o Hermes no WSL (ou o contrário). Instale nos dois ambientes apontando para o mesmo vault:

```powershell
# PowerShell (Windows)
py -3 scripts\instalar.py --vault "C:\Users\voce\Obsidian\Cofre"
```

```bash
# WSL
python3 scripts/instalar.py --vault /mnt/c/Users/voce/Obsidian/Cofre
```

O motor trata `C:/Users/voce/dev/loja` e `/mnt/c/Users/voce/dev/loja` como o mesmo caminho ao associar diretório a projeto, e converte entre os dois ao conferir evidências de arquivo. Escritas simultâneas são serializadas por um arquivo de trava (`.cofre.lock`).

## Ferramentas MCP

| Ferramenta | Uso |
| --- | --- |
| `cofre_contexto` | Pacote de contexto do projeto (ou geral) |
| `cofre_buscar` | Busca com status em cada resultado |
| `cofre_ler` | Nota completa por ID |
| `cofre_registrar_fato` | Novo fato (validações descritas no protocolo) |
| `cofre_atualizar_fato` | promover, contestar, refutar (com `afirmacao_correta`), tornar_obsoleto, adicionar_evidencia |
| `cofre_decisao` | registrar, aceitar, rejeitar |
| `cofre_checkpoint` | Estado + diário da sessão |
| `cofre_capturar` | Inbox |
| `cofre_projeto` | listar, criar, vincular |
| `cofre_missao` | listar, criar, atualizar |
| `cofre_recurso` | Guarda site/API/ferramenta externa (url, quando_usar); surge por relevância quando o assunto volta |
| `cofre_spec` | criar, ver, listar, adicionar, responder, aprovar, cancelar ([specs](08-specs-e-harness.md)) |
| `cofre_tarefa` | proxima, iniciar, concluir (roda a verificação), bloquear, reabrir, regressao |

O servidor implementa o transporte stdio do MCP (JSON-RPC por linha), negocia as versões `2024-11-05` a `2025-11-25`, expõe `instructions` no `initialize` e consulta `roots/list` quando o cliente oferece, para descobrir o workspace.

## Referências consultadas

Documentação oficial lida nos repositórios em outubro de 2026:
- Hermes Agent: `website/docs/user-guide/which-file-does-what.md`, `features/memory.md`, `features/context-files.md`, `features/hooks.md`, `features/plugins.md`, `features/skills.md`, `reference/mcp-config-reference.md`, `reference/cli-commands.md` em [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).
- OpenCode V2 (2.0.26): `instructions.mdx`, `skills.mdx`, `commands.mdx`, `compaction.mdx`, `mcp-servers.mdx`, `plugins.mdx`, `build/plugins/index.mdx`, `build/plugins/migrate-v1.mdx`, `migrate-v1.mdx` em [sst/opencode](https://github.com/sst/opencode).
- Tipos da API de plugins do OpenCode: V1 `@opencode-ai/plugin` 1.19.0 (`tool.execute.before` recebe `args` e pode lançar erro; `tool.execute.after` recebe `output`); V2 `@opencode/plugin` 2.0.26 (`ctx.tool.hook`, eventos com `input` e `result`).
- Esquema de configuração da V2: `@opencode/schema` 2.0.26 (`permissions` como lista `{action, resource, effect}`; `codemode` do MCP). Regras padrão e a forma de conferir caminhos (relativo dentro do diretório da sessão, absoluto fora) lidas no próprio binário do OpenCode 2.0.26.
- Hooks do Hermes: `website/docs/user-guide/features/hooks.md` (`pre_tool_call` devolve `{"action": "block", "message": ...}`; exceção no callback bloqueia a ferramenta; `transform_tool_result` substitui o resultado).
- Teste ponta a ponta: Hermes Agent 0.19.0 (PyPI) e OpenCode 1.19.0 e 2.0.26 reais, configurados pelo instalador do cofre num HOME isolado, falando com um LLM falso local (compatível com a API da OpenAI) que pede leituras, buscas, comandos de terminal e chamadas ao cofre. Conferido: contexto e relevância chegam ao modelo, as 13 ferramentas aparecem, a pasta privada é bloqueada e filtrada, e as regras nativas da V2 valem sem o plugin.
- Código do Hermes 0.19.0: `hermes_cli/config.py` (`set_config_value` só converte booleano e número), `hermes_cli/plugins.py` (`PluginContext` sem `register_system_prompt_section`; hooks válidos), `agent/turn_context.py` (contexto do `pre_llm_call` gravado com a mensagem e reenviado).
- Obsidian Bases: `Bases syntax.md`, `Views.md`, `Functions.md`, `Layouts/Kanban view.md` em [obsidianmd/obsidian-help](https://github.com/obsidianmd/obsidian-help).
- Código do OpenCode V2 para timeouts e agentes: `packages/core/src/mcp/client.ts` (timeout de execução padrão de 12 h), `packages/core/src/v1/config/migrate.ts` (migração de agentes V1), `packages/core/src/session/model-request.ts` (prompt de agente substitui o prompt base).
- Código do Hermes para timeouts e personalities: `tools/mcp_tool_common.py` (timeout de chamada padrão de 300 s), `hermes_cli/personality.py`.

Essas ferramentas mudam rápido. Se uma atualização quebrar algo, o ponto mais sensível é a API de plugins (o OpenCode já trocou a dele na V2); o MCP, as skills e os comandos são as partes mais estáveis.
