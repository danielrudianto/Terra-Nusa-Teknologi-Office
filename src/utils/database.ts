import { PrismaClient } from "@prisma/client"
import { logWarning, logError } from "./logger"

export const prisma = new PrismaClient({
  log: [
    { level: "warn",  emit: "event" },
    { level: "error", emit: "event" },
    { level: "query", emit: "event" },
  ],
})

prisma.$on("query", (e) => {
  if (e.duration > 300) logWarning(`Slow query (${e.duration}ms): ${e.query}`)
})

prisma.$on("error", (e) => {
  logError(`Prisma error: ${e.message}`)
})
