import { Elysia } from "elysia"
import { cors } from "@elysiajs/cors"
import { validateEnv } from "./utils/env"
import { prisma } from "./utils/database"
import { setupMeilisearch, syncMeilisearch } from "./utils/meilisearch"
import { syncRedis } from "./utils/redis"
import { logInfo, logError, logWarning } from "./utils/logger"
import { authRoutes } from "./routes/auth"
import { clientRoutes } from "./routes/clients"
import { supplierRoutes } from "./routes/suppliers"
import { employeeRoutes } from "./routes/employees"
import { bankRoutes } from "./routes/banks"
import { assetRoutes } from "./routes/assets"
import { expenseOpponentRoutes } from "./routes/expenseOpponents"
import { incomeRoutes } from "./routes/income"
import { loanRoutes } from "./routes/loans"
import { interpaymentRoutes } from "./routes/interpayments"
import { purchaseRoutes } from "./routes/purchases"
import { purchaseOrderRoutes } from "./routes/purchaseOrders"
import { purchaseDraftRoutes } from "./routes/purchaseDrafts"
import { expenseRoutes } from "./routes/expenses"
import { reimbursementRoutes } from "./routes/reimbursements"
import { salesInvoiceRoutes } from "./routes/salesInvoices"
import { paymentOutgoingRoutes } from "./routes/paymentsOutgoing"
import { paymentIncomingRoutes } from "./routes/paymentsIncoming"
import { salarySlipRoutes } from "./routes/salarySlips"
import { taxRoutes } from "./routes/taxes"
import { calendarRoutes } from "./routes/calendar"
import { attendanceRoutes } from "./routes/attendance"

validateEnv()

const startedAt = new Date().toISOString()

const app = new Elysia()
  .use(cors({ origin: "*", allowedHeaders: "*", methods: "*" }))

  // Request logger — logs every request with method, path, status, and duration
  .derive(() => ({ _t: Date.now() }))
  .onAfterHandle({ as: "global" }, ({ request, set, _t }) => {
    const ms = Date.now() - _t
    const path = new URL(request.url).pathname
    const status = set.status ?? 200
    const level = Number(status) >= 500 ? logError : Number(status) >= 400 ? logWarning : logInfo
    level(`${request.method} ${path} ${status} ${ms}ms`)
  })

  .on("start", async () => {
    try {
      await prisma.$connect()
      logInfo("Database connected successfully!")
    } catch (e) {
      logError(`Error connecting to database: ${e}`)
    }

    try {
      await setupMeilisearch()
      await syncMeilisearch()
      logInfo("Meilisearch setup completed successfully!")
    } catch (e) {
      logError(`Error connecting to meilisearch: ${e}`)
    }

    try {
      await syncRedis()
      logInfo("Redis setup completed successfully!")
    } catch (e) {
      logError(`Error connecting to redis: ${e}`)
    }
  })
  .on("stop", async () => {
    await prisma.$disconnect()
    logInfo("Database disconnected!")
  })

  .get("/", () => ({ message: "Terra Nusa Teknologi Office API" }))
  .get("/health", () => ({
    status: "ok",
    uptime: Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000),
    startedAt,
  }))

  .use(authRoutes)
  .use(clientRoutes)
  .use(supplierRoutes)
  .use(employeeRoutes)
  .use(bankRoutes)
  .use(assetRoutes)
  .use(expenseOpponentRoutes)
  .use(incomeRoutes)
  .use(loanRoutes)
  .use(interpaymentRoutes)
  .use(purchaseRoutes)
  .use(purchaseOrderRoutes)
  .use(purchaseDraftRoutes)
  .use(expenseRoutes)
  .use(reimbursementRoutes)
  .use(salesInvoiceRoutes)
  .use(paymentOutgoingRoutes)
  .use(paymentIncomingRoutes)
  .use(salarySlipRoutes)
  .use(taxRoutes)
  .use(calendarRoutes)
  .use(attendanceRoutes)
  .listen(7500)

logInfo(`Server running at http://0.0.0.0:7500`)

export type App = typeof app
