---
name: cofre-sdd
description: Spec-Driven Development com o cofre. Use antes de implementar qualquer pedido com várias etapas ou arquivos (feature, refatoração, integração) e para continuar uma spec já aprovada. Escreve requisitos verificáveis, quebra em tarefas com comando de verificação, espera a aprovação do usuário e executa uma tarefa por vez.
version: 1.0.0
---

# Spec-Driven Development com o cofre

A spec diz o que construir; as tarefas dizem em que ordem e como provar que cada parte ficou pronta. O cofre guarda a spec no vault (`10-Projetos/<projeto>/Specs/`), mostra a linha **AGORA** no contexto de toda chamada e só aceita uma tarefa como pronta se o comando de verificação passar.

## Quando usar

- Pedido com mais de uma etapa, mais de um arquivo ou que você não terminaria numa resposta: spec.
- Correção pequena e óbvia (um arquivo, um ajuste): não precisa.
- Já existe spec ativa (linha AGORA no contexto): siga ela, não crie outra.

## 1. Entender

Leia o código relacionado antes de propor (rotas, modelos, testes existentes, como os testes rodam no projeto: `package.json`, `pyproject.toml`, `Makefile`, `go.mod`). Anote o comando de teste real do projeto. Tudo que só o usuário sabe (regra de negócio, preferência, limite) vira pergunta, não suposição.

## 2. Especificar

`cofre_spec(acao='criar')` com:

- `titulo` e `objetivo` (o problema e o resultado esperado, 1 a 3 frases);
- `requisitos`: um comportamento por item, no formato **QUANDO \<situação\>, O SISTEMA DEVE \<comportamento observável\>**;
- `fora_escopo`: o que não será feito agora;
- `perguntas`: dúvidas para o usuário;
- `plano` (opcional): arquivos e abordagem.

Requisito bom: "QUANDO o cupom estiver vencido, O SISTEMA DEVE mostrar 'Cupom expirado' e manter o total". Requisito ruim: "melhorar o checkout" (não dá para testar).

## 3. Tarefas

Cada tarefa:

- pequena (uma sessão de trabalho), em ordem de dependência;
- `cobre`: os requisitos que ela atende (todo requisito precisa de pelo menos uma tarefa);
- `verificar`: o comando que sai com código 0 quando a tarefa está pronta. Prefira o teste específico (`npm test -- cupom`, `pytest tests/test_cupom.py`, `go test ./cupom/...`). Se o teste não existe, a própria tarefa cria o teste. Use `manual` só para o que não dá para testar (visual).

O cofre roda sozinho comandos de teste, lint, typecheck e build conhecidos, sem shell (nada de `&&`, `|`, `>`). Outros comandos viram verificação manual, a menos que o usuário libere em `verificacao_comandos` no `00-Sistema/config.md`.

## 4. Aprovar

Mostre ao usuário requisitos, fora de escopo e tarefas (com os comandos de verificação) e **pare**. Responda às perguntas com `cofre_spec(acao='responder', pergunta='P1', resposta=...)`. Com o "ok" do usuário: `cofre_spec(acao='aprovar', citacao_usuario='<palavras exatas dele>')`. Nunca invente aprovação. Sem aprovação, não edite código.

## 5. Implementar (uma tarefa por vez)

1. `cofre_tarefa(acao='proxima')` inicia a próxima tarefa.
2. Faça só essa tarefa. Se perceber trabalho de outra tarefa, deixe para ela.
3. Rode o comando de verificação você mesmo e veja passar.
4. `cofre_tarefa(acao='concluir')`: o cofre roda o comando de novo; só fica pronta se passar.
5. Na última tarefa, o cofre roda todas as verificações de novo (regressão). Se algo que já passava quebrou, a tarefa volta a ficar em andamento.
6. `cofre_checkpoint` curto ao fim de cada tarefa.

## 6. Quando falhar

- Leia a saída que o cofre devolveu e corrija o código.
- Nunca enfraqueça o teste, nunca troque o comando de verificação para passar e nunca marque tarefa como pronta editando a nota da spec (a revisão do cofre aponta isso).
- Três falhas seguidas bloqueiam a tarefa: pare, mostre o erro ao usuário e peça orientação.
- Tarefa impossível do jeito que está: `cofre_tarefa(acao='bloquear', motivo=...)` e explique ao usuário.

## 7. Escopo mudou

Requisito ou tarefa novos: `cofre_spec(acao='adicionar')`. Se a spec já estava aprovada, ela volta para rascunho e precisa de nova aprovação (o que já foi concluído continua concluído).

## Referência rápida

| Situação | Chamada |
| --- | --- |
| Ver a spec e o próximo passo | `cofre_spec(acao='ver')` |
| Listar specs do projeto | `cofre_spec(acao='listar')` |
| Começar a próxima tarefa | `cofre_tarefa(acao='proxima')` |
| Terminei a tarefa | `cofre_tarefa(acao='concluir')` |
| Verificação manual | `cofre_tarefa(acao='concluir', citacao_usuario='<o que o usuário disse>')` |
| Rodar a regressão de novo | `cofre_tarefa(acao='regressao')` |
