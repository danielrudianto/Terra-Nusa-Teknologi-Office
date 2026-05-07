import { SupplierRepository } from "../repository/supplier"
import { meili } from "../utils/meilisearch"
import { logError, logInfo } from "../utils/logger"
import { paginationMeta } from "../utils/pagination"

const index = meili.index("suppliers")

async function indexSupplier(supplier: Record<string, unknown>) {
  try {
    const doc = {
      ...supplier,
      phone_number: supplier.phoneNumber,
      name: `${supplier.name}, ${supplier.prefix ?? ""}`,
      items_sold: supplier.itemsSold ? String(supplier.itemsSold).split(",").map((s) => s.trim()) : [],
      service_area: supplier.serviceArea ? String(supplier.serviceArea).split(",").map((s) => s.trim()) : [],
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

export class SupplierController {
  static async create(data: Record<string, unknown>, userId: number) {
    try {
      const supplier = await SupplierRepository.create({ ...data, createdBy: userId, createdAt: new Date() })
      void indexSupplier(supplier as Record<string, unknown>)
      logInfo(`Supplier created: ${supplier.id}`)
      return supplier
    } catch (e) {
      logError(`Error creating supplier: ${e}`)
      return { error: "Failed to create supplier", status: 500 }
    }
  }

  static async getAll(page: number, pageSize: number, keyword?: string, sortBy?: string, sortDir?: string) {
    if (page < 1) return { error: "Page must be >= 1", status: 400 }
    try {
      const { data, total } = await SupplierRepository.getAll(page, pageSize, keyword, sortBy, sortDir)
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) {
      logError(`Error fetching suppliers: ${e}`)
      return { error: "Failed to fetch suppliers", status: 500 }
    }
  }

  static async getById(id: number) {
    try {
      const supplier = await SupplierRepository.getById(id)
      if (!supplier) return { error: "Supplier not found", status: 404 }
      return supplier
    } catch (e) {
      logError(`Error fetching supplier ${id}: ${e}`)
      return { error: "Failed to fetch supplier", status: 500 }
    }
  }

  static async update(id: number, data: Record<string, unknown>, userId: number) {
    try {
      const existing = await SupplierRepository.getById(id)
      if (!existing) return { error: "Supplier not found", status: 404 }

      const updated = await SupplierRepository.update(id, { ...data, updatedBy: userId, updatedAt: new Date() })
      void indexSupplier(updated as Record<string, unknown>)
      logInfo(`Supplier updated: ${id}`)
      return updated
    } catch (e) {
      logError(`Error updating supplier ${id}: ${e}`)
      return { error: "Failed to update supplier", status: 500 }
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
