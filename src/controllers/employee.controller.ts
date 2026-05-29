import { EmployeeRepository } from "../repository/employee"
import { UserRepository } from "../repository/user"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"
import { EmployeeModel } from "../models/employee.model"
import { UserModel } from "../models/user.model"
import type { IEmployeeCreate, IEmployeeOutput, IEmployeeUpdate, IEmployeeView } from "../interfaces/employee.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

type ControllerResult<T> = { kind: "success"; data: T } | { kind: "error"; error: string; status: number }

async function buildUserView(userId: number | null | undefined): Promise<IUserView> {
  if (!userId) return UserModel.toView(null)
  const user = await UserRepository.getById(userId)
  return UserModel.toView(user)
}

export class EmployeeController {
  static async create(data: IEmployeeCreate, userId: number): Promise<ControllerResult<IEmployeeOutput>> {
    try {
      const payload = EmployeeModel.createPayload(data)
      const result = await EmployeeRepository.create({ ...payload, createdBy: userId, createdAt: new Date() })
      const userView = await buildUserView(userId)
      logInfo(`Employee created: ${result.id}`)
      return { kind: "success", data: EmployeeModel.toOutput(result, userView, userView) }
    } catch (e) {
      logError(`Error creating employee: ${e}`)
      return { kind: "error", error: "Failed to create employee", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy?: string, sortDir?: string): Promise<ControllerResult<{ data: IEmployeeView[]; meta: any }>> {
    if (page < 1) return { kind: "error", error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await EmployeeRepository.getAll(page, pageSize, keyword, sortBy, sortDir)
      const transformedData = data.map(EmployeeModel.toView)
      return { kind: "success", data: { data: transformedData, meta: paginationMeta(total, page, pageSize) } }
    } catch (e) {
      logError(`Error fetching employees: ${e}`)
      return { kind: "error", error: "Failed to fetch employees", status: 500 }
    }
  }

  static async getById(id: number): Promise<ControllerResult<IEmployeeOutput>> {
    try {
      const employee = await EmployeeRepository.getById(id)
      if (!employee) return { kind: "error", error: "Employee not found", status: 404 }
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(employee.createdBy),
        buildUserView(employee.updatedBy),
      ])
      return { kind: "success", data: EmployeeModel.toOutput(employee, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error fetching employee ${id}: ${e}`)
      return { kind: "error", error: "Failed to fetch employee", status: 500 }
    }
  }

  static async update(id: number, data: IEmployeeUpdate, userId: number): Promise<ControllerResult<IEmployeeOutput>> {
    try {
      const existing = await EmployeeRepository.getById(id)
      if (!existing) return { kind: "error", error: "Employee not found", status: 404 }
      if (existing.isDelete) return { kind: "error", error: "Employee has been deleted", status: 400 }

      const payload = EmployeeModel.updatePayload(data)
      const result = await EmployeeRepository.update(id, { ...payload, updatedBy: userId, updatedAt: new Date() })
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(existing.createdBy),
        buildUserView(userId),
      ])
      logInfo(`Employee updated: ${id}`)
      return { kind: "success", data: EmployeeModel.toOutput(result, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error updating employee ${id}: ${e}`)
      return { kind: "error", error: "Failed to update employee", status: 500 }
    }
  }
}
