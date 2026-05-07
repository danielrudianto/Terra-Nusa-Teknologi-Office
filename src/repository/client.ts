import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

const SEARCH_FIELDS = ["name", "address", "city", "province", "phoneNumber", "email"] as const

function buildSearch(keyword: string) {
  return {
    OR: SEARCH_FIELDS.map((f) => ({ [f]: { contains: keyword } })),
  }
}

function buildOrderBy(sortBy = "name", dir = "asc") {
  return { [sortBy]: dir as "asc" | "desc" }
}

export class ClientRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.client.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy?: string, sortDir?: string) {
    const where = { isDelete: false, ...(keyword ? buildSearch(keyword) : {}) }
    const orderBy = buildOrderBy(sortBy, sortDir)
    const { skip, take } = paginationParams(page, pageSize)

    const [data, total] = await Promise.all([
      prisma.client.findMany({ where, orderBy, skip, take }),
      prisma.client.count({ where }),
    ])
    return { data, total }
  }

  static async getById(id: number) {
    return prisma.client.findFirst({ where: { id, isDelete: false } })
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.client.update({ where: { id }, data: data as never })
  }

  static async softDelete(id: number, deletedBy: number) {
    return prisma.client.update({
      where: { id },
      data: { isDelete: true, deletedBy, deletedAt: new Date() },
    })
  }

  static async search(keyword: string) {
    return prisma.client.findMany({
      where: { isDelete: false, ...buildSearch(keyword) },
      orderBy: { name: "asc" },
      take: 50,
    })
  }
}
