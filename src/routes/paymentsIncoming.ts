import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { logError } from "../utils/logger"

const PaymentIncomingBody = t.Object({
  date: t.String(),
  amount: t.Number(),
  salesInvoiceID: t.Optional(t.Number()),
  incomeID: t.Optional(t.Number()),
  loanID: t.Optional(t.Number()),
  bankAccountID: t.Optional(t.Number()),
})

export const paymentIncomingRoutes = new Elysia({ prefix: "/incoming-payments" })
  .use(guard)
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      return prisma.paymentIncoming.create({
        data: { ...b, date: new Date(b.date as string), isDelete: 0, isApprove: 0, createdBy: user.id, createdAt: new Date() } as never,
      })
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create incoming payment" } }
  }, { body: PaymentIncomingBody })
