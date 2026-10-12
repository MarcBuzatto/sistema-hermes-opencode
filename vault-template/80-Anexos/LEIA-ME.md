# 80-Anexos

Imagens, PDFs e outros arquivos que não são nota. O Obsidian já salva aqui o que você cola ou arrasta (Settings > Files & Links > Default location for new attachments = `80-Anexos`; já vem configurado no vault novo).

- As IAs não leem binários pelo cofre. Para um PDF ou imagem ser achado, crie uma nota de fonte (template **Fonte**) em `50-Fontes/` com `anexo: "[[arquivo.pdf]]"`, uma `description` de uma linha e os trechos que importam em texto.
- Dê nome descritivo antes de colar (`fluxo-checkout-stripe.png`, não `Pasted image 2026...png`).
- Página específica de PDF: `![[manual.pdf#page=5]]`.
- O git do cofre só versiona o que as IAs gravam pelo cofre; anexos não entram sozinhos. Se você versiona o vault inteiro, binários grandes incham o repositório: nesse caso acrescente `80-Anexos/` ao `.gitignore` e faça backup dos anexos por outro meio.
