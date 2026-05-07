import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

export class InterpaymentRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.interpayment.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, start?: string, end?: string, sortBy = "date", sortDir = "desc") {
    const where: Record<string, unknown> = { isDelete: false }
    if (start && end) where.date = { gte: new Date(start), lte: new Date(end) }

    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.interpayment.findMany({ where: where as never, orderBy: { [sortBy]: sortDir as "asc" | "desc" }, skip, take }),
      prisma.interpayment.count({ where: where as never }),
    ])
    return { data, total }
  }

  static async softDelete(id: number, deletedBy: number) {
    return prisma.interpayment.update({ where: { id }, data: { isDelete: true, deletedBy, deletedAt: new Date() } })
  }
}
