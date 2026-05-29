import type { IUserView } from "../interfaces/user.interfaces"

export class UserModel {
  static toView(record: { id: number; name: string } | null | undefined): IUserView {
    if (!record) return { id: 0, name: "Unknown" }
    return { id: record.id, name: record.name }
  }
}
