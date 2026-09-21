/* Generated from contracts/legacy-project-catalog-response.schema.json. Do not edit by hand. */

export type Projectid = string;
export type Items = LegacyProjectCatalogItemResponse[];

/**
 * Historic `items` envelope; the business API does not emit this shape.
 */
export interface LegacyProjectCatalogResponse {
  items: Items;
}
/**
 * Historic kernel catalog row accepted only by the frontend adapter.
 */
export interface LegacyProjectCatalogItemResponse {
  projectId: Projectid;
}
