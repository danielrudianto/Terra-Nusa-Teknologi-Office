import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { paginationMeta, paginationParams } from "../utils/pagination"
import { logError } from "../utils/logger"

const ReimbursementBody = t.Object({
  name: t.String(),
  date: t.String(),
  dueDate: t.Optional(t.String()),
  projectName: t.String(),
  purchaseType: t.String(),
  bankName: t.String(),
  bankAccountName: t.String(),
  bankAccountNumber: t.String(),
  paymentMethod: t.String(),
  items: t.Optional(t.Array(t.Object({ description: t.String(), amount: t.Number(), date: t.String() }))),
})

export const reimbursementRoutes = new Elysia({ prefix: "/reimbursements" })
  .use(guard)
  .put("/approve/:id", async ({ params, user, set }) => {
    await prisma.reimbursement.update({ where: { id: Number(params.id) }, data: { isApprove: true, approvedBy: user.id, approvedAt: new Date() } })
    return { message: "Reimbursement approved" }
  })
  .put("/reject/:id", async ({ params, user, set }) => {
    await prisma.reimbursement.update({ where: { id: Number(params.id) }, data: { isApprove: false, updatedBy: user.id, updatedAt: new Date() } })
    return { message: "Reimbursement rejected" }
  })
  .get("/:id", async ({ params, user, set }) => {
    const r = await prisma.reimbursement.findFirst({ where: { id: Number(params.id), isDelete: false } })
    if (!r) { set.status = 404; return { detail: "Not found" } }
    const items = await prisma.reimbursementItem.findMany({ where: { reimbursementID: r.id } })
    return { ...r, items }
  })
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const where: Record<string, unknown> = { isDelete: false }
    if (q.isApprove === "true") where.isApprove = true
    if (q.isPending === "true") where.isApprove = false
    if (q.isPaid === "true") where.isPaid = true
    if (q.isUnpaid === "true") where.isPaid = false
    if (q.keyword) where.OR = [{ name: { contains: q.keyword } }, { projectName: { contains: q.keyword } }]

    const page = Number(q.page ?? 1)
    const pageSize = Number(q.pageSize ?? 10)
    const { skip, take } = paginationParams(page, pageSize)
    try {
      const [data, total] = await Promise.all([
        prisma.reimbursement.findMany({ where: where as never, orderBy: { createdAt: "desc" }, skip, take }),
        prisma.reimbursement.count({ where: where as never }),
      ])
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as any
      const { items, ...rest } = b
      const r = await prisma.reimbursement.create({
        data: { ...rest, date: new Date(rest.date), dueDate: rest.dueDate ? new Date(rest.dueDate) : null, isPaid: false, isApprove: false, isDelete: false, createdBy: user.id, createdAt: new Date() } as never,
      })
      if (items?.length) {
        await prisma.reimbursementItem.createMany({
          data: items.map((item: any) => ({ ...item, date: new Date(item.date), reimbursementID: r.id })),
        })
      }
      return r
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create" } }
  }, { body: ReimbursementBody })
