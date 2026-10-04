import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, expectTypeOf, it, vi } from "vitest";
import { ClarityApiError, ClarityClient, expandPath } from "../src";
import type { ApiPath, MethodsOf, SessionView } from "../src";
import type { IsOpen } from "../src/routes";

type Call = { url: string; init: RequestInit };

function clientWith(respond: (call: Call) => Response) {
  const calls: Call[] = [];
  const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const call = { url: String(url), init: init ?? {} };
    calls.push(call);
    return respond(call);
  }) as unknown as typeof fetch;
  return { client: new ClarityClient({ baseUrl: "http://api.test/", fetchImpl }), calls };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("path expansion", () => {
  it("fills and encodes placeholders", () => {
    expect(expandPath("/v1/cases/{case_id}/timeline", { case_id: "a b/c" })).toBe(
      "/v1/cases/a%20b%2Fc/timeline",
    );
  });

  it("refuses to send a request with a missing parameter", () => {
    expect(() => expandPath("/v1/cases/{case_id}", {})).toThrow(/case_id/);
  });
});

describe("requests", () => {
  it("builds method, url and body from the route", async () => {
    const { client, calls } = clientWith(() => json({ case_id: "c1" }));
    await client.evaluateCase("c 1");
    expect(calls[0].url).toBe("http://api.test/v1/cases/c%201/evaluate");
    expect(calls[0].init.method).toBe("POST");
    expect(calls[0].init.body).toBeUndefined();
    expect(calls[0].init.credentials).toBe("include");
  });

  it("applies the server defaults the schema generator makes required", async () => {
    const { client, calls } = clientWith(() => json({ token: "t" }));
    await client.verifyOtp("ch-1", "123456");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({
      challenge_id: "ch-1",
      code: "123456",
      channel: "web",
    });
    await client.createCase({ msisdn: "0771234567" });
    expect(JSON.parse(String(calls[1].init.body))).toMatchObject({
      msisdn: "0771234567",
      channel: "web",
      customer_requested_human: false,
    });
  });

  it("drops empty and undefined query values", async () => {
    const { client, calls } = clientWith(() => json({ records: [] }));
    await client.auditTrail({ actor_ref: "", event_type: "x", after_seq: 0, limit: undefined });
    expect(calls[0].url).toBe("http://api.test/v1/audit?event_type=x&after_seq=0");
  });

  it("sends the bearer token and the CSRF header when it has them", async () => {
    vi.stubGlobal("document", { cookie: "a=1; clarity_csrf=tok%3D" });
    const { client, calls } = clientWith(() => json({}));
    client.setToken("jwt");
    await client.whoami();
    const headers = new Headers(calls[0].init.headers);
    expect(headers.get("Authorization")).toBe("Bearer jwt");
    expect(headers.get("X-CSRF-Token")).toBe("tok=");
    vi.unstubAllGlobals();
  });

  it("covers the customer routes the app was never calling", async () => {
    const { client, calls } = clientWith(() => json({}));
    await client.myApp();
    await client.myCases();
    await client.myReceipts();
    await client.reload("500");
    await client.purchasePackage("PKG-ANY-5");
    await client.cancelSubscription("sub-1");
    await client.setSafeguard("spend_cap", "1000");
    await client.addFamilyMember("0771234567");
    await client.savePreferences({ language: "si" });
    expect(calls.map((c) => `${c.init.method ?? "GET"} ${c.url.replace("http://api.test", "")}`)).toEqual([
      "GET /v1/me/app",
      "GET /v1/me/cases",
      "GET /v1/me/receipts",
      "POST /v1/me/reload",
      "POST /v1/me/packages/PKG-ANY-5/purchase",
      "POST /v1/me/subscriptions/sub-1/cancel",
      "POST /v1/me/safeguards",
      "POST /v1/me/family",
      "POST /v1/me/preferences",
    ]);
  });
});

describe("errors", () => {
  it("carries the status so a missing receipt is not an unreachable API", async () => {
    const { client } = clientWith(() => json({ detail: "no such receipt" }, 404));
    const error = await client.verifyReceipt("TR-1").catch((e) => e);
    expect(error).toBeInstanceOf(ClarityApiError);
    expect(error.status).toBe(404);
    expect(error.message).toBe("no such receipt");
  });

  it("flattens a validation list to field and reason", async () => {
    const { client } = clientWith(() =>
      json({ detail: [{ loc: ["body", "msisdn"], msg: "field required" }] }, 422),
    );
    const error = await client.requestOtp("").catch((e) => e);
    expect(error.message).toBe("body.msisdn: field required");
  });
});

describe("the schema is the source of truth", () => {
  const schema = JSON.parse(readFileSync(join(__dirname, "../../../../contracts/openapi.json"), "utf8")) as {
    paths: Record<string, Record<string, unknown>>;
  };
  const source = readFileSync(join(__dirname, "../src/client.ts"), "utf8");

  it("every route the client calls exists in the committed OpenAPI document", () => {
    const calls = [...source.matchAll(/(?:call|declared)\(\s*"(get|post|put|patch|delete)",\s*"([^"]+)"/g)];
    expect(calls.length).toBeGreaterThan(40);
    const missing = calls
      .filter(([, method, path]) => !schema.paths[path]?.[method])
      .map(([, method, path]) => `${method.toUpperCase()} ${path}`);
    expect(missing).toEqual([]);
  });

  it("types agree with the schema about which methods a path has", () => {
    expectTypeOf<MethodsOf<"/v1/cases">>().toEqualTypeOf<"post">();
    expectTypeOf<MethodsOf<"/v1/desk/queue">>().toEqualTypeOf<"get">();
    expectTypeOf<"/v1/cases/{case_id}">().toMatchTypeOf<ApiPath>();
    // @ts-expect-error a route the backend does not serve is not an ApiPath
    expectTypeOf<"/v1/detect">().toMatchTypeOf<ApiPath>();
  });

  it("tells a modelled response from an open one", () => {
    expectTypeOf<IsOpen<Record<string, unknown>>>().toEqualTypeOf<true>();
    expectTypeOf<IsOpen<Record<string, unknown>[]>>().toEqualTypeOf<true>();
    expectTypeOf<IsOpen<unknown>>().toEqualTypeOf<true>();
    expectTypeOf<IsOpen<SessionView>>().toEqualTypeOf<false>();
  });
});
