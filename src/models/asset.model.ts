import type {
  IAssetCreate,
  IAssetUpdate,
  IAssetOutput,
  IAssetView,
} from "../interfaces/assets.interfaces";
import type { IUserView } from "../interfaces/user.interfaces";

function formatAssetDate(value: string | Date): string {
  return typeof value === "string" ? value : value.toISOString().slice(0, 10);
}

export class AssetModel {
  static toOutput(
    asset: any,
    createdBy: IUserView,
    updatedBy: IUserView | null,
  ): IAssetOutput {
    return {
      id: asset.id,
      name: asset.name,
      description: asset.description,
      brand: asset.brand,
      type: asset.type,
      depreciation: asset.depreciation,
      location: asset.location,
      purchaseOrderName: asset.purchaseOrderName,
      purchaseDate: formatAssetDate(asset.purchaseDate),
      value: asset.value,
      soldValue: asset.soldValue,
      soldDate: asset.soldDate ? formatAssetDate(asset.soldDate) : undefined,
      createdAt: asset.createdAt,
      updatedAt: asset.updatedAt,
      createdBy,
      updatedBy,
    };
  }

  static toView(asset: any): IAssetView {
    return {
      id: asset.id,
      name: asset.name,
      description: asset.description,
      brand: asset.brand,
      type: asset.type,
      location: asset.location,
      value: asset.value,
    };
  }

  static createPayload(data: IAssetCreate) {
    return {
      ...data,
      purchaseDate:
        typeof data.purchaseDate === "string"
          ? new Date(data.purchaseDate)
          : data.purchaseDate,
    };
  }

  static updatePayload(data: IAssetUpdate) {
    return {
      ...data,
      purchaseDate: data.purchaseDate
        ? typeof data.purchaseDate === "string"
          ? new Date(data.purchaseDate)
          : data.purchaseDate
        : undefined,
    };
  }
}
