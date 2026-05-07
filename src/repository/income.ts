import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

export class IncomeRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.income.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, keyword?: string, start?: string, end?: string, sortBy = "date", sortDir = "desc") {
    const where: Record<string, unknown> = { isDelete: 0 }
    if (keyword) where.description = { contains: keyword }
    if (start && end) where.date = { gte: start, lte: end }

    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.income.findMany({ where: where as never, orderBy: { [sortBy]: sortDir as "asc" | "desc" }, skip, take }),
      prisma.income.count({ where: where as never }),
    ])
    return { data, total }
  }

  static async getById(id: number) {
    return prisma.income.findFirst({ where: { id, isDelete: 0 } })
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.income.update({ where: { id }, data: data as never })
  }

  static async softDelete(id: number, deletedBy: number) {
    return prisma.income.update({ where: { id }, data: { isDelete: 1, deletedBy, deletedAt: new Date() } })
  }
}
