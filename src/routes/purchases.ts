import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { PurchaseRepository } from "../repository/purchase"
import { paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"
import { prisma } from "../utils/database"

const PurchaseBody = t.Object({
  invoiceName: t.String(),
  receiptName: t.String(),
  taxInvoiceName: t.Optional(t.String()),
  supplierID: t.Number(),
  date: t.String(),
  dueDate: t.Optional(t.String()),
  purchaseOrderName: t.String(),
  projectName: t.String(),
  purchaseType: t.String(),
  procurementType: t.Optional(t.String()),
  dpp: t.Number(),
  ppn: t.Number(),
  pbbkb: t.Number(),
  pphCode: t.Optional(t.String()),
  pphTaxObject: t.Optional(t.String()),
  pphPercentage: t.Number(),
  otherValue: t.Optional(t.Number()),
  otherValueNote: t.Optional(t.String()),
  isInvoiceAttached: t.Boolean(),
  isReceiptAttached: t.Boolean(),
  isTaxInvoiceAttached: t.Boolean(),
  isCopAttached: t.Boolean(),
  isCopyPurchaseOrderAttached: t.Boolean(),
  bankName: t.String(),
  bankAccountName: t.String(),
  bankAccountNumber: t.String(),
  paymentMethod: t.String(),
})

export const purchaseRoutes = new Elysia({ prefix: "/purchases" })
  .use(guard)
  .post("/check", async ({ body, user, set }) => {
    const b = body as any
    const existing = await PurchaseRepository.checkExists(b.invoiceName, b.purchaseOrderName)
    return { exists: !!existing, purchase: existing }
  }, { body: t.Object({ invoiceName: t.String(), purchaseOrderName: t.String() }) })
  .get("/purchase-order/:name", async ({ params, user, set }) => {
    return PurchaseRepository.getByPurchaseOrderName(params.name)
  })
  .get("/payments/:id", async ({ params, user, set }) => {
    const payments = await prisma.paymentOutgoing.findMany({ where: { purchaseID: Number(params.id), isDelete: false } })
    return { payments }
  })
  .get("/:id", async ({ params, user, set }) => {
    const purchase = await PurchaseRepository.getById(Number(params.id))
    if (!purchase) { set.status = 404; return { detail: "Purchase not found" } }
    const payments = await prisma.paymentOutgoing.findMany({ where: { purchaseID: Number(params.id), isDelete: false } })
    return { ...purchase, payments }
  })
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    const filter = {
      isDue: q.isDue === "true",
      isNotDue: q.isNotDue === "true",
      isPaid: q.isPaid === "true",
      isUnpaid: q.isUnpaid === "true",
      isDraft: q.isDraft === "true",
      isReady: q.isReady === "true",
    }
    try {
      const { data, total } = await PurchaseRepository.getAll(Number(q.page ?? 1), Number(q.pageSize ?? 10), filter, q.keyword, q.sortBy, q.sortByDirection)
      return { data, meta: paginationMeta(total, Number(q.page ?? 1), Number(q.pageSize ?? 10)) }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch purchases" } }
  })
  .post("/", async ({ body, user, set }) => {
    try {
      const b = body as Record<string, unknown>
      const purchase = await PurchaseRepository.create({
        ...b,
        date: new Date(b.date as string),
        dueDate: b.dueDate ? new Date(b.dueDate as string) : null,
        isPaid: false,
        isDelete: false,
        lastStatus: "draft",
        isInternal: 0,
        createdBy: user.id,
        createdAt: new Date(),
      })
      await PurchaseRepository.createStatus({ purchaseID: purchase.id, status: "draft", createdBy: user.id })
      return purchase
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to create purchase" } }
  }, { body: PurchaseBody })
  .put("/update-status", async ({ body, user, set }) => {
    const b = body as any
    try {
      await PurchaseRepository.update(b.purchaseID, { lastStatus: "ready", lastStatusDescription: b.description, updatedBy: user.id, updatedAt: new Date() })
      await PurchaseRepository.createStatus({ purchaseID: b.purchaseID, status: "ready", createdBy: user.id, description: b.description })
      return { message: "Status updated" }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to update status" } }
  }, { body: t.Object({ purchaseID: t.Number(), description: t.Optional(t.String()) }) })
  .delete("/:id", async ({ params, user, set }) => {
    try {
      await PurchaseRepository.softDelete(Number(params.id), user.id)
      return { message: "Purchase deleted" }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to delete purchase" } }
  })
