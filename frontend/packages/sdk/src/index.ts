export {
  ClarityClient,
  ClarityApiError,
  createClarityClient,
  type ClarityClientOptions,
  type CasePayload,
  type OtpRequestResult,
  type OtpVerifyResult,
  type AutopsyCluster,
  type PolicyApproval,
  type PolicyImpact,
  type PolicyChangeView,
  type AutopsyWorkspace,
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
  type StaffLoginRequest,
  type RuledOutItem,
  // Audit assurance (plan 5.8, ADR-0037 to ADR-0039).
  type AuditRecordView,
  type AuditTrailPage,
  type AuditHealth,
  type AuditRecovery,
  type AuditRecordVerdict,
  type AuditGrantView,
  type AlertView,
  type AlertQueue,
} from "./client";

// Generated from contracts/openapi.json by `npm run sdk:generate` (B09).
// Checked in, and CI fails if it drifts from the backend's schema.
export type { components, operations, paths } from "./generated/schema";
export type { ApiPath, ResponseOf } from "./routes";
