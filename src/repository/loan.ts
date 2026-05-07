import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

export class LoanRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.loan.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, keyword?: string, isPaid?: boolean, sortBy = "date", sortDir = "desc") {
    const where: Record<string, unknown> = {}
    if (isPaid !== undefined) where.isPaid = isPaid ? 1 : 0
    if (keyword) where.OR = [{ creditorName: { contains: keyword } }, { description: { contains: keyword } }]

    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.loan.findMany({ where: where as never, orderBy: { [sortBy]: sortDir as "asc" | "desc" }, skip, take }),
      prisma.loan.count({ where: where as never }),
    ])
    return { data, total }
  }

  static async getById(id: number) {
    return prisma.loan.findUnique({ where: { id } })
  }

  static async getWithPayments(id: number) {
    const loan = await prisma.loan.findUnique({ where: { id } })
    if (!loan) return null
    const payments = await prisma.paymentOutgoing.findMany({ where: { loanID: id, isDelete: false } })
    return { ...loan, payments }
  }
}
