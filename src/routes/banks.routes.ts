import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { BankController } from "../controllers/bank.controller"
import { requireUser } from "../utils/auth.utils"
import { getEntityId, parsePositiveIntegerParam } from "../utils/number.utils"
import { IBankCreate, IBankUpdate } from "../interfaces/bank.interfaces"

const BankCreateBody = t.Object({
  bankName: t.String(),
  bankAccountName: t.String(),
  bankAccountNumber: t.String(),
})

const BankUpdateBody = t.Object({
  bankName: t.Optional(t.String()),
  bankAccountName: t.Optional(t.String()),
  bankAccountNumber: t.Optional(t.String()),
})

export const bankRoutes = new Elysia({ prefix: "/banks" })
  .use(guard)
  .get("/all", async ({ set }) => {
    const result = await BankController.getAllCached()
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
  .get("/:id", async ({ params, set }) => {
    const id = getEntityId(params, set, "bank account")
    if (id === null) return { detail: "Invalid bank account id" }

    const result = await BankController.getById(id)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
  .get("/", async ({ query, set }) => {
    const { keyword, page, pageSize } = query as {
      keyword?: string
      page?: unknown
      pageSize?: unknown
    }

    const parsedPage = parsePositiveIntegerParam(page ?? 1, "page", set)
    if (parsedPage === null) return { detail: "Invalid page value" }

    const parsedPageSize = parsePositiveIntegerParam(pageSize ?? 10, "pageSize", set)
    if (parsedPageSize === null) return { detail: "Invalid pageSize value" }

    const result = await BankController.getAll(parsedPage, parsedPageSize, keyword)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
  .post("/", async ({ body, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const result = await BankController.create(body as IBankCreate, currentUser.id)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { body: BankCreateBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const id = getEntityId(params, set, "bank account")
    if (id === null) return { detail: "Invalid bank account id" }

    const result = await BankController.update(id, body as IBankUpdate, currentUser.id)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { body: BankUpdateBody })
  .delete("/:id", async ({ params, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const id = getEntityId(params, set, "bank account")
    if (id === null) return { detail: "Invalid bank account id" }

    const result = await BankController.delete(id, currentUser.id)
    if (result.kind === "error") {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
