import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { ClientController } from "../controllers/client"

const ClientBody = t.Object({
  prefix: t.Optional(t.String()),
  name: t.String(),
  address: t.String(),
  city: t.String(),
  province: t.String(),
  phoneNumber: t.String(),
  email: t.Optional(t.String()),
  npwp: t.Optional(t.String()),
})

export const clientRoutes = new Elysia({ prefix: "/clients" })
  .use(guard)
  .get("/search/:keyword", async ({ params, user, set }) => {
    return ClientController.search(params.keyword)
  })
  .get("/:id", async ({ params, user, set }) => {
    const result = await ClientController.getById(Number(params.id))
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10", sortBy, sortByDirection } = query as Record<string, string>
    const result = await ClientController.getAll(Number(page), Number(pageSize), keyword, sortBy, sortByDirection)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
  .post("/", async ({ body, user, set }) => {
    const result = await ClientController.create(body as Record<string, unknown>, user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  }, { body: ClientBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const result = await ClientController.update(Number(params.id), body as Record<string, unknown>, user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  }, { body: ClientBody })
  .delete("/:id", async ({ params, user, set }) => {
    const result = await ClientController.delete(Number(params.id), user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
