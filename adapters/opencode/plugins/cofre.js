// Plugin do Cofre para OpenCode (V2, e V1 a partir da 1.18.29).
// Injeta o contexto do projeto (estado, fatos verificados, armadilhas, hipóteses e regras)
// no prompt de sistema de cada chamada e no pedido de compactação, para que o modelo não
// perca o fio nem promova hipóteses a fatos ao resumir. Gerado pelo instalador do cofre.
import { execFile } from "node:child_process"

const PYTHON = "{{PYTHON}}"
const APP = "{{APP}}"
const DESTINO_SKILLS = {{DESTINO_SKILLS}}
const TTL_MS = 30_000
const cacheContexto = new Map()
const cacheDiretorio = new Map()

const AVISO_COMPACTACAO =
  "Ao resumir esta conversa, preserve: os IDs do cofre citados (F-, D-, S-, M-), o status de cada informação " +
  "(VERIFICADO, HIPÓTESE, CONTESTADO, REFUTADO) e o sessao_id do último checkpoint. Não transforme hipóteses em " +
  "fatos no resumo. Correções do usuário que ainda não foram para o cofre devem constar como pendentes."

function rodar(args) {
  return new Promise((resolve) => {
    execFile(
      PYTHON,
      [APP, ...args],
      { encoding: "utf8", timeout: 8000, windowsHide: true, maxBuffer: 1 << 20 },
      (erro, stdout) => resolve(erro ? "" : String(stdout || "").trim()),
    )
  })
}

async function contexto(dir) {
  if (!dir) return ""
  const item = cacheContexto.get(dir)
  if (item && Date.now() - item.t < TTL_MS) return item.texto
  const texto = await rodar(["contexto", "--cwd", dir, "--modo", "sistema"])
  cacheContexto.set(dir, { t: Date.now(), texto })
  return texto
}

async function diretorioDaSessao(ctx, sessionID) {
  if (sessionID && cacheDiretorio.has(sessionID)) return cacheDiretorio.get(sessionID)
  let dir = ctx?.location?.directory
  try {
    const sessao = await ctx.session.get({ sessionID })
    dir = sessao?.location?.directory ?? sessao?.directory ?? dir
  } catch {}
  if (sessionID && dir) cacheDiretorio.set(sessionID, dir)
  return dir
}

export default {
  id: "cofre",
  async setup(ctx) {
    await ctx.session.hook("context", async (event) => {
      try {
        const texto = await contexto(await diretorioDaSessao(ctx, event.sessionID))
        if (texto) event.system.push({ type: "text", text: texto })
      } catch {}
    })
    await ctx.session.hook("compaction", async (event) => {
      try {
        const texto = await contexto(await diretorioDaSessao(ctx, event.sessionID))
        event.system.push({ type: "text", text: [AVISO_COMPACTACAO, texto].filter(Boolean).join("\n\n") })
      } catch {}
    })
  },
  async server(input) {
    // OpenCode V1 só enxerga ~/.config/opencode/skills/*/SKILL.md: copia as skills do vault ao iniciar.
    if (DESTINO_SKILLS) rodar(["skills", "sincronizar", "--destino", DESTINO_SKILLS])
    const dir = input?.directory || input?.worktree
    return {
      "experimental.chat.system.transform": async (_entrada, saida) => {
        try {
          const texto = await contexto(dir)
          if (texto && Array.isArray(saida?.system)) saida.system.push(texto)
        } catch {}
      },
      "experimental.session.compacting": async (_entrada, saida) => {
        try {
          const texto = await contexto(dir)
          if (Array.isArray(saida?.context)) saida.context.push([AVISO_COMPACTACAO, texto].filter(Boolean).join("\n\n"))
        } catch {}
      },
    }
  },
}
