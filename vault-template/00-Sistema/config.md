---
tipo: config
politica_verificacao: evidencia
validade_padrao_dias: 90
hipotese_antiga_dias: 14
ancora_a_cada_turnos: 5
lembrar_checkpoint_apos_turnos: 4
git_autocommit: true
contexto_max_chars: 6000
contexto_sistema_max_chars: 3500
fatos_verificados_no_contexto: 15
relevancia_ativa: true
relevancia_max_itens: 5
relevancia_max_chars: 1600
---
# Configuração do cofre

Edite as propriedades acima pelo painel de propriedades do Obsidian. Elas valem para todas as IAs.

| Propriedade | O que faz |
| --- | --- |
| `politica_verificacao` | `evidencia`: agente pode marcar fato como verificado se anexar evidência conferível. `humano`: agentes só registram hipóteses; só você promove para verificado. Use `humano` se perceber que os modelos estão forjando evidência. |
| `validade_padrao_dias` | Quantos dias um fato verificado vale até precisar ser reverificado (aparece como VENCIDO). |
| `hipotese_antiga_dias` | A revisão aponta hipóteses abertas há mais tempo que isso. |
| `ancora_a_cada_turnos` | No Hermes, a cada N turnos o plugin reinjeta uma linha com o foco atual do projeto. `0` desliga. |
| `lembrar_checkpoint_apos_turnos` | No Hermes, avisa ao fechar a sessão se ela teve pelo menos N turnos e nenhum checkpoint. |
| `git_autocommit` | Se o vault for um repositório git, cada escrita de agente vira um commit (trilha de quem gravou o quê). |
| `contexto_max_chars` | Tamanho máximo do contexto devolvido por `cofre_contexto`. |
| `contexto_sistema_max_chars` | Tamanho do contexto injetado no prompt de sistema pelos plugins (Hermes aceita até 4000). |
| `fatos_verificados_no_contexto` | Quantos fatos verificados entram no contexto (os de criticidade alta primeiro). |
| `relevancia_ativa` | A cada mensagem sua, os plugins procuram no vault o que tem a ver com o assunto (notas, fatos, decisões, fontes, skills) e mostram à IA. `false` desliga. |
| `relevancia_max_itens` | Quantos itens relacionados entram por mensagem. |
| `relevancia_max_chars` | Tamanho máximo desse bloco. |
