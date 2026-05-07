import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

function buildSearch(keyword: string) {
  const fields = ["name", "address", "city", "province", "phoneNumber", "email", "itemsSold", "serviceArea"]
  return { OR: fields.map((f) => ({ [f]: { contains: keyword } })) }
}

export class SupplierRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.supplier.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy = "name", sortDir = "asc") {
    const where = { isDelete: false, ...(keyword ? buildSearch(keyword) : {}) }
    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.supplier.findMany({ where, orderBy: { [sortBy]: sortDir as "asc" | "desc" }, skip, take }),
      prisma.supplier.count({ where }),
    ])
    return { data, total }
  }

  static async getById(id: number) {
    return prisma.supplier.findFirst({ where: { id, isDelete: false } })
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.supplier.update({ where: { id }, data: data as never })
  }

  static async softDelete(id: number, deletedBy: number) {
    return prisma.supplier.update({
      where: { id },
      data: { isDelete: true, deletedBy, deletedAt: new Date() },
    })
  }
}
