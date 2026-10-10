# Uso diário

## Começando uma sessão

- **OpenCode:** o plugin já injeta o contexto; rode `/ctx` quando quiser um resumo do estado antes de começar.
- **Hermes:** o contexto entra no prompt de sistema. Se o projeto não foi detectado, diga o slug ("trabalhe no projeto loja-acme") ou vincule a pasta.

## Durante o trabalho

| Situação | O que fazer |
| --- | --- |
| A IA descobriu algo relevante | Nada: o protocolo manda registrar. Se não registrou, peça "registra isso no cofre" |
| A IA afirmou algo que você sabe que é falso | OpenCode: `/corrigir <o certo>`. Hermes: `/cofre-corrigir <o certo>`. Ou só corrija na conversa e peça para aplicar no cofre |
| Escolheram uma biblioteca/arquitetura | Diga "pode registrar como decisão aceita"; sua frase vira a `citacao_usuario` |
| Conversa ficou longa | `/checkpoint` (OpenCode) ou `/cofre-checkpoint` (Hermes) |
| Vai trocar de assunto ou encerrar | Checkpoint antes |
| Informação solta que não sabe onde encaixar | "joga na inbox do cofre" |

O Hermes avisa ao fechar uma sessão longa sem checkpoint.

## Rotina semanal (10 a 15 minutos)

1. `cofre revisar --salvar` no terminal (relatório em `00-Sistema/Relatorios/`).
2. No Obsidian, `00-Sistema/Inicio`:
   - **Hipóteses abertas:** confirme (mude `status` para `verificado` e preencha `evidencia`), refute, ou peça a um agente `/revisar-cofre` / `/cofre-revisar` para verificar no código.
   - **Contestados:** decida.
   - **Revisão vencida:** peça reverificação.
   - **Decisões aguardando você:** aceite ou rejeite (mude `status` ou rode `cofre aceitar-decisao D-XXXXX --humano`).
   - **Inbox:** transforme em fato/decisão/missão ou apague.
3. Atualize o `Perfil` se alguma preferência nova apareceu.

## Comandos do terminal

```bash
cofre contexto                                  # o que as IAs recebem nesta pasta
cofre buscar "postgres"                         # busca com status
cofre ler F-1D69S                               # nota completa
cofre fato "O deploy é na Vercel" --status verificado --evidencia "usuario :: conversa :: o deploy é na vercel" --humano
cofre refutar F-T05W0 --motivo "auth é por sessão" --correto "A API autentica com sessão em cookie httpOnly" --humano
cofre promover F-HQF4N --evidencia "arquivo :: vercel.json:1 :: {" --humano
cofre decisao "Usar Drizzle" --decisao "Drizzle no lugar de Prisma" --aceita --humano
cofre aceitar-decisao D-0K12M --humano
cofre checkpoint --resumo "..." --proximo "..." --humano
cofre missao criar "Lançar checkout" --objetivo "Checkout em produção" --passo "Stripe" --passo "Webhook" --projeto loja-acme --humano
cofre missao atualizar M-80JG0 --concluir 1 --humano
cofre projeto listar
cofre revisar --projeto-atual --salvar
cofre exportar-notebooklm loja-acme
cofre importar-notebooklm resposta.md --titulo "Briefing" --projeto loja-acme
cofre doctor
```

`--humano` grava com a sua autoridade (pode refutar fatos confirmados por você, aceitar decisões, reabrir fatos). No seu terminal interativo ele é assumido automaticamente; dentro de um agente é recusado.

## Editando direto no Obsidian

Você pode editar qualquer propriedade pelo painel de propriedades. Boas práticas:
- Ao mudar `status` à mão, acrescente uma linha em `## Histórico` ("2026-10-12 — confirmado por mim").
- Para verificar um fato, preencha `evidencia` no formato `tipo :: ref :: trecho`.
- Não renomeie arquivos de fato/decisão: o nome contém o ID que os agentes usam.
- Para encerrar um projeto, mude `status` para `encerrado` no hub e mova a pasta para `90-Arquivo`.

## Quando trocar a política para `humano`

Se a revisão mostrar fatos "verificados" com evidência de comando/URL que você não reconhece, mude `politica_verificacao` para `humano` em `00-Sistema/config.md`. Os agentes passam a registrar só hipóteses (com a evidência anexada) e você promove.
