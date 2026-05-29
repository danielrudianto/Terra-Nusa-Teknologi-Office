import { Elysia } from "elysia"
import { guard } from "../utils/guard"
import { AssetController } from "../controllers/assets.controllers";
import type { Static } from "@sinclair/typebox"
import {
  AssetCreateBody,
  AssetIdParams,
  AssetListQuery,
  AssetSearchParams,
  AssetUpdateBody,
} from "../schemas/assets.schemas"
import { requireUser } from "../utils/auth.utils"
import { getEntityId, parsePositiveIntegerParam } from "../utils/number.utils"

type AssetCreatePayload = Static<typeof AssetCreateBody>
type AssetUpdatePayload = Static<typeof AssetUpdateBody>

export const assetRoutes = new Elysia({ prefix: "/assets" })
  .use(guard)
  .get("/search/:keyword", async ({ params, set }) => {
    const result = await AssetController.search(params.keyword)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { params: AssetSearchParams })
  .get("/:id", async ({ params, set }) => {
    const id = getEntityId(params, set, "asset")
    if (id === null) return { detail: "Invalid asset id" }

    const result = await AssetController.getById(id)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { params: AssetIdParams })
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

    const result = await AssetController.getAll(parsedPage, parsedPageSize, keyword, sortBy, sortByDirection)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { query: AssetListQuery })
  .post("/", async ({ body, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const payload = body as AssetCreatePayload
    const result = await AssetController.create({
      ...payload,
      purchaseDate: new Date(payload.purchaseDate),
    }, currentUser.id)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { body: AssetCreateBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const id = getEntityId(params, set, "asset")
    if (id === null) return { detail: "Invalid asset id" }

    const payload = body as AssetUpdatePayload
    const result = await AssetController.update(id, {
      ...payload,
    }, currentUser.id)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { params: AssetIdParams, body: AssetUpdateBody })
  .delete("/:id", async ({ params, user, set }) => {
    const currentUser = requireUser(user, set)
    if (!currentUser) return { detail: "Unauthorized" }

    const id = getEntityId(params, set, "asset")
    if (id === null) return { detail: "Invalid asset id" }

    const result = await AssetController.delete(id)
    if (result.kind === 'error') {
      set.status = result.status
      return { detail: result.error }
    }
    return result.data
  }, { params: AssetIdParams })
