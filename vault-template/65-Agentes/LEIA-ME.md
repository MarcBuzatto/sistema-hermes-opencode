# 65-Agentes

Agentes que você define uma vez e usa no OpenCode e no Hermes. Cada nota é um agente: o nome do arquivo é o nome do agente (minúsculas e hífen) e o corpo é o prompt.

```markdown
---
description: Revisa código procurando falhas de segurança. Use antes de publicar.
mode: primary                 # primary | subagent | all (OpenCode)
model: opencode/glm-4.6       # opcional; sem isso usa o modelo atual
ferramentas_desligadas: [write, edit]   # opcional: o agente só lê
---
Você é um revisor de segurança. Para cada risco, diga arquivo, linha e como corrigir.
```

Como chega em cada programa:

- **OpenCode**: vira `~/.config/opencode/agents/<nome>.md`. Troque de agente com Tab ou chame com `@nome` (subagente).
- **Hermes**: vira a personality `<nome>`. Use `/personality nome`.
- Os plugins levam os agentes daqui a cada abertura (o que mudar aparece na próxima sessão). Para levar agora: `cofre agentes sincronizar`.
- Agente que você criou à mão no OpenCode ou no Hermes com o mesmo nome é mantido; só o que o cofre criou é atualizado ou apagado.
- Nomes reservados (já usados pelo OpenCode ou pelo cofre): `spec`, `build`, `plan`, `general`, `explore`.
- Quando o assunto da conversa bate com a `description`, o bloco de relevância sugere o agente à IA.

`cofre agentes verificar` (e o `cofre revisar`) apontam agente sem `description`, corpo vazio, nome fora do padrão e credenciais no texto.
