import { Elysia, t } from "elysia";
import { guard } from "../utils/guard";
import { AttendanceController } from "../controllers/attendance";
import {
  AttendanceCreateBody,
  AttendanceUpdateBody,
} from "../schemas/attendance";

type AttendanceCreatePayload = Parameters<
  typeof AttendanceController.create
>[0];
type AttendanceUpdatePayload = Parameters<
  typeof AttendanceController.update
>[1];

type AuthenticatedUser = { id: number };

function requireUserId(user: unknown, set: { status: number }) {
  if (!user || typeof (user as AuthenticatedUser).id !== "number") {
    set.status = 401;
    return null;
  }
  return (user as AuthenticatedUser).id;
}

export const attendanceRoutes = new Elysia({ prefix: "/attendance" })
  .use(guard)
  // List — filters: supplierID, projectName, date, month, year, isConfirm, page, pageSize
  .get("/", async ({ query, set }) => {
    const result = await AttendanceController.getList(
      query as Record<string, string>,
    );
    if ("error" in result) {
      set.status = (result as any).status;
      return { detail: result.error };
    }
    return result;
  })

  // Single record
  .get("/:id", async ({ params, set }) => {
    const result = await AttendanceController.getById(Number(params.id));
    if ("error" in result) {
      set.status = (result as any).status;
      return { detail: result.error };
    }
    return result;
  })

  // Create
  .post(
    "/",
    async ({ body, user, set }) => {
      const userId = requireUserId(user, set);
      if (userId === null) return { detail: "Unauthorized" };

      const payload = body as AttendanceCreatePayload;
      const result = await AttendanceController.create(payload, userId);
      if ("error" in result) {
        set.status = (result as any).status;
        return { detail: result.error };
      }
      return result;
    },
    { body: AttendanceCreateBody },
  )

  // Update (partial)
  .patch(
    "/:id",
    async ({ params, body, user, set }) => {
      const userId = requireUserId(user, set);
      if (userId === null) return { detail: "Unauthorized" };

      const payload = body as AttendanceUpdatePayload;
      const result = await AttendanceController.update(
        Number(params.id),
        payload,
        userId,
      );
      if ("error" in result) {
        set.status = (result as any).status;
        return { detail: result.error };
      }
      return result;
    },
    { body: AttendanceUpdateBody },
  )

  // Confirm attendance
  .patch("/:id/confirm", async ({ params, user, set }) => {
    const userId = requireUserId(user, set);
    if (userId === null) return { detail: "Unauthorized" };

    const result = await AttendanceController.confirm(
      Number(params.id),
      userId,
    );
    if ("error" in result) {
      set.status = (result as any).status;
      return { detail: result.error };
    }
    return result;
  })

  // Soft delete
  .delete("/:id", async ({ params, user, set }) => {
    const userId = requireUserId(user, set);
    if (userId === null) return { detail: "Unauthorized" };

    const result = await AttendanceController.softDelete(
      Number(params.id),
      userId,
    );
    if ("error" in result) {
      set.status = (result as any).status;
      return { detail: result.error };
    }
    return result;
  });
