"""Avaliação da busca por relevância com um vault realista de freelancer.

Cada consulta é uma mensagem típica (com erro de digitação, inglês, stack trace, conversa
fiada) e lista o que DEVE aparecer (`esperado`) e o que é aceitável aparecer junto
(`aceitavel`). Qualquer outra coisa conta como falso positivo.

Rodar o relatório completo:  python tests/avaliacao_relevancia.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from cofre import relevancia  # noqa: E402
from cofre import registrar as r  # noqa: E402

NOTAS = {
    "60-Skills/seguranca/pentest-web/SKILL.md":
        "---\nname: pentest-web\ndescription: Roteiro de pentest autorizado em aplicações web: escopo, "
        "autorização por escrito, execução e relatório.\n---\n# Pentest web\n\n"
        "1. Confirmar escopo e autorização por escrito.\n2. Executar dentro da janela combinada.\n3. Relatório.\n",
    "60-Skills/seguranca/pentest-web/references/relatorio.md":
        "# Modelo de relatório de pentest\n\nSumário executivo, escopo, achados com severidade CVSS, "
        "recomendações e evidências.\n",
    "60-Skills/frontend/nextjs-app-router/SKILL.md":
        "---\nname: nextjs-app-router\ndescription: Next.js App Router: server components, cache de fetch, "
        "revalidate e revalidatePath.\n---\n# Next.js App Router\n\nO cache do fetch é por rota; use revalidate.\n",
    "60-Skills/mobile/react-native-expo/SKILL.md":
        "---\nname: react-native-expo\ndescription: Apps React Native com Expo: EAS build, variáveis de ambiente "
        "e publicação na Play Store e App Store.\n---\n# Expo\n\neas build --platform android\n",
    "60-Skills/backend/go-concorrencia/SKILL.md":
        "---\nname: go-concorrencia\ndescription: Concorrência em Go: goroutines, channels, context com "
        "cancelamento e errgroup.\n---\n# Go\n\nToda goroutine precisa de um jeito de terminar (context).\n",
    "60-Skills/backend/rust-async/SKILL.md":
        "---\nname: rust-async\ndescription: Rust assíncrono com tokio: async/await, tokio::spawn, Send e Sync, "
        "Arc e Mutex.\n---\n# Rust async\n\nFutures passados a tokio::spawn precisam ser Send.\n",
    "60-Skills/backend/laravel-filas/SKILL.md":
        "---\nname: laravel-filas\ndescription: Filas no Laravel: jobs, Horizon, retries e jobs falhos "
        "(failed_jobs).\n---\n# Laravel queues\n\nphp artisan queue:work\n",
    "60-Skills/devops/docker-compose-dev/SKILL.md":
        "---\nname: docker-compose-dev\ndescription: Ambiente de desenvolvimento com docker compose: serviços, "
        "volumes, healthcheck e rede.\n---\n# Docker compose\n\ndocker compose up -d\n",
    "60-Skills/dados/postgres-performance/SKILL.md":
        "---\nname: postgres-performance\ndescription: Performance no PostgreSQL: EXPLAIN ANALYZE, índices, "
        "vacuum e queries lentas.\n---\n# Postgres\n\nComece pelo EXPLAIN (ANALYZE, BUFFERS).\n",
    "60-Skills/ia/prompt-modelos-pequenos/SKILL.md":
        "---\nname: prompt-modelos-pequenos\ndescription: Como escrever prompts para LLMs pequenos que esquecem "
        "instruções: passos curtos, exemplos, repetição do essencial.\n---\n# Prompts\n\nUma instrução por linha.\n",
    "30-Conhecimento/Seguranca/Burp Suite.md":
        "---\ntags: [seguranca, ferramenta]\n---\n# Burp Suite\n\nProxy de interceptação usado no pentest web. "
        "Para HTTPS, instale o certificado da CA do Burp no navegador.\n",
    "30-Conhecimento/Seguranca/Nmap.md":
        "---\ntags: [seguranca, rede]\n---\n# Nmap\n\nScanner de portas e serviços. Só em alvos autorizados.\n",
    "30-Conhecimento/Frontend/Tailwind dark mode.md":
        "# Tailwind dark mode\n\nUse darkMode: 'class' no tailwind.config e alterne a classe dark no html.\n",
    "30-Conhecimento/Frontend/Zustand vs Redux.md":
        "---\naliases: [estado global]\n---\n# Zustand vs Redux\n\nZustand para estado global simples; "
        "Redux Toolkit quando há muito fluxo assíncrono.\n",
    "30-Conhecimento/Backend/Stripe webhooks.md":
        "# Stripe webhooks\n\nValide a assinatura (Stripe-Signature) e trate eventos de forma idempotente "
        "guardando o event.id; o Stripe reenvia eventos.\n",
    "30-Conhecimento/Backend/JWT refresh token.md":
        "# JWT com refresh token\n\nAccess token curto, refresh token rotativo em cookie httpOnly.\n",
    "30-Conhecimento/DevOps/Deploy na Vercel.md":
        "# Deploy na Vercel\n\nVariáveis de ambiente por ambiente (preview/production); logs em Deployments.\n",
    "30-Conhecimento/DevOps/GitHub Actions cache.md":
        "# Cache no GitHub Actions\n\nactions/cache com chave pelo hash do lockfile.\n",
    "30-Conhecimento/DevOps/Nginx proxy reverso.md":
        "# Nginx como proxy reverso\n\nproxy_pass para a aplicação e certificado TLS com certbot.\n",
    "30-Conhecimento/Mobile/Push com Firebase.md":
        "# Notificações push com Firebase (FCM)\n\nNo Android 13+ é preciso pedir a permissão "
        "POST_NOTIFICATIONS.\n",
    "30-Conhecimento/Python/FastAPI dependencias.md":
        "# FastAPI: dependências\n\nDepends com yield para abrir e fechar a sessão do banco.\n",
    "30-Conhecimento/Python/Pandas performance.md":
        "# Pandas lento\n\nEvite apply linha a linha; use operações vetorizadas e tipos category.\n",
    "30-Conhecimento/Ferramentas/Obsidian atalhos.md":
        "# Atalhos do Obsidian\n\nCtrl+O abre nota, Ctrl+P paleta de comandos.\n",
    "30-Conhecimento/Financeiro/Precificacao freelance.md":
        "---\naliases: [quanto cobrar, orçamento]\n---\n# Precificação de freelance\n\nValor da hora = custo mensal / horas faturáveis; orçamento por escopo "
        "com margem de 20%.\n",
    "40-Clientes/Acme.md":
        "---\ntipo: cliente\nnome: Acme\n---\n# Acme\n\nCliente de e-commerce. Prefere reuniões curtas.\n",
    "50-Fontes/Janela de contexto em LLMs.md":
        "---\ntipo: fonte\nid: N-4K2P1\norigem: notebooklm\n---\n# Janela de contexto em LLMs\n\n"
        "Modelos perdem informação no meio de contextos longos (lost in the middle).\n",
}


def popular(teste) -> dict[str, str]:
    """Cria as notas e os registros; devolve os IDs gerados por nome lógico."""
    for rel, texto in NOTAS.items():
        caminho = teste.vault / rel
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
    c, h = teste.cofre, teste.humano
    ids = {}
    ids["acme_staging"] = r.registrar_fato(
        c, h, "O cliente Acme autoriza pentest só no ambiente de staging", status="verificado", projeto="global",
        evidencias=[{"tipo": "usuario", "ref": "conversa", "trecho": "pentest só em staging"}]).id
    ids["postgres16"] = r.registrar_fato(
        c, h, "O projeto loja usa PostgreSQL 16 no docker compose", status="verificado", projeto="loja",
        evidencias=[{"tipo": "arquivo", "ref": f"{teste.proj / 'docker-compose.yml'}:3", "trecho": "postgres:16"}]).id
    jwt = r.registrar_fato(c, h, "A API da loja autentica com JWT no header Authorization", projeto="loja").id
    r.atualizar_fato(c, h, jwt, "refutar", motivo="a API usa sessão",
                     afirmacao_correta="A API da loja autentica com sessão em cookie httpOnly")
    ids["jwt_refutado"] = jwt
    ids["gradle"] = r.registrar_fato(
        c, teste.agente, "O build Android do app falha por causa da versão do Gradle", projeto="global").id
    ids["drizzle"] = r.decisao(c, h, titulo="Usar Drizzle no lugar de Prisma", decisao_txt="ORM Drizzle",
                               status="aceita", citacao_usuario="pode usar drizzle", projeto="loja").id
    ids["zustand"] = r.decisao(c, h, titulo="Usar Zustand para estado global do painel",
                               decisao_txt="Zustand", projeto="loja").id
    return ids


# (mensagem, esperado, aceitável, projeto). Itens são nomes lógicos (chaves de `ids`) ou trechos do caminho.
CONSULTAS = [
    ("vamos começar o pentest do cliente acme", ["pentest-web/SKILL", "acme_staging"],
     ["Acme.md", "Burp", "Nmap", "relatorio"], None),
    ("estou falando de penteast", ["pentest-web/SKILL"], ["Burp", "relatorio", "acme_staging"], None),
    ("como escrevo o relatório do pentest?", ["relatorio"], ["pentest-web/SKILL", "Burp", "acme_staging"], None),
    ("o burp nao ta interceptando https", ["Burp"], ["pentest-web/SKILL", "Nginx"], None),
    ("roda um nmap no alvo autorizado", ["Nmap"], ["pentest-web/SKILL", "acme_staging"], None),
    ("o cache do next ta servindo pagina velha", ["nextjs-app-router"], ["GitHub Actions"], None),
    ("server components com revalidate", ["nextjs-app-router"], [], None),
    ("gerar build do app com expo pra play store", ["react-native-expo"], ["gradle"], None),
    ("notificação push nao chega no android", ["Push com Firebase"], ["react-native-expo", "gradle"], None),
    ("goroutine vazando, acho que falta cancelar o context", ["go-concorrencia"], [], None),
    ("erro de Send no tokio spawn", ["rust-async"], [], None),
    ("jobs falhando na fila do laravel", ["laravel-filas"], [], None),
    ("subir o ambiente com docker compose", ["docker-compose-dev"], ["postgres16"], None),
    ("query lenta no postgres, explain analyze", ["postgres-performance"], ["postgres16"], None),
    ("qual versão do postgres a loja usa?", ["postgres16"], ["postgres-performance", "docker-compose-dev"], "loja"),
    ("a api da loja usa jwt né?", ["jwt_refutado"], ["JWT refresh", "autentica-com-sessao"], "loja"),
    ("implementar refresh token jwt", ["JWT refresh"], ["jwt_refutado"], None),
    ("webhook do stripe chegando duplicado", ["Stripe"], [], None),
    ("dark mode no tailwind", ["Tailwind"], [], None),
    ("zustand ou redux pro estado global?", ["Zustand vs Redux", "zustand"], [], "loja"),
    ("prisma ou drizzle?", ["drizzle"], [], "loja"),
    ("deploy na vercel deu erro", ["Vercel"], [], None),
    ("cache do github actions", ["GitHub Actions"], ["nextjs-app-router"], None),
    ("configurar nginx como proxy reverso com certificado", ["Nginx"], ["Burp"], None),
    ("fastapi depends com sessão do banco", ["FastAPI"], [], None),
    ("dataframe do pandas muito lento", ["Pandas"], ["postgres-performance"], None),
    ("quanto cobrar por hora nesse projeto", ["Precificacao"], [], None),
    ("prompt para modelo pequeno que esquece instruções", ["prompt-modelos-pequenos"],
     ["Janela de contexto"], None),
    ("janela de contexto dos llms", ["Janela de contexto"], ["prompt-modelos-pequenos"], None),
    ("build do android falhando no gradle", ["gradle"], ["react-native-expo", "Push com Firebase"], None),
    ("how do I set up dark mode with tailwind", ["Tailwind"], [], None),
    ("stripe webhook idempotency", ["Stripe"], [], None),
    ("panic: runtime error: invalid memory address or nil pointer dereference\ngoroutine 1 [running]:",
     ["go-concorrencia"], [], None),
    ("atalho do obsidian pra abrir nota", ["Obsidian atalhos"], [], None),
    ("configura o nginx, depois faz o deploy na vercel e arruma o dark mode do tailwind",
     ["Nginx", "Vercel", "Tailwind"], [], None),
    ("Bom dia! Hoje quero fechar a parte de pagamentos: o webhook do stripe tá chegando duplicado e acho que "
     "preciso guardar o event id. Depois a gente vê o resto, tá?", ["Stripe"], [], None),
    ("how to cancel goroutines when the request context is done", ["go-concorrencia"], [], None),
    ("tailwnd dark mod", ["Tailwind"], [], None),
    ("laravle queue travada", ["laravel-filas"], [], None),
    ("nexjs cache", ["nextjs-app-router"], ["GitHub Actions"], None),
    ("instala o certificado no burp pra pegar o trafego https", ["Burp"], ["Nginx"], None),
    # Sem relação com o vault: nada deve aparecer.
    ("oi, tudo bem?", [], [], None),
    ("ok, pode seguir", [], [], None),
    ("valeu, ficou ótimo", [], [], None),
    ("me explica o que é uma closure em javascript", [], [], None),
    ("qual a capital da austrália", [], [], None),
    ("continua de onde parou", [], [], None),
    ("faz o commit e abre o PR", [], [], None),
    ("roda os testes de novo", [], [], None),
    ("corrige o bug no formulário de login", [], ["JWT refresh"], None),
    ("usa a versão mais nova", [], [], None),
    ("deixa mais bonito e coloca um loading", [], [], None),
    ("isso, exatamente. pode mandar ver", [], [], None),
    ("escreve um email pro cliente pedindo mais prazo", [], ["Acme.md"], None),
    ("TypeError: Cannot read properties of undefined (reading 'map')", [], ["nextjs-app-router"], None),
]


def _casa(item: str, achado, ids: dict[str, str]) -> bool:
    if item in ids:
        return achado.doc.get("id") == ids[item]
    return item.lower() in achado.rel.lower()


def avaliar(teste, ids: dict[str, str]) -> dict:
    linhas, acertos, positivos, recall_soma, fp_total, negativos_ok, negativos = [], 0, 0, 0.0, 0, 0, 0
    falhas = []
    for msg, esperado, aceitavel, projeto in CONSULTAS:
        achados = relevancia.buscar(teste.cofre, msg, projeto=projeto, limite=5)
        achados_ok = [a for a in achados if any(_casa(e, a, ids) for e in esperado + aceitavel)]
        fps = [a for a in achados if a not in achados_ok]
        fp_total += len(fps)
        if esperado:
            positivos += 1
            vistos = [e for e in esperado if any(_casa(e, a, ids) for a in achados)]
            recall_soma += len(vistos) / len(esperado)
            if vistos:
                acertos += 1
            else:
                falhas.append(f"não achou {esperado}: {msg!r}")
        else:
            negativos += 1
            negativos_ok += not fps
        if fps:
            falhas.append(f"falso positivo {[a.rel for a in fps]}: {msg!r}")
        linhas.append((msg, [a.rel for a in achados], [a.rel for a in fps]))
    return {
        "acerto": acertos / positivos,
        "recall": recall_soma / positivos,
        "silencio_sem_relacao": negativos_ok / negativos,
        "falsos_positivos": fp_total,
        "falhas": falhas,
        "linhas": linhas,
    }


if __name__ == "__main__":
    import unittest

    from base import CofreTeste

    class _Rel(CofreTeste):
        def runTest(self):
            rel = avaliar(self, popular(self))
            for msg, achados, fps in rel["linhas"]:
                marca = "FP " if fps else "   "
                print(f"{marca}{msg[:60]!r}\n      -> {achados}")
            print("\n".join(rel["falhas"]) or "sem falhas")
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rel.items()
                   if k not in ("falhas", "linhas")})

    unittest.TextTestRunner(verbosity=0).run(_Rel())
