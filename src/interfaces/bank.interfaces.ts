import type { IUserView } from "./user.interfaces"

export interface IBankCreate {
  bankName: string
  bankAccountName: string
  bankAccountNumber: string
}

export interface IBankUpdate {
  bankName?: string
  bankAccountName?: string
  bankAccountNumber?: string
}

export interface IBankOutput {
  id: number
  bankName: string
  bankAccountName: string
  bankAccountNumber: string
  createdAt: Date
  updatedAt: Date | null
  createdBy: IUserView
  updatedBy: IUserView | null
}

export interface IBankView {
  id: number
  bankName: string
  bankAccountName: string
  bankAccountNumber: string
}
