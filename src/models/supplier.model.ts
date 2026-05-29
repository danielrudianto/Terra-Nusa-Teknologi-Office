import type { ISupplierCreate, ISupplierOutput, ISupplierUpdate, ISupplierView } from "../interfaces/supplier.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

export class SupplierModel {
  static toOutput(supplier: any, createdBy: IUserView, updatedBy: IUserView | null): ISupplierOutput {
    return {
      id: supplier.id,
      prefix: supplier.prefix,
      name: supplier.name,
      address: supplier.address,
      city: supplier.city,
      province: supplier.province,
      phoneNumber: supplier.phoneNumber,
      email: supplier.email,
      npwp: supplier.npwp,
      itemsSold: supplier.itemsSold,
      serviceArea: supplier.serviceArea,
      isBlackListed: supplier.isBlackListed ?? false,
      createdAt: supplier.createdAt,
      updatedAt: supplier.updatedAt ?? null,
      createdBy,
      updatedBy,
    }
  }

  static toView(supplier: any): ISupplierView {
    return {
      id: supplier.id,
      prefix: supplier.prefix,
      name: supplier.name,
      city: supplier.city,
      province: supplier.province,
      phoneNumber: supplier.phoneNumber,
      itemsSold: supplier.itemsSold,
      isBlackListed: supplier.isBlackListed ?? false,
    }
  }

  static createPayload(data: ISupplierCreate) {
    return {
      ...data,
      prefix: data.prefix ?? "",
      isBlackListed: data.isBlackListed ?? false,
    }
  }

  static updatePayload(data: ISupplierUpdate) {
    return {
      ...data,
    }
  }
}
