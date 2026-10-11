# Perguntas para o NotebookLM (pesquisa sobre Obsidian)

Lista única e final: substitui os "lotes" anteriores. Mande **uma pergunta por vez** no NotebookLM e me traga cada resposta com o número dela ("Resposta 3: ...").

Se quiser, cole este contexto antes da primeira pergunta:

> Estou montando um vault único no Obsidian que é a memória de longo prazo de IAs de terminal (agentes). Ele guarda tudo: contexto de projetos, fatos verificados, decisões, skills, agentes, pesquisas e links úteis. A IA não lê o vault inteiro: um sistema de busca entrega só as notas ligadas ao assunto da conversa. Economia de tokens é prioridade.

## 1. Estrutura de pastas

> Qual a melhor forma de organizar as pastas de um vault grande no Obsidian que mistura conhecimento de referência, projetos, pesquisas e procedimentos reutilizáveis? Compare PARA, Johnny.Decimal, MOC (Maps of Content) e Zettelkasten. O que funciona melhor quando o conteúdo é encontrado por busca, e não navegado à mão? Como evitar duplicação e notas órfãs?

## 2. Títulos e nomes de arquivo

> Qual convenção de título de nota favorece a busca e o autocompletar de [[links]] no Obsidian: títulos curtos, títulos em forma de frase/afirmação ou títulos únicos? Vale prefixar o nome do arquivo com um ID? Como lidar com títulos duplicados e renomear notas sem quebrar links?

## 3. Propriedades (frontmatter)

> Quais as boas práticas e os limites de usar propriedades (frontmatter/Properties) no Obsidian quando muitas notas têm metadados (status, datas, tags, links, campos próprios)? Quais tipos de propriedade o Obsidian trata melhor? Quais são padrão e quais personalizadas, e como padronizar os nomes para consultar bem no Bases? Há impacto de desempenho?

## 4. Tags, aliases, links e MOCs

> No Obsidian, quando usar tags aninhadas (#area/subarea) e quando usar tags planas? Quantas tags por nota é saudável? Como aliases ajudam a achar uma nota por sinônimo? Para agrupar e recuperar notas por assunto, o que a comunidade recomenda: tags, links internos ou MOCs? Como combinar os três sem virar bagunça?

## 5. Nota atômica e estrutura interna

> Qual o tamanho e o escopo ideais de uma nota no Obsidian (nota atômica ou nota longa) para que ela seja reaproveitável e fácil de recuperar sozinha? Quando quebrar um assunto em várias notas ligadas por um índice? Como estruturar o conteúdo interno (títulos, resumo no topo, callouts) para leitura rápida?

## 6. Bases e Dataview

> O que é o recurso Bases do Obsidian e como ele se compara ao Dataview? Como modelar notas com propriedades para montar tabelas, cartões e quadros (kanban) úteis? Quais são as boas práticas e as limitações atuais?

## 7. Escala e desempenho

> Como o Obsidian se comporta com vaults de 10 mil a 50 mil notas: o que fica lento (busca, gráfico, Bases/Dataview, abertura) e que práticas mantêm o vault rápido? Há limite prático de profundidade de pastas ou de tamanho de nota?

## 8. Captura rápida e triagem

> Qual o fluxo recomendado no Obsidian para capturar informação rápido (inbox) e depois transformar em notas permanentes sem perder tempo? O que plugins como Templater e QuickAdd resolvem? Dá para ter um bom fluxo só com recursos nativos (modelos, propriedades, Bases)?

## 9. Notas que não apodrecem e ritmo de revisão

> Resuma as ideias de notas permanentes/evergreen (Andy Matuschak) e do Zettelkasten aplicadas ao Obsidian. Como escrever notas que continuam úteis com o tempo e com que frequência revisá-las? Como evitar que virem lixo esquecido, e que rotina de revisão a comunidade usa?

## 10. Pesquisa externa → conhecimento validado → skill

> Como organizar no Obsidian materiais de pesquisa externa (resumos, guias de estudo, FAQ, linha do tempo) separados das minhas conclusões já validadas? Como registrar a fonte de cada afirmação? E como transformar uma pesquisa num procedimento reutilizável (passo a passo + referências), mantendo rastreável o que foi comprovado e o que é só o que a fonte disse?

## 11. Procedimentos, prompts e agentes reutilizáveis

> Como organizar no Obsidian conteúdo operacional reutilizável (procedimentos passo a passo, checklists, modelos de prompt, definições de agentes) separado das notas de conhecimento? Que estrutura de pastas, propriedades e nomes facilita achar e versionar esse tipo de conteúdo?

## 12. Anexos

> No Obsidian, onde e como guardar anexos (PDF, imagens, recortes de pesquisa) de forma organizada, como referenciá-los nas notas e como manter isso limpo num vault grande? Quais as boas práticas para a pasta de anexos e para citar a origem do anexo?

## 13. Dados sensíveis, sincronização e backup

> Quais as boas práticas para guardar informação sensível num vault do Obsidian (dados de clientes, resultados de testes de segurança), e como fica isso com sincronização (Obsidian Sync, git, nuvem) e backup? É comum excluir pastas da sincronização ou criptografar parte do vault?

---

Com as respostas eu vou:

- ajustar as pastas e os modelos do `vault-template/`;
- afinar o que a busca por relevância valoriza (título, tags, aliases, propriedades);
- definir o formato do fluxo "pesquisa do NotebookLM → skill", que ainda está pendente;
- revisar `docs/06-notebooklm.md`, o modelo de nota de fonte e o que vai ou não para o git.

O que conflitar com o protocolo epistêmico (por exemplo, tratar um resumo do NotebookLM como verdade) eu te aponto antes de mudar.
