import Redis from "ioredis"
import { prisma } from "./database"
import { logError } from "./logger"

export const redis = new Redis({ host: "localhost", port: 6379, enableOfflineQueue: false })

redis.on("error", () => {
  // suppress unhandled error events — errors are logged in syncRedis
})

export async function syncRedis() {
  try {
    await redis.del("bank_account")

    const banks = await prisma.bankAccount.findMany({
      where: { isDelete: false },
      select: { id: true, bankName: true, bankAccountName: true, bankAccountNumber: true },
    })

    if (!banks.length) return { message: "No bank accounts to synchronize." }

    await redis.rpush("bank_account", ...banks.map(b => JSON.stringify(b)))

    return { message: "Redis synchronized with bank accounts." }
  } catch (e) {
    logError(`Redis sync error: ${e}`)
    return { error: String(e) }
  }
}
