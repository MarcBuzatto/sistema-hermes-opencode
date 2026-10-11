// Plugin do Cofre para OpenCode (V2, e V1 a partir da 1.18.29).
// - Contexto do projeto (estado, verificados, armadilhas, hipóteses e regras) no prompt de
//   sistema de cada chamada e no pedido de compactação.
// - Relevância: procura no vault o que tem a ver com a última mensagem do usuário (notas,
//   fatos, decisões, fontes, skills) e mostra poucas linhas apontando para isso.
// - Agente "spec": acrescenta as instruções do modo spec sem trocar o prompt base.
// - Lembrete de checkpoint depois de N mensagens do usuário sem cofre_checkpoint.
// - O contexto fica em cache por 30 s, mas é refeito quando aparece chamada nova a uma
//   ferramenta do cofre (a linha AGORA da spec muda a cada tarefa).
// - Pasta privada do vault (99-Privado e pastas_privadas): bloqueia ferramentas que apontem
//   para ela e tira as linhas com o caminho dela da saída de glob/grep/list/bash (hooks V1).
// Gerado pelo instalador do cofre.
import { execFile } from "node:child_process"
import { homedir } from "node:os"
import { resolve as resolverCaminho } from "node:path"

const PYTHON = "{{PYTHON}}"
const APP = "{{APP}}"
const DESTINO_SKILLS = {{DESTINO_SKILLS}}
const TTL_MS = 30_000
const cacheContexto = new Map()
const cacheDiretorio = new Map()
const cacheRelevancia = new Map()
let ultimoTextoV1 = ""
let estadoV1 = { agente: "", chamadasCofre: 0, semCheckpoint: 0 }

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

const MSG_PRIVADO =
  "Bloqueado pelo cofre: esse caminho fica numa pasta privada do usuário (99-Privado ou pastas_privadas do cofre). " +
  "Não tente outro caminho nem outro comando; se precisar do conteúdo, peça ao usuário."
const FERRAMENTAS_LISTAGEM = new Set(["glob", "grep", "list", "bash"])
const normal = (s) => String(s).replace(/\\/g, "/").toLowerCase()

function textosDe(valor, saida = []) {
  if (typeof valor === "string") saida.push(valor)
  else if (Array.isArray(valor)) valor.forEach((v) => textosDe(v, saida))
  else if (valor && typeof valor === "object") Object.values(valor).forEach((v) => textosDe(v, saida))
  return saida
}

// Caminhos privados vindos do cofre. Nome relativo (99-Privado) só conta quando o texto também
// aponta para o vault ou a sessão roda dentro dele, para não bloquear nada em outros projetos.
async function carregarPrivado(dir) {
  try {
    const d = JSON.parse((await rodar(["privado", "--json"])) || "{}")
    const casa = normal(homedir())
    const til = (p) => (casa && p.startsWith(casa + "/") ? "~" + p.slice(casa.length) : p)
    const absolutas = (d.absolutas ?? []).map(normal).filter(Boolean)
    const vaults = (d.vaults ?? []).map(normal).filter(Boolean)
    const aqui = normal(dir ?? "") + "/"
    return {
      absolutas: [...new Set([...absolutas, ...absolutas.map(til)])],
      relativas: (d.relativas ?? []).map(normal).filter(Boolean),
      vault: [...new Set([...vaults, ...vaults.map(til)])],
      naVault: vaults.some((v) => aqui.startsWith(v + "/")),
    }
  } catch {
    return null
  }
}

function mencionaPrivado(texto, pv) {
  const n = normal(texto)
  if (pv.absolutas.some((p) => n.includes(p))) return true
  return (pv.naVault || pv.vault.some((v) => n.includes(v))) && pv.relativas.some((p) => n.includes(p))
}

function tocaPrivado(args, pv, dir) {
  return textosDe(args).some(
    (t) =>
      mencionaPrivado(t, pv) ||
      (Boolean(dir) && t.length < 1000 && !t.includes("\n") && mencionaPrivado(resolverCaminho(dir, t), pv)),
  )
}

const papel = (m) => m?.role ?? m?.info?.role
const partesDe = (m) => {
  const partes = m?.content ?? m?.parts ?? []
  return Array.isArray(partes) ? partes : [partes]
}
const textoDe = (m) =>
  partesDe(m)
    .map((p) => (typeof p === "string" ? p : p?.type === "text" && !p?.synthetic ? p.text : ""))
    .join("\n")
    .trim()
const nomeFerramenta = (p) =>
  p?.type === "tool-call" ? String(p?.name ?? "") : p?.type === "tool" ? String(p?.tool ?? "") : ""

function textoDaUltimaMensagem(mensagens) {
  if (!Array.isArray(mensagens)) return ""
  for (let i = mensagens.length - 1; i >= 0; i--) {
    if (papel(mensagens[i]) !== "user") continue
    const texto = textoDe(mensagens[i])
    if (texto) return texto.slice(0, 4000)
  }
  return ""
}

// Quantas chamadas a ferramentas do cofre houve (invalida o cache) e quantas mensagens do
// usuário desde o último cofre_checkpoint. V1 também informa o agente em info.agent.
function estadoDaConversa(mensagens) {
  let chamadasCofre = 0
  let semCheckpoint = 0
  let agente = ""
  for (const m of Array.isArray(mensagens) ? mensagens : []) {
    if (papel(m) === "user") {
      if (textoDe(m)) semCheckpoint++
      agente = String(m?.info?.agent ?? m?.agent ?? agente)
    }
    for (const p of partesDe(m)) {
      const nome = nomeFerramenta(p)
      if (!nome.includes("cofre_")) continue
      chamadasCofre++
      if (nome.includes("cofre_checkpoint")) semCheckpoint = 0
    }
  }
  return { agente, chamadasCofre, semCheckpoint }
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

async function contexto(dir, estado = {}) {
  if (!dir) return ""
  const agente = String(estado.agente ?? "").toLowerCase()
  const chave = [dir, agente, estado.chamadasCofre ?? 0, estado.semCheckpoint ?? 0].join("\u0000")
  const item = cacheContexto.get(chave)
  if (item && Date.now() - item.t < TTL_MS) return item.texto
  const args = ["contexto", "--cwd", dir, "--modo", "sistema", "--sem-checkpoint", String(estado.semCheckpoint ?? 0)]
  if (agente) args.push("--agente-ativo", agente)
  const texto = await rodar(args)
  if (cacheContexto.size > 100) cacheContexto.clear()
  cacheContexto.set(chave, { t: Date.now(), texto })
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
        const estado = { ...estadoDaConversa(event.messages), agente: String(event.agent ?? "") }
        const [texto, relacionado] = await Promise.all([
          contexto(dir, estado),
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
    const privado = carregarPrivado(dir)
    return {
      "tool.execute.before": async (_entrada, saida) => {
        const pv = await privado
        if (pv && tocaPrivado(saida?.args, pv, dir)) throw new Error(MSG_PRIVADO)
      },
      "tool.execute.after": async (entrada, saida) => {
        const pv = await privado
        if (!pv || !FERRAMENTAS_LISTAGEM.has(String(entrada?.tool ?? "")) || typeof saida?.output !== "string") return
        saida.output = saida.output
          .split("\n")
          .filter((ln) => !mencionaPrivado(ln, pv))
          .join("\n")
      },
      "experimental.chat.messages.transform": async (_entrada, saida) => {
        try {
          ultimoTextoV1 = textoDaUltimaMensagem(saida?.messages) || ultimoTextoV1
          estadoV1 = estadoDaConversa(saida?.messages)
        } catch {}
      },
      "experimental.chat.system.transform": async (_entrada, saida) => {
        try {
          const [texto, relacionado] = await Promise.all([contexto(dir, estadoV1), relevancia(dir, ultimoTextoV1)])
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
