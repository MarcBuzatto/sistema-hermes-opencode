---
name: cofre-revisar
description: Revisa as hipóteses e conflitos do projeto no Cofre, verificando cada uma no código para promover, contestar ou refutar. Use quando o usuário pedir revisão do cofre ou limpeza de hipóteses.
version: 1.0.0
---

# Revisar o cofre do projeto

1. `cofre_contexto` e anote as HIPÓTESES, os CONTESTADOS e os VERIFICADOS VENCIDOS.
2. Para cada item, verifique na fonte primária (ler arquivo, rodar comando somente leitura, documentação oficial):
   - confirmado -> `cofre_atualizar_fato(acao='promover', evidencias=[...])`;
   - falso -> `cofre_atualizar_fato(acao='refutar', motivo, evidencias, afirmacao_correta)`;
   - mudou -> `tornar_obsoleto` com `afirmacao_correta`;
   - não dá para verificar daqui -> deixe como está e liste para o usuário.
3. Não execute comandos que alterem o projeto durante a revisão.
4. Termine com uma tabela curta: ID, antes, depois, evidência usada; e a lista do que só o usuário pode confirmar.
5. Sugira ao usuário rodar `cofre revisar --salvar` no terminal para a checagem automática de evidências e segredos.
