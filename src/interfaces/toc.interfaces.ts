export interface ITocCreate {
  name: string
  purchaseType: string
  description?: string
  content: string
}

export interface ITocOutput {
  id: number
  name: string
  purchaseType: string
  revision: number
  description?: string | null
  content: string
  createdAt: Date
  updatedAt: Date | null
}
