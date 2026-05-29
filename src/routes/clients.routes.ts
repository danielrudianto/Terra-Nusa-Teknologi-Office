import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { ClientController } from "../controllers/client.controller"
import { requireUser } from "../utils/auth.utils"
import { getEntityId, parsePositiveIntegerParam } from "../utils/number.utils"
import type { IClientCreate, IClientUpdate } from "../interfaces/client.interfaces"

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
  .get("/search/:keyword", async ({ params, set }) => {
    const result = await ClientController.search(params.keyword)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
  .get("/:id", async ({ params, set }) => {
    const id = getEntityId(params, set, "client")
    if (id === null) return { detail: "Invalid client id" }

    const result = await ClientController.getById(id)
    if (result.kind === 'error') {
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

    const result = await ClientController.getAll(parsedPage, parsedPageSize, keyword, sortBy, sortByDirection)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
  .post("/", async ({ body, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const result = await ClientController.create(body as IClientCreate, currentUser.id)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { body: ClientBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const id = getEntityId(params, set, "client")
    if (id === null) return { detail: "Invalid client id" }

    const result = await ClientController.update(id, body as IClientUpdate, currentUser.id)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { body: ClientBody })
  .delete("/:id", async ({ params, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const id = getEntityId(params, set, "client")
    if (id === null) return { detail: "Invalid client id" }

    const result = await ClientController.delete(id, currentUser.id)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  })
