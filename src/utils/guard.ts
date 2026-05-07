import { Elysia } from "elysia"
import { decodeToken } from "./auth"
import { UserRepository } from "../repository/user"

// In-memory user cache — avoids a DB round-trip on every protected request.
// TTL is short so revoked/deactivated accounts are noticed quickly.
const USER_CACHE_TTL_MS = 2 * 60 * 1000
const userCache = new Map<number, { user: Awaited<ReturnType<typeof UserRepository.getById>>; expiresAt: number }>()

function getCached(id: number) {
  const entry = userCache.get(id)
  if (!entry) return null
  if (entry.expiresAt < Date.now()) { userCache.delete(id); return null }
  return entry.user
}

function setCache(id: number, user: Awaited<ReturnType<typeof UserRepository.getById>>) {
  userCache.set(id, { user, expiresAt: Date.now() + USER_CACHE_TTL_MS })
}

export function invalidateUserCache(id: number) {
  userCache.delete(id)
}

export const guard = new Elysia({ name: "guard" })
  .derive({ as: "scoped" }, async ({ headers }) => {
    const authHeader = headers.authorization
    if (!authHeader?.startsWith("Bearer ")) return { user: null }

    const payload = decodeToken(authHeader.slice(7))
    if (!payload || typeof payload.user_id !== "number") return { user: null }

    const cached = getCached(payload.user_id)
    if (cached) return { user: cached }

    const user = await UserRepository.getById(payload.user_id)
    if (user) setCache(payload.user_id, user)
    return { user: user ?? null }
  })
  // Single enforcement point — handlers never need to check user themselves
  .onBeforeHandle({ as: "scoped" }, ({ user, set }) => {
    if (!user) { set.status = 401; return { detail: "Unauthorized" } }
  })
