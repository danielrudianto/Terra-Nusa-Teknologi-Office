import { t } from "elysia"

export const AttendanceCreateBody = t.Object({
  supplierID: t.Number(),
  date: t.String(),
  startTime: t.String(),
  endTime: t.Optional(t.String()),
  projectName: t.String(),
})

export const AttendanceUpdateBody = t.Object({
  startTime: t.Optional(t.String()),
  endTime: t.Optional(t.Nullable(t.String())),
  projectName: t.Optional(t.String()),
  isConfirm: t.Optional(t.Boolean()),
})
