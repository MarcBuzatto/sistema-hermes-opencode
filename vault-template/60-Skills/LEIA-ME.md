# 60-Skills

Skills (habilidades) que as IAs carregam sob demanda. Ficam aqui, versionadas com o vault, e os agentes leem direto desta pasta:

- **Hermes**: `skills.create_dir` aponta para cá. Ele lê todas as skills daqui e as skills que ele aprende também são criadas aqui (com `skills.write_approval: true`, cada criação/edição espera sua aprovação em `/skills pending`).
- **OpenCode V2**: `"skills": ["<esta pasta>"]` no `opencode.json`.
- **OpenCode V1**: só enxerga `~/.config/opencode/skills/*/SKILL.md`; o plugin do cofre copia as skills daqui para lá a cada início (`cofre skills sincronizar`).

## Formato (padrão Agent Skills)

```
60-Skills/
├── sistema/                 skills do cofre (o instalador atualiza; não edite)
│   └── cofre-protocolo/SKILL.md
└── <categoria>/             opcional (ex.: frontend, devops, clientes)
    └── <nome-da-skill>/
        ├── SKILL.md         frontmatter `name` (igual ao nome da pasta) e `description`
        ├── references/      material de apoio lido sob demanda
        └── scripts/
```

- O nome da pasta é o ID da skill: minúsculas, números e hífen (ex.: `nextjs-cache`).
- A `description` decide quando o modelo usa a skill: diga o que ela faz e quando usar.
- Mantenha o `SKILL.md` enxuto e mova detalhes para `references/`.
- Nunca coloque credenciais (o `cofre revisar` aponta).

`cofre skills listar` mostra o que existe; `cofre skills verificar` aponta problemas (description ausente, nome divergente da pasta, IDs repetidos, segredos).

> Fluxo para criar skills a partir de pesquisas do NotebookLM: pendente da sua pesquisa (ver `docs/pesquisa/` no repositório).
