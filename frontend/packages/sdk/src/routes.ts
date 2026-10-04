/**
 * Typed route names and bodies, from the committed OpenAPI schema (B09, E5).
 *
 * The handwritten client drifted: it called `/v1/detect` and `/v1/decide`,
 * which only ever existed in a retired backend, and nothing caught it because
 * the route was a plain string. `ApiPath` is the set of paths the backend
 * actually serves, and every method the client calls is checked against it, so
 * a route that is renamed or removed is a type error here rather than a 404 in
 * front of a customer.
 */

import type { paths } from "./generated/schema";

/** Every path the backend serves. */
export type ApiPath = keyof paths;

export type HttpMethod = "get" | "post" | "put" | "patch" | "delete";

/** The methods a path actually defines. A path with no `post` has no `"post"` here. */
export type MethodsOf<P extends ApiPath> = {
  [M in HttpMethod]: paths[P][M & keyof paths[P]] extends { responses: unknown } ? M : never;
}[HttpMethod];

type Operation<P extends ApiPath, M extends HttpMethod> = M extends keyof paths[P] ? paths[P][M] : never;

type JsonOf<R> = R extends { content: { "application/json": infer J } } ? J : void;

/** The body of the success response (200, 201 or 202) for one path and method. */
export type SuccessBody<P extends ApiPath, M extends HttpMethod> = Operation<P, M> extends {
  responses: infer R;
}
  ? { [K in keyof R & (200 | 201 | 202)]: JsonOf<R[K]> }[keyof R & (200 | 201 | 202)]
  : never;

/** The 200 response body for one path and method, when it has one. */
export type ResponseOf<P extends ApiPath, M extends keyof paths[P]> = paths[P][M] extends {
  responses: { 200: { content: { "application/json": infer R } } };
}
  ? R
  : never;

/** The JSON request body for one path and method. */
export type BodyOf<P extends ApiPath, M extends HttpMethod> = Operation<P, M> extends {
  requestBody?: { content: { "application/json": infer B } };
}
  ? B
  : never;

/** The `{placeholders}` in the path. */
export type PathParamsOf<P extends ApiPath, M extends HttpMethod> = Operation<P, M> extends {
  parameters: { path?: infer X };
}
  ? Exclude<X, undefined | never>
  : never;

/** The query string parameters. */
export type QueryOf<P extends ApiPath, M extends HttpMethod> = Operation<P, M> extends {
  parameters: { query?: infer Q };
}
  ? Exclude<Q, undefined | never>
  : never;

/**
 * True when the schema says nothing about the response shape: an open
 * dictionary, `unknown`, or a list of those. The backend returns `dict[str,
 * Any]` from these routes and publishes no model, so the SDK declares the shape
 * itself (see `declared` in the client) until the backend does.
 */
export type IsOpen<T> = unknown extends T
  ? true
  : T extends readonly (infer E)[]
    ? IsOpen<E>
    : T extends object
      ? string extends keyof T
        ? true
        : false
      : false;

/**
 * Required trailing argument that only type-checks when the route's response is
 * open. A route the schema already types cannot be re-declared by hand: that is
 * how the two drifted apart.
 */
export type OnlyIfOpen<P extends ApiPath, M extends HttpMethod> = IsOpen<SuccessBody<P, M>> extends true
  ? []
  : [error: "the schema already types this response: use the generated type"];
