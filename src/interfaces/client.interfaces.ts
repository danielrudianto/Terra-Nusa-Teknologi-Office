import type { IUserView } from "./user.interfaces"

export interface IClientCreate {
  prefix?: string
  name: string
  address: string
  city: string
  province: string
  phoneNumber: string
  email?: string
  npwp?: string
}

export interface IClientUpdate {
  prefix?: string
  name?: string
  address?: string
  city?: string
  province?: string
  phoneNumber?: string
  email?: string
  npwp?: string
}

export interface IClientOutput {
  id: number
  prefix: string
  name: string
  address: string
  city: string
  province: string
  phoneNumber: string
  email?: string | null
  npwp?: string | null
  createdAt: Date
  updatedAt: Date | null
  createdBy: IUserView
  updatedBy: IUserView | null
}

export interface IClientView {
  id: number
  prefix: string
  name: string
  city: string
  province: string
  phoneNumber: string
}
