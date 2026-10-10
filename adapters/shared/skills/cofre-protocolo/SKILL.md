---
name: cofre-protocolo
description: Referência completa do Cofre (memória compartilhada em Obsidian). Use ao registrar fatos, decisões ou checkpoints, quando o cofre rejeitar uma chamada, ou quando houver dúvida sobre status (hipótese, verificado, contestado, refutado).
version: 1.0.0
---

# Cofre: referência para agentes

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
