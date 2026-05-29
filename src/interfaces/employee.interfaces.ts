import type { IUserView } from "./user.interfaces"

export interface IEmployeeCreate {
  name: string
  nik: string
  birthday: string
  email: string
  phoneNumber: string
  address: string
  position: string
  department: string
  taxCategory: string
  startDate?: string
  endDate?: string
}

export interface IEmployeeUpdate {
  name?: string
  nik?: string
  birthday?: string
  email?: string
  phoneNumber?: string
  address?: string
  position?: string
  department?: string
  taxCategory?: string
  startDate?: string
  endDate?: string
}

export interface IEmployeeOutput {
  id: number
  name: string
  nik: string
  birthday: string
  email: string
  phoneNumber: string
  address: string
  position: string
  department: string
  taxCategory: string
  startDate?: string | null
  endDate?: string | null
  createdAt: Date
  updatedAt: Date | null
  createdBy: IUserView
  updatedBy: IUserView | null
}

export interface IEmployeeView {
  id: number
  name: string
  nik: string
  email: string
  phoneNumber: string
  position: string
  department: string
  taxCategory: string
}
