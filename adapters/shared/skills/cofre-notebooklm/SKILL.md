---
name: cofre-notebooklm
description: Exporta o Cofre para o NotebookLM, importa respostas/pesquisas do NotebookLM como fonte e transforma uma pesquisa em skill com fontes rastreáveis. Use quando o usuário mencionar NotebookLM, pesquisa externa ou pedir uma skill a partir de uma pesquisa.
version: 1.1.0
---

# Cofre e NotebookLM

## Exportar
Rode no terminal: `cofre exportar-notebooklm <slug-do-projeto>` (acrescente `--hipoteses` só se o usuário quiser analisar hipóteses; elas vão em arquivo separado e rotulado). Informe a pasta gerada e oriente: cada arquivo vira uma fonte no notebook do projeto; reenvie quando houver mudanças relevantes (apague as fontes antigas do notebook antes).

## Importar
1. Salve o texto que o usuário trouxe do NotebookLM em um arquivo temporário ou passe por stdin:
   `cofre importar-notebooklm - --titulo "<título>" --projeto <slug> --notebook "<nome do notebook>"`.
2. A nota criada (N-XXXXX) é síntese externa, não fonte primária. Ela reflete a visão da fonte, não a do usuário.
3. Para cada afirmação útil do texto: `cofre_registrar_fato(status='hipotese', evidencias=[{tipo:'nota', ref:'N-XXXXX', trecho:'<trecho>'}])`.
4. Só promova depois de conferir no código, na documentação oficial (evidência `url` com a citação) ou com o usuário.

## Pesquisa -> skill
Quando o usuário pedir uma skill a partir de uma pesquisa:
1. A pesquisa precisa estar no cofre como fonte (passo Importar). Anote o N-XXXXX.
2. Escreva a skill em `60-Skills/<categoria>/<nome-da-skill>/SKILL.md` (nome em minúsculas e hífen, igual ao da pasta).
3. Frontmatter:
   ```yaml
   name: <nome-da-skill>
   description: <o que faz e quando usar, uma ou duas frases>
   status: rascunho            # rascunho | verificada | obsoleta
   fontes: [N-XXXXX]           # notas de fonte, fatos (F-...) ou links oficiais
   ```
4. Corpo enxuto (detalhes longos vão em `references/`). Em cada passo, separe o que foi testado do que só a fonte diz:
   ```markdown
   1. <passo>
      > [!check] Comprovado
      > <como foi testado, quando, resultado> (F-XXXXX)

      > [!quote] Recomendação da fonte
      > <o que a fonte diz e ainda não foi testado> (N-XXXXX)
   ```
5. A skill nasce `status: rascunho`. Só mude para `verificada` quando os passos principais tiverem bloco "Comprovado" e o usuário concordar.
6. Nunca copie credenciais, tokens ou dados de clientes para a skill.
7. Avise o usuário onde a skill ficou e que ela está em rascunho; `cofre skills verificar` aponta problemas de formato.
