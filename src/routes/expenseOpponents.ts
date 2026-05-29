import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { ExpenseOpponentController } from "../controllers/expenseOpponent.controller"
import type { IExpenseOpponentCreate, IExpenseOpponentUpdate } from "../interfaces/expenseOpponent.interfaces"
import { paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"

const OpponentBody = t.Object({
  name: t.String(),
  type: t.String(),
  description: t.Optional(t.String()),
  paymentNumber: t.Optional(t.String()),
  npwp: t.Optional(t.String()),
})

const OpponentUpdateBody = t.Object({
  name: t.Optional(t.String()),
  type: t.Optional(t.String()),
  description: t.Optional(t.String()),
  paymentNumber: t.Optional(t.String()),
  npwp: t.Optional(t.String()),
})

export const expenseOpponentRoutes = new Elysia({ prefix: "/expense-opponents" })
  .use(guard)
  .get("/search/:keyword", async ({ params, query, user, set }) => {
    const limit = Number((query as any).limit ?? 20)
    try {
      const result = await ExpenseOpponentController.search(params.keyword, limit)
      if (Array.isArray(result)) return result
      set.status = result.status
      return result
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to search" } }
  })
  .get("/:id", async ({ params, user, set }) => {
    const result = await ExpenseOpponentController.getById(Number(params.id))
    if ("error" in result) { set.status = result.status; return result }
    return result.data
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10", sortBy, sortByDirection } = query as Record<string, string>
    const result = await ExpenseOpponentController.getAll(Number(page), Number(pageSize), keyword, sortBy, sortByDirection)
    if ("error" in result) { set.status = result.status; return result }
    return result
  })
  .post("/", async ({ body, user, set }) => {
    const result = await ExpenseOpponentController.create(body as IExpenseOpponentCreate, user!.id)
    if ("error" in result) { set.status = result.status; return result }
    return result.data
  }, { body: OpponentBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const result = await ExpenseOpponentController.update(Number(params.id), body as IExpenseOpponentUpdate, user!.id)
    if ("error" in result) { set.status = result.status; return result }
    return result.data
  }, { body: OpponentUpdateBody })
  .delete("/:id", async ({ params, user, set }) => {
    const result = await ExpenseOpponentController.delete(Number(params.id), user!.id)
    if ("error" in result) { set.status = result.status; return result }
    return result
  })
