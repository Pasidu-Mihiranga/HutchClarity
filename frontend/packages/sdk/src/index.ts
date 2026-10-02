export {
  ClarityClient,
  createClarityClient,
  type ClarityClientOptions,
  type CasePayload,
  type OtpRequestResult,
  type OtpVerifyResult,
  type ReceiptPayload,
  type SessionView,
  type QueueItem,
  type DecisionPayload,
  type TimelinePayload,
  type TimelineEvent,
  type TimelineSource,
  type ProposalPayload,
  type ApproveResult,
  type DemoSubscriber,
  type SwitchStateView,
  type StaffSessionRequest,
  type RuledOutItem,
} from "./client";

// Generated from contracts/openapi.json by `npm run sdk:generate` (B09).
// Checked in, and CI fails if it drifts from the backend's schema.
export type { components, operations, paths } from "./generated/schema";
export type { ApiPath, ResponseOf } from "./routes";
