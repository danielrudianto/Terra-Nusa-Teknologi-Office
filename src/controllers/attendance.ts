import { prisma } from "../utils/database"
import { paginationParams, paginationMeta } from "../utils/pagination"
import { logError } from "../utils/logger"

export class AttendanceController {
  static async create(body: {
    supplierID: number
    date: string
    startTime: string
    endTime?: string
    projectName: string
  }, userID: number) {
    try {
      return await prisma.attendance.create({
        data: {
          supplierID: body.supplierID,
          date: new Date(body.date),
          startTime: new Date(body.startTime),
          endTime: body.endTime ? new Date(body.endTime) : null,
          projectName: body.projectName,
          isConfirm: false,
          isDelete: false,
          createdBy: userID,
          createdAt: new Date(),
        },
      })
    } catch (e) {
      logError(`AttendanceController.create: ${e}`)
      return { error: "Failed to create attendance record", status: 500 }
    }
  }

  static async getList(q: Record<string, string>) {
    const page = Number(q.page ?? 1)
    const pageSize = Number(q.pageSize ?? 20)
    const { skip, take } = paginationParams(page, pageSize)

    // Build WHERE clause — column/operator from code only, values go into params
    const conditions: string[] = ["a.isDelete = 0"]
    const params: unknown[] = []

    if (q.supplierID) {
      conditions.push("a.supplierID = ?")
      params.push(Number(q.supplierID))
    }
    if (q.projectName) {
      conditions.push("a.projectName LIKE ?")
      params.push(`%${q.projectName}%`)
    }
    if (q.isConfirm !== undefined) {
      conditions.push("a.isConfirm = ?")
      params.push(q.isConfirm === "true" ? 1 : 0)
    }
    if (q.month && q.year) {
      conditions.push("MONTH(a.date) = ? AND YEAR(a.date) = ?")
      params.push(Number(q.month), Number(q.year))
    } else if (q.date) {
      conditions.push("a.date = ?")
      params.push(q.date)
    }

    const where = conditions.join(" AND ")
    const dataSql = `
      SELECT a.*, s.name AS supplierName, s.prefix AS supplierPrefix
      FROM attendance a
      LEFT JOIN suppliers s ON a.supplierID = s.id
      WHERE ${where}
      ORDER BY a.date DESC, a.startTime ASC
      LIMIT ${take} OFFSET ${skip}
    `
    const countSql = `SELECT COUNT(*) AS total FROM attendance a WHERE ${where}`

    try {
      const [data, countResult] = await Promise.all([
        prisma.$queryRawUnsafe<any[]>(dataSql, ...params),
        prisma.$queryRawUnsafe<[{ total: bigint }]>(countSql, ...params),
      ])
      const total = Number(countResult[0]?.total ?? 0)
      return { data, meta: paginationMeta(total, page, pageSize) }
    } catch (e) {
      logError(`AttendanceController.getList: ${e}`)
      return { error: "Failed to fetch attendance records", status: 500 }
    }
  }

  static async getById(id: number) {
    try {
      const rows = await prisma.$queryRaw<any[]>`
        SELECT a.*, s.name AS supplierName, s.prefix AS supplierPrefix
        FROM attendance a
        LEFT JOIN suppliers s ON a.supplierID = s.id
        WHERE a.id = ${id} AND a.isDelete = 0
        LIMIT 1
      `
      if (!rows.length) return { error: "Not found", status: 404 }
      return rows[0]
    } catch (e) {
      logError(`AttendanceController.getById: ${e}`)
      return { error: "Failed to fetch attendance record", status: 500 }
    }
  }

  static async update(id: number, body: {
    startTime?: string
    endTime?: string | null
    projectName?: string
    isConfirm?: boolean
  }, userID: number) {
    try {
      const data: Record<string, unknown> = { updatedBy: userID, updatedAt: new Date() }
      if (body.startTime !== undefined) data.startTime = new Date(body.startTime)
      if (body.endTime !== undefined) data.endTime = body.endTime ? new Date(body.endTime) : null
      if (body.projectName !== undefined) data.projectName = body.projectName
      if (body.isConfirm !== undefined) data.isConfirm = body.isConfirm

      return await prisma.attendance.update({
        where: { id },
        data: data as never,
      })
    } catch (e) {
      logError(`AttendanceController.update: ${e}`)
      return { error: "Failed to update attendance record", status: 500 }
    }
  }

  static async confirm(id: number, userID: number) {
    try {
      return await prisma.attendance.update({
        where: { id },
        data: { isConfirm: true, updatedBy: userID, updatedAt: new Date() },
      })
    } catch (e) {
      logError(`AttendanceController.confirm: ${e}`)
      return { error: "Failed to confirm attendance", status: 500 }
    }
  }

  static async softDelete(id: number, userID: number) {
    try {
      await prisma.attendance.update({
        where: { id },
        data: { isDelete: true, deletedBy: userID, deletedAt: new Date() },
      })
      return { message: "Deleted" }
    } catch (e) {
      logError(`AttendanceController.softDelete: ${e}`)
      return { error: "Failed to delete attendance record", status: 500 }
    }
  }
}
