/**
 * Typed route names, from the committed OpenAPI schema (B09).
 *
 * The handwritten client drifted: it called `/v1/detect` and `/v1/decide`,
 * which only ever existed in a retired backend, and nothing caught it because
 * the route was a plain string. `ApiPath` is now the set of paths the backend
 * actually serves, so a route that is renamed or removed is a type error here
 * rather than a 404 in front of a customer.
 */

import type { paths } from "./generated/schema";

/** Every path the backend serves. */
export type ApiPath = keyof paths;

/** The 200 response body for one path and method, when it has one. */
export type ResponseOf<
  P extends ApiPath,
  M extends keyof paths[P],
> = paths[P][M] extends {
  responses: { 200: { content: { "application/json": infer R } } };
}
  ? R
  : never;
