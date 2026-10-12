---
description: "[cofre] Salva o progresso desta conversa no Cofre"
---
Faça um checkpoint no Cofre seguindo a skill `cofre-checkpoint`:
1. Registre descobertas ainda não salvas (`cofre_registrar_fato`: verificado só com evidência copiada exatamente nesta conversa; senão hipótese).
2. Aplique no cofre correções que o usuário fez (`cofre_atualizar_fato` com evidência `usuario`).
3. Registre decisões (`cofre_decisao`).
4. Chame `cofre_checkpoint` com resumo, feito, proximos_passos (lista completa), bloqueios, foco e os IDs criados.
5. Responda em 2 linhas: o que foi salvo e o próximo passo.

Observações do usuário para este checkpoint: $ARGUMENTS
