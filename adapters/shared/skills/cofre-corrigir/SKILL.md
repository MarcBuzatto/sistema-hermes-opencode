---
name: cofre-corrigir
description: Aplica no Cofre uma correção feita pelo usuário (informação errada que a IA estava usando). Use sempre que o usuário disser que algo está errado, que não é assim, ou corrigir um fato do projeto.
version: 1.0.0
---

# Corrigir informação no cofre

Corrigir só na conversa não basta: a informação errada volta na próxima sessão se ficar no cofre ou na memória do modelo.

1. Identifique a afirmação errada e a correta a partir das palavras do usuário.
2. `cofre_buscar` com termos da afirmação errada (e da correta) para achar fatos relacionados.
3. Se existe fato com a afirmação errada:
   `cofre_atualizar_fato(id=<ID>, acao='refutar', motivo='Usuário corrigiu: <resumo>', evidencias=[{tipo:'usuario', ref:'conversa', trecho:'<palavras literais do usuário>'}], afirmacao_correta='<afirmação correta>')`.
4. Se não existe: `cofre_registrar_fato(afirmacao='<afirmação correta>', status='verificado', evidencias=[{tipo:'usuario', ref:'conversa', trecho:'<palavras literais>'}])`.
5. Se a correção afeta uma decisão, registre nova decisão com `substitui=<ID antigo>`.
6. Se você (Hermes) salvou a informação errada na ferramenta `memory`, remova a entrada.
7. Confirme ao usuário em uma linha: qual fato foi refutado e qual ficou no lugar (IDs).
