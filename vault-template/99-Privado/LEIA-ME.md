# 99-Privado

Notas que você quer no Obsidian mas que nenhuma IA deve receber (dados de clientes, contratos, anotações pessoais).

O que o cofre garante:

- Nada daqui entra no índice, na busca, no bloco de relevância, no contexto, na exportação para o NotebookLM nem na revisão.
- `cofre_ler` recusa caminhos desta pasta.
- No OpenCode (plugin V1), leitura, busca, edição e comandos de terminal que apontem para esta pasta são bloqueados, e linhas com o caminho dela são removidas da saída de `glob`, `grep`, `list` e `bash`.
- Está no `.gitignore` do vault: o git do cofre não versiona esta pasta.

O que o cofre NÃO garante:

- Um agente com terminal livre ainda consegue ler arquivos do disco por caminhos que o cofre não prevê (no Hermes não há bloqueio de ferramenta pelo plugin). Isto aqui reduz exposição acidental; não é cofre criptografado.
- Senhas, tokens e chaves não devem ficar nem aqui: use um gerenciador de senhas e registre no vault só onde a credencial fica.

Outras pastas podem ser privadas: liste em `pastas_privadas` no `00-Sistema/config.md` (ex.: `40-Clientes/Confidencial`) e acrescente a mesma pasta ao `.gitignore` do vault. O `cofre revisar` avisa se uma pasta privada estiver sendo versionada.
