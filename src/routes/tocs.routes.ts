import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { logError } from "../utils/logger"
import type { ITocCreate, ITocOutput } from "../interfaces/toc.interfaces"

const TocBody = t.Object({
  name: t.String(),
  purchaseType: t.String(),
  description: t.Optional(t.String()),
  content: t.String(),
})

export const tocRoutes = new Elysia({ prefix: "/tocs" })
  .use(guard)
  .get("/:id", async ({ params, user, set }) => {
    try {
      const toc = await prisma.toc.findUnique({ where: { id: Number(params.id) } })
      if (!toc) { set.status = 404; return { detail: "TOC not found" } }
      return toc
    } catch (e) {
      logError(`${e}`)
      set.status = 500
      return { detail: "Failed to fetch TOC" }
    }
  })
  .get("/", async ({ query, user, set }) => {
    try {
      const q = query as Record<string, string>
      const where: Record<string, unknown> = {}
      if (q.purchaseType) where.purchaseType = q.purchaseType

      const latestOnly = q.latest !== "false"
      const tocs = await prisma.toc.findMany({
        where,
        orderBy: [{ name: "asc" }, { revision: "desc" }],
      })

      if (!latestOnly) return { data: tocs }

      const latest: ITocOutput[] = []
      const seen = new Set<string>()
      for (const toc of tocs) {
        if (!seen.has(toc.name)) {
          seen.add(toc.name)
          latest.push(toc as ITocOutput)
        }
      }

      return { data: latest }
    } catch (e) {
      logError(`${e}`)
      set.status = 500
      return { detail: "Failed to fetch TOCs" }
    }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const payload = body as ITocCreate
      const latest = await prisma.toc.findFirst({
        where: { name: payload.name, purchaseType: payload.purchaseType },
        orderBy: { revision: "desc" },
      })
      const revision = latest ? latest.revision + 1 : 0
      const toc = await prisma.toc.create({
        data: {
          name: payload.name,
          purchaseType: payload.purchaseType,
          description: payload.description ?? null,
          content: payload.content,
          revision,
        },
      })
      return toc
    } catch (e) {
      logError(`${e}`)
      set.status = 500
      return { detail: "Failed to create TOC" }
    }
  }, { body: TocBody })

export type TocRoutes = typeof tocRoutes
