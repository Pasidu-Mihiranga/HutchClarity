export type ClarityClientOptions = {
  baseUrl?: string;
  token?: string;
  fetchImpl?: typeof fetch;
};

export type OtpRequestResult = {
  ok: boolean;
  msisdn_masked?: string;
  message?: string;
  demo_code?: string;
};

export type OtpVerifyResult = {
  token: string;
  expires_at: string;
  principal: Record<string, unknown>;
  rls?: Record<string, unknown>;
};

export type CasePayload = {
  case_id?: string;
  id?: string;
  state?: string;
  [key: string]: unknown;
};

export type ReceiptPayload = {
  receipt_id?: string;
  id?: string;
  valid?: boolean;
  chain_ok?: boolean;
  [key: string]: unknown;
};

function resolveBase(baseUrl?: string): string {
  const fromEnv =
    typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_API_BASE
      : undefined;
  return (baseUrl ?? fromEnv ?? "http://localhost:8000").replace(/\/$/, "");
}

export class ClarityClient {
  private baseUrl: string;
  private token?: string;
  private fetchImpl: typeof fetch;

  constructor(options: ClarityClientOptions = {}) {
    this.baseUrl = resolveBase(options.baseUrl);
    this.token = options.token;
    this.fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);
  }

  setToken(token: string | undefined): void {
    this.token = token;
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has("Content-Type") && init.body) {
      headers.set("Content-Type", "application/json");
    }
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Clarity API ${res.status}: ${text || res.statusText}`);
    }

    if (res.status === 204) {
      return undefined as T;
    }

    return (await res.json()) as T;
  }

  health(): Promise<{ status: string }> {
    return this.request("/health");
  }

  requestOtp(msisdn: string): Promise<OtpRequestResult> {
    return this.request("/v1/auth/otp/request", {
      method: "POST",
      body: JSON.stringify({ msisdn }),
    });
  }

  verifyOtp(msisdn: string, code: string): Promise<OtpVerifyResult> {
    return this.request("/v1/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({ msisdn, code }),
    });
  }

  createCase(body: Record<string, unknown>): Promise<CasePayload> {
    return this.request("/v1/cases", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  getCase(caseId: string): Promise<CasePayload> {
    return this.request(`/v1/cases/${encodeURIComponent(caseId)}`);
  }

  getReceipt(receiptId: string): Promise<ReceiptPayload> {
    return this.request(`/v1/receipts/${encodeURIComponent(receiptId)}`);
  }

  verifyReceipt(receiptId: string): Promise<ReceiptPayload> {
    return this.request(`/v1/verify/${encodeURIComponent(receiptId)}`);
  }

  detect(body: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request("/v1/detect", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  decide(body: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request("/v1/decide", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }
}

export function createClarityClient(
  options?: ClarityClientOptions,
): ClarityClient {
  return new ClarityClient(options);
}
