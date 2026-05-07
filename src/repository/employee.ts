import { prisma } from "../utils/database"
import { paginationParams } from "../utils/pagination"

export class EmployeeRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.employee.create({ data: data as never })
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy = "name", sortDir = "asc") {
    const where = {
      isDelete: false,
      ...(keyword ? { OR: [{ name: { contains: keyword } }, { nik: { contains: keyword } }, { email: { contains: keyword } }, { department: { contains: keyword } }, { position: { contains: keyword } }] } : {}),
    }
    const { skip, take } = paginationParams(page, pageSize)
    const [data, total] = await Promise.all([
      prisma.employee.findMany({ where, orderBy: { [sortBy]: sortDir as "asc" | "desc" }, skip, take }),
      prisma.employee.count({ where }),
    ])
    return { data, total }
  }

  static async getById(id: number) {
    return prisma.employee.findFirst({ where: { id, isDelete: false } })
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.employee.update({ where: { id }, data: data as never })
  }
}
