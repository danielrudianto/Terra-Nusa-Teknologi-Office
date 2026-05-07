import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { paginationMeta, paginationParams } from "../utils/pagination"
import { logError } from "../utils/logger"

const SalarySlipBody = t.Object({
  userID: t.Number(),
  month: t.Number(),
  year: t.Number(),
  basicSalary: t.Number(),
  transportationAllowanceQuantity: t.Optional(t.Number()),
  transportationAllowanceRate: t.Optional(t.Number()),
  mealAllowanceQuantity: t.Optional(t.Number()),
  mealAllowanceRate: t.Optional(t.Number()),
  overtimeQuantity: t.Optional(t.Number()),
  overtimeRate: t.Optional(t.Number()),
  taxAmount: t.Optional(t.Number()),
  taxCategory: t.String(),
  position: t.String(),
  department: t.String(),
  bankName: t.Optional(t.String()),
  bankAccountName: t.Optional(t.String()),
  bankAccountNumber: t.Optional(t.String()),
  paymentMethod: t.Optional(t.String()),
  allowances: t.Optional(t.Array(t.Object({ name: t.String(), description: t.String(), amount: t.Number(), isIncluded: t.Optional(t.Boolean()) }))),
  deductions: t.Optional(t.Array(t.Object({ name: t.String(), description: t.String(), amount: t.Number(), isIncluded: t.Optional(t.Boolean()) }))),
})

export const salarySlipRoutes = new Elysia({ prefix: "/salary-slips" })
  .use(guard)
  .post("/check", async ({ body, user, set }) => {
    const { userID, month, year } = body as any
    const existing = await prisma.salarySlip.findFirst({ where: { userID, month, year, isDelete: false } })
    return { exists: !!existing, salarySlip: existing }
  }, { body: t.Object({ userID: t.Number(), month: t.Number(), year: t.Number() }) })
  .get("/:id", async ({ params, user, set }) => {
    const slip = await prisma.salarySlip.findFirst({ where: { id: Number(params.id), isDelete: false } })
    if (!slip) { set.status = 404; return { detail: "Not found" } }
    const [allowances, deductions, payments] = await Promise.all([
      prisma.salarySlipAllowance.findMany({ where: { salarySlipID: slip.id } }),
      prisma.salarySlipDeduction.findMany({ where: { salarySlipID: slip.id } }),
      prisma.paymentOutgoing.findMany({ where: { salarySlipID: slip.id, isDelete: false } }),
    ])
    return { ...slip, allowances, deductions, payments }
  })
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const where: Record<string, unknown> = { isDelete: false }
    if (q.keyword) where.OR = [{ taxCategory: { contains: q.keyword } }, { position: { contains: q.keyword } }, { department: { contains: q.keyword } }]
    if (q.month) where.month = Number(q.month)
    if (q.year) where.year = Number(q.year)

    const page = Number(q.page ?? 1)
    const pageSize = Number(q.pageSize ?? 10)
    const { skip, take } = paginationParams(page, pageSize)
    try {
      const [data, total] = await Promise.all([
        prisma.salarySlip.findMany({ where: where as never, orderBy: { createdAt: "desc" }, skip, take }),
        prisma.salarySlip.count({ where: where as never }),
      ])
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const { allowances, deductions, ...rest } = body as any
      const slip = await prisma.salarySlip.create({
        data: { ...rest, isPaid: false, isDelete: false, createdBy: user.id, createdAt: new Date() } as never,
      })
      if (allowances?.length) {
        await prisma.salarySlipAllowance.createMany({ data: allowances.map((a: any) => ({ ...a, salarySlipID: slip.id, isIncluded: a.isIncluded ? 1 : 0 })) })
      }
      if (deductions?.length) {
        await prisma.salarySlipDeduction.createMany({ data: deductions.map((d: any) => ({ ...d, salarySlipID: slip.id, isIncluded: d.isIncluded ?? 1 })) })
      }
      // Update employee tax category / position / department
      await prisma.employee.updateMany({ where: { id: rest.userID }, data: { taxCategory: rest.taxCategory, position: rest.position, department: rest.department } }).catch(() => {})
      return slip
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create salary slip" } }
  }, { body: SalarySlipBody })
  .delete("/:id", async ({ params, user, set }) => {
    await prisma.salarySlip.update({ where: { id: Number(params.id) }, data: { isDelete: true, deletedBy: user.id, deletedAt: new Date() } })
    return { message: "Salary slip deleted" }
  })
