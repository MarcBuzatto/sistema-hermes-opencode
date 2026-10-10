# Protocolo epistêmico

O texto exato que as IAs recebem está em [`adapters/shared/PROTOCOLO-AGENTE.md`](../adapters/shared/PROTOCOLO-AGENTE.md) (também copiado para `00-Sistema/Protocolo das IAs.md` no vault). Este documento explica o porquê de cada regra e o que é garantido em código.

## Status

| Status | Significado | Entra no contexto como | Quem muda |
| --- | --- | --- | --- |
| `hipotese` | Afirmado sem prova | "HIPÓTESES abertas — NÃO trate como verdade" | Qualquer agente cria |
| `verificado` | Tem evidência conferível | "Fatos VERIFICADOS — pode usar" (VENCIDO após `revisar_em`) | Agente com evidência (política `evidencia`) ou só você (política `humano`) |
| `contestado` | Surgiu evidência contra | "CONTESTADOS — verificar antes de usar" | Qualquer agente, com motivo |
| `refutado` | Comprovadamente falso | "Armadilhas — nunca repita", com o correto ao lado | Agente com evidência; fato confirmado por você só você refuta |
| `obsoleto` | Era verdade, mudou | Não entra | Agente com motivo |

## Hierarquia de confiança

1. O que o agente acabou de ler no código ou na saída de um comando.
2. O que você disse na conversa atual.
3. Fato verificado do cofre.
4. Hipótese/contestado do cofre.
5. Memória do modelo, treino e resumos antigos.

A hierarquia resolve o caso clássico: o cofre diz X, o código mostra Y. Vence o código, e o agente é obrigado a registrar o conflito (contestar/refutar), em vez de silenciosamente "corrigir" só na conversa.

## Evidência

Formato salvo na propriedade `evidencia` (lista): `tipo :: ref :: trecho`.

| Tipo | `ref` | `trecho` | Conferência automática |
| --- | --- | --- | --- |
| `arquivo` | caminho (absoluto ou relativo ao projeto) com linha opcional | texto copiado do arquivo | Sim: o arquivo é aberto e o trecho procurado (espaços normalizados). Não achou = rejeitado |
| `comando` | comando executado | parte da saída | Não (reexecutar comandos é arriscado) |
| `url` | link da documentação | citação | Só formato (`http(s)://`) |
| `usuario` | `conversa` | suas palavras literais | Não; fica registrado quem gravou |
| `nota` | ID de nota do cofre | trecho | Sim: a nota precisa existir |

`cofre revisar` reconfere todas as evidências de arquivo dos fatos verificados. Se o código mudou e o trecho sumiu, o fato aparece como erro (e `--aplicar` o marca como contestado).

## O que é garantido em código

| Regra | Onde |
| --- | --- |
| `verificado` sem evidência é gravado como `hipotese`, com aviso | `registrar_fato` |
| Evidência de arquivo com trecho inexistente é recusada (nada é gravado) | `_validar_evidencias` |
| Afirmação similar a uma refutada é recusada, com o motivo e o correto na mensagem; paráfrase quase idêntica não aceita `forcar` | `registrar_fato` |
| Afirmação parecida com uma existente é recusada (orienta adicionar evidência, contestar ou forçar) | `registrar_fato` |
| Afirmação que nega um fato verificado é recusada (orienta contestar o verificado) | `registrar_fato` |
| Fato com fonte `usuario` não é refutado por agente sem nova citação sua | `atualizar_fato` |
| Promover exige evidência; promover contestado exige evidência nova; evidências de arquivo existentes são reconferidas | `atualizar_fato` |
| Decisão só fica `aceita` com `citacao_usuario` | `decisao` |
| Credenciais (chaves sk-, tokens GitHub/Slack, AWS, chaves privadas, URLs com senha) bloqueiam a escrita | `barrar_segredos` |
| `--humano` no CLI é recusado quando roda dentro de um agente (variáveis `OPENCODE`, `CLAUDECODE`, `HERMES_SESSION_*` etc.) | `cli._autor` |
| Cada escrita vira commit git com o autor (`opencode/glm-4.6`, `hermes`, `usuario`) | `gitlog.commit` |

O que **não** dá para garantir em código: que uma evidência de comando ou URL seja real, que a citação do usuário seja literal, que o modelo siga a hierarquia ao responder. Para isso existem a revisão semanal, o histórico git e a política `politica_verificacao: humano` (só você promove para verificado), que vale ativar se notar evidências forjadas.

## Por que manter os refutados

Apagar um erro deixa o modelo livre para "redescobri-lo" (a suposição que gerou o erro continua plausível para ele). Mantido como armadilha, com o motivo e a versão correta, o erro passa a funcionar como vacina: aparece em toda sessão e bloqueia a regravação.

## Validade

Fatos verificados recebem `revisar_em` (padrão: 90 dias, `validade_padrao_dias` em `00-Sistema/config.md`). Depois disso aparecem como `VERIFICADO·VENCIDO (reverificar)`. Versões de dependências, configurações de deploy e preços mudam; o vencimento força a reverificação.

## Sessões e estado são diário, não verdade

`Estado` e `Sessões` são escritos por agentes e marcados como tal. Servem para retomar o fio. Qualquer afirmação factual que importe deve virar nota de fato com status.

## Memória nativa dos agentes

- **Hermes:** o instalador desliga `MEMORY.md` (`memory.memory_enabled: false`), liga `memory.write_approval: true` (o `USER.md` só muda com seu `/memory approve`) e `skills.write_approval: true` (skills criadas pelo agente também passam por você). As entradas antigas do `MEMORY.md`/`USER.md` vão para a inbox do cofre como capturas não verificadas.
- **OpenCode:** não tem memória persistente própria além do histórico de sessões; o cofre é a memória.
