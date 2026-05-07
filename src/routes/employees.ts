import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { EmployeeController } from "../controllers/employee"

const EmployeeBody = t.Object({
  id: t.Optional(t.Number()),
  name: t.String(),
  nik: t.String(),
  birthday: t.String(),
  email: t.String(),
  phoneNumber: t.String(),
  address: t.String(),
  position: t.String(),
  department: t.String(),
  taxCategory: t.String(),
  startDate: t.Optional(t.String()),
  endDate: t.Optional(t.String()),
})

export const employeeRoutes = new Elysia({ prefix: "/employees" })
  .use(guard)
  .get("/:id", async ({ params, user, set }) => {
    const result = await EmployeeController.getById(Number(params.id))
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10", sortBy, sortByDirection } = query as Record<string, string>
    const result = await EmployeeController.getAll(Number(page), Number(pageSize), keyword, sortBy, sortByDirection)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  })
  .post("/", async ({ body, user, set }) => {
    const result = await EmployeeController.create(body as Record<string, unknown>, user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  }, { body: EmployeeBody })
  .put("/", async ({ body, user, set }) => {
    const { id, ...rest } = body as any
    if (!id) { set.status = 400; return { detail: "id is required" } }
    const result = await EmployeeController.update(Number(id), rest, user.id)
    if ("error" in result) { set.status = (result as any).status; return result }
    return result
  }, { body: EmployeeBody })
