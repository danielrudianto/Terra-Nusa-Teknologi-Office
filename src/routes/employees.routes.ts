import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { EmployeeController } from "../controllers/employee.controller"
import { requireUser } from "../utils/auth.utils"
import { getEntityId, parsePositiveIntegerParam } from "../utils/number.utils"
import { IEmployeeCreate, IEmployeeUpdate } from "../interfaces/employee.interfaces"

const EmployeeCreateBody = t.Object({
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

const EmployeeUpdateBody = t.Object({
  name: t.Optional(t.String()),
  nik: t.Optional(t.String()),
  birthday: t.Optional(t.String()),
  email: t.Optional(t.String()),
  phoneNumber: t.Optional(t.String()),
  address: t.Optional(t.String()),
  position: t.Optional(t.String()),
  department: t.Optional(t.String()),
  taxCategory: t.Optional(t.String()),
  startDate: t.Optional(t.String()),
  endDate: t.Optional(t.String()),
})

export const employeeRoutes = new Elysia({ prefix: "/employees" })
  .use(guard)
  .get("/:id", async ({ params, set }) => {
    const id = getEntityId(params, set, "employee")
    if (id === null) return { detail: "Invalid employee id" }

    const result = await EmployeeController.getById(id)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
  .get("/", async ({ query, set }) => {
    const { keyword, page, pageSize, sortBy, sortByDirection } = query as {
      keyword?: string
      page?: unknown
      pageSize?: unknown
      sortBy?: string
      sortByDirection?: string
    }

    const parsedPage = parsePositiveIntegerParam(page ?? 1, "page", set)
    if (parsedPage === null) return { detail: "Invalid page value" }

    const parsedPageSize = parsePositiveIntegerParam(pageSize ?? 10, "pageSize", set)
    if (parsedPageSize === null) return { detail: "Invalid pageSize value" }

    const result = await EmployeeController.getAll(parsedPage, parsedPageSize, keyword, sortBy, sortByDirection)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
  .post("/", async ({ body, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const result = await EmployeeController.create(body as IEmployeeCreate, currentUser.id)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { body: EmployeeCreateBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const id = getEntityId(params, set, "employee")
    if (id === null) return { detail: "Invalid employee id" }

    const result = await EmployeeController.update(id, body as IEmployeeUpdate, currentUser.id)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { body: EmployeeUpdateBody })
