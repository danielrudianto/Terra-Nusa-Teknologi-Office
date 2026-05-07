import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

export class ExpenseOpponentRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.expenseOpponent.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy = "name", sortDir = "asc") {
    const where = {
      isDelete: false,
      ...(keyword ? { OR: [{ name: { contains: keyword } }, { type: { contains: keyword } }, { paymentNumber: { contains: keyword } }] } : {}),
    }
    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.expenseOpponent.findMany({ where, orderBy: { [sortBy]: sortDir as "asc" | "desc" }, skip, take }),
      prisma.expenseOpponent.count({ where }),
    ])
    return { data, total }
  }

  static async getById(id: number) {
    return prisma.expenseOpponent.findFirst({ where: { id, isDelete: false } })
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.expenseOpponent.update({ where: { id }, data: data as never })
  }

  static async softDelete(id: number, deletedBy: number) {
    return prisma.expenseOpponent.update({ where: { id }, data: { isDelete: true, deletedBy, deletedAt: new Date() } })
  }

  static async search(keyword: string, limit = 20) {
    return prisma.expenseOpponent.findMany({
      where: { isDelete: false, OR: [{ name: { contains: keyword } }, { type: { contains: keyword } }] },
      take: limit,
      orderBy: { name: "asc" },
    })
  }
}
