import { Elysia, t } from "elysia"
import { guard } from "../utils/guard"
import { AttendanceController } from "../controllers/attendance"
import { AttendanceCreateBody, AttendanceUpdateBody } from "../schemas/attendance"

export const attendanceRoutes = new Elysia({ prefix: "/attendance" })
  .use(guard)

  // List — filters: supplierID, projectName, date, month, year, isConfirm, page, pageSize
  .get("/", async ({ query, user, set }) => {
    const result = await AttendanceController.getList(query as Record<string, string>)
    if ("error" in result) { set.status = (result as any).status; return { detail: result.error } }
    return result
  })

  // Single record
  .get("/:id", async ({ params, user, set }) => {
    const result = await AttendanceController.getById(Number(params.id))
    if ("error" in result) { set.status = (result as any).status; return { detail: result.error } }
    return result
  })

  // Create
  .post("/", async ({ body, user, set }) => {
    const result = await AttendanceController.create(body as any, user.id)
    if ("error" in result) { set.status = (result as any).status; return { detail: result.error } }
    return result
  }, { body: AttendanceCreateBody })

  // Update (partial)
  .patch("/:id", async ({ params, body, user, set }) => {
    const result = await AttendanceController.update(Number(params.id), body as any, user.id)
    if ("error" in result) { set.status = (result as any).status; return { detail: result.error } }
    return result
  }, { body: AttendanceUpdateBody })

  // Confirm attendance
  .patch("/:id/confirm", async ({ params, user, set }) => {
    const result = await AttendanceController.confirm(Number(params.id), user.id)
    if ("error" in result) { set.status = (result as any).status; return { detail: result.error } }
    return result
  })

  // Soft delete
  .delete("/:id", async ({ params, user, set }) => {
    const result = await AttendanceController.softDelete(Number(params.id), user.id)
    if ("error" in result) { set.status = (result as any).status; return { detail: result.error } }
    return result
  })
