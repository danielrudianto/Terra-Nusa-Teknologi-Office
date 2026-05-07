import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { paginationMeta, paginationParams } from "../utils/pagination"
import { logError } from "../utils/logger"

const DraftBody = t.Object({
  supplierID: t.Number(),
  description: t.String(),
  date: t.String(),
  purchaseOrderName: t.String(),
  projectName: t.String(),
  purchaseType: t.String(),
  dpp: t.Number(),
  ppn: t.Number(),
  pbbkb: t.Number(),
})

export const purchaseDraftRoutes = new Elysia({ prefix: "/purchase-draft" })
  .use(guard)
  .get("/:id", async ({ params, user, set }) => {
    const draft = await prisma.purchaseDraft.findFirst({ where: { id: Number(params.id), isDelete: 0 } })
    if (!draft) { set.status = 404; return { detail: "Not found" } }
    return draft
  })
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const where: Record<string, unknown> = { isDelete: 0 }
    if (q.keyword) where.description = { contains: q.keyword }

    const page = Number(q.page ?? 1)
    const pageSize = Number(q.pageSize ?? 10)
    const { skip, take } = paginationParams(page, pageSize)
    try {
      const [data, total] = await Promise.all([
        prisma.purchaseDraft.findMany({ where: where as never, orderBy: { createdAt: "desc" }, skip, take }),
        prisma.purchaseDraft.count({ where: where as never }),
      ])
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      return prisma.purchaseDraft.create({
        data: { ...b, date: new Date(b.date as string), isDelete: 0, createdBy: user.id, createdAt: new Date() } as never,
      })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create" } }
  }, { body: DraftBody })
  .delete("/:id", async ({ params, user, set }) => {
    await prisma.purchaseDraft.update({ where: { id: Number(params.id) }, data: { isDelete: 1, deletedBy: user.id, deletedAt: new Date() } })
    return { message: "Deleted" }
  })
