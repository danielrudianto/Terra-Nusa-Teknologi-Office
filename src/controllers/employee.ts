import { EmployeeRepository } from "../repository/employee"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"

export class EmployeeController {
  static async create(data: Record<string, unknown>, userId: number) {
    try {
      const result = await EmployeeRepository.create({ ...data, createdBy: userId, createdAt: new Date() })
      logInfo(`Employee created: ${result.id}`)
      return result
    } catch (e) {
      logError(`Error creating employee: ${e}`)
      return { error: "Failed to create employee", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy?: string, sortDir?: string) {
    if (page < 1) return { error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await EmployeeRepository.getAll(page, pageSize, keyword, sortBy, sortDir)
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) {
      logError(`Error fetching employees: ${e}`)
      return { error: "Failed to fetch employees", status: 500 }
    }
  }

  static async getById(id: number) {
    try {
      const employee = await EmployeeRepository.getById(id)
      if (!employee) return { error: "Employee not found", status: 404 }
      return employee
    } catch (e) {
      logError(`Error fetching employee ${id}: ${e}`)
      return { error: "Failed to fetch employee", status: 500 }
    }
  }

  static async update(id: number, data: Record<string, unknown>, userId: number) {
    try {
      const existing = await EmployeeRepository.getById(id)
      if (!existing) return { error: "Employee not found", status: 404 }
      if (existing.isDelete) return { error: "Employee has been deleted", status: 400 }

      const result = await EmployeeRepository.update(id, { ...data, updatedBy: userId, updatedAt: new Date() })
      logInfo(`Employee updated: ${id}`)
      return result
    } catch (e) {
      logError(`Error updating employee ${id}: ${e}`)
      return { error: "Failed to update employee", status: 500 }
    }
  }
}
