export type AuthenticatedUser = { id: number }

export function requireUser(user: unknown, set: { status?: number | string }) {
  if (!user || typeof (user as AuthenticatedUser).id !== "number") {
    set.status = 401
    return null
  }
  return user as AuthenticatedUser
}
