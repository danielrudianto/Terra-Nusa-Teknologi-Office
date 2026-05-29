import type { IClientCreate, IClientOutput, IClientUpdate, IClientView } from "../interfaces/client.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

export class ClientModel {
  static toOutput(client: any, createdBy: IUserView, updatedBy: IUserView | null): IClientOutput {
    return {
      id: client.id,
      prefix: client.prefix,
      name: client.name,
      address: client.address,
      city: client.city,
      province: client.province,
      phoneNumber: client.phoneNumber,
      email: client.email,
      npwp: client.npwp,
      createdAt: client.createdAt,
      updatedAt: client.updatedAt ?? null,
      createdBy,
      updatedBy,
    }
  }

  static toView(client: any): IClientView {
    return {
      id: client.id,
      prefix: client.prefix,
      name: client.name,
      city: client.city,
      province: client.province,
      phoneNumber: client.phoneNumber,
    }
  }

  static createPayload(data: IClientCreate) {
    return {
      ...data,
      prefix: data.prefix ?? "",
    }
  }

  static updatePayload(data: IClientUpdate) {
    return {
      ...data,
    }
  }
}
