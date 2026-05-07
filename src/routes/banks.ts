import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { BankController } from "../controllers/bank"

const BankBody = t.Object({
  bankName: t.String(),
  bankAccountName: t.String(),
  bankAccountNumber: t.String(),
})

export const bankRoutes = new Elysia({ prefix: "/banks" })
  .use(guard)
  .get("/all", async ({ user, set }) => {
    return BankController.getAllCached()
  })
  .get("/:id", async ({ params, user, set }) => {
    const result = await BankController.getById(Number(params.id))
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10" } = query as Record<string, string>
    const result = await BankController.getAll(Number(page), Number(pageSize), keyword)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
  .post("/", async ({ body, user, set }) => {
    const result = await BankController.create(body as Record<string, unknown>, user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  }, { body: BankBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const result = await BankController.update(Number(params.id), body as Record<string, unknown>, user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  }, { body: BankBody })
  .delete("/:id", async ({ params, user, set }) => {
    const result = await BankController.delete(Number(params.id), user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
