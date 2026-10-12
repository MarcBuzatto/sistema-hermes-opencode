---
name: cofre-checkpoint
description: Salva o progresso da conversa no Cofre (estado do projeto + diário da sessão) e registra descobertas pendentes. Use ao fim de uma etapa, antes de encerrar, quando a conversa estiver longa ou quando o usuário pedir checkpoint.
version: 1.0.0
---

# Checkpoint no cofre

1. Revise o que aconteceu desde o último checkpoint desta conversa.
2. Para cada descoberta ainda não registrada:
   - comprovada (você leu no arquivo ou viu na saída do comando nesta conversa) -> `cofre_registrar_fato` com `status: verificado` e evidência copiada exatamente;
   - não comprovada -> `cofre_registrar_fato` com `status: hipotese`.
3. Para cada correção feita pelo usuário que ainda não foi para o cofre -> `cofre_atualizar_fato` (refutar com evidência `usuario` e `afirmacao_correta`).
4. Para cada escolha de arquitetura/biblioteca -> `cofre_decisao` (proposta, ou aceita com `citacao_usuario`).
5. Chame `cofre_checkpoint` com:
   - `resumo`: 1 a 3 frases do que mudou;
   - `feito`: itens concluídos;
   - `proximos_passos`: lista completa e atualizada (ela substitui a anterior);
   - `bloqueios`: o que impede avançar (ou `[]` para limpar);
   - `foco`: a frente atual em uma frase;
   - `fatos` e `decisoes`: IDs criados nos passos 2 a 4;
   - `sessao_id`: o mesmo devolvido no checkpoint anterior desta conversa, se houver.
6. Responda ao usuário em 2 linhas: o que foi salvo e o próximo passo.
