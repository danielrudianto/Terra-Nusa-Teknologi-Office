import { prisma } from "../utils/database"

export class UserRepository {
  static async getByEmail(email: string) {
    return prisma.user.findFirst({ where: { email } })
  }

  static async getById(id: number) {
    return prisma.user.findUnique({ where: { id } })
  }

  static async create(data: {
    name: string
    email: string
    password: string
    authenticationLevel?: number
    createdBy?: number
  }) {
    return prisma.user.create({ data: { ...data, createdAt: new Date() } })
  }
}
