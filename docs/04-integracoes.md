# Integrações

## Quem usa o cofre e quem não usa

| Ferramenta | Usa o cofre? | Como |
| --- | --- | --- |
| Hermes Agent (qualquer modelo: OpenCode Zen/Go, Claude, GPT etc.) | Sim | `SOUL.md`, plugin, MCP, skills, ajustes de memória |
| OpenCode (V1 >= 1.18.29 e V2) | Sim | `AGENTS.md` global, plugin, MCP, comandos, skills |
| Claude Code CLI | Opcional (`--claude-code`) | `~/.claude/CLAUDE.md` + MCP escopo usuário |
| Codex CLI | Opcional (`--codex`) | `~/.codex/AGENTS.md` + `config.toml` |
| Claude Desktop (chat) | Não | Nenhum arquivo dele é alterado (`claude_desktop_config.json` intocado) |
| ChatGPT app | Não | Nenhum conector ou arquivo é criado |

O isolamento é estrutural: o cofre só existe para quem tem o servidor MCP `cofre` configurado e o protocolo instalado. O instalador nunca escreve na configuração dos apps de chat.

Atenção a dois casos de borda:
- A aba **Code** do app Claude Desktop é o Claude Code e lê `~/.claude/CLAUDE.md`. Por isso `--claude-code` é opcional e desligado por padrão: ligue só se quiser o cofre também ali.
- O app **Codex** compartilha `~/.codex` com o Codex CLI; mesma lógica para `--codex`.
- O OpenCode também lê skills de `~/.claude/skills`. O cofre instala as dele em `~/.agents/skills`, que o Claude Desktop não usa.

## Hermes Agent

Arquivos e configurações tocados (Linux/macOS/WSL: `~/.hermes`; Windows nativo: `%LOCALAPPDATA%\hermes`; ou `HERMES_HOME`):

| Item | O que muda | Por quê |
| --- | --- | --- |
| `SOUL.md` | Bloco gerenciado com o protocolo (seu conteúdo fora do bloco é preservado; backup `SOUL.md.cofre-bak`) | O Hermes não tem `AGENTS.md` global; o `SOUL.md` é o único arquivo carregado em toda sessão, em qualquer diretório |
| `plugins/cofre/` | Plugin Python | Seção estável do prompt de sistema com o contexto do projeto (preservada na compactação), âncora com o foco atual a cada N turnos, aviso ao fechar sessão longa sem checkpoint |
| `mcp_servers.cofre` | Servidor MCP stdio | As 10 ferramentas `cofre_*` (no Hermes aparecem com prefixo do servidor) |
| `plugins.enabled` | `+ cofre` | Plugins do usuário são opt-in |
| `skills.external_dirs` | `+ ~/.agents/skills` | Skills compartilhadas com o OpenCode |
| `skills.disabled` | `+ obsidian` (pule com `--manter-skill-obsidian`) | A skill nativa escreve no vault sem as regras do cofre |
| `memory.memory_enabled` | `false` (pule com `--manter-memoria-hermes`) | `MEMORY.md` era a principal fonte de "fatos errados persistentes" |
| `memory.write_approval` | `true` | `USER.md` (perfil) só muda com sua aprovação (`/memory pending`, `/memory approve`) |
| `skills.write_approval` | `true` | Skills aprendidas pelo agente passam por você (`/skills pending`) |

As listas são mescladas (o instalador lê o valor atual com `hermes config get --json` e acrescenta). Antes de desligar o `MEMORY.md`, o instalador faz backup e leva cada entrada para `01-Inbox` como captura não verificada.

O plugin não depende do modelo lembrar de nada: a seção de sistema entra no início da sessão; a âncora lê o `Estado` do disco, então reflete checkpoints feitos no meio da conversa.

Skills viram comandos: `/cofre-checkpoint`, `/cofre-corrigir`, `/cofre-revisar`, `/cofre-notebooklm`.

Observação sobre o scanner de segurança do Hermes: arquivos de contexto de projeto com padrões como comentários HTML ocultos são bloqueados. Os textos do cofre evitam esses padrões, e o `SOUL.md` não é bloqueado (só gera aviso).

## OpenCode

Arquivos tocados em `~/.config/opencode` (ou `OPENCODE_CONFIG_DIR`):

| Item | O que muda | Por quê |
| --- | --- | --- |
| `AGENTS.md` | Bloco gerenciado com o protocolo (resto preservado; backup) | Instruções globais carregadas em toda sessão (V1 e V2). Na V2 o campo `instructions` do `opencode.json` não é resolvido, por isso o cofre não depende dele |
| `plugins/cofre.js` | Plugin (pule com `--sem-plugin-opencode`) | V2: hooks `context` (contexto no sistema a cada chamada, com cache de 30 s) e `compaction`; V1: `experimental.chat.system.transform` e `experimental.session.compacting` |
| `opencode.json` | Servidor MCP `cofre` | V2 detectada: `mcp.servers.cofre` com `codemode: false` (ferramentas direto na lista nativa, melhor para modelos fracos). V1 ou versão desconhecida: `mcp.cofre` (formato aceito pelas duas). Se você usa `opencode.jsonc`, o instalador mostra o trecho para colar |
| `commands/` | `ctx.md`, `checkpoint.md`, `corrigir.md`, `revisar-cofre.md` | Comandos `/ctx`, `/checkpoint`, `/corrigir`, `/revisar-cofre`. Arquivos seus com o mesmo nome não são sobrescritos |
| `~/.agents/skills/` | Skills `cofre-*` | Descobertas pelo OpenCode (e pelo Hermes via `external_dirs`) |

O servidor MCP recebe do OpenCode o ID da sessão (`_meta["ai.opencode/sessionID"]`) e usa isso para agrupar os checkpoints de uma conversa na mesma nota de sessão.

## Claude Code CLI e Codex CLI (opcionais)

- `--claude-code`: bloco em `~/.claude/CLAUDE.md` e `claude mcp add -s user cofre -- <python> <app> mcp`.
- `--codex`: bloco em `~/.codex/AGENTS.md` e entrada `[mcp_servers.cofre]` em `~/.codex/config.toml` (entre marcadores `# cofre:inicio`/`# cofre:fim`).

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

O servidor implementa o transporte stdio do MCP (JSON-RPC por linha), negocia as versões `2024-11-05` a `2025-11-25`, expõe `instructions` no `initialize` e consulta `roots/list` quando o cliente oferece, para descobrir o workspace.

## Referências consultadas

Documentação oficial lida nos repositórios em outubro de 2026:
- Hermes Agent: `website/docs/user-guide/which-file-does-what.md`, `features/memory.md`, `features/context-files.md`, `features/hooks.md`, `features/plugins.md`, `features/skills.md`, `reference/mcp-config-reference.md`, `reference/cli-commands.md` em [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).
- OpenCode V2 (2.0.26): `instructions.mdx`, `skills.mdx`, `commands.mdx`, `compaction.mdx`, `mcp-servers.mdx`, `plugins.mdx`, `build/plugins/index.mdx`, `build/plugins/migrate-v1.mdx`, `migrate-v1.mdx` em [sst/opencode](https://github.com/sst/opencode).
- Obsidian Bases: `Bases syntax.md`, `Views.md`, `Functions.md` em [obsidianmd/obsidian-help](https://github.com/obsidianmd/obsidian-help).

Essas ferramentas mudam rápido. Se uma atualização quebrar algo, o ponto mais sensível é a API de plugins (o OpenCode já trocou a dele na V2); o protocolo no `AGENTS.md`/`SOUL.md`, o MCP e os comandos são as partes mais estáveis.
