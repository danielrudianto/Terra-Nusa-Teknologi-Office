import type { IExpenseOpponentCreate, IExpenseOpponentOutput, IExpenseOpponentUpdate, IExpenseOpponentView } from "../interfaces/expenseOpponent.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

export class ExpenseOpponentModel {
  static toOutput(record: any, createdBy: IUserView, updatedBy: IUserView | null): IExpenseOpponentOutput {
    return {
      id: record.id,
      name: record.name,
      type: record.type,
      description: record.description ?? null,
      paymentNumber: record.paymentNumber ?? null,
      npwp: record.npwp ?? null,
      createdAt: record.createdAt,
      updatedAt: record.updatedAt ?? null,
      createdBy,
      updatedBy,
    }
  }

  static toView(record: any): IExpenseOpponentView {
    return {
      id: record.id,
      name: record.name,
      type: record.type,
      paymentNumber: record.paymentNumber ?? null,
      npwp: record.npwp ?? null,
    }
  }

  static createPayload(data: IExpenseOpponentCreate) {
    return {
      ...data,
    }
  }

  static updatePayload(data: IExpenseOpponentUpdate) {
    return {
      ...data,
    }
  }
}
