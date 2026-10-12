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

## Skill feita a partir de pesquisa

A pesquisa entra primeiro como fonte (`cofre importar-notebooklm`, vira `N-XXXXX` em `50-Fontes/`). A skill aponta para ela e separa o que você testou do que só a fonte diz:

```markdown
---
name: backup-rclone
description: Backup do vault para nuvem com rclone crypt. Use ao configurar ou revisar o backup.
status: rascunho          # rascunho | verificada | obsoleta
fontes: [N-AB123]         # notas de fonte, fatos (F-...) ou links oficiais
---
# Backup com rclone

1. Criar o remoto cifrado.
   > [!check] Comprovado
   > Testado em 2026-10-11: `rclone lsd cofre-cripto:` lista as pastas. (F-CD456)

   > [!quote] Recomendação da fonte
   > Usar `--backup-dir` para guardar versões apagadas. (N-AB123)
```

- `status: rascunho` faz a IA avisar você antes de seguir a skill (aparece marcado no bloco de relevância).
- Mude para `verificada` quando os passos principais tiverem bloco "Comprovado"; `cofre skills verificar` reclama de skill verificada sem `fontes`.
- Peça a uma IA "transforma a pesquisa N-AB123 numa skill": a skill `cofre-notebooklm` segue este formato.
