import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { paginationMeta, paginationParams } from "../utils/pagination"
import { logError } from "../utils/logger"

const PaymentBody = t.Object({
  date: t.String(),
  amount: t.Number(),
  purchaseID: t.Optional(t.Number()),
  expenseID: t.Optional(t.Number()),
  reimbursementID: t.Optional(t.Number()),
  salarySlipID: t.Optional(t.Number()),
  loanID: t.Optional(t.Number()),
  bankAccountID: t.Optional(t.Number()),
})

async function updatePaymentStatus(id: number, status: string, userId: number) {
  const payment = await prisma.paymentOutgoing.findUnique({ where: { id } })
  if (!payment) return null

  const isApprove = status === "approved"
  await prisma.paymentOutgoing.update({ where: { id }, data: { isApprove, updatedBy: userId, updatedAt: new Date() } })

  // Cascade: mark related entity as paid when approved
  if (isApprove) {
    if (payment.purchaseID) await prisma.purchase.update({ where: { id: payment.purchaseID }, data: { isPaid: true } }).catch(() => {})
    if (payment.expenseID) await prisma.expense.update({ where: { id: payment.expenseID }, data: { isPaid: true } }).catch(() => {})
    if (payment.reimbursementID) await prisma.reimbursement.update({ where: { id: payment.reimbursementID }, data: { isPaid: true } }).catch(() => {})
  }
  return payment
}

export const paymentOutgoingRoutes = new Elysia({ prefix: "/outgoing-payments" })
  .use(guard)
  .post("/approve/bulk", async ({ body, user, set }) => {
    const { ids } = body as { ids: number[] }
    await Promise.all(ids.map(id => updatePaymentStatus(id, "approved", user.id)))
    return { message: `${ids.length} payments approved` }
  }, { body: t.Object({ ids: t.Array(t.Number()) }) })
  .post("/reject/bulk", async ({ body, user, set }) => {
    const { ids } = body as { ids: number[] }
    await Promise.all(ids.map(id => updatePaymentStatus(id, "rejected", user.id)))
    return { message: `${ids.length} payments rejected` }
  }, { body: t.Object({ ids: t.Array(t.Number()) }) })
  .post("/move", async ({ body, user, set }) => {
    const { id, date } = body as { id: number; date: string }
    const payment = await prisma.paymentOutgoing.findUnique({ where: { id } })
    if (!payment || payment.isApprove || payment.isDelete) { set.status = 400; return { detail: "Cannot move this payment" } }
    await prisma.paymentOutgoing.update({ where: { id }, data: { date: new Date(date), updatedBy: user.id, updatedAt: new Date() } })
    return { message: "Payment date moved" }
  }, { body: t.Object({ id: t.Number(), date: t.String() }) })
  .put("/approve/:id", async ({ params, user, set }) => {
    await updatePaymentStatus(Number(params.id), "approved", user.id)
    return { message: "Payment approved" }
  })
  .put("/reject/:id", async ({ params, user, set }) => {
    await updatePaymentStatus(Number(params.id), "rejected", user.id)
    return { message: "Payment rejected" }
  })
  .get("/:id", async ({ params, user, set }) => {
    const payment = await prisma.paymentOutgoing.findUnique({ where: { id: Number(params.id) } })
    if (!payment) { set.status = 404; return { detail: "Not found" } }
    return payment
  })
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const where: Record<string, unknown> = { isDelete: false }
    if (q.isPending === "true") where.isApprove = false
    if (q.isApproved === "true") where.isApprove = true

    const page = Number(q.page ?? 1)
    const pageSize = Number(q.pageSize ?? 10)
    const { skip, take } = paginationParams(page, pageSize)
    try {
      const [data, total] = await Promise.all([
        prisma.paymentOutgoing.findMany({ where: where as never, orderBy: { createdAt: "desc" }, skip, take }),
        prisma.paymentOutgoing.count({ where: where as never }),
      ])
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      return prisma.paymentOutgoing.create({
        data: { ...b, date: new Date(b.date as string), isDelete: false, isApprove: false, status: "ready", createdBy: user.id, createdAt: new Date() } as never,
      })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create payment" } }
  }, { body: PaymentBody })
