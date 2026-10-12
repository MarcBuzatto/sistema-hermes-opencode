# Instalação

## Pré-requisitos

- Python 3.9 ou mais novo. O Hermes já traz um; no Windows sem Hermes nativo, instale pelo `winget install Python.Python.3.12`.
- Git (recomendado, para o histórico do vault).
- Obsidian 1.9+ (Bases nativo).
- Hermes e/ou OpenCode já instalados e funcionando. O instalador detecta os dois; se algum não estiver no PATH, ele grava os arquivos e lista os comandos que faltam.

## Passo a passo

### 1. Clonar

```bash
git clone https://github.com/marcbuzatto/sistema-hermes-opencode.git
cd sistema-hermes-opencode
```

### 2. Simular (opcional)

```bash
python3 scripts/instalar.py --vault ~/Obsidian/Cofre --git --dry-run
```

### 3. Instalar

Linux, macOS ou WSL:

```bash
python3 scripts/instalar.py --vault ~/Obsidian/Cofre --git
```

Windows (PowerShell), com Hermes/OpenCode nativos:

```powershell
py -3 scripts\instalar.py --vault "$env:USERPROFILE\Obsidian\Cofre" --git
```

O que acontece, em ordem:
1. Copia o motor para `~/.local/share/cofre/app` (Windows: `%LOCALAPPDATA%\cofre\app`) e cria o comando `cofre` (`~/.local/bin/cofre` ou `%LOCALAPPDATA%\cofre\bin\cofre.cmd`, adicionado ao PATH do usuário; use `--sem-path` para não mexer no PATH).
2. Cria ou completa o vault a partir do template (arquivos existentes nunca são sobrescritos), grava as skills do cofre em `60-Skills/sistema/` e grava `~/.config/cofre/config.json` (Windows: `%APPDATA%\cofre\config.json`) com o caminho do vault.
3. Com `--git`, inicializa o repositório do vault.
4. Remove blocos que versões antigas do instalador tenham deixado em `AGENTS.md`/`SOUL.md`/`CLAUDE.md`. Nenhum arquivo de instruções seu é editado.
5. Integra o OpenCode e o Hermes, inclusive apontando os dois para as skills do vault (detalhes em [04-integracoes.md](04-integracoes.md)).
6. Roda `cofre doctor` e lista pendências.

Flags úteis:

| Flag | Efeito |
| --- | --- |
| `--sem-hermes` / `--sem-opencode` | Pula uma integração |
| `--hermes` / `--opencode` | Força a integração mesmo sem detectar |
| `--sem-plugin-opencode` | Não instala o plugin de injeção de contexto no OpenCode |
| `--manter-memoria-hermes` | Não desliga o `MEMORY.md` do Hermes |
| `--manter-skill-obsidian` | Não desativa a skill nativa `obsidian` do Hermes |
| `--claude-code` / `--codex` | Liga também esses CLIs |

### 4. Abrir no Obsidian

"Abrir pasta como cofre" e escolha a pasta do vault. Em Configurações > Plugins principais, confirme **Bases** e **Modelos (Templates)** ativos. Abra `00-Sistema/Inicio`.

Se preferir usar uma pasta dentro de um vault que você já tem, passe esse caminho em `--vault` (ex.: `~/Obsidian/MeuVault/Cofre`). O instalador detecta o `.obsidian` do vault pai e não cria outro.

### 5. Reiniciar os agentes

Feche e abra de novo o OpenCode e o Hermes (o Hermes monta o prompt no início da sessão; o PATH novo só vale em terminais novos). No Hermes, confira com `hermes plugins list` (o `cofre` deve aparecer como enabled) e `hermes mcp list` (o `cofre` deve aparecer como enabled). Se o Hermes foi instalado com `pip`, instale o suporte a MCP: `pip install "hermes-agent[mcp]"`.

### 6. Vincular projetos

Em cada pasta de código:

```bash
cd ~/dev/loja-acme
cofre projeto criar loja-acme --nome "Loja Acme" --caminho . --humano --stack Next.js --stack PostgreSQL
```

Pasta adicional ou remoto git para um projeto existente:

```bash
cofre projeto vincular loja-acme --caminho /mnt/c/dev/loja-acme --humano
cofre projeto vincular loja-acme --repo git@github.com:acme/loja.git --humano
```

Pastas sem projeto recebem o contexto geral (lista de projetos, perfil, missões e fatos globais).

### 7. Revisar a memória antiga do Hermes

O instalador levou as entradas do `MEMORY.md`/`USER.md` para `01-Inbox`. Para cada uma: vire fato (com a evidência certa), preferência no `Perfil`, ou apague.

## Verificação

```bash
cofre doctor
cofre contexto --cwd ~/dev/loja-acme
```

No OpenCode, rode `/ctx` numa pasta de projeto. No Hermes, pergunte "qual o foco atual do projeto?" logo no início da sessão: a resposta deve vir do cofre.

Teste rápido das proteções (dentro do agente):
1. Peça para registrar um fato verificado citando um trecho que não existe no arquivo: deve ser recusado.
2. Corrija algo ("não é X, é Y") e depois peça para registrar X de novo: deve ser bloqueado como refutado.

## Atualizar

```bash
cd sistema-hermes-opencode
git pull
python3 scripts/instalar.py
```

Sem `--vault`, o instalador reutiliza o vault da configuração. Os blocos gerenciados são substituídos; o resto dos seus arquivos fica como está.

## Desinstalar

```bash
python3 scripts/instalar.py --desinstalar
```

Remove blocos, plugins, comandos, skills, entradas MCP e o motor. O vault não é tocado. Para reativar a memória nativa do Hermes, o desinstalador mostra os comandos.

## Problemas comuns

| Sintoma | Causa provável | Solução |
| --- | --- | --- |
| `cofre: Vault do cofre não configurado` | Config ausente | `cofre init <pasta> --registrar` ou rode o instalador com `--vault` |
| Contexto sem projeto numa pasta de código | Pasta não vinculada | `cofre projeto vincular <slug> --caminho . --humano` |
| Ferramentas `cofre_*` não aparecem no OpenCode V2 | MCP em Code Mode ou `opencode.jsonc` sem a entrada | Confira `mcp.servers.cofre` com `"codemode": false` |
| Hermes não carrega o plugin | `plugins.enabled` sem `cofre` | `hermes plugins enable cofre` (ou rode o instalador de novo com o `hermes` no PATH) |
| Evidência "não encontrada" em arquivo relativo | O servidor MCP não sabe o diretório do projeto | O agente deve usar caminho absoluto (o protocolo pede isso) ou passar `cwd` |
| `--humano não é aceito` | Comando rodando dentro de um agente | Rode no seu terminal, fora do agente |
