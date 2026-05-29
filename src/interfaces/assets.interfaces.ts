import type { IUserView } from "./user.interfaces"

export interface IAssetCreate {
  name: string
  description: string
  brand: string
  type: string
  depreciation: number
  location: string
  purchaseOrderName: string
  purchaseDate: string | Date
  value: number
  soldValue?: number
  soldDate?: string
}

export interface IAssetUpdate {
  name?: string
  description?: string
  brand?: string
  type?: string
  depreciation?: number
  location?: string
  purchaseOrderName?: string
  purchaseDate?: string | Date
  value?: number
  soldValue?: number
  soldDate?: string
}

export interface IAssetOutput {
  id: number
  name: string
  description: string
  brand: string
  type: string
  depreciation: number
  location: string
  purchaseOrderName: string
  purchaseDate: string
  value: number
  soldValue?: number
  soldDate?: string
  createdAt: Date
  updatedAt: Date | null
  createdBy: IUserView
  updatedBy: IUserView | null
}

export interface IAssetView {
  id: number
  name: string
  description: string
  brand: string
  type: string
  location: string
  value: number
}
