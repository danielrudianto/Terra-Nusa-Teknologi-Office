export interface IAuthLoginBody {
  email: string
  password: string
}

export interface IAuthUser {
  id: number
  name: string
  email?: string
  authenticationLevel?: number
}

export interface IAuthTokens {
  access_token: string
  refresh_token: string
  token_type: "bearer"
  user: IAuthUser
}
