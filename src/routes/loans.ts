import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { LoanRepository } from "../repository/loan"
import { paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"

const LoanBody = t.Object({
  date: t.String(),
  creditorName: t.String(),
  creditorAddress: t.String(),
  creditorNPWP: t.Optional(t.String()),
  description: t.Optional(t.String()),
  received: t.Number(),
  debt: t.Number(),
  bankAccountName: t.String(),
  bankAccountNumber: t.String(),
  bankName: t.String(),
})

export const loanRoutes = new Elysia({ prefix: "/loans" })
  .use(guard)
  .get("/payments/:id", async ({ params, user, set }) => {
    const result = await LoanRepository.getWithPayments(Number(params.id))
    if (!result) { set.status = 404; return { detail: "Loan not found" } }
    return result
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10", isPaid, isUnpaid, sortBy, sortByDirection } = query as Record<string, string>
    try {
      const paidFilter = isPaid === "true" ? true : isUnpaid === "true" ? false : undefined
      const { data, total } = await LoanRepository.getAll(Number(page), Number(pageSize), keyword, paidFilter, sortBy, sortByDirection)
      return { data, meta: paginationMeta(total, Number(page), Number(pageSize)) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch loans" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      return LoanRepository.create({ ...b, date: new Date(b.date as string), createdBy: user.id, createdAt: new Date() })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create loan" } }
  }, { body: LoanBody })
