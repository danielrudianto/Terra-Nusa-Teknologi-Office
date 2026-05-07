import { ClientRepository } from "../repository/client"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"

export class ClientController {
  static async create(data: Record<string, unknown>, userId: number) {
    try {
      const result = await ClientRepository.create({ ...data, createdBy: userId, createdAt: new Date() })
      logInfo(`Client created: ${result.id}`)
      return result
    } catch (e) {
      logError(`Error creating client: ${e}`)
      return { error: "Failed to create client", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy?: string, sortDir?: string) {
    if (page < 1) return { error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await ClientRepository.getAll(page, pageSize, keyword, sortBy, sortDir)
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) {
      logError(`Error fetching clients: ${e}`)
      return { error: "Failed to fetch clients", status: 500 }
    }
  }

  static async getById(id: number) {
    try {
      const client = await ClientRepository.getById(id)
      if (!client) return { error: "Client not found", status: 404 }
      return client
    } catch (e) {
      logError(`Error fetching client ${id}: ${e}`)
      return { error: "Failed to fetch client", status: 500 }
    }
  }

  static async update(id: number, data: Record<string, unknown>, userId: number) {
    try {
      const existing = await ClientRepository.getById(id)
      if (!existing) return { error: "Client not found", status: 404 }

      const result = await ClientRepository.update(id, { ...data, updatedBy: userId, updatedAt: new Date() })
      logInfo(`Client updated: ${id}`)
      return result
    } catch (e) {
      logError(`Error updating client ${id}: ${e}`)
      return { error: "Failed to update client", status: 500 }
    }
  }

  static async delete(id: number, userId: number) {
    try {
      const existing = await ClientRepository.getById(id)
      if (!existing) return { error: "Client not found", status: 404 }

      await ClientRepository.softDelete(id, userId)
      logInfo(`Client deleted: ${id}`)
      return { message: "Client deleted successfully" }
    } catch (e) {
      logError(`Error deleting client ${id}: ${e}`)
      return { error: "Failed to delete client", status: 500 }
    }
  }

  static async search(keyword: string) {
    try {
      return await ClientRepository.search(keyword)
    } catch (e) {
      logError(`Error searching clients: ${e}`)
      return { error: "Failed to search clients", status: 500 }
    }
  }
}
