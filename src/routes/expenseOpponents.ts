import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { ExpenseOpponentRepository } from "../repository/expenseOpponent"
import { paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"

const OpponentBody = t.Object({
  name: t.String(),
  type: t.String(),
  description: t.Optional(t.String()),
  paymentNumber: t.Optional(t.String()),
  npwp: t.Optional(t.String()),
})

export const expenseOpponentRoutes = new Elysia({ prefix: "/expense-opponents" })
  .use(guard)
  .get("/search/:keyword", async ({ params, query, user, set }) => {
    const limit = Number((query as any).limit ?? 20)
    return ExpenseOpponentRepository.search(params.keyword, limit)
  })
  .get("/:id", async ({ params, user, set }) => {
    const item = await ExpenseOpponentRepository.getById(Number(params.id))
    if (!item) { set.status = 404; return { detail: "Not found" } }
    return item
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10", sortBy, sortByDirection } = query as Record<string, string>
    try {
      const { data, total } = await ExpenseOpponentRepository.getAll(Number(page), Number(pageSize), keyword, sortBy, sortByDirection)
      return { data, meta: paginationMeta(total, Number(page), Number(pageSize)) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      return ExpenseOpponentRepository.create({ ...body as object, createdBy: user.id, createdAt: new Date() })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create" } }
  }, { body: OpponentBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const existing = await ExpenseOpponentRepository.getById(Number(params.id))
    if (!existing) { set.status = 404; return { detail: "Not found" } }
    return ExpenseOpponentRepository.update(Number(params.id), { ...body as object, updatedBy: user.id, updatedAt: new Date() })
  }, { body: OpponentBody })
  .delete("/:id", async ({ params, user, set }) => {
    const existing = await ExpenseOpponentRepository.getById(Number(params.id))
    if (!existing) { set.status = 404; return { detail: "Not found" } }
    await ExpenseOpponentRepository.softDelete(Number(params.id), user.id)
    return { message: "Deleted successfully" }
  })
