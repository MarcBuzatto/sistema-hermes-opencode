---
exemplo: true
tipo: fato
id: F-AG9DQ
afirmacao: O ORM do projeto é Prisma
status: refutado
fonte: inferencia
evidencia: []
projeto: "[[exemplo-loja]]"
criticidade: normal
registrado_por: opencode
registrado_em: 2026-10-10
aliases:
  - F-AG9DQ
refutado_em: 2026-10-10
motivo: package.json mostra drizzle-orm e não há dependência do Prisma
evidencia_contraria:
  - "arquivo :: ~/dev/exemplo-loja/package.json:5 :: \"drizzle-orm\": \"0.44.5\""
substituido_por: "[[F-W9MDV o-orm-do-projeto-e-drizzle-orm-0-44-5]]"
---
# O ORM do projeto é Prisma

> [!failure] REFUTADO
> Comprovadamente FALSO. Não repita esta afirmação.
> Motivo: package.json mostra drizzle-orm e não há dependência do Prisma
> Correto/atual: [[F-W9MDV o-orm-do-projeto-e-drizzle-orm-0-44-5]]

## Evidência
- (nenhuma)

## Evidência contrária
- `arquivo` ~/dev/exemplo-loja/package.json:5 — ""drizzle-orm": "0.44.5""

## Contexto
Suposição feita no início da conversa, sem abrir o package.json.

## Histórico
- 2026-10-10 23:18 — criado como **hipotese** (por opencode)
- 2026-10-10 23:18 — **refutado**: package.json mostra drizzle-orm e não há dependência do Prisma (por hermes)
- 2026-10-10 23:18 — substituído por F-W9MDV (por hermes)
