import { Elysia } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { logError } from "../utils/logger"

export const taxRoutes = new Elysia({ prefix: "/taxes" })
  .use(guard)
  .get("/ppn", async ({ query, user, set }) => {
    const { month, year } = query as Record<string, string>
    if (!month || !year) { set.status = 400; return { detail: "month and year are required" } }
    try {
      const start = new Date(Number(year), Number(month) - 1, 1)
      const end = new Date(Number(year), Number(month), 0)
      const purchases = await prisma.purchase.findMany({
        where: { isDelete: false, date: { gte: start, lte: end } },
        select: { id: true, invoiceName: true, supplierID: true, date: true, dpp: true, ppn: true, purchaseOrderName: true, projectName: true, paymentMethod: true },
      })
      return { data: purchases, month: Number(month), year: Number(year) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch PPN report" } }
  })
  .get("/pph", async ({ query, user, set }) => {
    const { month, year } = query as Record<string, string>
    if (!month || !year) { set.status = 400; return { detail: "month and year are required" } }
    try {
      const start = new Date(Number(year), Number(month) - 1, 1)
      const end = new Date(Number(year), Number(month), 0)
      const [purchases, expenses] = await Promise.all([
        prisma.purchase.findMany({
          where: { isDelete: false, date: { gte: start, lte: end }, NOT: { pphCode: null } },
          select: { id: true, invoiceName: true, date: true, dpp: true, pphCode: true, pphTaxObject: true, pphPercentage: true, supplierID: true },
        }),
        prisma.expense.findMany({
          where: { isDelete: false, date: { gte: start, lte: end }, NOT: { pphCode: null } },
          select: { id: true, invoiceName: true, date: true, dpp: true, pphCode: true, pphTaxObject: true, pphPercentage: true },
        }),
      ])
      return { purchases, expenses, month: Number(month), year: Number(year) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch PPH report" } }
  })
  .get("/pph-salary", async ({ query, user, set }) => {
    const { month, year } = query as Record<string, string>
    if (!month || !year) { set.status = 400; return { detail: "month and year are required" } }
    try {
      const slips = await prisma.salarySlip.findMany({
        where: { isDelete: false, month: Number(month), year: Number(year) },
        select: { id: true, userID: true, month: true, year: true, basicSalary: true, taxAmount: true, taxCategory: true, position: true, department: true },
      })
      return { data: slips, month: Number(month), year: Number(year) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch PPH salary report" } }
  })
