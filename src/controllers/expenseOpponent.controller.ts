import { ExpenseOpponentRepository } from "../repository/expenseOpponent"
import { UserRepository } from "../repository/user"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"
import { ExpenseOpponentModel } from "../models/expenseOpponent.model"
import type { IExpenseOpponentCreate, IExpenseOpponentOutput, IExpenseOpponentUpdate, IExpenseOpponentView } from "../interfaces/expenseOpponent.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

async function buildUserView(userId: number | null | undefined): Promise<IUserView> {
  if (!userId) return { id: 0, name: "Unknown" }
  const user = await UserRepository.getById(userId)
  return { id: user?.id ?? 0, name: user?.name ?? "Unknown" }
}

export class ExpenseOpponentController {
  static async create(data: IExpenseOpponentCreate, userId: number): Promise<{ kind: "success"; data: IExpenseOpponentOutput } | { error: string; status: number }> {
    try {
      const payload = ExpenseOpponentModel.createPayload(data)
      const record = await ExpenseOpponentRepository.create({ ...payload, createdBy: userId, createdAt: new Date(), isDelete: false })
      const createdBy = await buildUserView(userId)
      return { kind: "success", data: ExpenseOpponentModel.toOutput(record, createdBy, null) }
    } catch (e) {
      logError(`Error creating expense opponent: ${e}`)
      return { error: "Failed to create expense opponent", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy = "name", sortDir = "asc"): Promise<{ data: IExpenseOpponentView[]; meta: any } | { error: string; status: number }> {
    if (page < 1) return { error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await ExpenseOpponentRepository.getAll(page, pageSize, keyword, sortBy, sortDir)
      return { data: data.map(ExpenseOpponentModel.toView), meta: paginationMeta(total, page, pageSize) }
    } catch (e) {
      logError(`Error fetching expense opponents: ${e}`)
      return { error: "Failed to fetch expense opponents", status: 500 }
    }
  }

  static async getById(id: number): Promise<{ kind: "success"; data: IExpenseOpponentOutput } | { error: string; status: number }> {
    try {
      const record = await ExpenseOpponentRepository.getById(id)
      if (!record) return { error: "Expense opponent not found", status: 404 }
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(record.createdBy),
        buildUserView(record.updatedBy),
      ])
      return { kind: "success", data: ExpenseOpponentModel.toOutput(record, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error fetching expense opponent ${id}: ${e}`)
      return { error: "Failed to fetch expense opponent", status: 500 }
    }
  }

  static async update(id: number, data: IExpenseOpponentUpdate, userId: number): Promise<{ kind: "success"; data: IExpenseOpponentOutput } | { error: string; status: number }> {
    try {
      const existing = await ExpenseOpponentRepository.getById(id)
      if (!existing) return { error: "Expense opponent not found", status: 404 }
      const payload = ExpenseOpponentModel.updatePayload(data)
      const updated = await ExpenseOpponentRepository.update(id, { ...payload, updatedBy: userId, updatedAt: new Date() })
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(existing.createdBy),
        buildUserView(userId),
      ])
      return { kind: "success", data: ExpenseOpponentModel.toOutput(updated, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error updating expense opponent ${id}: ${e}`)
      return { error: "Failed to update expense opponent", status: 500 }
    }
  }

  static async delete(id: number, userId: number): Promise<{ message: string } | { error: string; status: number }> {
    try {
      const existing = await ExpenseOpponentRepository.getById(id)
      if (!existing) return { error: "Expense opponent not found", status: 404 }
      await ExpenseOpponentRepository.softDelete(id, userId)
      return { message: "Expense opponent deleted successfully" }
    } catch (e) {
      logError(`Error deleting expense opponent ${id}: ${e}`)
      return { error: "Failed to delete expense opponent", status: 500 }
    }
  }

  static async search(keyword: string, limit = 20): Promise<IExpenseOpponentView[] | { error: string; status: number }> {
    try {
      const results = await ExpenseOpponentRepository.search(keyword, limit)
      return results.map(ExpenseOpponentModel.toView)
    } catch (e) {
      logError(`Error searching expense opponents: ${e}`)
      return { error: "Failed to search expense opponents", status: 500 }
    }
  }
}
