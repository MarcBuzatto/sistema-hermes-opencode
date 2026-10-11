# Arquitetura

## Diagnóstico

O comportamento descrito ("lembram, mas lembram errado e defendem o erro") tem causas concretas, não é falta de inteligência do modelo:

- **Memória automática sem verificação.** O Hermes mantém `~/.hermes/memories/MEMORY.md` e `USER.md`, injetados no prompt de sistema de toda sessão. O agente grava ali sozinho, inclusive numa revisão em segundo plano depois de cada turno (`write_approval: false` por padrão). Um palpite errado vira "nota pessoal" e reaparece em todas as sessões seguintes como se fosse fato.
- **Compactação com perda.** Hermes e OpenCode resumem conversas longas. O resumo é feito pelo próprio modelo (fraco), que mistura o que foi verificado com o que foi especulado, e o detalhe que corrigia o erro some.
- **Nenhuma distinção de confiabilidade.** "Vi no `package.json`" e "acho que é assim" ocupam o mesmo espaço no contexto, com o mesmo peso.
- **Correção que não persiste.** Quando você corrige, a correção vive só naquela conversa; a informação errada continua na memória nativa.

## Princípios do desenho

1. **Uma fonte de verdade fora do modelo**, legível e editável por você: o vault do Obsidian.
2. **Status epistêmico em toda informação** (hipótese, verificado, contestado, refutado, obsoleto) e hierarquia explícita de confiança.
3. **Não inflar arquivos de instrução.** Nada vai para `AGENTS.md`, `SOUL.md` ou `CLAUDE.md`: são arquivos que já costumam estar grandes demais para o modelo ler inteiros. O protocolo entra por canais curtos e sob demanda (9 regras no prompt via plugin, instruções do MCP, skill `cofre-protocolo`).
4. **Regras aplicadas em código.** Modelos fracos ignoram instruções; por isso as regras críticas são validadas pelo servidor (evidência conferida no disco, bloqueio de afirmação refutada, citação obrigatória do usuário para decisões aceitas, bloqueio de credenciais).
5. **Contexto reinjetado mecanicamente**, sem depender de o modelo lembrar de pedir.
6. **Erros viram anticorpos**: fatos refutados não são apagados; aparecem como armadilhas.
7. **Auditável e reversível**: cada escrita de agente vira commit git no vault, com o agente/modelo que gravou.
8. **Escopo controlado**: só agentes de terminal configurados usam o cofre; apps de chat ficam de fora.

## Componentes

```mermaid
flowchart TB
    subgraph PC["Seu PC"]
        subgraph Vault["Vault Obsidian (Cofre)"]
            F["Fatos (status + evidência)"]
            E["Estado do projeto"]
            D["Decisões"]
            S["Sessões (diário)"]
            M["Missões"]
            P["Perfil do usuário"]
            K["60-Skills (skills)"]
        end
        Motor["Motor cofre (Python, sem dependências)<br/>validação epistêmica · contexto · revisão · NotebookLM"]
        MCP["Servidor MCP 'cofre' (stdio)<br/>10 ferramentas"]
        CLI["CLI 'cofre'"]
        Motor --> Vault
        MCP --> Motor
        CLI --> Motor

        subgraph Hermes["Hermes Agent"]
            HP["Plugin cofre:<br/>contexto + regras no prompt de sistema<br/>âncora a cada N turnos<br/>aviso sem checkpoint"]
            HM["memory: MEMORY.md desligado<br/>USER.md com aprovação"]
        end
        subgraph OpenCode["OpenCode"]
            OP["Plugin cofre:<br/>contexto + regras a cada chamada<br/>e na compactação"]
            OC["/ctx /checkpoint /corrigir /revisar-cofre"]
        end
        Hermes -- "ferramentas MCP" --> MCP
        OpenCode -- "ferramentas MCP" --> MCP
        HP --> Motor
        OP --> CLI
        Hermes -- "skills.create_dir" --> K
        OpenCode -- "skills (V2) / cópia (V1)" --> K
        Voce(("Você")) -- "lê, edita, aprova" --> Vault
    end
    Apps["Claude Desktop / ChatGPT app"] -. "sem acesso" .- Vault
    NLM["NotebookLM"] <-. "exportar/importar (manual)" .-> Vault
```

| Componente | Papel |
| --- | --- |
| Vault | Fonte de verdade em Markdown com frontmatter (propriedades do Obsidian). Painéis com o core plugin Bases. |
| Motor `cofre/` | Lê/escreve notas, aplica as regras, monta o pacote de contexto, revisa e exporta. Python 3.9+ puro, roda em Windows, Linux, macOS e WSL. |
| Servidor MCP | Interface dos agentes. Mesmo binário para Hermes, OpenCode, Claude Code e Codex. Descobre o workspace por `roots/list` quando o cliente oferece. |
| Plugins | Injetam o contexto sem depender do modelo: no Hermes como seção do prompt de sistema (estável, sobrevive à compactação) mais uma âncora periódica; no OpenCode em toda chamada e no pedido de compactação. |
| Protocolo | 9 regras curtas dentro do pacote de contexto que os plugins injetam; versão completa na skill `cofre-protocolo`; resumo nas instruções do servidor MCP (para clientes sem plugin). Nenhum arquivo de instruções do usuário é editado. |
| Relevância | `cofre/relevancia.py`: busca no vault inteiro a cada mensagem e devolve no máximo 5 itens (configurável) com status; mesmo motor do `cofre_buscar`. |
| Skills | Ficam no vault (`60-Skills/`, formato Agent Skills). Hermes lê e cria skills lá (`skills.create_dir`); OpenCode V2 lê pelo campo `skills`; no V1 o plugin copia para `~/.config/opencode/skills` ao iniciar. As do cofre ficam em `60-Skills/sistema/`. |

## Fluxos

### Início de sessão
1. Você abre o agente numa pasta de código.
2. O plugin descobre o projeto pelo diretório (campo `caminhos` do hub do projeto ou remoto git em `repos`; caminhos Windows e WSL são equivalentes).
3. O pacote de contexto entra no prompt: estado atual, armadilhas, contestados, verificados, decisões, hipóteses, missões, suas preferências e as regras.

### Cada mensagem: o que o vault tem sobre o assunto
1. Você escreve, por exemplo, "vamos fazer o penteast do cliente".
2. O plugin (Hermes: `pre_llm_call`; OpenCode: hook `context`) manda o texto da mensagem para `cofre relevante`.
3. O motor busca no vault inteiro (notas livres, fatos, decisões, fontes do NotebookLM, skills e referências de skills), com ranqueamento BM25 e tolerância a erro de digitação, usando um índice em cache (`.cofre/indice.json`, atualizado só para arquivos alterados).
4. Se houver algo forte o bastante, a IA recebe um bloco curto:
   ```
   [cofre] Possivelmente relevante para esta mensagem (abra só o que servir; só VERIFICADO é fato):
   - F-C9XN2 [VERIFICADO] O cliente Acme autoriza testes de intrusão só em staging
   - skill `pentest-web` — Metodologia de pentest em aplicações web (OWASP)... (carregue a skill se servir)
   - nota Burp Suite: Proxy para pentest web... — cofre_ler "30-Conhecimento/Seguranca/Burp Suite.md"
   ```
5. A IA abre só o que servir (`cofre_ler` ou a skill). Mensagens sem relação ("oi", "ok", assunto que o vault não cobre) não geram bloco nenhum. No Hermes, itens já mostrados na sessão não se repetem.

### Descoberta durante o trabalho
1. O agente lê `docker-compose.yml` e vê `image: postgres:16`.
2. Chama `cofre_registrar_fato(afirmacao="O banco é PostgreSQL 16", status="verificado", evidencias=[{tipo: "arquivo", ref: "/caminho/docker-compose.yml:3", trecho: "image: postgres:16"}])`.
3. O motor abre o arquivo, confere o trecho, verifica duplicatas/contradições/refutados e grava. Se o trecho não existir, recusa com a explicação.

### Correção sua
1. Você diz "não é JWT, é sessão com cookie" (ou usa `/corrigir`).
2. O agente refuta o fato com evidência `usuario` (suas palavras) e registra a versão correta, ligada à antiga.
3. Dali em diante, toda sessão de qualquer IA vê: `NÃO é verdade: "A API usa JWT" — correto: "A API autentica com sessão em cookie httpOnly"`. Tentativas de registrar de novo "usa JWT" (ou paráfrases) são bloqueadas.

### Conversa longa e compactação
- Checkpoints gravam foco, próximos passos e bloqueios no `Estado` do projeto.
- No OpenCode, o plugin injeta o contexto no pedido de compactação e instrui o resumo a preservar IDs e status.
- No Hermes, a seção do prompt de sistema é congelada e preservada na compactação; a âncora reinjeta o foco atual (lido do disco) a cada N turnos.

### Revisão
- `cofre revisar` reconfere evidências de arquivo (detecta fato verificado cujo trecho mudou no código), aponta verificações vencidas, hipóteses antigas, duplicatas, contradições, decisões aceitas sem citação e credenciais coladas no vault. `--aplicar` marca como contestado o que deixou de conferir.

## Decisões de desenho e trade-offs

| Decisão | Por quê | Custo |
| --- | --- | --- |
| Arquivos Markdown, não banco vetorial | Você lê e corrige no Obsidian; git audita; zero infraestrutura | Busca é lexical (suficiente para o volume de um freelancer; dá para plugar embeddings depois) |
| Python sem dependências | Funciona com o Python do Hermes e em qualquer SO, sem `pip install` | Parser YAML próprio (subconjunto usado pelo Obsidian) |
| MCP como interface | Padrão suportado por Hermes, OpenCode, Claude Code e Codex; não toca apps de chat | Ferramentas consomem alguns milhares de tokens de schema |
| Plugins em vez de `AGENTS.md`/`SOUL.md` | Arquivos de instrução grandes já não são lidos por inteiro; o plugin injeta só o necessário, e modelos fracos esquecem de pedir contexto | Depende da API de plugins de cada ferramenta (OpenCode V2 mudou a API; o plugin já suporta V1 e V2). Sem plugin, só as instruções do MCP chegam ao modelo |
| Skills no vault | Uma fonte só, versionada com git, visível no Obsidian, compartilhada por Hermes e OpenCode | Skills que o Hermes aprende também caem no vault (com aprovação); bundled do Hermes com o mesmo nome têm precedência |
| Evidência de arquivo conferida | Detecta trecho inventado, o erro mais comum de modelo fraco | Evidência de comando/URL não é reexecutada (seria arriscado); fica a cargo da revisão humana e da política `humano` |
| Desligar `MEMORY.md` do Hermes | Elimina a segunda fonte de verdade que contaminava as sessões | O agente perde o "diário pessoal" nativo; o cofre substitui com regras melhores (reversível) |
| Relevância lexical (BM25 + radical + distância de edição) | Sem modelo de embeddings, roda em qualquer máquina, explicável, ~0,3 s com 2.000 notas | Não entende sinônimos que não aparecem no texto ("teste de intrusão" x "pentest" só casa se uma nota usar os dois). Mitigação: `tags` e `aliases` nas notas. Busca semântica com embeddings locais pode ser acrescentada depois sem mudar o resto |
| Similaridade lexical para refutados/duplicatas | Sem dependências, previsível, explicável na mensagem de erro | Pode deixar passar paráfrases distantes ou acusar falsos positivos (agente pode usar `forcar` em casos não idênticos; você revisa) |
