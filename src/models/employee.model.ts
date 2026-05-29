import type { IEmployeeCreate, IEmployeeOutput, IEmployeeUpdate, IEmployeeView } from "../interfaces/employee.interfaces"
import type { IUserView } from "../interfaces/user.interfaces"

function formatEmployeeDate(value: string | Date | undefined | null): string | undefined {
  if (value === undefined || value === null) return undefined
  return typeof value === "string" ? value : value.toISOString().slice(0, 10)
}

function parseEmployeeDate(value: string | Date | undefined | null): Date | undefined {
  if (value === undefined || value === null) return undefined
  return typeof value === "string" ? new Date(value) : value
}

export class EmployeeModel {
  static toOutput(employee: any, createdBy: IUserView, updatedBy: IUserView | null): IEmployeeOutput {
    return {
      id: employee.id,
      name: employee.name,
      nik: employee.nik,
      birthday: formatEmployeeDate(employee.birthday) ?? "",
      email: employee.email,
      phoneNumber: employee.phoneNumber,
      address: employee.address,
      position: employee.position,
      department: employee.department,
      taxCategory: employee.taxCategory,
      startDate: formatEmployeeDate(employee.startDate),
      endDate: formatEmployeeDate(employee.endDate),
      createdAt: employee.createdAt,
      updatedAt: employee.updatedAt ?? null,
      createdBy,
      updatedBy,
    }
  }

  static toView(employee: any): IEmployeeView {
    return {
      id: employee.id,
      name: employee.name,
      nik: employee.nik,
      email: employee.email,
      phoneNumber: employee.phoneNumber,
      position: employee.position,
      department: employee.department,
      taxCategory: employee.taxCategory,
    }
  }

  static createPayload(data: IEmployeeCreate) {
    return {
      ...data,
      birthday: parseEmployeeDate(data.birthday),
      startDate: parseEmployeeDate(data.startDate),
      endDate: parseEmployeeDate(data.endDate),
    }
  }

  static updatePayload(data: IEmployeeUpdate) {
    return {
      ...data,
      birthday: data.birthday ? parseEmployeeDate(data.birthday) : undefined,
      startDate: data.startDate ? parseEmployeeDate(data.startDate) : undefined,
      endDate: data.endDate ? parseEmployeeDate(data.endDate) : undefined,
    }
  }
}
