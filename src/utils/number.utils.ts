export function parseIntegerParam(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value : null
  }

  if (typeof value === "string") {
    if (!/^-?\d+$/.test(value)) return null
    const parsed = Number(value)
    return Number.isInteger(parsed) ? parsed : null
  }

  return null
}

export function parsePositiveIntegerParam(
  value: unknown,
  name: string,
  set: { status?: number | string },
  min = 1,
) {
  const parsed = parseIntegerParam(value)
  if (parsed === null || parsed < min) {
    set.status = 400
    return null
  }
  return parsed
}

export function getEntityId(
  params: { id?: unknown },
  set: { status?: number | string },
  entityName: string = "entity",
) {
  return parsePositiveIntegerParam(params.id, entityName + " id", set)
}
