import type { IBankCreate, IBankOutput, IBankUpdate, IBankView } from "../interfaces/bank.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

export class BankModel {
  static toOutput(bank: any, createdBy: IUserView, updatedBy: IUserView | null): IBankOutput {
    return {
      id: bank.id,
      bankName: bank.bankName,
      bankAccountName: bank.bankAccountName,
      bankAccountNumber: bank.bankAccountNumber,
      createdAt: bank.createdAt,
      updatedAt: bank.updatedAt ?? null,
      createdBy,
      updatedBy,
    }
  }

  static toView(bank: any): IBankView {
    return {
      id: bank.id,
      bankName: bank.bankName,
      bankAccountName: bank.bankAccountName,
      bankAccountNumber: bank.bankAccountNumber,
    }
  }

  static createPayload(data: IBankCreate) {
    return {
      ...data,
    }
  }

  static updatePayload(data: IBankUpdate) {
    return {
      ...data,
    }
  }
}
