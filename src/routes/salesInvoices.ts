import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { paginationMeta, paginationParams } from "../utils/pagination"
import { logError } from "../utils/logger"

const SalesInvoiceBody = t.Object({
  name: t.String(),
  date: t.String(),
  projectName: t.String(),
  clientID: t.Number(),
  dpp: t.Optional(t.Number()),
  pphCode: t.Optional(t.String()),
  pphTaxObject: t.Optional(t.String()),
  pphPercentage: t.Optional(t.Number()),
  ppn: t.Optional(t.Number()),
  bpjs: t.Optional(t.Number()),
  spkNumber: t.String(),
  taxInvoiceName: t.Optional(t.String()),
  description: t.Optional(t.String()),
  bankAccountID: t.Number(),
  separatedInvoice: t.Optional(t.Number()),
})

export const salesInvoiceRoutes = new Elysia({ prefix: "/sales-invoices" })
  .use(guard)
  .get("/exists", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const existing = await prisma.salesInvoice.findFirst({
      where: { description: q.description, projectName: q.projectName, clientID: Number(q.clientID), name: q.name, isDelete: false },
    })
    return { exists: !!existing, invoice: existing }
  })
  .put("/approve/:id", async ({ params, body, user, set }) => {
    const { taxInvoiceName } = body as any
    await prisma.salesInvoice.update({ where: { id: Number(params.id) }, data: { isApprove: true, taxInvoiceName, updatedBy: user.id, updatedAt: new Date() } })
    return { message: "Approved" }
  }, { body: t.Object({ taxInvoiceName: t.Optional(t.String()) }) })
  .put("/reject/:id", async ({ params, user, set }) => {
    await prisma.salesInvoice.update({ where: { id: Number(params.id) }, data: { isApprove: false, updatedBy: user.id, updatedAt: new Date() } })
    return { message: "Rejected" }
  })
  .get("/:id", async ({ params, user, set }) => {
    const inv = await prisma.salesInvoice.findFirst({ where: { id: Number(params.id), isDelete: false } })
    if (!inv) { set.status = 404; return { detail: "Not found" } }
    return inv
  })
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const where: Record<string, unknown> = { isDelete: false }
    if (q.keyword) where.OR = [{ name: { contains: q.keyword } }, { projectName: { contains: q.keyword } }]

    const page = Number(q.page ?? 1)
    const pageSize = Number(q.pageSize ?? 10)
    const { skip, take } = paginationParams(page, pageSize)
    try {
      const [data, total] = await Promise.all([
        prisma.salesInvoice.findMany({ where: where as never, orderBy: { createdAt: "desc" }, skip, take }),
        prisma.salesInvoice.count({ where: where as never }),
      ])
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      return prisma.salesInvoice.create({
        data: { ...b, date: new Date(b.date as string), dpp: b.dpp ?? 0, ppn: b.ppn ?? 0, bpjs: b.bpjs ?? 0, pphPercentage: b.pphPercentage ?? 0, isApprove: false, isDelete: false, createdBy: user.id, createdAt: new Date() } as never,
      })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create" } }
  }, { body: SalesInvoiceBody })
