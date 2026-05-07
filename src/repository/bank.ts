import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

export class BankRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.bankAccount.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, keyword?: string) {
    const where = {
      isDelete: false,
      ...(keyword ? { OR: [{ bankName: { contains: keyword } }, { bankAccountName: { contains: keyword } }, { bankAccountNumber: { contains: keyword } }] } : {}),
    }
    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.bankAccount.findMany({ where, orderBy: { bankName: "asc" }, skip, take }),
      prisma.bankAccount.count({ where }),
    ])
    return { data, total }
  }

  static async getAllActive() {
    return prisma.bankAccount.findMany({
      where: { isDelete: false },
      select: { id: true, bankName: true, bankAccountName: true, bankAccountNumber: true },
      orderBy: { bankName: "asc" },
    })
  }

  static async getById(id: number) {
    return prisma.bankAccount.findFirst({ where: { id, isDelete: false } })
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.bankAccount.update({ where: { id }, data: data as never })
  }

  static async softDelete(id: number, deletedBy: number) {
    return prisma.bankAccount.update({
      where: { id },
      data: { isDelete: true, deletedBy, deletedAt: new Date() },
    })
  }
}
