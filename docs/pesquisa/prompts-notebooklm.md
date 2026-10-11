# Prompts para o NotebookLM (pesquisa sobre Obsidian)

Rode um de cada vez no seu NotebookLM (com fontes sobre Obsidian) e me mande cada resposta. São curtos de propósito — o NotebookLM se perde com prompt gigante. O objetivo é alinhar a estrutura do vault às boas práticas e deixar a recuperação de contexto barata (menos tokens) para IAs fracas e fortes.

Contexto que você pode colar junto, se quiser, antes de qualquer prompt:

> Estou montando um vault único no Obsidian que serve de memória de longo prazo para IAs de terminal (agentes). Ele guarda tudo: contexto de projetos, fatos verificados, decisões, skills, "agentes" e links úteis. A IA não lê o vault inteiro — um sistema de busca entrega só as notas relacionadas ao assunto da conversa. Economia de tokens é prioridade.

## 1. Estrutura de pastas e organização

> Qual é a melhor forma de organizar as pastas e notas de um vault grande no Obsidian que mistura conhecimento de referência, anotações de projetos, materiais de pesquisa e procedimentos reutilizáveis? Compare organização por pastas vs. por tags/links (PARA, Johnny.Decimal, MOC/Maps of Content, zettelkasten). Diga o que funciona melhor quando o conteúdo é consultado por busca, não navegado à mão, e como evitar duplicação e notas órfãs.

## 2. Tornar notas "encontráveis" (tags, aliases, propriedades, links)

> No Obsidian, o que faz uma nota ser facilmente encontrada por busca automática: título, tags, aliases, propriedades (frontmatter/properties) ou links internos? Quais são as boas práticas de nomenclatura de notas e de uso de tags e aliases para que uma busca por palavra-chave (ou por um sinônimo) encontre a nota certa? Como propriedades no frontmatter devem ser usadas e quais são padrão vs. personalizadas?

## 3. Nota atômica e tamanho ideal

> No método de notas do Obsidian, qual o tamanho e escopo ideal de uma nota (nota atômica vs. nota longa) para que ela seja reaproveitável e fácil de recuperar isoladamente? Como quebrar um assunto grande em notas menores ligadas por um índice (MOC), e quando é melhor manter tudo numa nota só? Como estruturar o conteúdo interno (títulos, resumo no topo, callouts) para leitura rápida.

## 4. Bases (banco de dados nativo) e consultas

> O que é o recurso "Bases" do Obsidian e como ele se compara ao Dataview? Como modelar notas com propriedades para montar tabelas e quadros (kanban) úteis com Bases, e quais são as boas práticas e limitações atuais? Quais tipos de visão existem e quando usar cada uma.

## 5. Materiais de pesquisa e conhecimento reutilizável (fluxo com NotebookLM)

> Como organizar no Obsidian materiais vindos de pesquisa externa (resumos, guias de estudo, FAQ, linha do tempo) de forma que fiquem separados das minhas próprias conclusões já validadas? Como registrar a fonte de cada afirmação e como transformar uma pesquisa em um procedimento reutilizável (uma "skill": passo a passo + referências), mantendo rastreável o que foi comprovado e o que ainda é só o que a fonte disse?

---

Quando as respostas voltarem, me mande todas aqui. Vou usar para:

- ajustar a divisão de pastas do `vault-template/` se a sua pesquisa indicar algo melhor;
- afinar o que a busca por relevância valoriza (título vs. tags vs. propriedades);
- definir o formato de `SKILL.md` e das notas de pesquisa (o fluxo "pesquisa do NotebookLM -> skill", hoje pendente);
- revisar `docs/06-notebooklm.md` e o modelo de nota de fonte.

Pontos da pesquisa que conflitarem com o protocolo epistêmico (por exemplo, tratar um resumo do NotebookLM como verdade) eu te aponto antes de mudar.

---

# Lote 2 (depois do estresse do sistema)

Estas cavam decisões concretas que o cofre já toma e que a sua pesquisa confirmaria ou mudaria. Mesmo contexto do topo. Um por vez.

## 6. Propriedades (frontmatter) a sério

> No Obsidian, quais as boas práticas e os limites de usar propriedades (frontmatter/Properties) para um vault onde muitas notas têm metadados (status, data, tags, links, campos próprios)? Há impacto de desempenho ou de usabilidade com muitas propriedades ou muitas notas? Quais tipos de propriedade (texto, lista, data, checkbox, número) o Obsidian trata melhor, e como padronizar nomes de propriedade para consultar bem no Bases?

## 7. Tags: aninhadas vs planas, e tags vs links

> No Obsidian, quando usar tags aninhadas (#area/subarea) vs tags planas, e qual o limite saudável de tags por nota? Para agrupar notas por assunto e recuperá-las depois, o que a comunidade recomenda: tags, links internos ([[ ]]) ou MOCs? Como tags e links se complementam sem virar bagunça.

## 8. Títulos e nomes de arquivo

> No Obsidian, qual convenção de título de nota favorece busca e autocompletar de [[links]]: títulos curtos, títulos em forma de frase/afirmação, ou títulos únicos? Vale prefixar o arquivo com um ID? Como lidar com títulos duplicados e com renomear notas sem quebrar links.

## 9. Escala e desempenho

> Como o Obsidian se comporta com vaults grandes (10 mil, 50 mil notas): o que fica lento (busca, gráfico, Bases/Dataview, abertura), e quais práticas mantêm o vault rápido? Há limite prático de profundidade de pastas ou de tamanho de nota?

## 10. Notas que não apodrecem (evergreen) e ritmo de revisão

> Resuma as ideias de "notas permanentes/evergreen" (Andy Matuschak) e do Zettelkasten aplicadas ao Obsidian: como escrever notas que continuam úteis com o tempo, com que frequência revisá-las, e como evitar que virem lixo esquecido. Que rotina de revisão a comunidade usa.

## 11. Captura rápida e triagem (inbox -> permanente)

> Qual o fluxo recomendado no Obsidian para capturar informação rápido (inbox) e depois processar em notas permanentes, sem perder tempo? O que plugins como Templater e QuickAdd resolvem, e dá para ter um bom fluxo só com recursos nativos (modelos, propriedades, Bases)?

## 12. Anexos de pesquisa (PDF, imagem, recorte)

> No Obsidian, onde e como guardar anexos (PDF, imagens, recortes de pesquisa) de forma organizada, como referenciá-los nas notas, e como manter isso limpo num vault grande? Boas práticas para a pasta de anexos e para citar a fonte do anexo.
