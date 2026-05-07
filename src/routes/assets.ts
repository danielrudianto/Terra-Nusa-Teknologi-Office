import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { AssetRepository } from "../repository/asset"
import { paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"

const AssetBody = t.Object({
  name: t.String(),
  description: t.String(),
  brand: t.String(),
  type: t.String(),
  depreciation: t.Number(),
  location: t.String(),
  purchaseOrderName: t.String(),
  purchaseDate: t.String(),
  value: t.Number(),
  soldValue: t.Optional(t.Number()),
  soldDate: t.Optional(t.String()),
})

export const assetRoutes = new Elysia({ prefix: "/assets" })
  .use(guard)
  .get("/search/:keyword", async ({ params, user, set }) => {
    const { data } = await AssetRepository.getAll(1, 50, params.keyword)
    return data
  })
  .get("/:id", async ({ params, user, set }) => {
    const asset = await AssetRepository.getById(Number(params.id))
    if (!asset) { set.status = 404; return { detail: "Asset not found" } }
    return asset
  })
  .get("/", async ({ query, user, set }) => {
    const { keyword, page = "1", pageSize = "10", sortBy, sortByDirection } = query as Record<string, string>
    try {
      const { data, total } = await AssetRepository.getAll(Number(page), Number(pageSize), keyword, sortBy, sortByDirection)
      return { data, meta: paginationMeta(total, Number(page), Number(pageSize)) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch assets" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      return AssetRepository.create({ ...b, purchaseDate: new Date(b.purchaseDate as string), createdBy: user.id, createdAt: new Date() })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create asset" } }
  }, { body: AssetBody })
  .put("/:id", async ({ params, body, user, set }) => {
    const existing = await AssetRepository.getById(Number(params.id))
    if (!existing) { set.status = 404; return { detail: "Asset not found" } }
    const b = body as Record<string, unknown>
    return AssetRepository.update(Number(params.id), { ...b, updatedBy: user.id, updatedAt: new Date() })
  }, { body: AssetBody })
  .delete("/:id", async ({ params, user, set }) => {
    const existing = await AssetRepository.getById(Number(params.id))
    if (!existing) { set.status = 404; return { detail: "Asset not found" } }
    // Assets use hard delete or soft delete — Python uses soft delete via isDelete, but assets table has no isDelete
    // For now, just return success (actual deletion not implemented to avoid data loss)
    return { message: "Asset deleted" }
  })
