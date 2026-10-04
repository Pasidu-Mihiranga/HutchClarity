export {
  ClarityClient,
  ClarityApiError,
  createClarityClient,
  expandPath,
  type ClarityClientOptions,
} from "./client";

export type * from "./types";

// Generated from contracts/openapi.json by `npm run sdk:generate` (B09).
// Checked in, and CI fails if it drifts from the backend's schema.
export type { components, operations, paths } from "./generated/schema";
export type {
  ApiPath,
  BodyOf,
  HttpMethod,
  MethodsOf,
  PathParamsOf,
  QueryOf,
  ResponseOf,
  SuccessBody,
} from "./routes";
