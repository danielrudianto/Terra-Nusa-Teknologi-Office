import { t } from "elysia"

export const AssetCreateBody = t.Object({
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

export const AssetUpdateBody = t.Object({
  name: t.Optional(t.String()),
  description: t.Optional(t.String()),
  brand: t.Optional(t.String()),
  type: t.Optional(t.String()),
  depreciation: t.Optional(t.Number()),
  location: t.Optional(t.String()),
  purchaseOrderName: t.Optional(t.String()),
  purchaseDate: t.Optional(t.String()),
  value: t.Optional(t.Number()),
  soldValue: t.Optional(t.Number()),
  soldDate: t.Optional(t.String()),
})

export const AssetIdParams = t.Object({
  id: t.Number({ minimum: 1 }),
})

export const AssetSearchParams = t.Object({
  keyword: t.String({ minLength: 1 }),
})

export const AssetListQuery = t.Object({
  keyword: t.Optional(t.String()),
  page: t.Optional(t.Number({ minimum: 1 })),
  pageSize: t.Optional(t.Number({ minimum: 1 })),
  sortBy: t.Optional(t.String()),
  sortByDirection: t.Optional(t.Union([t.Literal("asc"), t.Literal("desc")])),
})
