import { SupplierRepository } from "../repository/supplier"
import { UserRepository } from "../repository/user"
import { meili } from "../utils/meilisearch"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"
import { SupplierModel } from "../models/supplier.model"
import { UserModel } from "../models/user.model"
import type { ISupplierCreate, ISupplierOutput, ISupplierUpdate, ISupplierView } from "../interfaces/supplier.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

const index = meili.index("suppliers")

async function indexSupplier(supplier: Record<string, unknown>) {
  try {
    const doc = {
      ...supplier,
      phone_number: supplier.phoneNumber,
      name: `${supplier.name}, ${supplier.prefix ?? ""}`,
      items_sold: supplier.itemsSold ? String(supplier.itemsSold).split(",").map((s) => s.trim()) : [],
      service_area: supplier.serviceArea ? String(supplier.serviceArea).split(",").map((s) => s.trim()) : [],
      is_blacklisted: supplier.isBlackListed ?? false,
    }
    for (const [k, v] of Object.entries(doc)) {
      if (v instanceof Date) (doc as Record<string, unknown>)[k] = v.toISOString()
      else if (v === null) (doc as Record<string, unknown>)[k] = ""
    }
    await index.addDocuments([doc])
  } catch (e) {
    logError(`Meilisearch indexing error: ${e}`)
  }
}

async function buildUserView(userId: number | null | undefined): Promise<IUserView> {
  if (!userId) return UserModel.toView(null)
  const user = await UserRepository.getById(userId)
  return UserModel.toView(user)
}

export class SupplierController {
  static async create(data: ISupplierCreate, userId: number): Promise<{ kind: 'success'; data: ISupplierOutput } | { kind: 'error'; error: string; status: number }> {
    try {
      const payload = SupplierModel.createPayload(data)
      const supplier = await SupplierRepository.create({ ...payload, createdBy: userId, createdAt: new Date() })
      void indexSupplier(supplier as Record<string, unknown>)
      const userView = await buildUserView(userId)
      logInfo(`Supplier created: ${supplier.id}`)
      return { kind: 'success', data: SupplierModel.toOutput(supplier, userView, userView) }
    } catch (e) {
      logError(`Error creating supplier: ${e}`)
      return { kind: 'error', error: "Failed to create supplier", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy?: string, sortDir?: string): Promise<{ data: ISupplierView[]; meta: any } | { error: string; status: number }> {
    if (page < 1) return { error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await SupplierRepository.getAll(page, pageSize, keyword, sortBy, sortDir)
      const transformedData = data.map(SupplierModel.toView)
      return { data: transformedData, meta: paginationMeta(total, page, pageSize) }
    } catch (e) {
      logError(`Error fetching suppliers: ${e}`)
      return { error: "Failed to fetch suppliers", status: 500 }
    }
  }

  static async getById(id: number): Promise<{ kind: 'success'; data: ISupplierOutput } | { error: string; status: number }> {
    try {
      const supplier = await SupplierRepository.getById(id)
      if (!supplier) return { error: "Supplier not found", status: 404 }
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(supplier.createdBy),
        buildUserView(supplier.updatedBy),
      ])
      return { kind: 'success', data: SupplierModel.toOutput(supplier, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error fetching supplier ${id}: ${e}`)
      return { error: "Failed to fetch supplier", status: 500 }
    }
  }

  static async update(id: number, data: ISupplierUpdate, userId: number): Promise<{ kind: 'success'; data: ISupplierOutput } | { error: string; status: number }> {
    try {
      const existing = await SupplierRepository.getById(id)
      if (!existing) return { error: "Supplier not found", status: 404 }

      const payload = SupplierModel.updatePayload(data)
      const updated = await SupplierRepository.update(id, { ...payload, updatedBy: userId, updatedAt: new Date() })
      void indexSupplier(updated as Record<string, unknown>)
      const [createdBy, updatedBy] = await Promise.all([
        buildUserView(existing.createdBy),
        buildUserView(userId),
      ])
      logInfo(`Supplier updated: ${id}`)
      return { kind: 'success', data: SupplierModel.toOutput(updated, createdBy, updatedBy) }
    } catch (e) {
      logError(`Error updating supplier ${id}: ${e}`)
      return { error: "Failed to update supplier", status: 500 }
    }
  }

  static async setBlackList(id: number, isBlackListed: boolean, userId: number) {
    try {
      const existing = await SupplierRepository.getById(id)
      if (!existing) return { error: "Supplier not found", status: 404 }

      const updated = await SupplierRepository.update(id, { isBlackListed, updatedBy: userId, updatedAt: new Date() })
      void indexSupplier(updated as Record<string, unknown>)
      logInfo(`Supplier ${id} blacklist set to ${isBlackListed}`)
      return { message: "Supplier blacklist updated" }
    } catch (e) {
      logError(`Error setting blacklist for supplier ${id}: ${e}`)
      return { error: "Failed to update blacklist", status: 500 }
    }
  }

  static async delete(id: number, userId: number) {
    try {
      const existing = await SupplierRepository.getById(id)
      if (!existing) return { error: "Supplier not found", status: 404 }

      await SupplierRepository.softDelete(id, userId)
      await index.deleteDocument(id)
      logInfo(`Supplier deleted: ${id}`)
      return { message: "Supplier deleted successfully" }
    } catch (e) {
      logError(`Error deleting supplier ${id}: ${e}`)
      return { error: "Failed to delete supplier", status: 500 }
    }
  }
}
