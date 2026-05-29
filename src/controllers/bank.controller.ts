import { BankRepository } from "../repository/bank"
import { UserRepository } from "../repository/user"
import { redis, syncRedis } from "../utils/redis"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"
import { BankModel } from "../models/bank.model"
import { UserModel } from "../models/user.model"
import type { IBankCreate, IBankOutput, IBankUpdate, IBankView } from "../interfaces/bank.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

type ControllerResult<T> = { kind: "success"; data: T } | { kind: "error"; error: string; status: number }

async function buildUserView(userId: number | null | undefined): Promise<IUserView> {
  if (!userId) return UserModel.toView(null)
  const user = await UserRepository.getById(userId)
  return UserModel.toView(user)
}

export class BankController {
  static async create(data: IBankCreate, userId: number): Promise<ControllerResult<IBankOutput>> {
    try {
      const payload = BankModel.createPayload(data)
      const result = await BankRepository.create({ ...payload, createdBy: userId, createdAt: new Date() })
      await syncRedis()
      const userView = await buildUserView(userId)
      logInfo(`Bank account created: ${result.id}`)
      return { kind: "success", data: BankModel.toOutput(result, userView, userView) }
    } catch (e) {
      logError(`Error creating bank account: ${e}`)
      return { kind: "error", error: "Failed to create bank account", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string): Promise<ControllerResult<{ data: IBankView[]; meta: any }>> {
    if (page < 1) return { kind: "error", error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await BankRepository.getAll(page, pageSize, keyword)
      const transformedData = data.map(BankModel.toView)
      return { kind: "success", data: { data: transformedData, meta: paginationMeta(total, page, pageSize) } }
    } catch (e) {
      logError(`Error fetching banks: ${e}`)
      return { kind: "error", error: "Failed to fetch banks", status: 500 }
    }
  }

  static async getAllCached(): Promise<ControllerResult<IBankView[]>> {
    try {
      const cached = await redis.lrange("bank_account", 0, -1)
      if (cached.length > 0) {
        const banks = cached.map((b) => JSON.parse(b))
        banks.sort((a: any, b: any) => a.bankAccountNumber.localeCompare(b.bankAccountNumber))
        return { kind: "success", data: banks }
      }
      const banks = await BankRepository.getAllActive()
      return { kind: "success", data: banks.map(BankModel.toView) }
    } catch (e) {
      logError(`Error fetching cached banks: ${e}`)
      return { kind: "error", error: "Failed to fetch cached banks", status: 500 }
    }
  }

  static async getById(id: number): Promise<ControllerResult<IBankOutput>> {
    try {
      const bank = await BankRepository.getById(id)
      if (!bank) return { kind: "error", error: "Bank account not found", status: 404 }
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(bank.createdBy),
        buildUserView(bank.updatedBy),
      ])
      return { kind: "success", data: BankModel.toOutput(bank, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error fetching bank ${id}: ${e}`)
      return { kind: "error", error: "Failed to fetch bank account", status: 500 }
    }
  }

  static async update(id: number, data: IBankUpdate, userId: number): Promise<ControllerResult<IBankOutput>> {
    try {
      const existing = await BankRepository.getById(id)
      if (!existing) return { kind: "error", error: "Bank account not found", status: 404 }

      const payload = BankModel.updatePayload(data)
      const result = await BankRepository.update(id, { ...payload, updatedBy: userId, updatedAt: new Date() })
      await syncRedis()
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(existing.createdBy),
        buildUserView(userId),
      ])
      logInfo(`Bank account updated: ${id}`)
      return { kind: "success", data: BankModel.toOutput(result, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error updating bank ${id}: ${e}`)
      return { kind: "error", error: "Failed to update bank account", status: 500 }
    }
  }

  static async delete(id: number, userId: number): Promise<ControllerResult<{ message: string }>> {
    try {
      const existing = await BankRepository.getById(id)
      if (!existing) return { kind: "error", error: "Bank account not found", status: 404 }

      await BankRepository.softDelete(id, userId)
      await syncRedis()
      logInfo(`Bank account deleted: ${id}`)
      return { kind: "success", data: { message: "Bank account deleted successfully" } }
    } catch (e) {
      logError(`Error deleting bank ${id}: ${e}`)
      return { kind: "error", error: "Failed to delete bank account", status: 500 }
    }
  }
}
