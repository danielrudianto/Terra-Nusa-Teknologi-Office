import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { ExpenseRepository } from "../repository/expense"
import { prisma } from "../utils/database"
import { paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"

const ExpenseBody = t.Object({
  invoiceName: t.String(),
  receiptName: t.String(),
  opponentID: t.Optional(t.Number()),
  date: t.String(),
  dueDate: t.Optional(t.String()),
  purchaseType: t.String(),
  dpp: t.Number(),
  pbbkb: t.Number(),
  pphCode: t.Optional(t.String()),
  pphTaxObject: t.Optional(t.String()),
  pphPercentage: t.Number(),
  bankName: t.String(),
  bankAccountName: t.String(),
  bankAccountNumber: t.String(),
  paymentMethod: t.String(),
  description: t.String(),
})

export const expenseRoutes = new Elysia({ prefix: "/expenses" })
  .use(guard)
  .get("/:id/payments", async ({ params, user, set }) => {
    return prisma.paymentOutgoing.findMany({ where: { expenseID: Number(params.id), isDelete: false } })
  })
  .get("/:id", async ({ params, user, set }) => {
    const expense = await ExpenseRepository.getById(Number(params.id))
    if (!expense) { set.status = 404; return { detail: "Expense not found" } }
    const payments = await prisma.paymentOutgoing.findMany({ where: { expenseID: Number(params.id), isDelete: false } })
    return { ...expense, payments }
  })
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const filter = { isDue: q.isDue === "true", isNotDue: q.isNotDue === "true", isPaid: q.isPaid === "true", isUnpaid: q.isUnpaid === "true" }
    try {
      const { data, total } = await ExpenseRepository.getAll(Number(q.page ?? 1), Number(q.pageSize ?? 10), filter, q.keyword, q.start, q.end, q.sortBy, q.sortByDirection)
      return { data, meta: paginationMeta(total, Number(q.page ?? 1), Number(q.pageSize ?? 10)) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch expenses" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      return ExpenseRepository.create({ ...b, date: new Date(b.date as string), dueDate: b.dueDate ? new Date(b.dueDate as string) : null, isPaid: false, isDelete: false, createdBy: user.id, createdAt: new Date() })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create expense" } }
  }, { body: ExpenseBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const b = body as Record<string, unknown>
    return ExpenseRepository.update(Number(params.id), { ...b, updatedBy: user.id, updatedAt: new Date() })
  }, { body: ExpenseBody })
  .put("/:id/approve", async ({ params, user, set }) => {
    await ExpenseRepository.update(Number(params.id), { updatedBy: user.id, updatedAt: new Date() })
    return { message: "Expense approved" }
  })
  .patch("/:id/payment-status", async ({ params, body, user, set }) => {
    const { isPaid } = body as { isPaid: boolean }
    await ExpenseRepository.update(Number(params.id), { isPaid, updatedBy: user.id, updatedAt: new Date() })
    return { message: "Payment status updated" }
  }, { body: t.Object({ isPaid: t.Boolean() }) })
  .delete("/:id", async ({ params, user, set }) => {
    await ExpenseRepository.softDelete(Number(params.id), user.id)
    return { message: "Expense deleted" }
  })
