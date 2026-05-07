import { Elysia, t } from "elysia"
import { AuthController } from "../controllers/auth"
import { createAccessToken, decodeToken } from "../utils/auth"
import { logError } from "../utils/logger"

const TWELVE_HOURS = 12 * 60 * 60
const SEVEN_DAYS = 7 * 24 * 60 * 60

export const authRoutes = new Elysia({ prefix: "/auth" })
  .post(
    "/",
    async ({ body, set }) => {
      const result = await AuthController.login(body.email, body.password)

      if ("error" in result) {
        set.status = result.status as number
        return { detail: result.error }
      }

      const now = Math.floor(Date.now() / 1000)
      const accessToken = createAccessToken({ user_id: result.id, name: result.name, iat: now }, TWELVE_HOURS)
      const refreshToken = createAccessToken({ user_id: result.id, iat: now }, SEVEN_DAYS)

      return {
        access_token: accessToken,
        refresh_token: refreshToken,
        token_type: "bearer",
        user: {
          name: result.name,
          email: result.email,
          authenticationLevel: result.authenticationLevel,
        },
      }
    },
    {
      body: t.Object({ email: t.String(), password: t.String() }),
    }
  )
  .post(
    "/refresh",
    ({ headers, set }) => {
      const authHeader = headers["x-refresh-token"]
      if (!authHeader) {
        set.status = 401
        return { detail: "Refresh token not provided" }
      }

      const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : authHeader
      const payload = decodeToken(token)

      if (!payload) {
        set.status = 401
        return { detail: "Invalid refresh token" }
      }

      const now = Math.floor(Date.now() / 1000)
      const newToken = createAccessToken({ user_id: payload.user_id, iat: now }, TWELVE_HOURS)

      return { access_token: newToken, token_type: "bearer" }
    }
  )
