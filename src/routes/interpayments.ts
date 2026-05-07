import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { InterpaymentRepository } from "../repository/interpayment"
import { paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"

const InterpaymentBody = t.Object({
  bankAccountIDOrigin: t.Number(),
  bankAccountIDDestination: t.Number(),
  amount: t.Number(),
  description: t.String(),
  date: t.String(),
})

export const interpaymentRoutes = new Elysia({ prefix: "/interpayments" })
  .use(guard)
  .get("/", async ({ query, user, set }) => {
    const { page = "1", pageSize = "10", start, end, sortBy, sortByDirection } = query as Record<string, string>
    try {
      const { data, total } = await InterpaymentRepository.getAll(Number(page), Number(pageSize), start, end, sortBy, sortByDirection)
      return { data, meta: paginationMeta(total, Number(page), Number(pageSize)) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch interpayments" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      return InterpaymentRepository.create({ ...b, date: new Date(b.date as string), createdBy: user.id, createdAt: new Date() })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create interpayment" } }
  }, { body: InterpaymentBody })
  .delete("/:id", async ({ params, user, set }) => {
    try {
      await InterpaymentRepository.softDelete(Number(params.id), user.id)
      return { message: "Deleted successfully" }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to delete" } }
  })
