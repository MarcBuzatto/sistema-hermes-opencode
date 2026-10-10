---
exemplo: true
tipo: fato
id: F-W9MDV
afirmacao: O ORM do projeto é Drizzle ORM 0.44.5
status: verificado
fonte: arquivo
evidencia:
  - "arquivo :: ~/dev/exemplo-loja/package.json:5 :: \"drizzle-orm\": \"0.44.5\""
projeto: "[[exemplo-loja]]"
criticidade: normal
registrado_por: hermes
registrado_em: 2026-10-10
verificado_por: hermes
verificado_em: 2026-10-10
revisar_em: 2027-01-08
substitui: "[[F-AG9DQ o-orm-do-projeto-e-prisma]]"
aliases:
  - F-W9MDV
---
# O ORM do projeto é Drizzle ORM 0.44.5

> [!success] VERIFICADO
> Comprovado por evidência conferível. Pode ser usado; reverifique se estiver vencido.
> Substitui: [[F-AG9DQ o-orm-do-projeto-e-prisma]]

## Evidência
- `arquivo` ~/dev/exemplo-loja/package.json:5 — ""drizzle-orm": "0.44.5""

## Contexto
Correção de [[F-AG9DQ o-orm-do-projeto-e-prisma]]: package.json mostra drizzle-orm e não há dependência do Prisma

## Histórico
- 2026-10-10 23:18 — criado como **verificado** (por hermes)
