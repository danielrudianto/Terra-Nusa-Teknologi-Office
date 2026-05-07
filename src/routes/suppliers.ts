import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { SupplierController } from "../controllers/supplier"

const SupplierBody = t.Object({
  id: t.Optional(t.Number()),
  prefix: t.Optional(t.String()),
  name: t.String(),
  address: t.String(),
  city: t.String(),
  province: t.String(),
  phoneNumber: t.String(),
  email: t.Optional(t.String()),
  npwp: t.Optional(t.String()),
  itemsSold: t.String(),
  serviceArea: t.String(),
})

export const supplierRoutes = new Elysia({ prefix: "/suppliers" })
  .use(guard)
  .get("/:id", async ({ params, user, set }) => {
    const result = await SupplierController.getById(Number(params.id))
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10", sortBy, sortByDirection } = query as Record<string, string>
    const result = await SupplierController.getAll(Number(page), Number(pageSize), keyword, sortBy, sortByDirection)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
  .post("/", async ({ body, user, set }) => {
    const result = await SupplierController.create(body as Record<string, unknown>, user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  }, { body: SupplierBody })
  .put("/", async ({ body, user, set }) => {
    const { id, ...rest } = body as any
    if (!id) { set.status = 400; return { detail: "id is required" } }
    const result = await SupplierController.update(Number(id), rest, user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  }, { body: SupplierBody })
  .delete("/:id", async ({ params, user, set }) => {
    const result = await SupplierController.delete(Number(params.id), user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
