# Respostas do NotebookLM (pesquisa sobre Obsidian)

Respostas do usuário às perguntas de `prompts-notebooklm.md`, guardadas para análise depois que todas chegarem. O texto é o que o NotebookLM respondeu, com duas edições: tirei os emojis e as ofertas do fim de cada resposta ("Quer que eu monte..."). Os números entre colchetes são as citações das fontes do caderno do usuário.

Situação: recebidas todas (contexto e 1 a 13) e analisadas.

## O que virou mudança no cofre

| Resposta | Aplicado | Não aplicado (e por quê) |
| --- | --- | --- |
| 1-4 | Datas no formato do Obsidian, `description` como resumo do ponteiro, MOC por `tipo: moc` ou tag, arquivo morto fora da busca automática, regras de título/tags/propriedades na doc | `CLAUDE.md`, `.claude/rules` e `.claudeignore`: são do Claude Code, que não usa o cofre; mover notas pelo Obsidian CLI: o cofre não move notas |
| 5 e 7 | `cofre_ler` de nota longa devolve o começo e a lista de seções (`ler_max_chars`); a IA pede só a seção (`secao`); revisão aponta nota longa sem títulos | Ler só o frontmatter de cada arquivo: o índice do cofre já resume cada nota em uma linha; os números de economia (92,5%, 60%) não têm fonte verificável |
| 6 | Já estava: todos os `.base` começam filtrando por `tipo` ou pasta e o do projeto usa `this.file`; Skills.base ganhou `status` e `fontes` | Dataview: o cofre usa só recursos nativos |
| 7 e 12 | Pasta `80-Anexos` com `attachmentFolderPath`; fonte com `anexo:` | `userIgnoreFilters` para arquivo morto e anexos: no Obsidian isso esconde da busca e das sugestões de link, o que atrapalha você; o cofre já ignora essas pastas sozinho |
| 8 e 9 | Inbox.base com "Tudo na inbox"; revisão aponta notas sem nenhum link, temas com 3+ notas sem MOC e itens parados na inbox; rotina semanal/mensal na doc | Templater e QuickAdd: opcionais, nada no cofre depende deles |
| 10 | Fluxo fonte -> hipótese -> verificado -> skill com `status` e `fontes`, blocos `[!check]`/`[!quote]`; skill em rascunho marcada na relevância; `cofre skills verificar` cobra `fontes` | Pastas `20-Literature/` e `30-Permanent/`: o cofre já separa por `tipo` (fonte vs. fato verificado) |
| 11 | Procedimentos para as IAs continuam como skills em `60-Skills/` (com `status`, `fontes` e git) | `.claude/agents` e `CLAUDE.md`: Claude Code. Agentes guardados no vault e sincronizados para OpenCode/Hermes: proposto como próximo passo |
| 13 | `99-Privado/` e `pastas_privadas`: fora do índice, da busca, da relevância e do `cofre_ler`; no `.gitignore`; revisão acusa pasta privada versionada; plugin do OpenCode bloqueia ferramentas que apontem para ela; doc de sync e backup | Deny rules em `.claude/settings.local.json`: Claude Code. No Hermes o plugin não tem como bloquear ferramenta de arquivo; documentado como limite |

---

## Contexto (resposta ao texto de contexto)

Essa abordagem de utilizar um **vault único do Obsidian como memória de longo prazo para agentes de terminal** é uma das arquiteturas mais eficazes e sustentáveis para evitar o esquecimento e a degradação de contexto entre sessões de trabalho [1-3]. Como o Obsidian opera sobre arquivos Markdown locais, a IA consegue ler, pesquisar e atualizar o conhecimento sem depender de bancos de dados proprietários ou formatos fechados [1, 4, 5].

Como a **economia de tokens** é a sua prioridade absoluta, existem estratégias cruciais baseadas nas melhores práticas de integração para garantir que o agente consuma apenas o contexto estritamente necessário em cada interação:

### 1. Estratégias Principais para Economia de Tokens

* **Abordagem *Frontmatter-First* (Metadados YAML)**: Padronize o bloco de metadados YAML no topo de todas as notas (campos como `type`, `status`, `project`, `tags` e `summary`) [6-8]. Instrua o agente nas diretivas gerais a realizar avaliações preliminares lendo **apenas as primeiras 10 a 15 linhas de cada arquivo** [9, 10]. Essa leitura focada nos metadados reduz o consumo inicial de tokens de exploração em cerca de **92,5%** em comparação com a leitura bruta do corpo das notas [9, 10].
* **Busca Estruturada via Obsidian CLI ou Motores Semânticos**: Evite permitir que o agente faça varreduras brutas no sistema de arquivos (como comandos `grep` ou `glob` genéricos), pois eles carregam arquivos inteiros para o contexto de forma ineficiente [11-13]. O uso do **Obsidian CLI** (`obsidian-cli`) ou motores locais como **QMD** permite realizar pesquisas por tags, backlinks e propriedades do YAML, reduzindo a ingestão desnecessária de tokens em mais de **60%** [11, 14, 15].
* **Manifestos Dinâmicos e Índices Leves**: Para vaults que crescem bastante ao longo do tempo, crie arquivos de índice ou um **manifesto consolidado** (por exemplo, `docs/_manifest.yaml`) contendo apenas os dados de frontmatter e resumos de todo o cofre [10, 16]. O agente consulta esse manifesto leve em poucos tokens para identificar exatamente quais caminhos de notas precisa carregar [10].
* **Estrutura de Pastas como Filtro de Custo Zero**: Organize o vault com diretórios de escopos bem delimitados (ex.: `_inbox/`, `projetos/`, `decisoes/`, `fatos/`) e configure o `.claudeignore` ou regras de bloqueio de leitura (`settings.local.json`) para impedir que a IA varra pastas pesadas como `.obsidian/`, mídias, anexos ou arquivos de ambiente sensíveis [17-21].

### 2. Governança de Contexto do Agente

* **`CLAUDE.md` Enxuto (< 200 linhas)**: O arquivo `CLAUDE.md` na raiz do vault funciona como o guia operacional básico do agente [22, 23]. Mantenha-o enxuto, contendo apenas convenções globais, atalhos e a taxonomia do vault [23, 24].
* **Regras Específicas por Caminho (`.claude/rules/`)**: Instruções detalhadas para subdomínios ou tipos específicos de notas devem ser isoladas na pasta `.claude/rules/` usando filtros por diretório (*path-scoped rules*) [23, 25]. Com isso, o agente só anexa essas regras à janela de contexto se a tarefa ativa interagir com arquivos dessa pasta [25].
* **Padrão CPR (Compress, Preserve, Resume)**: Adote rotinas de finalização e retomada de sessão [26, 27]:
  * `/preserve`: Extrai aprendizados permanentes, convenções e decisões arquiteturais e grava na memória persistente [27, 28].
  * `/compress`: Resume a conversa atual e grava um log estruturado e pesquisável na pasta de sessões [27, 29].
  * `/resume`: Ao iniciar uma nova sessão, recupera apenas o contexto recente ou busca notas ligadas ao tema específico, sem recarregar históricos longos [27, 29].

### 3. Diretriz "Agents Read, Humans Write"

Mantenha as notas do vault atômicas (princípio Zettelkasten: uma nota por conceito) e interconectadas por wikilinks (`[[Nome da Nota]]`) [30-32]. O princípio orientador desse tipo de integração é **"Agentes leem, humanos escrevem"**: o agente consulta a rede de conhecimento para recuperar contexto e atualizar memórias sintéticas, mantendo o conhecimento autêntico organizado e fácil de filtrar sem carregar documentos vizinhos desnecessariamente [13, 30, 31].

---

## 1. Estrutura de pastas

Para um *vault* grande do Obsidian projetado para atuar como memória de longo prazo de agentes de IA em terminal, **a arquitetura de informação precisa ser otimizada para busca semântica/estruturada e economia de tokens**, e não para navegação manual humana [1, 2].

Quando o conteúdo é consumido por agentes, a estrutura de pastas deixa de ser uma árvore de navegação e passa a funcionar como um **filtro de escopo de custo zero** para restringir a janela de contexto [3, 4].

### 1. Comparativo dos Métodos sob a Ótica da Busca e Economia de Tokens

| Método | Funcionamento Básico | Desempenho para Recuperação por Agentes/IA | Impacto na Economia de Tokens |
| :--- | :--- | :--- | :--- |
| **PARA** (*Projects, Areas, Resources, Archives*) | Organização por estado de ação e ciclo de vida [5, 6]. | **Excelente para filtragem de escopo [4].** Permite que o agente ignore pastas inteiras (como `Archives/` ou anexos) antes de ler os arquivos [3, 4]. | **Muito Alto.** Ao isolar o contexto ativo em `Projects/` e `Areas/`, evita que o agente varra materiais históricos ou irrelevantes [3, 4]. |
| **Johnny.Decimal** | Sistema numérico estrito de categorias de 2 dígitos (ex: `10-19`, `11.01`) [7]. | **Rígido e Ruidoso.** A numeração estrita adiciona fricção e ruído taxonômico. Agentes ao criarem/moverem notas podem errar a numeração ou alucinar categorias [3, 8]. | **Baixo.** A numeração em si não ajuda a economizar tokens e pode confundir a busca por palavras-chave/tags do agente [3]. |
| **Zettelkasten** | Notas atômicas (*uma ideia por nota*), escritas em linguagem própria e conectadas por wikilinks (`[[Nota]]`) [9, 10]. | **Ideal para Ingestão de Contexto [9, 11].** Notas pequenas e focadas cabem facilmente na janela de contexto da IA sem carregar "palha" ou trechos irrelevantes [6, 12]. | **Muito Alto.** Em consultas específicas, o sistema de busca entrega exatamente a nota atômica necessária (ex: 200 tokens em vez de um documento longo de 3.000 tokens) [11, 12]. |
| **MOCs** (*Maps of Content* / Notas de Estrutura) | Notas de índice que agrupam conexões bidirecionais por temas [11, 13, 14]. | **Excelente como Mapa de Navegação [14, 15].** Servem como pontos de entrada centralizados que o agente pode ler para entender a arquitetura de um tópico sem abrir todas as notas filhas [11, 14, 15]. | **Extremamente Alto.** O agente consulta uma nota MOC de poucas linhas para descobrir exatamente quais caminhos atômicos precisa ler [14, 15]. |

### 2. A Estrutura de Pastas Ideal (Modelo Híbrido PARA + Zettelkasten)

A arquitetura mais recomendada é a **fusão do PARA (como vetor de escopo/ação) com o Zettelkasten (como incubadora atômica de conhecimento)** em um *vault* unificado [16, 17]:

```text
meu-vault/
├── CLAUDE.md                   # Manual de operações e diretrizes do agente (< 200 linhas) [18]
├── .claude/                    # Regras de escopo, permissões e skills [19, 20]
├── 00-Inbox/                   # Triagem primária e capturas brutas [6, 19]
├── 10-Projects/                # Projetos ativos com entregáveis e prazos delimitados [6]
├── 20-Areas/                   # Procedimentos reutilizáveis, SOPs, checklists e padrões [6]
├── 30-Resources/               # O Zettelkasten: Notas Atômicas, Pesquisas e Fatos Verificados [6, 21]
│   ├── MOCs/                   # Mapas de Conteúdo (Índices temáticos) [11, 14]
│   ├── Literature/             # Fichamentos de fontes externas e referências [6]
│   └── Permanent/              # Fatos verificados e conceitos atômicos autorais [6]
└── 40-Archives/                # Projetos e recursos desativados (bloqueados para busca) [4, 6]
```

Como o conteúdo se divide:

1. **Procedimentos Reutilizáveis (SOPs, guias de infra, regras)**: Ficam em `20-Areas/` [6]. São consultados pelo agente quando precisa executar uma tarefa operacional recorrente [6].
2. **Conhecimento de Referência, Pesquisas e Fatos**: Ficam em `30-Resources/` organizados de forma atômica (Zettelkasten) [6, 21].
3. **Contexto de Projetos**: Fica em `10-Projects/` [6]. As notas de projeto são enxutas e apenas **apontam via wikilinks** para as notas de procedimento em `Areas/` e conceitos em `Resources/` [6, 21].
4. **Arquivos Mortos**: Ficam em `40-Archives/` [6]. Fica explicitamente configurado no `.claudeignore` ou nas permissões locais (`settings.local.json`) para que o agente nunca gaste tokens buscando nessa pasta durante sessões comuns [3, 4, 20].

### 3. Como Evitar Duplicação e Notas Órfãs

**A. Prevenção de Duplicação (*Single Owner Principle*)**

* **Regra do Documento Dono (*Ownership Boundary*)**: Defina que cada fato ou conceito verificado possui **apenas uma nota oficial que o define** em `30-Resources/` [4, 6]. Se um projeto precisa dessa informação, ele nunca duplica o texto: insere um wikilink `[[Conceito X]]` ou realiza uma transclusão `![[Conceito X#Seção]]` [4, 22].
* **Busca Semântica Pré-Criação**: Configure a instrução do agente (`CLAUDE.md`) para rodar uma busca prévia (via busca vetorial/MCP ou `obsidian-cli`) usando palavras-chave ou *aliases* antes de gerar qualquer arquivo novo [2, 3, 23].
* **Estratégia *Frontmatter-First***: Todas as notas devem conter metadados YAML com o campo `aliases:` (nomes alternativos) e `type:` [2, 24]. Ler apenas o cabeçalho YAML de notas existentes economiza cerca de 92,5% de tokens na verificação de duplicatas antes da escrita [12, 15].

**B. Eliminação de Notas Órfãs**

* **Regra do Link Único (*Single Link Rule*)**: Estabeleça a norma de que nenhuma nota nova pode ser gravada sem possuir ao menos um wikilink apontando para uma nota existente ou para um MOC da categoria [11].
* **Movimentação Segura via Obsidian CLI (Crítico)**: **Nunca permita que o agente use comandos do sistema de arquivos tradicional (como `mv` do Bash)** para mover ou renomear arquivos no *vault* [25, 26]. O uso direto do SO altera o caminho do arquivo, mas rompe todos os wikilinks que apontavam para ele em outras notas, gerando links quebrados e notas órfãs [25, 26]. O agente deve usar obrigatoriamente o **Obsidian CLI** (`obsidian rename` ou `obsidian move`) ou APIs nativas via MCP; isso força o Obsidian a reescrever automaticamente os enlaces no *vault* inteiro, mantendo a integridade da rede [25-27].
* **Varredura e Conectividade via MCP**: Utilize ferramentas de manutenção de plugins MCP (como `find_orphaned_notes` e `find_broken_links`) em rotinas semanais para que o agente identifique notas isoladas e as vincule aos MOCs correspondentes [28].

---

## 2. Títulos e nomes de arquivo

A convenção de títulos e a governança do nome dos arquivos são pontos cruciais em um vault do Obsidian, pois afetam diretamente a precisão do autocompletar do `[[links]]`, a busca semântica do agente e a prevenção de links quebrados.

### 1. Títulos em Forma de Afirmação + Aliases no Frontmatter

A convenção que melhor funciona para a busca e o autocompletar combina **títulos em forma de frase/afirmação atômica** com **aliases no metadado YAML** [1-4]:

* **Títulos em Forma de Afirmação (Declarativos/Atômicos)**: Seguindo o princípio do Zettelkasten ("uma ideia por nota") [2, 5, 6], nomeie o arquivo com uma frase completa que expresse a ideia do documento (ex: `A leitura de YAML frontmatter reduz o consumo de tokens em 90.md`) [1, 2, 7]. No autocompletar do `[[links]]`, ver a declaração inteira ajuda tanto o humano quanto o agente a entender a ideia exata do link sem precisar abrir o arquivo.
* **Uso Estratégico de `aliases:`**: Para não precisar digitar frases longas toda vez que criar um link, defina nomes curtos e atalhos na propriedade `aliases` do YAML frontmatter [3, 4]:

  ```yaml
  ---
  id: 202610110648-economia-tokens
  tags: [obsidian, tokens, frontmatter]
  aliases: [economia de tokens, leitura de frontmatter]
  ---
  ```

  **Por que essa combinação é superior?** O Obsidian indexa tanto o título oficial quanto os *aliases* [3]. Ao digitar `[[economia de tokens` no editor, o autocompletar sugere automaticamente a nota com o título longo, garantindo títulos descritivos e atalhos rápidos de digitação [3, 4].

### 2. Prefixar o Nome do Arquivo com ID: Vale a Pena?

* **No nome do arquivo (Não recomendado)**: Prefixar arquivos com números ou timestamps (ex: `202610110648 - Título da Nota`) polui a lista do autocompletar com ruído visual e dificulta a busca por palavras-chave quando você ou o agente digita `[[...` [3, 4].
* **No YAML Frontmatter (Recomendado)**: O identificador único e imutável (ex: `id: 202610110648` ou `id: YYYYMMDDHHmm-slug`) deve ser mantido estritamente no **YAML frontmatter** [3, 4]. Isso permite que consultas estruturadas (como no Obsidian Bases ou Dataview) rastreiem o arquivo de forma estável [8, 9], mantendo o nome do arquivo limpo e legível para a rede de wikilinks.

### 3. Como Evitar e Lidar com Títulos Duplicados

1. **Evite nomes genéricos**: Títulos curtos como `Backup` ou `Configuração` colidem facilmente em vaults grandes. Transforme-os em declarações específicas (ex: `Estratégia de backup versionado com rclone` e `Configuração do Claude Code local`) [10, 11].
2. **Escopo por pasta + Aliases**: Se dois projetos possuírem documentos de mesmo nome (ex: `Projetos/AppA/Arquitetura.md` e `Projetos/AppB/Arquitetura.md`), o Obsidian exigirá a diferenciação por caminho no wikilink (`[[Projetos/AppA/Arquitetura|Arquitetura App A]]`).

### 4. Renomeando Notas sem Quebrar Links (`obsidian-cli` vs. `mv`)

Renomear arquivos em um vault com milhares de conexões exige cuidado especial com agentes de terminal:

* **Proibido usar o comando nativo do SO (`mv`)**: Executar um comando tradicional do sistema de arquivos como `mv nota-antiga.md nota-nova.md` altera o arquivo no disco rígido, mas **rompe instantaneamente todos os wikilinks** em outras notas do vault que apontavam para aquele arquivo [12, 13].
* **Uso Obrigatório do Obsidian CLI**: Quando o agente de terminal precisa renomear ou mover um arquivo, ele deve utilizar o utilitário **Obsidian CLI** [12, 13]:

  ```bash
  obsidian rename path="30-Resources/NotaAntiga.md" name="NovaAfirmacao"
  obsidian move path="30-Resources/NotaAntiga.md" to="20-Areas/"
  ```

  O Obsidian CLI comunica-se diretamente com a instância aberta do Obsidian e aciona a API nativa do aplicativo, que **reescreve automaticamente todos os `[[wikilinks]]` em todas as notas do vault inteiro**, preservando a integridade do seu grafo [12, 13].

---

## 3. Propriedades (frontmatter)

(Recebida duas vezes, com texto idêntico.)

O uso de **propriedades (*Properties* / YAML Frontmatter)** no topo das notas é o motor que transforma o Obsidian em uma base de dados relacional flexível e legível por IAs [1, 2]. Quando o *vault* cresce para milhares de arquivos e precisa ser consultado tanto pelo **Obsidian Bases** quanto por **agentes de terminal**, seguir padrões rigorosos de nomenclatura, tipos e estrutura previne inconsistências e garante alta performance [1, 3].

### 1. Tipos de Propriedade: Nativas (Padrão) vs. Personalizadas

O Obsidian possui um sistema de propriedades nativo integrado ao editor visual [2]. As propriedades se dividem entre chaves reservadas do ecossistema e tipos de dados customizáveis:

**A. Propriedades Padrão (Reservadas pelo Obsidian)**

* **`tags`**: Aceita uma lista ou valor único de tags (ex: `tags: [projeto, ativo]`). É integrada ao indexador nativo de tags do Obsidian [4, 5].
* **`aliases`**: Lista de nomes alternativos da nota [4, 6]. Fundamental para ativar o autocompletar do `[[wikilinks]]` quando a nota tem um título longo.
* **`cssclasses`** (ou `cssclass`): Permite aplicar estilos visuais de CSS específicos para aquela nota.

**B. Tipos de Dados Suportados pelo Editor**

O Obsidian trata melhor as propriedades quando elas declaram tipos primários claros:

1. **Texto (*Text*)**: Para valores curtos ou cadeias de caracteres.
2. **Lista (*List*)**: Para conjuntos de itens (como tags, links ou participantes) [6, 7].
3. **Número (*Number*)**: Para inteiros e decimais (útil para `rating`, `cost`, `priority`).
4. **Booleano (*Checkbox / Boolean*)**: Valores `true` ou `false` (útil para `archived: false`).
5. **Data (*Date*)**: Formato padrão ISO `YYYY-MM-DD` [4].
6. **Data e Hora (*Date & Time*)**: Formato `YYYY-MM-DDTHH:mm`.

**C. Campos Personalizados (*Custom Fields*)**

São as propriedades criadas para a sua taxonomia. Para manter o *vault* coeso, os campos mais recomendados incluem:

* `type`: Opcional/Essencial para filtrar o tipo de documento (`project`, `sops`, `meeting`, `concept`) [4, 5].
* `status`: Estado atual (`active`, `completed`, `draft`, `on-hold`) [4, 5].
* `project`: Wikilink apontando para a nota de projeto pai (ex: `project: "[[Projeto Alpha]]"`) [4, 7].
* `date` / `due_date`: Data de criação ou prazo final [4, 7].

### 2. Boas Práticas e Padronização para o Obsidian Bases

O **Obsidian Bases** (plugin nativo da versão 1.9+) lê e grava informações diretamente no YAML frontmatter dos arquivos [3, 8]. Para que suas tabelas e visões de cartão funcionem sem erros [9, 10]:

* **Padronize nomes em `snake_case` ou `kebab-case` minúsculo**: O YAML e o indexador de propriedades são sensíveis a maiúsculas/minúsculas. Defina regras estritas para usar sempre minúsculas (ex: `due_date` e não `Due Date` ou `dueDate`).
* **Mantenha Tipo Único por Nome de Propriedade**: Evite definir `status` como booleano (`true`) em uma nota e como texto (`"em_progresso"`) em outra. O Bases e o Dataview agrupam a coluna com base em um tipo único; misturar tipos gera comportamentos imprevisíveis em filtros e ordenações.
* **Sintaxe YAML Estrita**:
  * O bloco deve ser a **primeira coisa da nota** (linha 1), delimitado por três traços (`---`) no início e no fim [1, 11].
  * Use **espaços** para indentação, nunca tabulações (*tabs*) [11, 12].
  * Coloque aspas duplas em valores que contenham caracteres especiais como dois pontos (`:`), cerquilha (`#`), colchetes (`[`) ou chaves (`{`) [11].
* **Relações por Wikilinks**: Para relacionar documentos, atribua wikilinks entre aspas dentro das propriedades (ex: `author: "[[Sönke Ahrens]]"` ou `attendees: ["[[Ana]]", "[[Carlos]]"]`) [5, 7]. O Bases renderiza esses links como elementos clicáveis que preservam o grafo de conexões.

### 3. Impacto de Desempenho e Limites

**Impacto na Interface do Obsidian e no Bases**

* **Desempenho Nativo Custo-Zero**: Como o Bases é um plugin nativo do núcleo (*Core Plugin*), ele utiliza o cache interno do Obsidian (`app.metadataCache`) [3, 13]. Ele carrega e edita milhares de notas em lote quase instantaneamente, superando o impacto de memória de plugins comunitários baseados em scripts complexos de leitura em tempo de execução [3, 13, 14].
* **Evite Objetos YAML Muito Aninhados (*Nested YAML*)**: O Obsidian visualiza melhor propriedades de nível plano (*flat key-value*). Estruturas profundamente aninhadas podem causar problemas de renderização no editor visual de propriedades e falhas na edição via lote [3].

**Impacto no Agente de Terminal (Economia de Tokens)**

* **Padrão *Frontmatter-First***: Para agentes de terminal, um frontmatter bem estruturado é a ferramenta número um de economia de tokens [1]. Ao ler apenas os primeiros 10 a 15 linhas do YAML (~150 tokens) para avaliar se a nota é relevante, o agente economiza até **92,5% de tokens** em comparação com a leitura do corpo inteiro do documento (~2.000 tokens) [15, 16].
* **Edição Segura via CLI**: Quando um agente precisa alterar uma propriedade, ele deve utilizar a funcionalidade `obsidian property:set` da CLI do Obsidian ou chamadas de API nativas, garantindo que o YAML não seja corrompido durante a gravação [17-19].

---

## 4. Tags, aliases, links e MOCs

A organização taxonômica de um *vault* no Obsidian exige uma divisão clara entre o que é **atributo de estado**, o que é **conexão conceitual** e o que é **mapa de navegação**.

### 1. Tags Aninhadas (`#area/subarea`) vs. Tags Planas (`#tag`)

* **Tags Planas (`#tag`)**: A comunidade de PKM e as diretrizes recomendadas de *frontmatter* orientam o uso predominante de **tags planas e minimalistas** (ex: `#cli`, `#ia`, `#banco-de-dados`) [1, 2]. Elas mantêm a taxonomia simples, facilitam as consultas de busca e evitam criar uma estrutura hierárquica paralela e rígida [1, 2].
* **Tags Aninhadas (`#area/subarea`)**: Devem ser reservadas primariamente para **estados operacionais ou fluxos de trabalho** (ex: `#status/rascunho`, `#status/revisado`). Utilizar tags aninhadas para tentar mapear toda a árvore de conhecimento do *vault* costuma gerar ruído e desordem à medida que o número de notas cresce [1, 3, 4].

### 2. Quantidade Saudável de Tags por Nota

* O padrão recomendado para manter a utilidade das etiquetas é de **2 a 5 tags por nota** [2].
* Quando uma nota necessita de mais de 5 tags, isso é um indicativo de que o documento abrange múltiplos conceitos e deveria ser dividido em notas atômicas menores [2, 4]. O excesso de tags gera diluição informativa: se tudo é etiquetado com dezenas de termos, o filtro por tags perde sua precisão [4].

### 3. Como os `aliases` Ajudam a Achar Notas por Sinônimo

* A propriedade `aliases:` declarada no YAML frontmatter permite definir uma lista de **nomes alternativos, acrônimos, siglas ou sinônimos** para o arquivo [2, 5].
* Quando você digita `[[` no editor do Obsidian para criar um link ou realiza uma busca, o sistema de autocompletar indexa tanto o nome do arquivo quanto os seus *aliases* [2, 5].
* **Exemplo**: Uma nota com título declarativo longo como `A Leitura de Frontmatter Reduz Consumo de Tokens.md` pode conter na propriedade `aliases: [economia de tokens, leitura de YAML]`. Ao digitar `[[economia de tokens`, o autocompletar do Obsidian localiza a nota imediatamente [2, 5].

### 4. Tags vs. Links Internos (`[[links]]`) vs. MOCs: A Recomendação da Comunidade

A arquitetura recomendada pela comunidade adota o princípio de **"Hubs/MOCs sobre Tags"** (*Hubs over Tags*) [1]:

1. **Links Internos (`[[wikilinks]]`)**: São o **mecanismo primário de conexão semântica** [6, 7]. Servem para conectar ideias atômicas diretamente e contextualizar no corpo do texto *por que* dois conceitos se relacionam [8, 9].
2. **MOCs (Maps of Content / Hub Notes)**: São o **instrumento recomendado para agrupar e recuperar notas por assunto** [1, 7]. Um MOC é uma nota de índice temática que lista e organiza os links de um determinado tópico, funcionando como um mapa de navegação sem engessar os arquivos em pastas rígidas [1, 7].
3. **Tags (`#tags`)**: Funcionam apenas para **categorização leve e atributos transversais**, e não como o sistema principal de organização por tópicos [1, 2, 4].

### 5. Como Combinar os Três sem Virar Bagunça

Para manter a ordem no *vault*, atribua papéis estritos e não sobrepostos a cada elemento:

| Elemento | Papel Único no Vault | Regra de Uso |
| :--- | :--- | :--- |
| **Tags** | Metadados de **Tipo, Estado e Atributo Transversal** [1, 2]. | Mantenha entre 2 a 5 tags planas no frontmatter (ex: `tags: [conceito, verificado]`) [1, 2]. |
| **Wikilinks** | **Conexão Atômica e Explícita** entre ideias [8, 10]. | Aplique a **Regra do Link Único**: toda nota nova deve ter ao menos 1 link apontando para outra nota ou MOC [8, 11]. |
| **MOCs** | **Agrupamento e Navegação Temática** por assunto [1, 7]. | Crie um MOC sempre que acumular **3 ou mais notas** sobre o mesmo tópico para centralizar os links do assunto [1]. |

---

## 5. Nota atômica e estrutura interna

A definição do tamanho, escopo e estrutura interna de uma nota no Obsidian determina a eficiência da sua base de conhecimento, influenciando diretamente a reaproveitabilidade para humanos e a **economia de tokens nas consultas de agentes de IA** [1, 2].

### 1. Tamanho e Escopo Ideal: Nota Atômica vs. Nota Longa

O padrão consagrado para memórias de longo prazo e integração agêntica é o uso de **notas atômicas (*One Note = One Idea*)** [2, 3]:

* **O Princípio da Atomicidade**: Cada nota permanente deve focar estritamente em **um único conceito, fato, argumento ou decisão** [2, 4]. A nota precisa ser autônoma e autossuficiente — ou seja, compreensível por si só, mesmo quando lida isoladamente sem o contexto de onde foi extraída [2, 4].
* **Por que Notas Atômicas favorecem a IA e a Busca?**
  * **Precisão e Economia de Tokens**: Quando o sistema de busca recupera uma nota atômica (geralmente entre 200 e 500 tokens), o agente de terminal consome exatamente o trecho necessário [1, 3]. Documentos longos (2.000+ tokens) forçam o agente a ingerir texto irrelevante ("palha"), encarecendo a conversa e aumentando a latência [1].
  * **Reaproveitamento Dinâmico**: Uma nota atômica sobre um conceito específico pode ser vinculada por wikilinks a múltiplos projetos, decisões e MOCs sem gerar duplicação [2, 5].
* **Quando usar Notas Longas?**: Documentos extensos devem ser reservados para a fase de captura/literatura (fichamento bruto de um livro/artigo) [2, 3] ou entregáveis finais (como um PRD ou relatório). No entanto, à medida que a informação amadurece, os conceitos validados de uma nota longa devem ser divididos em notas atômicas permanentes [3, 4].

### 2. Quando Quebrar um Assunto em Várias Notas + Nota de Índice (MOC)

Em vez de criar estruturas de pastas profundas, adote a regra **"Hubs/MOCs sobre Tags"** (*Hubs over Tags*) [6]:

* **A Regra dos 3+ Itens**: Sempre que você acumular **3 ou mais notas atômicas sobre um mesmo tema**, crie uma **Nota de Índice ou MOC (Map of Content / Hub Note)** [6].
* **Como o MOC Funciona**: O MOC é um "mapa de navegação" enxuto que lista e contextualiza os wikilinks das notas atômicas daquele tópico [2, 6].
* **Vantagem para Agentes de IA**: O MOC funciona como um filtro de custo mínimo de tokens [7]. Ao invés de o agente varrer dezenas de arquivos, ele lê uma única nota de índice de poucas linhas, descobre exatamente quais caminhos atômicos precisa consultar e abre apenas as notas certas [6, 7].

### 3. Estruturação Interna da Nota para Leitura Rápida

Para garantir escaneabilidade imediata (para os seus olhos e para o leitor de contexto da IA), estruture a nota em quatro blocos bem delimitados:

1. **YAML Frontmatter (*Frontmatter-First*)**: Insira os metadados no topo da nota entre `---` [8]. Inclua propriedades padronizadas como `id`, `type`, `tags`, `status` e `aliases` [6, 9].
   * *Impacto em Tokens*: Instruir o agente a ler apenas o bloco YAML (primeiras 10–15 linhas) permite avaliar a relevância do arquivo consumindo ~150 tokens por nota em vez de 2.000+, gerando uma **economia de até 92,5% de tokens** em etapas exploratórias [1, 7].
2. **Resumo / Declaração Principal (Logo abaixo do Frontmatter)**: Abra o corpo do texto com uma frase ou parágrafo curto (estilo Técnica de Feynman) que resuma a ideia central da nota em suas próprias palavras [4].
3. **Callouts (Blocos de Destaque Visual)**: Utilize a sintaxe de *callouts* do Obsidian (`> [!abstract]`, `> [!info]`, `> [!warning]`) [10]. Eles destacam conclusões essenciais e são interpretados por ferramentas e habilidades de Markdown do agente [10].
4. **Seção de Conexões e Referências (`## Conexões`)**: No final da nota, crie uma seção dedicada aos links de contexto [11]. Aplique a **Regra do Link Único**: toda nota nova deve obrigatoriamente incluir pelo menos um wikilink `[[Nome da Nota]]` apontando para uma nota existente ou para seu MOC correspondente, eliminando notas órfãs [4, 12].

Exemplo de estrutura padrão de nota atômica:

```markdown
---
id: 20261011-leitura-frontmatter
type: concept
tags: [obsidian, tokens, otimizacao]
aliases: [economia de frontmatter, leitura de metadados]
status: verificado
---

# Leitura de Frontmatter Reduz Consumo de Tokens

Ler apenas as primeiras 15 linhas de metadados YAML de uma nota permite avaliar sua relevância gastando ~150 tokens, reduzindo o custo de contexto em mais de 90% em comparação com a leitura integral do arquivo.

> [!abstract] Ponto Chave
> O padrão Frontmatter-First atua como uma camada de índice leve que preserva a janela de contexto de agentes de terminal.

## Detalhes do Conceito
Quando um agente varre um vault grande com milhares de arquivos, carregar notas completas esgota a memória de trabalho. A estrutura YAML padronizada fornece a classificação e o resumo necessários para decisões rápidas de leitura.

## Conexões
- Baseado em: [[Otimização de Contexto para Agentes]]
- MOC Relacionado: [[MOC Arquitetura de Informação]]
```

---

## 6. Bases e Dataview

O recurso **Obsidian Bases** (introduzido como plugin nativo do núcleo a partir da versão 1.9 do Obsidian) representa uma evolução na forma como o aplicativo lida com dados estruturados [1-3]. Ele permite transformar qualquer conjunto de notas Markdown em um banco de dados relacional e interativo, armazenando a estrutura de consulta em arquivos abertos de extensão `.base` (com sintaxe baseada em YAML) [4-6].

### 1. Obsidian Bases vs. Dataview

| Critério | Obsidian Bases (Core Plugin) | Dataview (Plugin Comunitário) |
| :--- | :--- | :--- |
| **Origem e Suporte** | Plugin oficial do núcleo do aplicativo, garantindo longevidade e atualizações integradas [1, 7]. | Plugin desenvolvido pela comunidade (Michael Brenan / blacksmithgu) [1, 8]. |
| **Modo de Edição** | **Bidirecional (Read-Write)**: Permite editar os metadados diretamente nas colunas das tabelas (*batch editing*), atualizando o YAML das notas em tempo real [4, 9, 10]. | **Somente Leitura (Read-Only)**: Gera tabelas e listas estáticas para consulta visual sem alterar os arquivos diretamente [1, 11]. |
| **Desempenho** | **Ultrarrápido em escala**: Utiliza o cache interno de metadados do Obsidian (`app.metadataCache`), funcionando de forma fluida mesmo em vaults com milhares de notas [1, 4, 12]. | Pode apresentar lentidão ou travamentos de interface ao processar milhares de notas ou scripts complexos de DataviewJS [1, 4, 11]. |
| **Interface de Uso** | Interface gráfica baseada em **clique para filtrar e ordenar** (*click-to-add*), sem necessidade de programar [1, 7, 9]. | Requer o aprendizado de uma linguagem de consulta própria (DQL - Dataview Query Language ou JavaScript/DataviewJS) [1, 8, 11]. |
| **Escopo de Dados** | Consulta exclusivamente as **propriedades do YAML Frontmatter** e **tags** do documento [1, 4, 13]. | Consulta o YAML e também o **corpo do texto** (tarefas/checkboxes, blocos e campos *inline* como `chave:: valor`) [1, 8]. |

### 2. Modelagem de Notas com Propriedades para Tabela, Cartões e Kanban

Para alimentar as visualizações do Bases, é necessário modelar o **YAML Frontmatter** das notas de forma consistente [4, 14].

**A. Exemplo de Estrutura de Propriedades (YAML)**

```yaml
---
type: project            # Categoria da nota (ex: project, book, meeting)
status: in_progress      # Estado (ex: backlog, in_progress, completed)
project: "[[Projeto X]]" # Relacionamento com outra nota via Wikilink entre aspas
due_date: 2026-11-01     # Data ISO (YYYY-MM-DD)
cover: "assets/capa.jpg" # Caminho da imagem para visualização visual
tags: [trabalho, ia]     # Lista de etiquetas
---
```

**B. Montando as Visualizações**

* **Tabelas (Table View)**: Ideais para gerenciar listas operacionais (como reuniões ou tarefas de projetos) com adição e edição dinâmica de colunas [2, 7, 9].
* **Cartões (Card View)**: Excelentes para bibliotecas de referências, fichamentos de livros e perfis de pessoas, exibindo uma imagem de capa (`cover`) e os metadados principais em formato de galeria [15, 16].
* **Quadros e Agrupamentos (Kanban)**: O Bases permite criar visualizações agrupadas por propriedades (por exemplo, agrupar registros pela coluna `status`) [17, 18]. No entanto, se você precisa do comportamento tradicional de quadro Kanban com colunas interativas para arrastar e soltar cartões (*drag-and-drop*), a recomendação da comunidade continua sendo integrar o plugin comunitário **Kanban** [19-21].

### 3. Boas Práticas e Limitações Atuais

**Boas Práticas**

* **Inicie Afunilando os Resultados (*Whittle Down*)**: O Bases parte do princípio de carregar todas as notas do vault e aplicar filtros [9, 12]. Crie um filtro inicial de escopo no topo da base (ex: `folder = "10-Projects"` ou `type = "project"`) para trabalhar apenas com os arquivos relevantes [9, 22].
* **Geração Automatizada de Notas via Base**: Cada visão criada no Bases atua como um gerador de modelos (*Template Generator*) [23, 24]. Ao clicar no botão "Novo" dentro de uma base de projetos, o Obsidian gera uma nota preenchida automaticamente com os metadados e tags daquela base [23, 24].
* **Embeds Dinâmicos com `this.note`**: É possível embutir um código de Base dentro de uma nota MOC ou de Projeto usando filtros dinâmicos (como `project = this.note`) [25, 26]. Dessa forma, ao abrir a nota do "Projeto Alpha", a tabela embutida exibe automaticamente apenas as reuniões e decisões vinculadas àquele projeto [25, 26].
* **Padronização Estrita de Nomes**: Mantenha as chaves de propriedades em `snake_case` minúsculo e evite alternar os tipos de dados (por exemplo, não use texto em um campo de data) [27].

**Limitações Atuais**

* **Sem Leitura do Corpo de Texto**: O Bases não lê caixas de seleção, blocos ou metadados *inline* inseridos no corpo do texto (função na qual o Dataview/Datacore ainda é indispensável) [1, 13, 28].
* **Ajuste de Células Limitado**: A interface do Bases ainda possui restrições para redimensionamento manual fino da largura de colunas em tabelas [29].
* **Ambiente Individual Local**: Como todo o ecossistema Obsidian, o Bases opera localmente e não substitui bancos de dados em nuvem voltados para colaboração multi-usuário simultânea em tempo real (como o Notion) [30, 31].

---

## 7. Escala e desempenho

Em vaults do **Obsidian com 10.000 a 50.000 notas**, o modelo *local-first* baseado em arquivos de texto Markdown simples garante excelente estabilidade e perenidade dos dados [1, 2]. No entanto, a quantidade massiva de arquivos impõe gargalos em recursos específicos de visualização e indexação.

### 1. O Que Fica Lento em Vaults Grandes (10k a 50k Notas)

* **Grafo Global (Graph View)**: Com dezenas de milhares de nós e arestas, a renderização do grafo global consome muita CPU/GPU e se torna visualmente poluída e pouco prática para navegação [3, 4].
* **Consultas do Dataview**: O plugin *Dataview* executa scripts de busca e renderização em tempo de execução [5]. Em vaults desse porte, queries sem filtros restritivos provocam engasgos na interface e congelamentos no editor [5, 6].
* **Inicialização do Obsidian Bases sem Filtros**: Ao contrário do Dataview, o recurso nativo **Obsidian Bases** utiliza o cache interno do aplicativo (`app.metadataCache`) e é ultrarrápido [5-7]. Porém, o comportamento padrão do Bases é carregar **todas as notas do vault** para depois afunilar pelos filtros [7, 8]. Se a base não possuir um filtro estrito no topo, a abertura inicial varre dezenas de milhares de registros.
* **Abertura do Vault e Sincronização**: Na inicialização, o Obsidian precisa ler a árvore de arquivos para atualizar o cache de metadados. Além disso, sincronizar 50 mil arquivos pequenos por serviços genéricos de nuvem (como o iCloud) causa alto uso de I/O em disco e pode provocar erros de sincronização ou descarregamento silencioso de cache [9-11].

### 2. Práticas Recomendadas para Manter o Vault Rápido

1. **Aplique a Técnica de Afunilamento (*Whittle Down*) nas Bases**: Sempre insira um filtro de escopo no topo das tabelas e visões do Bases (por exemplo, `folder = "10-Projects"` ou `type = "concept"`), garantindo que a base processe apenas o subconjunto necessário de notas [7, 8].
2. **Configure Exclusões no `app.json` / `.claudeignore`**: Oculte pastas de arquivos mortos (`40-Archives`), anexos pesados, mídias e dependências do indexador nativo definindo filtros de exclusão (`userIgnoreFilters`) no arquivo `.obsidian/app.json` ou no `.claudeignore` para agentes [12].
3. **Priorize o Grafo Local (*Local Graph*)**: Substitua o uso do Grafo Global pelo **Local Graph** com profundidade limitada a 1 ou 2 conexões para explorar a vizinhança semântica da nota ativa sem sobrecarregar a interface [3].
4. **Adote o Padrão *Frontmatter-First* (Metadados YAML)**: Mantenha um bloco YAML padronizado no topo de cada arquivo [2, 13]. Ler apenas o cabeçalho YAML de notas reduz drasticamente o tempo de exploração e o consumo de contexto em buscas automatizadas [14, 15].
5. **Utilize Soluções Dedicadas de Backup e Sync**: Evite sincronizadores que descarregam arquivos locais (como o iCloud em dispositivos móveis) [10, 11]. Utilize o **Obsidian Sync** ou scripts com **rclone** para snapshots e backups versionados [9, 16, 17].

### 3. Limites Práticos

**A. Profundidade de Pastas**

* **Limite do Sistema Operacional (Caminhos de Arquivo)**: O Obsidian não impõe um limite rígido de subpastas. O gargalo real é o limite do sistema operacional para o caminho absoluto do arquivo (como a limitação clássica de 260 caracteres do `MAX_PATH` no Windows).
* **Recomendação**: Mantenha uma árvore de pastas rasa (máximo de 2 a 3 níveis de profundidade, como no sistema **PARA**) e dependa de **wikilinks (`[[Nota]]`)**, **MOCs (Notas de Índice)** e **tags** para navegação [18, 19].

**B. Tamanho de Nota**

* **Desempenho do Editor**: Notas atômicas em texto plano de **200 a 1.000 palavras** (alguns KB) abrem e renderizam instantaneamente [14, 18]. Arquivos gigantescos de texto contínuo (com múltiplos Megabytes ou dezenas de milhares de linhas, como *logs* não formatados) tornam a digitação e a renderização no editor visual (*CodeMirror 6*) lentas e instáveis.
* **Economia e IA**: Notas atômicas concentradas em uma única ideia são facilmente reusáveis e evitam o esgotamento desnecessário da janela de contexto de agentes de terminal em buscas semânticas [14, 15, 18].

---

## 8. Captura rápida e triagem

### 1. Fluxo Recomendado: Da Captura Rápida (Inbox) à Nota Permanente

1. **Captura Fricção-Zero (A Pasta `_inbox`)**: Todas as anotações rápidas, áudios, clippings de web e transcrições de reuniões devem cair em um único diretório temporário: a pasta `_inbox` (ou `00-Inbox`) [3-5]. **Não perca tempo formatando ou categorizando no momento da captura** [1, 6]. Se você utiliza agentes de IA no terminal, comandos simplificados como `/capture` podem injetar ideias diretamente no inbox sem interromper seu raciocínio [7, 8].
2. **Filtragem e Carência Temporal**: Deixe as notas repousarem no inbox por **1 a 2 dias** antes do processamento definitivo [1, 9]. Esse intervalo frio permite descartar ideias passageiras e filtrar ruídos que pareceram urgentes no momento do registro [9].
3. **Transformação Atômica e Conexão (Nota Permanente)**:
   * **Técnica de Feynman**: Ao revisar a nota do inbox, reescreva o conceito **com suas próprias palavras** em um novo arquivo [1, 10, 11].
   * **Atomicidade**: Garanta que a nova nota trate de um único conceito autônomo [10, 13, 14].
   * **Regra do Link Único**: Nenhuma nota vai para a pasta definitiva sem pelo menos um `[[wikilink]]` conectando-a a uma nota preexistente ou a um MOC [10, 15].
   * *Processamento Assistido por IA*: comandos como `/process-inbox` para a IA analisar os itens brutos, sugerir referências cruzadas, aplicar tags e organizar a nota no destino [8, 16].

### 2. O Que Plugins como Templater e QuickAdd Resolvem

* **Templater**: motor avançado de modelos baseado em JavaScript [17, 18]. Insere datas/horas dinâmicas no YAML, abre prompts interativos na criação, manipula nomes de arquivo e executa comandos externos [17, 19, 20].
* **QuickAdd**: velocidade de entrada e macros [21]. Atalhos globais para injetar texto, criar estruturas de projeto por formulário e encadear ações [21, 22].

### 3. Dá para Ter um Bom Fluxo Apenas com Recursos Nativos?

Sim. Com **Obsidian Bases** (v1.9+) + Templates + Propriedades (YAML) [19, 23, 24]:

* **Gerador Automático de Notas via Bases**: cada visão atua como criador de modelos; o botão "Novo" gera nota herdando as propriedades/tags/status do filtro [25, 26].
* **Triagem e Edição em Lote na Inbox**: ver a `00-Inbox` numa tabela do Bases e editar propriedades direto nas células [23, 27, 28].
* **Padronização Nativa de YAML**: o editor visual de propriedades valida tipos sem erros de sintaxe [23, 24, 29].

## 9. Notas que não apodrecem e ritmo de revisão

### 1. Resumo das Ideias-Chave (Zettelkasten & Andy Matuschak no Obsidian)

* **Atomicidade**: cada nota permanente isola **um único conceito/fato/argumento/decisão** [1-3].
* **Reescrita Autoral (Feynman)**: toda nota permanente escrita **com suas próprias palavras** [2, 3, 5].
* **Estrutura Emergente (Bottom-Up)**: a organização surge das conexões (`[[wikilinks]]`), não de pastas rígidas [2, 6, 7, 8].
* **Títulos Declarativos**: o nome da nota é a própria declaração do conceito (ex.: `A leitura de frontmatter reduz o consumo de tokens` em vez de `Economia de Tokens`) [9, 10].
* **Fluxo Evergreen**: as notas maturam (coleta, processamento, estado atômico/estável) e são refinadas conforme novas ideias se conectam [9, 11].

### 2. Como Escrever Notas que Continuam Úteis

1. **Autonomia e Autossuficiência**: inteligível por si só no futuro, sem reconsultar a fonte [2].
2. **Regra do Link Único**: toda nova nota permanente com pelo menos um `[[wikilink]]` para nota ou MOC [3, 12, 13].
3. **Metadados Padronizados (YAML)**: `id:` estável, `type: concept` (ou `permanent`), `aliases:`, 2 a 5 `tags:` planas [10, 13].
4. **Resumo Visual / Callouts**: abre com síntese curta e callouts com a ideia principal [3, 14].

### 3. Como Evitar o "Lixo Esquecido" e Rotinas de Revisão

**A. Fricção Proposital**: inbox com período de carência (deixe repousar 1 a 3 dias; o que parecia urgente some) [11, 16, 17].

**B. Rotinas de Revisão da Comunidade**:

* **Revisão Focada em Projetos (Just-in-Time)**: a melhor revisão ocorre **quando você produz algo**; ao pesquisar um tema, siga backlinks e crie novos links entre o que sabia e o que está aprendendo [18, 19].
* **Manutenção Periódica**: diária (5–10 min: esvaziar inbox); semanal (1 h: transformar inbox em notas permanentes, atualizar MOCs, limpar divergências); mensal (varredura por "ilhas" — notas sem backlinks — para conectá-las) [5, 20, 21, 22].
* **Revisão Auxiliada por Agentes**: rotinas no terminal (`/process-inbox`, `/weekly-review`, busca semântica) para sugerir referências cruzadas esquecidas e identificar ideias com conexões suficientes para virar um MOC [20-22].

## 10. Pesquisa externa → conhecimento validado → skill

A chave é combinar PARA + Zettelkasten [1] com um padrão estrito de **proveniência no YAML e no texto** [2, 3].

### 1. Separação de Estrutura: Notas de Literatura vs. Notas Permanentes

* **Pasta de Pesquisa/Fontes (`20-Literature/` ou `30-Resources/Literature/`)**: resumos de livros, guias, transcrições, FAQs, linhas do tempo [1]. O texto reflete **a visão da fonte** [1, 4]. YAML com `type: literature`, `source: "https://..."` ou `author:` [1, 3].
* **Pasta de Conclusões Validadas (`30-Permanent/`)**: **apenas as suas conclusões testadas** [1, 4], atômicas e pela Técnica de Feynman [4, 5]. YAML com `type: permanent` e `status: verificado` [1, 4].

### 2. Como Registrar e Rastrear a Fonte de Cada Afirmação

1. **Atribuição Global no Frontmatter**: `source:` apontando para a nota de literatura ou URL [1, 3].
2. **Conexão Granular com Wikilinks de Seção**: no corpo, link para o cabeçalho/bloco exato da fonte, ex.: `... [[Literature - Guia Rclone 2026#Comportamento do Cache]]` [2].
3. **Contraste Visual com Callouts Semânticos**: diferencie a afirmação da fonte do seu teste:
   ```markdown
   > [!quote] Afirmação da Fonte
   > A doc afirma que `--transfers 4` é ideal para 100Mbps [[Literature - Rclone Doc#Performance]].

   > [!check] Validação Prática
   > Testado em produção em 11/10/2026: estabilizou melhor com `--transfers 2`.
   ```

### 3. Transformando Pesquisa em Procedimento Reutilizável (SOP)

Um SOP mora em **`50-Areas/`** (ou `20-Areas/`), voltado para execução rápida mas com backlinks transparentes para a pesquisa de origem [1, 5, 6]. O frontmatter traz `type: sop`, `area:`, `status: verificado` e uma lista `sources:` de notas de literatura. O corpo separa, em cada passo, **o que foi comprovado** (teste prático) do **que é recomendação da fonte** (com o wikilink para o trecho).

## 11. Procedimentos, prompts e agentes reutilizáveis

Conhecimento (Zettelkasten) é conceitual e atemporal; procedimentos e definições de agentes são **ativos de execução** — demandam validação contínua, tipagem clara e recuperação por filtros [1, 2].

### 1. Arquitetura de Pastas: Ilhas de Execução vs. Conhecimento

```text
meu-vault/
├── CLAUDE.md                      # Manual operacional raiz da IA (< 200 linhas)
├── .claude/                       # [SISTEMA DA IA]
│   ├── rules/                     # Regras ativadas por caminho (path-scoped)
│   ├── skills/                    # Agent Skills (skills/<nome>/SKILL.md)
│   └── agents/                    # Subagentes (ex: code-reviewer.md)
├── 00-Inbox/
├── 20-Areas/                      # [OPERACIONAL] SOPs e Checklists
│   ├── SOPs/
│   └── Checklists/
├── 30-Resources/                  # [CONHECIMENTO] Zettelkasten
└── 90-System/                     # [SISTEMA DO OBSIDIAN]
    ├── Templates/
    ├── Prompts/                   # Repositório de prompts reutilizáveis
    └── Bases/                     # Arquivos .base
```

* **Definições de agentes e habilidades de IA**: em `.claude/skills/` e `.claude/agents/` no padrão Agent Skills (`SKILL.md`) [4-8].
* **SOPs e Checklists**: em `20-Areas/` [9].
* **Conhecimento e fatos**: isolados em `30-Resources/` ou `Permanent/`, atômicos [9].

### 2. Esquema de Propriedades (YAML) Operacional

```yaml
---
id: sop-deploy-producao
type: sop                   # sop, checklist, prompt-template, agent-spec
status: active              # draft, active, deprecated
version: 1.2.0
last_updated: 2026-10-11
domain: devops
tags: [sop, deploy]
aliases: ["Procedimento de Deploy", "SOP-01"]
---
```

### 3. Convenção de Nomes para Autocompletar

Prefixos funcionais: `SOP - Backup Offsite com Rclone.md`, `Checklist - Pre-flight Release Produção.md`, `Prompt - Gerador de PRDs.md`, `Agent - Especialista em Revisão de Segurança.md`. Ao digitar `[[SOP` o autocompletar exibe o catálogo correspondente.

### 4. Versionamento e Rastreabilidade

1. **Git (recomendado)**: histórico de commits registra quem alterou cada linha sem poluir a nota [16, 17].
2. **Log interno (callouts)**: bloco `> [!history] Histórico de Revisões` no fim do procedimento.

### 5. Recuperação Dinâmica com Obsidian Bases

Catálogos `.base` por `type` (ex.: `sops.base` com `type = "sop"` mostrando `domain`, `status`, `version`, `last_updated`; `prompts.base` como galeria de cartões por `type = "prompt-template"`). Editar status/versão direto na célula atualiza o YAML em tempo real [10, 11, 18, 19].

## 12. Anexos

### 1. Onde Guardar (Settings > Files & links > Default location for new attachments)

* **Pasta centralizada (recomendado)**: pasta global dedicada (ex.: `60-Resources/Attachments/` ou `_assets/`) — concentra binários, facilita backup, sync e exclusão [1, 2, 3].
* **Subpasta na pasta da nota**: cria `./assets/` junto da nota ativa — útil se você move pastas de projeto inteiras.

### 2. Como Manter o Vault Limpo

* **Padronização de nomes na importação**: evite `Pasted image ...png`; use plugin como **Paste Image Rename** [6].
* **Filtro de ignorados (`app.json` / `.claudeignore`)**: `userIgnoreFilters` em `.obsidian/app.json` para o indexador não varrer binários pesados [7, 8]:
  ```json
  { "userIgnoreFilters": ["assets/", "*.pdf", "*.png", "*.jpg"] }
  ```
* **Limpeza de anexos órfãos**: plugins (Attachment Organizer) para remover imagens/PDFs sem nenhum `[[wikilink]]` [9].

### 3. Como Referenciar e Citar a Origem

* **Sintaxe**: embutir `![[diagrama.png]]` / `![[documento.pdf]]`; link simples `[[documento.pdf]]`; página específica `![[documento.pdf#page=5]]`.
* **Rastreabilidade via Nota de Literatura**: não deixe o PDF "solto"; crie uma nota em `20-Literature/` com `type: literature`, `source:` e `attachment: "[[arquivo.pdf]]"` [1, 10].
* **Citação contextual (callout)**: `> [!quote] Origem da Imagem` com o wikilink do anexo e o trecho da fonte [11].

### 4. Plugins Recomendados

1. **Omnisearch**: busca com ranking BM25, pesquisa dentro de PDFs e OCR em imagens [4, 12].
2. **Image Converter / Compression**: comprime/converte imagens coladas para `.webp` [13].
3. **Paste Image Rename**: pede nome descritivo ao colar imagem [6].

## 13. Dados sensíveis, sincronização e backup

O Obsidian é *local-first* em texto plano `.md`: qualquer processo com leitura no sistema de arquivos vê o conteúdo [2-4]. A abordagem é em camadas [1].

### 1. Excluir Pastas da Sync e Criptografar São Comuns? Sim [1, 5, 6]

* **Sincronização seletiva**: isole dados críticos numa pasta (ex.: `50-Areas/Clientes-Confidencial/` ou `_secretos/`) e exclua-a da sincronização para dispositivos móveis [6, 7, 8].
* **Criptografia E2EE**: na transmissão e nos snapshots de backup fora da máquina [5, 9, 10].

### 2. Sincronização por Método

| Método | Segurança para dados sensíveis | Como lidar |
| :--- | :--- | :--- |
| **Obsidian Sync (oficial)** | Muito alto: E2EE AES-256 nativa; dados cifrados localmente antes de sair [10-12]. | Usar **Pastas Excluídas** para não baixar confidenciais em móveis [6, 8]. |
| **Git / GitHub / GitLab** | Baixo a médio: texto plano, sem cripto nativa [13, 14]. | `.gitignore` para pastas confidenciais/`.env`, ou `git-crypt` [14, 15]. |
| **Nuvens genéricas (iCloud, Drive, Dropbox)** | Frágil/inadequado: sem E2EE por arquivo, falhas de sync; iCloud pode descarregar cache no iOS e sobrescrever por arquivo vazio [5, 16, 17, 18]. | Evitar para este vault. |

### 3. Proteção Contra Agentes de IA em Terminal

O `.gitignore` **não basta**: ferramentas `Glob`/busca de agentes podem ignorá-lo e ler segredos [19-21]. Use **read deny rules** em `.claude/settings.local.json`:

```json
{
  "permissions": {
    "deny": ["read:50-Areas/Clientes-Confidencial/*", "read:**/*.env", "read:**/*.pem"]
  }
}
```

### 4. Backup Resiliente (sync != backup)

Sincronizar replica deleção/corrupção; backup preserva histórico imutável [16, 24-26].

1. **Backup local criptografado**: plugin **Local Backup** gera `.zip` com data em volume local cifrado (BitLocker/FileVault) [27-29].
2. **Off-site com `rclone crypt`**: cifra conteúdo e nomes com AES-256 antes do envio (Backblaze B2, S3); flag `--backup-dir` move alterados/apagados para pastas de versão sem sobrescrever o histórico [9, 30-33].
