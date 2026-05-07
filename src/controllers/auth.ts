import { UserRepository } from "../repository/user"
import { verifyPassword } from "../utils/auth"
import { logError, logInfo } from "../utils/logger"

export class AuthController {
  static async login(email: string, password: string) {
    try {
      const user = await UserRepository.getByEmail(email)

      if (!user || !user.password) {
        logInfo("Login failed - user not found")
        return { error: "Email or password is incorrect", status: 401 }
      }

      const valid = await verifyPassword(password, user.password)
      if (!valid) {
        logInfo("Login failed - invalid password")
        return { error: "Email or password is incorrect", status: 401 }
      }

      logInfo(`Login successful for user ID: ${user.id}`)
      return user
    } catch (e) {
      logError(`Login error: ${e}`)
      return { error: "Internal server error", status: 500 }
    }
  }
}
