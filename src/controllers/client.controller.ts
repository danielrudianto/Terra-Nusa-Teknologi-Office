import { ClientRepository } from "../repository/client"
import { UserRepository } from "../repository/user"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"
import { ClientModel } from "../models/client.model"
import { UserModel } from "../models/user.model"
import type { IClientCreate, IClientOutput, IClientUpdate, IClientView } from "../interfaces/client.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

type ControllerResult<T> = { kind: 'success'; data: T } | { kind: 'error'; error: string; status: number }

async function buildUserView(userId: number | null | undefined): Promise<IUserView> {
  if (!userId) return UserModel.toView(null)
  const user = await UserRepository.getById(userId)
  return UserModel.toView(user)
}

export class ClientController {
  static async create(data: IClientCreate, userId: number): Promise<ControllerResult<IClientOutput>> {
    try {
      const payload = ClientModel.createPayload(data)
      const result = await ClientRepository.create({ ...payload, createdBy: userId, createdAt: new Date() })
      const userView = await buildUserView(userId)
      logInfo(`Client created: ${result.id}`)
      return { kind: 'success', data: ClientModel.toOutput(result, userView, userView) }
    } catch (e) {
      logError(`Error creating client: ${e}`)
      return { kind: 'error', error: "Failed to create client", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy?: string, sortDir?: string): Promise<ControllerResult<{ data: IClientView[]; meta: any }>> {
    if (page < 1) return { kind: 'error', error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await ClientRepository.getAll(page, pageSize, keyword, sortBy, sortDir)
      const transformedData = data.map(ClientModel.toView)
      return { kind: 'success', data: { data: transformedData, meta: paginationMeta(total, page, pageSize) } }
    } catch (e) {
      logError(`Error fetching clients: ${e}`)
      return { kind: 'error', error: "Failed to fetch clients", status: 500 }
    }
  }

  static async getById(id: number): Promise<ControllerResult<IClientOutput>> {
    try {
      const client = await ClientRepository.getById(id)
      if (!client) return { kind: 'error', error: "Client not found", status: 404 }
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(client.createdBy),
        buildUserView(client.updatedBy),
      ])
      return { kind: 'success', data: ClientModel.toOutput(client, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error fetching client ${id}: ${e}`)
      return { kind: 'error', error: "Failed to fetch client", status: 500 }
    }
  }

  static async update(id: number, data: IClientUpdate, userId: number): Promise<ControllerResult<IClientOutput>> {
    try {
      const existing = await ClientRepository.getById(id)
      if (!existing) return { kind: 'error', error: "Client not found", status: 404 }

      const payload = ClientModel.updatePayload(data)
      const result = await ClientRepository.update(id, { ...payload, updatedBy: userId, updatedAt: new Date() })
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(existing.createdBy),
        buildUserView(userId),
      ])
      logInfo(`Client updated: ${id}`)
      return { kind: 'success', data: ClientModel.toOutput(result, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error updating client ${id}: ${e}`)
      return { kind: 'error', error: "Failed to update client", status: 500 }
    }
  }

  static async search(keyword: string): Promise<ControllerResult<IClientView[]>> {
    try {
      const data = await ClientRepository.search(keyword)
      const transformedData = data.map(ClientModel.toView)
      return { kind: 'success', data: transformedData }
    } catch (e) {
      logError(`Error searching clients: ${e}`)
      return { kind: 'error', error: "Failed to search clients", status: 500 }
    }
  }

  static async delete(id: number, userId: number): Promise<ControllerResult<{ message: string }>> {
    try {
      const existing = await ClientRepository.getById(id)
      if (!existing) return { kind: 'error', error: "Client not found", status: 404 }

      await ClientRepository.softDelete(id, userId)
      logInfo(`Client deleted: ${id}`)
      return { kind: 'success', data: { message: "Client deleted" } }
    } catch (e) {
      logError(`Error deleting client ${id}: ${e}`)
      return { kind: 'error', error: "Failed to delete client", status: 500 }
    }
  }
}