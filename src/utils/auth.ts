import bcrypt from "bcryptjs"
import jwt from "jsonwebtoken"

const SECRET_KEY = process.env.SECRET_KEY!
const ALGORITHM = (process.env.ALGORITHM ?? "HS256") as jwt.Algorithm

export function verifyPassword(plain: string, hashed: string): Promise<boolean> {
  return bcrypt.compare(plain, hashed)
}

export function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, 10)
}

export function createAccessToken(payload: Record<string, unknown>, expiresInSeconds?: number): string {
  const exp = Math.floor(Date.now() / 1000) + (expiresInSeconds ?? ACCESS_TOKEN_EXPIRE_MINUTES * 60)
  return jwt.sign({ ...payload, exp }, SECRET_KEY, { algorithm: ALGORITHM })
}

export function decodeToken(token: string): Record<string, unknown> | null {
  try {
    return jwt.verify(token, SECRET_KEY, { algorithms: [ALGORITHM] }) as Record<string, unknown>
  } catch {
    return null
  }
}
