import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { IncomeRepository } from "../repository/income"
import { paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"

const IncomeBody = t.Object({
  description: t.String(),
  date: t.String(),
  incomeType: t.String(),
  amount: t.Number(),
  opponentID: t.Number(),
})

export const incomeRoutes = new Elysia({ prefix: "/income" })
  .use(guard)
  .get("/:id", async ({ params, user, set }) => {
    const item = await IncomeRepository.getById(Number(params.id))
    if (!item) { set.status = 404; return { detail: "Not found" } }
    return item
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10", start, end, sortBy, sortByDirection } = query as Record<string, string>
    try {
      const { data, total } = await IncomeRepository.getAll(Number(page), Number(pageSize), keyword, start, end, sortBy, sortByDirection)
      return { data, meta: paginationMeta(total, Number(page), Number(pageSize)) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      return IncomeRepository.create({ ...body as object, createdBy: user.id, createdAt: new Date() })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create" } }
  }, { body: IncomeBody })
  .put("/:id", async ({ params, body, user, set }) => {
    return IncomeRepository.update(Number(params.id), body as Record<string, unknown>)
  }, { body: IncomeBody })
  .delete("/:id", async ({ params, user, set }) => {
    await IncomeRepository.softDelete(Number(params.id), user.id)
    return { message: "Deleted successfully" }
  })
