import { Elysia } from "elysia"
import { guard } from "../utils/guard"
import { prisma } from "../utils/database"
import { Prisma } from "@prisma/client"
import { logError } from "../utils/logger"

function parseAccounts(raw: string | undefined): number[] {
  if (!raw) return []
  return String(raw).split(",").map(Number).filter(n => !isNaN(n) && n > 0)
}

export const calendarRoutes = new Elysia({ prefix: "/calendar" })
  .use(guard)
  .get("/", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    if (!q.month || !q.year) { set.status = 400; return { detail: "month and year are required" } }
    const m = Number(q.month)
    const y = Number(q.year)
    const bankAccounts = parseAccounts(q.bankAccounts)

    try {
      const start = new Date(y, m - 1, 1)
      const end = new Date(y, m, 0)

      // Outgoing payments: sum per day
      const paymentGroups = await prisma.paymentOutgoing.groupBy({
        by: ["date"],
        where: {
          isDelete: false,
          date: { gte: start, lte: end },
          ...(bankAccounts.length > 0 && { bankAccountID: { in: bankAccounts } }),
        },
        _sum: { amount: true },
        orderBy: { date: "asc" },
      })
      const payments = paymentGroups.map(p => ({ date: p.date, amount: p._sum.amount }))

      // Interpayments with origin/destination bank info
      const interpayments: any[] = bankAccounts.length > 0
        ? await prisma.$queryRaw`
            SELECT i.*, ob.bankName as originBankName, ob.bankAccountName as originBankAccountName,
              ob.bankAccountNumber as originBankAccountNumber, db.bankName as destinationBankName,
              db.bankAccountName as destinationBankAccountName, db.bankAccountNumber as destinationBankAccountNumber
            FROM interpayments i
            LEFT JOIN bank_accounts ob ON i.bankAccountIDOrigin = ob.id
            LEFT JOIN bank_accounts db ON i.bankAccountIDDestination = db.id
            WHERE i.isDelete = 0 AND MONTH(i.date) = ${m} AND YEAR(i.date) = ${y}
              AND (i.bankAccountIDOrigin IN (${Prisma.join(bankAccounts)}) OR i.bankAccountIDDestination IN (${Prisma.join(bankAccounts)}))`
        : await prisma.$queryRaw`
            SELECT i.*, ob.bankName as originBankName, ob.bankAccountName as originBankAccountName,
              ob.bankAccountNumber as originBankAccountNumber, db.bankName as destinationBankName,
              db.bankAccountName as destinationBankAccountName, db.bankAccountNumber as destinationBankAccountNumber
            FROM interpayments i
            LEFT JOIN bank_accounts ob ON i.bankAccountIDOrigin = ob.id
            LEFT JOIN bank_accounts db ON i.bankAccountIDDestination = db.id
            WHERE i.isDelete = 0 AND MONTH(i.date) = ${m} AND YEAR(i.date) = ${y}`

      // Incoming payments with client/opponent/loan name and document info
      const incomes: any[] = bankAccounts.length > 0
        ? await prisma.$queryRaw`
            SELECT pi.id, pi.amount, pi.bankAccountID, pi.date, pi.salesInvoiceID, pi.incomeID, pi.loanID,
              COALESCE(c.name, eo.name, l.creditorName) as name,
              COALESCE(si.name, inc.description, l.description) as document_name,
              COALESCE(si.date, inc.date, l.date) as document_date
            FROM payment_incoming pi
            LEFT JOIN sales_invoices si ON pi.salesInvoiceID = si.id
            LEFT JOIN clients c ON si.clientID = c.id
            LEFT JOIN income inc ON pi.incomeID = inc.id
            LEFT JOIN expense_opponents eo ON inc.opponentID = eo.id
            LEFT JOIN loans l ON pi.loanID = l.id
            WHERE pi.isDelete = 0 AND MONTH(pi.date) = ${m} AND YEAR(pi.date) = ${y}
              AND pi.bankAccountID IN (${Prisma.join(bankAccounts)})`
        : await prisma.$queryRaw`
            SELECT pi.id, pi.amount, pi.bankAccountID, pi.date, pi.salesInvoiceID, pi.incomeID, pi.loanID,
              COALESCE(c.name, eo.name, l.creditorName) as name,
              COALESCE(si.name, inc.description, l.description) as document_name,
              COALESCE(si.date, inc.date, l.date) as document_date
            FROM payment_incoming pi
            LEFT JOIN sales_invoices si ON pi.salesInvoiceID = si.id
            LEFT JOIN clients c ON si.clientID = c.id
            LEFT JOIN income inc ON pi.incomeID = inc.id
            LEFT JOIN expense_opponents eo ON inc.opponentID = eo.id
            LEFT JOIN loans l ON pi.loanID = l.id
            WHERE pi.isDelete = 0 AND MONTH(pi.date) = ${m} AND YEAR(pi.date) = ${y}`

      // Opening balance from mutation view (last balance per account before start of month)
      let balances: any[] = []
      try {
        balances = bankAccounts.length > 0
          ? await prisma.$queryRaw`
              SELECT m.bankaccountid, m.balance FROM mutation m
              INNER JOIN (
                SELECT bankaccountid,
                  MAX(CONCAT(DATE_FORMAT(date,'%Y-%m-%d'),'-',LPAD(sortorder,2,'0'),'-',LPAD(tiebreaker,10,'0'))) AS max_key
                FROM mutation WHERE date < ${start} AND bankaccountid IN (${Prisma.join(bankAccounts)})
                GROUP BY bankaccountid
              ) last_row ON m.bankaccountid = last_row.bankaccountid
              AND CONCAT(DATE_FORMAT(m.date,'%Y-%m-%d'),'-',LPAD(m.sortorder,2,'0'),'-',LPAD(m.tiebreaker,10,'0')) = last_row.max_key`
          : await prisma.$queryRaw`
              SELECT m.bankaccountid, m.balance FROM mutation m
              INNER JOIN (
                SELECT bankaccountid,
                  MAX(CONCAT(DATE_FORMAT(date,'%Y-%m-%d'),'-',LPAD(sortorder,2,'0'),'-',LPAD(tiebreaker,10,'0'))) AS max_key
                FROM mutation WHERE date < ${start}
                GROUP BY bankaccountid
              ) last_row ON m.bankaccountid = last_row.bankaccountid
              AND CONCAT(DATE_FORMAT(m.date,'%Y-%m-%d'),'-',LPAD(m.sortorder,2,'0'),'-',LPAD(m.tiebreaker,10,'0')) = last_row.max_key`
      } catch (e) {
        logError(`Balance query failed (mutation view may not exist): ${e}`)
      }
      const totalBalance = (balances as any[]).reduce((sum, r) => sum + Number(r.balance ?? 0), 0)

      return { payments, incomes, interpayments, balances: totalBalance, month: m, year: y }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch calendar data" } }
  })

  .get("/daily", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    if (!q.date) { set.status = 400; return { detail: "date is required (YYYY-MM-DD)" } }
    const dt = new Date(q.date)
    const day = dt.getDate()
    const month = dt.getMonth() + 1
    const year = dt.getFullYear()
    const bankAccounts = parseAccounts(q.bankAccounts)

    try {
      const rawPayments: any[] = bankAccounts.length > 0
        ? await prisma.$queryRaw`
            SELECT po.*,
              pu.invoiceName as purchase_invoiceName, pu.date as purchase_date,
              pu.projectName as purchase_project_name, pu.purchaseOrderName as purchase_purchase_order_name,
              r.name as reimbursement_name, r.date as reimbursement_date,
              r.projectName as reimbursement_project_name, r.bankAccountName as reimbursement_account_name,
              e.invoiceName as expense_invoiceName, e.date as expense_date, e.description as expense_description,
              s.name as purchase_account_name, eo.name as expense_account_name,
              ss.month as salary_slip_month, ss.year as salary_slips_year, emp.name as salary_slip_name,
              l.creditorName as loan_creditor_name, l.description as loan_description
            FROM payment_outgoing po
            LEFT JOIN purchases pu ON po.purchaseID = pu.id
            LEFT JOIN suppliers s ON pu.supplierID = s.id
            LEFT JOIN reimbursements r ON po.reimbursementID = r.id
            LEFT JOIN expenses e ON po.expenseID = e.id
            LEFT JOIN expense_opponents eo ON e.opponentID = eo.id
            LEFT JOIN salary_slips ss ON po.salarySlipID = ss.id
            LEFT JOIN employees emp ON ss.userID = emp.id
            LEFT JOIN loans l ON po.loanID = l.id
            WHERE DAY(po.date) = ${day} AND MONTH(po.date) = ${month} AND YEAR(po.date) = ${year}
              AND po.isDelete = 0 AND po.bankAccountID IN (${Prisma.join(bankAccounts)})`
        : await prisma.$queryRaw`
            SELECT po.*,
              pu.invoiceName as purchase_invoiceName, pu.date as purchase_date,
              pu.projectName as purchase_project_name, pu.purchaseOrderName as purchase_purchase_order_name,
              r.name as reimbursement_name, r.date as reimbursement_date,
              r.projectName as reimbursement_project_name, r.bankAccountName as reimbursement_account_name,
              e.invoiceName as expense_invoiceName, e.date as expense_date, e.description as expense_description,
              s.name as purchase_account_name, eo.name as expense_account_name,
              ss.month as salary_slip_month, ss.year as salary_slips_year, emp.name as salary_slip_name,
              l.creditorName as loan_creditor_name, l.description as loan_description
            FROM payment_outgoing po
            LEFT JOIN purchases pu ON po.purchaseID = pu.id
            LEFT JOIN suppliers s ON pu.supplierID = s.id
            LEFT JOIN reimbursements r ON po.reimbursementID = r.id
            LEFT JOIN expenses e ON po.expenseID = e.id
            LEFT JOIN expense_opponents eo ON e.opponentID = eo.id
            LEFT JOIN salary_slips ss ON po.salarySlipID = ss.id
            LEFT JOIN employees emp ON ss.userID = emp.id
            LEFT JOIN loans l ON po.loanID = l.id
            WHERE DAY(po.date) = ${day} AND MONTH(po.date) = ${month} AND YEAR(po.date) = ${year}
              AND po.isDelete = 0`

      const payments = rawPayments.map((p: any) => ({
        id: p.id, date: p.date, amount: p.amount,
        purchaseID: p.purchaseID, expenseID: p.expenseID,
        reimbursementID: p.reimbursementID, salarySlipID: p.salarySlipID,
        loanID: p.loanID, bankAccountID: p.bankAccountID,
        isApprove: p.isApprove, isDelete: p.isDelete, status: p.status,
        purchase: p.purchaseID ? {
          date: p.purchase_date, invoiceName: p.purchase_invoiceName,
          accountName: p.purchase_account_name, projectName: p.purchase_project_name,
          purchaseOrderName: p.purchase_purchase_order_name,
        } : null,
        reimbursement: p.reimbursementID ? {
          date: p.reimbursement_date, name: p.reimbursement_name,
          accountName: p.reimbursement_account_name, projectName: p.reimbursement_project_name,
        } : null,
        expense: p.expenseID ? {
          date: p.expense_date, invoiceName: p.expense_invoiceName,
          accountName: p.expense_account_name, description: p.expense_description,
        } : null,
        salarySlip: p.salarySlipID ? {
          month: p.salary_slip_month, year: p.salary_slips_year, name: p.salary_slip_name,
        } : null,
        loan: p.loanID ? { creditorName: p.loan_creditor_name, description: p.loan_description } : null,
      }))

      const interpayments: any[] = bankAccounts.length > 0
        ? await prisma.$queryRaw`
            SELECT i.*, ob.bankName as originBankName, ob.bankAccountName as originBankAccountName,
              ob.bankAccountNumber as originBankAccountNumber, db.bankName as destinationBankName,
              db.bankAccountName as destinationBankAccountName, db.bankAccountNumber as destinationBankAccountNumber
            FROM interpayments i
            LEFT JOIN bank_accounts ob ON i.bankAccountIDOrigin = ob.id
            LEFT JOIN bank_accounts db ON i.bankAccountIDDestination = db.id
            WHERE i.isDelete = 0 AND DAY(i.date) = ${day} AND MONTH(i.date) = ${month} AND YEAR(i.date) = ${year}
              AND (i.bankAccountIDOrigin IN (${Prisma.join(bankAccounts)}) OR i.bankAccountIDDestination IN (${Prisma.join(bankAccounts)}))`
        : await prisma.$queryRaw`
            SELECT i.*, ob.bankName as originBankName, ob.bankAccountName as originBankAccountName,
              ob.bankAccountNumber as originBankAccountNumber, db.bankName as destinationBankName,
              db.bankAccountName as destinationBankAccountName, db.bankAccountNumber as destinationBankAccountNumber
            FROM interpayments i
            LEFT JOIN bank_accounts ob ON i.bankAccountIDOrigin = ob.id
            LEFT JOIN bank_accounts db ON i.bankAccountIDDestination = db.id
            WHERE i.isDelete = 0 AND DAY(i.date) = ${day} AND MONTH(i.date) = ${month} AND YEAR(i.date) = ${year}`

      return { payments, interpayments }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to fetch daily calendar data" } }
  })

  .get("/download", async ({ query, user, set }) => {
    const q = query as Record<string, string>
    if (!q.month || !q.year) { set.status = 400; return { detail: "month and year are required" } }
    const m = Number(q.month)
    const y = Number(q.year)
    const bankAccounts = parseAccounts(q.bankAccounts)

    try {
      const start = new Date(y, m - 1, 1)

      const bank_accounts = bankAccounts.length > 0
        ? await prisma.bankAccount.findMany({ where: { id: { in: bankAccounts }, isDelete: false } })
        : await prisma.bankAccount.findMany({ where: { isDelete: false } })

      const payments: any[] = bankAccounts.length > 0
        ? await prisma.$queryRaw`
            SELECT po.*,
              COALESCE(pu.invoiceName, r.name, CONCAT('Salary ', emp.name, ' ', ss.month, ' ', ss.year), e.invoiceName) as documentName,
              COALESCE(s.name, r.bankAccountName, emp.name, eo.name) as opponent,
              COALESCE(pu.date, r.date, ss.createdAt, e.date) as documentDate,
              ba.bankAccountName, ba.bankAccountNumber, ba.bankName
            FROM payment_outgoing po
            LEFT JOIN purchases pu ON po.purchaseID = pu.id
            LEFT JOIN suppliers s ON pu.supplierID = s.id
            LEFT JOIN reimbursements r ON po.reimbursementID = r.id
            LEFT JOIN salary_slips ss ON po.salarySlipID = ss.id
            LEFT JOIN employees emp ON ss.userID = emp.id
            LEFT JOIN expenses e ON po.expenseID = e.id
            LEFT JOIN expense_opponents eo ON e.opponentID = eo.id
            LEFT JOIN bank_accounts ba ON po.bankAccountID = ba.id
            WHERE (po.isApprove = 1 OR (po.isApprove = 0 AND po.isDelete = 0))
              AND MONTH(po.date) = ${m} AND YEAR(po.date) = ${y}
              AND po.bankAccountID IN (${Prisma.join(bankAccounts)})`
        : await prisma.$queryRaw`
            SELECT po.*,
              COALESCE(pu.invoiceName, r.name, CONCAT('Salary ', emp.name, ' ', ss.month, ' ', ss.year), e.invoiceName) as documentName,
              COALESCE(s.name, r.bankAccountName, emp.name, eo.name) as opponent,
              COALESCE(pu.date, r.date, ss.createdAt, e.date) as documentDate,
              ba.bankAccountName, ba.bankAccountNumber, ba.bankName
            FROM payment_outgoing po
            LEFT JOIN purchases pu ON po.purchaseID = pu.id
            LEFT JOIN suppliers s ON pu.supplierID = s.id
            LEFT JOIN reimbursements r ON po.reimbursementID = r.id
            LEFT JOIN salary_slips ss ON po.salarySlipID = ss.id
            LEFT JOIN employees emp ON ss.userID = emp.id
            LEFT JOIN expenses e ON po.expenseID = e.id
            LEFT JOIN expense_opponents eo ON e.opponentID = eo.id
            LEFT JOIN bank_accounts ba ON po.bankAccountID = ba.id
            WHERE (po.isApprove = 1 OR (po.isApprove = 0 AND po.isDelete = 0))
              AND MONTH(po.date) = ${m} AND YEAR(po.date) = ${y}`

      const interpayments: any[] = bankAccounts.length > 0
        ? await prisma.$queryRaw`
            SELECT i.*, ob.bankName as originBankName, ob.bankAccountName as originBankAccountName,
              ob.bankAccountNumber as originBankAccountNumber, db.bankName as destinationBankName,
              db.bankAccountName as destinationBankAccountName, db.bankAccountNumber as destinationBankAccountNumber
            FROM interpayments i
            LEFT JOIN bank_accounts ob ON i.bankAccountIDOrigin = ob.id
            LEFT JOIN bank_accounts db ON i.bankAccountIDDestination = db.id
            WHERE i.isDelete = 0 AND MONTH(i.date) = ${m} AND YEAR(i.date) = ${y}
              AND (i.bankAccountIDOrigin IN (${Prisma.join(bankAccounts)}) OR i.bankAccountIDDestination IN (${Prisma.join(bankAccounts)}))`
        : await prisma.$queryRaw`
            SELECT i.*, ob.bankName as originBankName, ob.bankAccountName as originBankAccountName,
              ob.bankAccountNumber as originBankAccountNumber, db.bankName as destinationBankName,
              db.bankAccountName as destinationBankAccountName, db.bankAccountNumber as destinationBankAccountNumber
            FROM interpayments i
            LEFT JOIN bank_accounts ob ON i.bankAccountIDOrigin = ob.id
            LEFT JOIN bank_accounts db ON i.bankAccountIDDestination = db.id
            WHERE i.isDelete = 0 AND MONTH(i.date) = ${m} AND YEAR(i.date) = ${y}`

      const incomes: any[] = bankAccounts.length > 0
        ? await prisma.$queryRaw`
            SELECT pi.id, pi.amount, pi.bankAccountID, pi.date, pi.salesInvoiceID, pi.incomeID, pi.loanID,
              COALESCE(c.name, eo.name, l.creditorName) as name,
              COALESCE(si.name, inc.description, l.description) as document_name,
              COALESCE(si.date, inc.date, l.date) as document_date
            FROM payment_incoming pi
            LEFT JOIN sales_invoices si ON pi.salesInvoiceID = si.id
            LEFT JOIN clients c ON si.clientID = c.id
            LEFT JOIN income inc ON pi.incomeID = inc.id
            LEFT JOIN expense_opponents eo ON inc.opponentID = eo.id
            LEFT JOIN loans l ON pi.loanID = l.id
            WHERE pi.isDelete = 0 AND MONTH(pi.date) = ${m} AND YEAR(pi.date) = ${y}
              AND pi.bankAccountID IN (${Prisma.join(bankAccounts)})`
        : await prisma.$queryRaw`
            SELECT pi.id, pi.amount, pi.bankAccountID, pi.date, pi.salesInvoiceID, pi.incomeID, pi.loanID,
              COALESCE(c.name, eo.name, l.creditorName) as name,
              COALESCE(si.name, inc.description, l.description) as document_name,
              COALESCE(si.date, inc.date, l.date) as document_date
            FROM payment_incoming pi
            LEFT JOIN sales_invoices si ON pi.salesInvoiceID = si.id
            LEFT JOIN clients c ON si.clientID = c.id
            LEFT JOIN income inc ON pi.incomeID = inc.id
            LEFT JOIN expense_opponents eo ON inc.opponentID = eo.id
            LEFT JOIN loans l ON pi.loanID = l.id
            WHERE pi.isDelete = 0 AND MONTH(pi.date) = ${m} AND YEAR(pi.date) = ${y}`

      let balances: any[] = []
      try {
        balances = bankAccounts.length > 0
          ? await prisma.$queryRaw`
              SELECT m.bankaccountid, m.balance FROM mutation m
              INNER JOIN (
                SELECT bankaccountid,
                  MAX(CONCAT(DATE_FORMAT(date,'%Y-%m-%d'),'-',LPAD(sortorder,2,'0'),'-',LPAD(tiebreaker,10,'0'))) AS max_key
                FROM mutation WHERE date < ${start} AND bankaccountid IN (${Prisma.join(bankAccounts)})
                GROUP BY bankaccountid
              ) last_row ON m.bankaccountid = last_row.bankaccountid
              AND CONCAT(DATE_FORMAT(m.date,'%Y-%m-%d'),'-',LPAD(m.sortorder,2,'0'),'-',LPAD(m.tiebreaker,10,'0')) = last_row.max_key`
          : await prisma.$queryRaw`
              SELECT m.bankaccountid, m.balance FROM mutation m
              INNER JOIN (
                SELECT bankaccountid,
                  MAX(CONCAT(DATE_FORMAT(date,'%Y-%m-%d'),'-',LPAD(sortorder,2,'0'),'-',LPAD(tiebreaker,10,'0'))) AS max_key
                FROM mutation WHERE date < ${start}
                GROUP BY bankaccountid
              ) last_row ON m.bankaccountid = last_row.bankaccountid
              AND CONCAT(DATE_FORMAT(m.date,'%Y-%m-%d'),'-',LPAD(m.sortorder,2,'0'),'-',LPAD(m.tiebreaker,10,'0')) = last_row.max_key`
      } catch (e) {
        logError(`Balance query failed (mutation view may not exist): ${e}`)
      }

      return { bank_accounts, payments, incomes, interpayments, balances }
    } catch (e) { logError(`${e}`); set.status = 500; return { detail: "Failed to download calendar data" } }
  })
