import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { paginationMeta, paginationParams } from "../utils/pagination"
import { logError } from "../utils/logger"

const PurchaseOrderBody = t.Object({
  date: t.String(),
  supplierID: t.Number(),
  name: t.Optional(t.String()),
  purchaseType: t.String(),
  templateVersion: t.Optional(t.String()),
  projectName: t.String(),
  dpp: t.Number(),
  ppn: t.Optional(t.Number()),
  customData: t.Optional(t.Any()),
})

export const purchaseOrderRoutes = new Elysia({ prefix: "/purchase-orders" })
  .use(guard)
  .get("/:id", async ({ params, user, set }) => {
    const po = await prisma.purchaseOrder.findFirst({ where: { id: Number(params.id), isDelete: false } })
    if (!po) { set.status = 404; return { detail: "Not found" } }
    return po
  })
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const page = Number(q.page ?? 1)
    const pageSize = Number(q.page_size ?? 10)
    const { skip, take } = paginationParams(page, pageSize)
    try {
      const [data, total] = await Promise.all([
        prisma.purchaseOrder.findMany({ where: { isDelete: false }, orderBy: { createdAt: "desc" }, skip, take }),
        prisma.purchaseOrder.count({ where: { isDelete: false } }),
      ])
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      const count = await prisma.purchaseOrder.count()
      const name = b.name ?? `PO-${String(count + 1).padStart(4, "0")}`
      return prisma.purchaseOrder.create({
        data: { ...b, name, date: new Date(b.date as string), templateVersion: b.templateVersion ?? "v1", status: "draft", isDelete: false, createdBy: user.id, createdAt: new Date() } as never,
      })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create" } }
  }, { body: PurchaseOrderBody })
  .patch("/:id/status", async ({ params, body, user, set }) => {
    const { status } = body as { status: string }
    await prisma.purchaseOrder.update({ where: { id: Number(params.id) }, data: { status: status as any } })
    return { message: "Status updated" }
  }, { body: t.Object({ status: t.String() }) })
  .delete("/:id", async ({ params, user, set }) => {
    await prisma.purchaseOrder.update({ where: { id: Number(params.id) }, data: { isDelete: true, deletedBy: user.id, deletedAt: new Date() } })
    return { message: "Deleted" }
  })
