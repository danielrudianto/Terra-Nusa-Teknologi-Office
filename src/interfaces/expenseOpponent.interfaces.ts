import type { IUserView } from "./user.interfaces"

export interface IExpenseOpponentCreate {
  name: string
  type: string
  description?: string
  paymentNumber?: string
  npwp?: string
}

export interface IExpenseOpponentUpdate {
  name?: string
  type?: string
  description?: string
  paymentNumber?: string
  npwp?: string
}

export interface IExpenseOpponentOutput {
  id: number
  name: string
  type: string
  description?: string | null
  paymentNumber?: string | null
  npwp?: string | null
  createdAt: Date
  updatedAt: Date | null
  createdBy: IUserView
  updatedBy: IUserView | null
}

export interface IExpenseOpponentView {
  id: number
  name: string
  type: string
  paymentNumber?: string | null
  npwp?: string | null
}
