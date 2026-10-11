# 99-Privado

Notas que você quer no Obsidian mas que nenhuma IA deve receber (dados de clientes, contratos, anotações pessoais).

O que o cofre garante:

- Nada daqui entra no índice, na busca, no bloco de relevância, no contexto, na exportação para o NotebookLM nem na revisão.
- `cofre_ler` recusa caminhos desta pasta.
- No Hermes e no OpenCode (V1 e V2), o plugin do cofre bloqueia leitura, busca, edição e comandos de terminal que apontem para esta pasta, e tira das respostas das ferramentas as linhas com o caminho dela.
- No OpenCode V2, o instalador também grava regras de permissão nativas (`deny` para ler, editar e acessar esta pasta), que valem mesmo se o plugin falhar.
- Está no `.gitignore` do vault: o git do cofre não versiona esta pasta.

O que o cofre NÃO garante:

- Um agente com terminal livre ainda consegue ler arquivos do disco por caminhos que nenhuma regra prevê (um script que monta o caminho em partes, por exemplo). Isto aqui reduz exposição acidental; não é cofre criptografado.
- Senhas, tokens e chaves não devem ficar nem aqui: use um gerenciador de senhas e registre no vault só onde a credencial fica.

Outras pastas podem ser privadas: liste em `pastas_privadas` no `00-Sistema/config.md` (ex.: `40-Clientes/Confidencial`) e acrescente a mesma pasta ao `.gitignore` do vault. Os plugins passam a respeitar a mudança em até 30 segundos; para as regras nativas do OpenCode V2, rode o instalador de novo. O `cofre revisar` avisa se uma pasta privada estiver sendo versionada.
