export function paginationParams(page: number, pageSize: number) {
  const skip = page * pageSize;
  return { skip, take: pageSize };
}

export function paginationMeta(total: number, page: number, pageSize: number) {
  return { total, page, pageSize, totalPages: Math.ceil(total / pageSize) };
}
