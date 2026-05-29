export interface IUserView {
  id: number
  name: string
}

export interface IUserModel {
  id: number
  name: string
  email?: string
  authenticationLevel?: number
  createdAt?: Date
  updatedAt?: Date
}
