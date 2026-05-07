import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

export class ExpenseRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.expense.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, filter: Record<string, boolean> = {}, keyword?: string, start?: string, end?: string, sortBy = "createdAt", sortDir = "desc") {
    const where: Record<string, unknown> = { isDelete: false }
    const today = new Date()
    if (filter.isDue) where.dueDate = { lt: today }
    if (filter.isNotDue) where.dueDate = { gte: today }
    if (filter.isPaid) where.isPaid = true
    if (filter.isUnpaid) where.isPaid = false
    if (keyword) where.OR = [{ invoiceName: { contains: keyword } }, { description: { contains: keyword } }, { purchaseType: { contains: keyword } }]
    if (start && end) (where as any).date = { gte: new Date(start), lte: new Date(end) }

    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.expense.findMany({ where: where as never, orderBy: { [sortBy]: sortDir as "asc" | "desc" }, skip, take }),
      prisma.expense.count({ where: where as never }),
    ])
    return { data, total }
  }

  static async getById(id: number) {
    return prisma.expense.findFirst({ where: { id, isDelete: false } })
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.expense.update({ where: { id }, data: data as never })
  }

  static async softDelete(id: number, deletedBy: number) {
    return prisma.expense.update({ where: { id }, data: { isDelete: true, deletedBy, deletedAt: new Date() } })
  }
}
