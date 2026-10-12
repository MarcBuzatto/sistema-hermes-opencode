---
name: cofre-protocolo
description: Protocolo completo do Cofre (memória compartilhada do usuário em Obsidian, ferramentas cofre_*). Carregue no início de trabalho em projeto, ao registrar fatos, decisões ou checkpoints, quando o cofre rejeitar uma chamada ou houver dúvida sobre status (hipótese, verificado, contestado, refutado).
version: 1.0.0
---

# Protocolo do Cofre

Você trabalha para um único usuário que usa várias IAs. A memória de longo prazo de todas elas é o **Cofre**: um vault do Obsidian acessado pelas ferramentas `cofre_*` (servidor MCP "cofre"). Sua memória interna e o histórico desta conversa são a fonte MENOS confiável: eles se perdem em resumos e podem conter erros que você mesmo registrou.

## 1. Ao começar
- Se o contexto do cofre ainda não apareceu nesta conversa, ou depois de qualquer resumo/compactação, chame `cofre_contexto`.
- Leia "Armadilhas": são afirmações comprovadamente FALSAS. Nunca as repita.

## 1b. Durante a conversa
- A cada mensagem do usuário, o plugin procura no vault o que tem a ver com o assunto e mostra um bloco "[cofre] Possivelmente relevante". Abra só o que servir para a mensagem: notas e fontes com `cofre_ler <ID ou caminho>`, skills com o mecanismo de skills do seu harness.
- Sem plugin (ou se o assunto mudou e nada apareceu), use `cofre_buscar` com os termos do tema antes de responder de memória. A busca tolera erro de digitação.
- Nota livre e fonte são referência, não fato: só VERIFICADO é fato.

## 2. Em quem confiar (do mais forte ao mais fraco)
1. O que você acabou de ler no código ou na saída de um comando.
2. O que o usuário disse nesta conversa.
3. Fato VERIFICADO do cofre (se estiver VENCIDO, reverifique).
4. HIPÓTESE ou CONTESTADO do cofre: não é fato.
5. Sua memória, seu treinamento e resumos antigos da conversa.

Quando dois níveis discordam, vence o mais forte, e você registra o conflito no cofre (seção 4).

## 3. Como falar com o usuário
- Ao usar algo do cofre que não seja VERIFICADO, diga o status: "pelo cofre (hipótese, não verificada): ...".
- Se você não conferiu algo, diga "não verifiquei". Nunca transforme suposição em afirmação.

## 4. O que registrar e como
- **Descobriu algo sobre o projeto ou o ambiente** -> `cofre_registrar_fato`, uma afirmação atômica por chamada.
  - Sem prova: `status: hipotese`.
  - `status: verificado` só com evidência: abra o arquivo ou rode o comando e copie o trecho EXATO. Use caminho absoluto. O cofre confere o trecho no disco e rejeita evidência inventada.
- **O usuário corrigiu algo, ou o código contradiz o cofre** -> `cofre_atualizar_fato`:
  - `refutar` quando é falso (motivo + evidência; passe `afirmacao_correta`). Correção do usuário = evidência `usuario` com as palavras dele.
  - `contestar` quando há conflito mas você não tem certeza.
  - Corrigir só na conversa não basta: se não for para o cofre, o erro volta na próxima sessão.
- **Decisão de projeto** (biblioteca, arquitetura, padrão) -> `cofre_decisao`. Fica `proposta`; só vira `aceita` com `citacao_usuario` (palavras literais do usuário aprovando).
- **Não sabe classificar** -> `cofre_capturar` (vai para a inbox do usuário).
- **Nunca** grave senhas, tokens, chaves ou dados pessoais sensíveis. Registre só onde a credencial fica (ex.: "variável STRIPE_KEY no .env").

## 5. Checkpoint (memória de trabalho)
Chame `cofre_checkpoint` com resumo, feito, proximos_passos, bloqueios e foco:
- ao concluir cada etapa ou tarefa;
- a cada ~10 trocas em conversas longas;
- antes de encerrar ou quando o usuário mudar de assunto.

Reutilize o `sessao_id` devolvido. Liste em `fatos` e `decisoes` os IDs registrados na etapa.

## 6. Quando o cofre rejeitar sua chamada
A mensagem diz exatamente o que corrigir (trecho que não confere, afirmação já refutada, duplicata, contradição). Corrija e tente de novo. Não contorne escrevendo direto nos arquivos.

## 7. Limites
- Escreva no vault apenas pelas ferramentas `cofre_*` (exceção: skills em `60-Skills/`, criadas pelo mecanismo de skills do seu harness). Ler arquivos do vault diretamente é permitido.
- Crie ou vincule projetos (`cofre_projeto`) só quando o usuário pedir ou confirmar.
- Ausência no cofre não prova que algo é falso: verifique no código ou pergunte.
- Nunca mova, renomeie ou apague notas do vault pelo terminal (`mv`, `rm`): isso quebra os `[[links]]` das outras notas. Renomear e mover é com o usuário, no Obsidian.
- Linha "mapa do assunto: ..." no bloco de relevância = índice (MOC) do tema: abra ele primeiro e siga só os links que servirem.
- Nunca abra nem procure arquivos em `99-Privado/` (ou outras pastas privadas do usuário), nem por terminal. Se o cofre ou o plugin bloquear um caminho, não tente outro: peça ao usuário.
- `cofre_ler` de nota longa devolve o começo e a lista de seções: peça só a seção útil (`secao`), não a nota inteira. Se o ponteiro do bloco de relevância já trouxer `secao="..."`, use exatamente ela.

## 8. Skills
As skills do usuário ficam no vault em `60-Skills/` e aparecem para você como skills normais. Antes de seguir uma skill com `status: rascunho` ou sem `fontes`, avise o usuário; ela pode conter informação não verificada. Dentro da skill, bloco `[!check] Comprovado` foi testado; `[!quote] Recomendação da fonte` não foi. Criar skill a partir de pesquisa: skill `cofre-notebooklm`.

## 9. Specs (pedidos grandes)
Pedido com várias etapas ou arquivos: siga a skill `cofre-sdd`. Em resumo: `cofre_spec` (requisitos QUANDO/DEVE, tarefas com comando de verificação), aprovação do usuário com as palavras dele, depois uma tarefa por vez com `cofre_tarefa`. Tarefa só termina com `cofre_tarefa(acao='concluir')`, que roda a verificação. Se houver linha **AGORA** no contexto, ela diz o que fazer agora.

## 10. Instruções do usuário por assunto
Linha "instrução sua: ..." no bloco de relevância = regra que o usuário escreveu para aquele assunto (veio do AGENTS.md dele). Se a tarefa envolve o assunto, leia com `cofre_ler` e siga.

## 10b. Agentes do usuário
Linha "agente `nome`: ..." no bloco de relevância = agente que o usuário definiu para esse tipo de trabalho. Não troque de agente sozinho: sugira ao usuário (Hermes `/personality nome`; OpenCode Tab ou `@nome`).

## 11. Recursos (sites, APIs, ferramentas)
Linha "recurso: ... [abra: ...]" no bloco de relevância = site/API/ferramenta que o usuário guardou para esse tipo de trabalho. Se servir à tarefa, use: abra o link, use a API (ou o navegador, se não houver API) ou rode o comando — com a permissão normal do seu ambiente. Quando o usuário apontar um site/ferramenta nova que vale guardar ("guarda esse site"), use `cofre_recurso` (titulo, url, quando_usar).

# Referência rápida

## Status de um fato
| Status | Quando | Você pode afirmar? |
| --- | --- | --- |
| hipotese | Sem prova (inferência, suposição, algo que "parece") | Não. Diga "hipótese, não verificada". |
| verificado | Evidência conferível anexada | Sim. Se VENCIDO, reverifique antes. |
| contestado | Surgiu evidência contra | Não até resolver. |
| refutado | Comprovadamente falso | Nunca. É armadilha. |
| obsoleto | Era verdade, mudou | Não. |

## Evidência (formato dos itens em `evidencias`)
- `arquivo`: ref = caminho ABSOLUTO com linha (`/home/u/proj/src/db.ts:42`), trecho = texto copiado EXATAMENTE do arquivo. O cofre abre o arquivo e procura o trecho; se não achar, rejeita.
- `comando`: ref = comando executado (`npm ls drizzle-orm`), trecho = parte relevante da saída.
- `url`: ref = link da documentação oficial, trecho = citação.
- `usuario`: ref = `conversa`, trecho = palavras literais do usuário.
- `nota`: ref = ID de outra nota do cofre.

Regra prática: só use `arquivo` depois de ler o arquivo nesta conversa. Nunca escreva o trecho de memória.

## Boas afirmações
- Atômica e verificável: "O banco de produção é PostgreSQL 16", "Os testes rodam com `pnpm test`".
- Ruim: "O projeto é bem organizado e usa várias tecnologias modernas" (vaga), "Postgres e Redis e deploy na Vercel" (três fatos numa frase).

## Fluxos comuns
- Usuário corrigiu: `cofre_buscar` o fato errado -> `cofre_atualizar_fato(id, acao='refutar', motivo, evidencias=[{tipo:'usuario', ref:'conversa', trecho:'<palavras dele>'}], afirmacao_correta='<versão certa>')`. Se o fato errado não existia no cofre, registre o correto com evidência `usuario`.
- Código contradiz o cofre: `contestar` (ou `refutar`, se a prova for clara) com evidência `arquivo`/`comando`; avise o usuário.
- Hipótese confirmada: `cofre_atualizar_fato(id, acao='promover', evidencias=[...])`.
- Versão/configuração mudou: `tornar_obsoleto` com `afirmacao_correta`.

## Erros do cofre e o que fazer
| Mensagem | Ação |
| --- | --- |
| "Evidência NÃO confere" | Abra o arquivo, copie o trecho exato, use caminho absoluto. |
| "já foi REFUTADA" | Não repita. Leia o "Correto". Só conteste com evidência nova. |
| "Já existe fato parecido" | Mesmo fato: adicionar_evidencia/promover. Valor diferente: contestar/refutar o existente. Outro fato: forcar=true. |
| "CONTRADIZ um fato VERIFICADO" | Verifique no código. Se o cofre estiver errado, contestar e avisar o usuário. |
| "Conteúdo bloqueado: credencial" | Remova o segredo; registre só o nome da variável/onde fica. |

## Checkpoint
`cofre_checkpoint(resumo, feito=[...], proximos_passos=[...], bloqueios=[...], foco='...', fatos=[IDs], decisoes=[IDs], sessao_id=...)`.
`proximos_passos` substitui a lista anterior do Estado; omita para manter. Passe `bloqueios=[]` para limpar.
