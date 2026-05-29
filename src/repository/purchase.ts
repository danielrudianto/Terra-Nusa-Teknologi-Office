import { prisma } from "../utils/database";
import { paginationParams } from "../utils/pagination";

type PurchaseFilter = {
  isDue?: boolean;
  isNotDue?: boolean;
  isPaid?: boolean;
  isUnpaid?: boolean;
  isDraft?: boolean;
  isReady?: boolean;
};

export class PurchaseRepository {
  static async create(data: Record<string, unknown>) {
    return prisma.purchase.create({ data: data as never });
  }

  static async createStatus(data: {
    purchaseID: number;
    status: string;
    createdBy: number;
    description?: string;
  }) {
    return prisma.purchaseStatus.create({
      data: { ...data, createdAt: new Date() },
    });
  }

  static async getAll(
    page: number,
    pageSize: number,
    filter: PurchaseFilter = {},
    keyword?: string,
    sortBy = "createdAt",
    sortDir = "desc",
  ) {
    const where: Record<string, unknown> = { isDelete: false };
    const today = new Date();

    if (filter.isDue) where.dueDate = { lt: today };
    if (filter.isNotDue) where.dueDate = { gte: today };
    if (filter.isPaid) where.isPaid = true;
    if (filter.isUnpaid) where.isPaid = false;
    if (filter.isDraft) where.lastStatus = "draft";
    if (filter.isReady) where.lastStatus = "ready";
    if (keyword) {
      where.OR = [
        { invoiceName: { contains: keyword } },
        { purchaseOrderName: { contains: keyword } },
        { projectName: { contains: keyword } },
      ];
    }

    const { skip, take } = paginationParams(page, pageSize);
    const [data, total] = await Promise.all([
      prisma.purchase.findMany({
        where: where,
        orderBy: { [sortBy]: sortDir as "asc" | "desc" },
        skip,
        take,
      }),
      prisma.purchase.count({ where: where as never }),
    ]);
    return { data, total };
  }

  static async getById(id: number) {
    return prisma.purchase.findFirst({ where: { id, isDelete: false } });
  }

  static async getByPurchaseOrderName(name: string) {
    return prisma.purchase.findMany({
      where: { purchaseOrderName: name, isDelete: false },
    });
  }

  static async update(id: number, data: Record<string, unknown>) {
    return prisma.purchase.update({ where: { id }, data: data as never });
  }

  static async softDelete(id: number, deletedBy: number) {
    return prisma.purchase.update({
      where: { id },
      data: { isDelete: true, deletedBy, deletedAt: new Date() },
    });
  }

  static async checkExists(invoiceName: string, purchaseOrderName: string) {
    return prisma.purchase.findFirst({
      where: { invoiceName, purchaseOrderName, isDelete: false },
    });
  }
}
