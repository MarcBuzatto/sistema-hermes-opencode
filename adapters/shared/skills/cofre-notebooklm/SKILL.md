---
name: cofre-notebooklm
description: Prepara exportação do Cofre para o NotebookLM ou importa uma resposta/briefing do NotebookLM de volta para o Cofre. Use quando o usuário mencionar NotebookLM.
version: 1.0.0
---

# Cofre e NotebookLM

## Exportar
Rode no terminal: `cofre exportar-notebooklm <slug-do-projeto>` (acrescente `--hipoteses` só se o usuário quiser analisar hipóteses; elas vão em arquivo separado e rotulado). Informe a pasta gerada e oriente: cada arquivo vira uma fonte no notebook do projeto; reenvie quando houver mudanças relevantes (apague as fontes antigas do notebook antes).

## Importar
1. Salve o texto que o usuário trouxe do NotebookLM em um arquivo temporário ou passe por stdin:
   `cofre importar-notebooklm - --titulo "<título>" --projeto <slug> --notebook "<nome do notebook>"`.
2. A nota criada (N-XXXXX) é síntese externa, não fonte primária.
3. Para cada afirmação útil do texto: `cofre_registrar_fato(status='hipotese', evidencias=[{tipo:'nota', ref:'N-XXXXX', trecho:'<trecho>'}])`.
4. Só promova depois de conferir no código, na documentação oficial ou com o usuário.
