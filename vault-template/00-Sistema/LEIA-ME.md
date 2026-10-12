# Cofre — como este vault funciona

Este vault é a memória de longo prazo das IAs que trabalham no seu PC (Hermes e OpenCode, e opcionalmente Claude Code/Codex CLI). Elas leem e escrevem aqui através do servidor MCP `cofre` e carregam as skills de `60-Skills`. Você lê e edita normalmente pelo Obsidian.

Nada disso depende do seu `AGENTS.md` ou do `SOUL.md`: o protocolo chega aos modelos pelos plugins do Hermes e do OpenCode (prompt de sistema), pelas instruções do servidor MCP e pela skill `cofre-protocolo`.

A cada mensagem sua, os plugins procuram aqui o que tem a ver com o assunto da conversa (notas livres, fatos, decisões, fontes, skills) e mostram para a IA, que abre só o que servir. Títulos claros e `tags`/`aliases` ajudam a nota a ser achada.

## A ideia central
Modelos (principalmente os mais fracos) esquecem, resumem errado e, pior, guardam suposições como se fossem verdade e passam a defender o erro. O cofre resolve isso separando **o que foi comprovado** do **que foi suposto**:

| Status | Significa | As IAs podem usar? |
| --- | --- | --- |
| `hipotese` | Alguém achou, ninguém comprovou | Não como fato; precisam verificar |
| `verificado` | Tem evidência conferível (arquivo, comando, doc ou você) | Sim; se vencido, reverificam |
| `contestado` | Apareceu evidência contra | Não até resolver |
| `refutado` | Comprovadamente falso | Vira "armadilha": nunca repetir |
| `obsoleto` | Era verdade, mudou | Não |

Fatos refutados não são apagados: eles aparecem para as IAs como armadilhas, com a versão correta ao lado. É isso que impede o modelo de "reaprender" o erro.

## Onde fica cada coisa
| Pasta | Conteúdo |
| --- | --- |
| `00-Sistema` | Configuração, seu perfil, painéis (Bases), modelos e relatórios |
| `01-Inbox` | Capturas brutas para você triar |
| `02-Sessoes` | Diário de sessões sem projeto |
| `10-Projetos/<slug>` | Hub do projeto, `<slug> - Estado` (memória de trabalho), `Fatos/`, `Decisoes/`, `Sessoes/` |
| `20-Missoes` | Objetivos com critérios de pronto e passos |
| `30-Conhecimento` | Fatos e decisões globais (máquina, ferramentas, conhecimento que vale para tudo) |
| `40-Clientes` | Um hub por cliente (preferências e restrições) |
| `50-Fontes` | Material externo: pesquisas, documentação, respostas do NotebookLM |
| `60-Skills` | Skills que Hermes e OpenCode carregam sob demanda (formato Agent Skills) |
| `65-Agentes` | Agentes que viram agentes do OpenCode e personalities do Hermes |
| `80-Anexos` | Imagens e PDFs (o Obsidian salva aqui o que você cola) |
| `90-Arquivo` | Projetos encerrados e exportações para o NotebookLM |
| `99-Privado` | O que nenhuma IA deve receber pelo cofre (fora do git) |

## Sua rotina (10 minutos, 1 a 2 vezes por semana)
1. Abra [[Inicio]] e veja **Hipóteses abertas**, **Contestados**, **Revisão vencida** e a **Inbox**.
2. Para cada hipótese: confirme (mude `status` para `verificado` e anexe evidência, ou peça para uma IA verificar), refute ou apague.
3. Aceite ou rejeite as **decisões propostas**.
4. Rode `cofre revisar --salvar` no terminal para checar evidências que deixaram de conferir e segredos vazados.

## Regras que valem para você também
- Você é a autoridade final: pode editar qualquer propriedade pelo Obsidian.
- Nunca coloque senhas, tokens ou chaves aqui. O conteúdo vai para o contexto das IAs (e para o NotebookLM, se exportar).
- Se o vault estiver em git, cada escrita de IA vira um commit: dá para ver quem gravou o quê e desfazer.
