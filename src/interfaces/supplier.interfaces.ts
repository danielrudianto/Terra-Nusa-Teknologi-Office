import type { IUserView } from "./user.interfaces"

export interface ISupplierCreate {
  prefix?: string
  name: string
  address: string
  city: string
  province: string
  phoneNumber: string
  email?: string
  npwp?: string
  itemsSold: string
  serviceArea: string
  isBlackListed?: boolean
}

export interface ISupplierUpdate {
  prefix?: string
  name?: string
  address?: string
  city?: string
  province?: string
  phoneNumber?: string
  email?: string
  npwp?: string
  itemsSold?: string
  serviceArea?: string
  isBlackListed?: boolean
}

export interface ISupplierOutput {
  id: number
  prefix: string
  name: string
  address: string
  city: string
  province: string
  phoneNumber: string
  email?: string | null
  npwp?: string | null
  itemsSold: string
  serviceArea: string
  isBlackListed?: boolean
  createdAt: Date
  updatedAt: Date | null
  createdBy: IUserView
  updatedBy: IUserView | null
}

export interface ISupplierView {
  id: number
  prefix: string
  name: string
  city: string
  province: string
  phoneNumber: string
  itemsSold: string
  isBlackListed?: boolean
}
