# Cofre — memória epistêmica em Obsidian para Hermes e OpenCode

Sistema para as IAs de terminal do seu PC (Hermes Agent e OpenCode, com Claude Code CLI e Codex CLI opcionais) compartilharem **uma memória de longo prazo organizada no Obsidian**, separando o que foi **comprovado** do que foi **suposto**.

## O problema que ele resolve

Modelos mais fracos (como os gratuitos do OpenCode Zen usados no Hermes) não são "burros": eles **guardam errado**. Três falhas se combinam:

1. **Esquecem** dentro da própria conversa (compactação/resumo perde detalhes).
2. **Registram suposição como verdade** — na memória nativa do Hermes (`MEMORY.md`, escrita até em segundo plano) ou no próprio histórico.
3. **Persistem no erro**: a informação errada volta em toda sessão, e o modelo a defende porque "está na memória".

O Cofre ataca as três com regras que rodam **em código**, não só no prompt:

| Falha | Mecanismo |
| --- | --- |
| Esquecimento | Estado de trabalho por projeto + checkpoints; contexto reinjetado no prompt de sistema (Hermes) e a cada chamada (OpenCode), inclusive na compactação |
| Suposição virando fato | Todo fato nasce `hipotese`; `verificado` exige evidência, e evidência de arquivo é **conferida no disco** (trecho inventado é rejeitado) |
| Persistir no erro | Fato refutado vira **armadilha** visível em toda sessão, com a versão correta ao lado; registrar de novo a afirmação refutada (ou paráfrase) é **bloqueado** |
| Memória nativa contaminada | Instalador desliga o `MEMORY.md` do Hermes, liga aprovação para `USER.md`/skills e leva as entradas antigas para triagem |

## Como fica

```
Obsidian (vault "Cofre")          <- você lê, edita e aprova
   ^            ^
   |  MCP "cofre" (10 ferramentas com validação)
   |            |
Hermes        OpenCode            <- usam o ecossistema
(plugin:      (plugin: contexto
 contexto no   no sistema + na
 sistema)      compactação)

Claude Desktop / ChatGPT app      <- NÃO tocados
```

Detalhes em [docs/01-arquitetura.md](docs/01-arquitetura.md).

## Instalação rápida

Requer Python 3.9+ (o do Hermes serve) e git (recomendado).

```bash
git clone https://github.com/marcbuzatto/sistema-hermes-opencode.git
cd sistema-hermes-opencode
python3 scripts/instalar.py --vault ~/Obsidian/Cofre --git
```

No Windows (PowerShell):

```powershell
git clone https://github.com/marcbuzatto/sistema-hermes-opencode.git
cd sistema-hermes-opencode
py -3 scripts\instalar.py --vault "$env:USERPROFILE\Obsidian\Cofre" --git
```

Depois abra a pasta do vault no Obsidian ("Abrir pasta como cofre") e vincule seu primeiro projeto:

```bash
cd ~/dev/meu-projeto
cofre projeto criar meu-projeto --nome "Meu Projeto" --caminho . --humano
```

Guia completo (Windows nativo, WSL, Linux/macOS, verificação e desinstalação): [docs/05-instalacao.md](docs/05-instalacao.md).

## Uso no dia a dia

| Onde | O que fazer |
| --- | --- |
| OpenCode | `/ctx` no início, `/checkpoint` ao fim de cada etapa, `/corrigir <correção>` quando a IA errar, `/revisar-cofre` de vez em quando |
| Hermes | `/cofre-checkpoint`, `/cofre-corrigir`, `/cofre-revisar` (skills viram comandos) |
| Obsidian | Nota `00-Sistema/Inicio`: hipóteses, contestados, revisão vencida, decisões aguardando você, inbox |
| Terminal | `cofre revisar --salvar` semanal; `cofre contexto` para ver o que as IAs recebem |

Mais em [docs/07-uso-diario.md](docs/07-uso-diario.md).

## Estrutura do repositório

| Caminho | Conteúdo |
| --- | --- |
| `cofre/` | Motor em Python puro (sem dependências): vault, regras epistêmicas, contexto, revisão, NotebookLM, CLI e servidor MCP |
| `vault-template/` | Vault inicial: pastas, perfil, configuração, painéis (Bases), modelos e um projeto de exemplo |
| `adapters/shared/` | Protocolo dos agentes (texto único para todas as IAs) e skills compartilhadas (`~/.agents/skills`) |
| `adapters/hermes/` | Bloco do `SOUL.md`, plugin do Hermes e exemplo de `config.yaml` |
| `adapters/opencode/` | Bloco do `AGENTS.md` global, comandos e plugin (V1 e V2) |
| `adapters/claude-code/`, `adapters/codex/` | Integrações opcionais (desligadas por padrão) |
| `scripts/instalar.py` | Instalador/desinstalador multiplataforma, idempotente, com `--dry-run` |
| `docs/` | Arquitetura, protocolo, estrutura do vault, integrações, instalação, NotebookLM e uso diário |
| `tests/` | Testes (`python3 -m unittest discover -s tests`) |

## Documentação

1. [Arquitetura](docs/01-arquitetura.md)
2. [Protocolo epistêmico](docs/02-protocolo-epistemico.md)
3. [Estrutura do vault](docs/03-estrutura-do-vault.md)
4. [Integrações (Hermes, OpenCode, isolamento dos apps)](docs/04-integracoes.md)
5. [Instalação](docs/05-instalacao.md)
6. [NotebookLM](docs/06-notebooklm.md)
7. [Uso diário](docs/07-uso-diario.md)
