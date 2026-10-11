// Plugin do Cofre para OpenCode (V2, e V1 a partir da 1.18.29).
// - Contexto do projeto (estado, verificados, armadilhas, hipóteses e regras) no prompt de
//   sistema de cada chamada e no pedido de compactação.
// - Relevância: procura no vault o que tem a ver com a última mensagem do usuário (notas,
//   fatos, decisões, fontes, skills) e mostra poucas linhas apontando para isso.
// Gerado pelo instalador do cofre.
import { execFile } from "node:child_process"

const PYTHON = "{{PYTHON}}"
const APP = "{{APP}}"
const DESTINO_SKILLS = {{DESTINO_SKILLS}}
const TTL_MS = 30_000
const cacheContexto = new Map()
const cacheDiretorio = new Map()
const cacheRelevancia = new Map()
let ultimoTextoV1 = ""

const AVISO_COMPACTACAO =
  "Ao resumir esta conversa, preserve: os IDs do cofre citados (F-, D-, S-, M-), o status de cada informação " +
  "(VERIFICADO, HIPÓTESE, CONTESTADO, REFUTADO) e o sessao_id do último checkpoint. Não transforme hipóteses em " +
  "fatos no resumo. Correções do usuário que ainda não foram para o cofre devem constar como pendentes."

function rodar(args, entrada) {
  return new Promise((resolve) => {
    const filho = execFile(
      PYTHON,
      [APP, ...args],
      { encoding: "utf8", timeout: 8000, windowsHide: true, maxBuffer: 1 << 20 },
      (erro, stdout) => resolve(erro ? "" : String(stdout || "").trim()),
    )
    if (entrada !== undefined) filho.stdin?.end(entrada)
  })
}

function textoDaUltimaMensagem(mensagens) {
  if (!Array.isArray(mensagens)) return ""
  for (let i = mensagens.length - 1; i >= 0; i--) {
    const m = mensagens[i]
    if ((m?.role ?? m?.info?.role) !== "user") continue
    const partes = m?.content ?? m?.parts ?? []
    const texto = (Array.isArray(partes) ? partes : [partes])
      .map((p) => (typeof p === "string" ? p : p?.type === "text" && !p?.synthetic ? p.text : ""))
      .join("\n")
      .trim()
    if (texto) return texto.slice(0, 4000)
  }
  return ""
}

async function relevancia(dir, texto) {
  if (!texto) return ""
  const chave = `${dir}\u0000${texto}`
  if (cacheRelevancia.has(chave)) return cacheRelevancia.get(chave)
  const bloco = await rodar(["relevante", "--stdin", ...(dir ? ["--cwd", dir] : [])], texto)
  if (cacheRelevancia.size > 200) cacheRelevancia.clear()
  cacheRelevancia.set(chave, bloco)
  return bloco
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
        const dir = await diretorioDaSessao(ctx, event.sessionID)
        const [texto, relacionado] = await Promise.all([
          contexto(dir),
          relevancia(dir, textoDaUltimaMensagem(event.messages)),
        ])
        if (texto) event.system.push({ type: "text", text: texto })
        if (relacionado) event.system.push({ type: "text", text: relacionado })
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
      "experimental.chat.messages.transform": async (_entrada, saida) => {
        try {
          ultimoTextoV1 = textoDaUltimaMensagem(saida?.messages) || ultimoTextoV1
        } catch {}
      },
      "experimental.chat.system.transform": async (_entrada, saida) => {
        try {
          const [texto, relacionado] = await Promise.all([contexto(dir), relevancia(dir, ultimoTextoV1)])
          if (texto && Array.isArray(saida?.system)) saida.system.push(texto)
          if (relacionado && Array.isArray(saida?.system)) saida.system.push(relacionado)
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
