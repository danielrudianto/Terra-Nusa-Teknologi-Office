import { BankRepository } from "../repository/bank"
import { redis, syncRedis } from "../utils/redis"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"

export class BankController {
  static async create(data: Record<string, unknown>, userId: number) {
    try {
      const result = await BankRepository.create({ ...data, createdBy: userId, createdAt: new Date() })
      await syncRedis()
      logInfo(`Bank account created: ${result.id}`)
      return result
    } catch (e) {
      logError(`Error creating bank account: ${e}`)
      return { error: "Failed to create bank account", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string) {
    if (page < 1) return { error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await BankRepository.getAll(page, pageSize, keyword)
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) {
      logError(`Error fetching banks: ${e}`)
      return { error: "Failed to fetch banks", status: 500 }
    }
  }

  static async getAllCached() {
    try {
      const cached = await redis.lrange("bank_account", 0, -1)
      if (cached.length > 0) {
        const banks = cached.map((b) => JSON.parse(b))
        banks.sort((a: any, b: any) => a.bankAccountNumber.localeCompare(b.bankAccountNumber))
        return banks
      }
      return BankRepository.getAllActive()
    } catch {
      return BankRepository.getAllActive()
    }
  }

  static async getById(id: number) {
    try {
      const bank = await BankRepository.getById(id)
      if (!bank) return { error: "Bank account not found", status: 404 }
      return bank
    } catch (e) {
      logError(`Error fetching bank ${id}: ${e}`)
      return { error: "Failed to fetch bank account", status: 500 }
    }
  }

  static async update(id: number, data: Record<string, unknown>, userId: number) {
    try {
      const existing = await BankRepository.getById(id)
      if (!existing) return { error: "Bank account not found", status: 404 }

      const result = await BankRepository.update(id, { ...data, updatedBy: userId, updatedAt: new Date() })
      await syncRedis()
      logInfo(`Bank account updated: ${id}`)
      return result
    } catch (e) {
      logError(`Error updating bank ${id}: ${e}`)
      return { error: "Failed to update bank account", status: 500 }
    }
  }

  static async delete(id: number, userId: number) {
    try {
      const existing = await BankRepository.getById(id)
      if (!existing) return { error: "Bank account not found", status: 404 }

      await BankRepository.softDelete(id, userId)
      await syncRedis()
      logInfo(`Bank account deleted: ${id}`)
      return { message: "Bank account deleted successfully" }
    } catch (e) {
      logError(`Error deleting bank ${id}: ${e}`)
      return { error: "Failed to delete bank account", status: 500 }
    }
  }
}
