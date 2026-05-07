import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

export class AssetRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.asset.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy = "name", sortDir = "asc") {
    const where = keyword
      ? { OR: [{ name: { contains: keyword } }, { brand: { contains: keyword } }, { type: { contains: keyword } }, { location: { contains: keyword } }] }
      : {}
    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.asset.findMany({ where, orderBy: { [sortBy]: sortDir as "asc" | "desc" }, skip, take }),
      prisma.asset.count({ where }),
    ])
    return { data, total }
  }

  static async getById(id: number) {
    return prisma.asset.findUnique({ where: { id } })
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.asset.update({ where: { id }, data: data as never })
  }
}
