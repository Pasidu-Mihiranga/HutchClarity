/**
 * The customer journey at 10x pilot load (X02, issue #43).
 *
 *   BASE_URL=http://127.0.0.1:8000 k6 run tests/load/journeys.js
 *
 * ## Where the numbers come from, and what they are worth
 *
 * Plan 03 NFR-SC-01 says "model tested to 10x pilot load" without stating the
 * pilot. Plan 15 section 38 does: the pilot column is 2K interactions/day,
 * 16K API requests/day, peak API RPS ~1. So 10x pilot is ~10 RPS peak, which
 * is what `rate` below targets.
 *
 * Both figures are **ASSUMPTION / PROPOSED TARGET - REQUIRES HUTCH
 * VALIDATION**, exactly as plan 03 section 4.2 labels them. Passing this
 * scenario means the prototype meets a target this project wrote down. It is
 * not a measurement of HUTCH's real load, and no capacity decision should rest
 * on it until the pilot figure is confirmed.
 *
 * The thresholds are the plan's, not invented here:
 *   NFR-PERF-01  Why? on the rules + template path, p95 <= 2.5 s
 *   NFR-PERF-04  desk case cockpit load, p95 <= 2 s
 *   NFR-PERF-05  receipt verification page, p95 <= 800 ms
 *
 * The run is against the `lite` profile with simulated HUTCH adapters, so it
 * excludes "HUTCH adapter latency beyond its SLA", which NFR-PERF-01 excludes
 * too.
 */
import http from 'k6/http';
import { check, group } from 'k6';
import { Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

/**
 * The four demo subscribers, one per decision outcome. Spreading across them
 * is not cosmetic: signing in repeatedly as one number is refused by the OTP
 * rate limit (429, the TH1 mitigation), so a script that re-authenticates
 * every iteration measures the rate limiter rather than the journey. The
 * first run of this scenario did exactly that and reported 92% failures.
 */
const SUBSCRIBERS = [
  { msisdn: '+94771234567', outcome: 'ONE_TAP_FIX', pays: true },
  { msisdn: '+94772223333', outcome: 'AUTO_FIX', pays: false },
  { msisdn: '+94773334444', outcome: 'EXPLAIN_ONLY', pays: false },
  { msisdn: '+94774445555', outcome: 'STAFF_APPROVAL', pays: false },
];

const whyDuration = new Trend('clarity_why_duration', true);
const verifyDuration = new Trend('clarity_verify_duration', true);

export const options = {
  scenarios: {
    ten_times_pilot: {
      executor: 'constant-arrival-rate',
      // 10x the pilot peak of ~1 RPS (plan 15 section 38).
      rate: 10,
      timeUnit: '1s',
      duration: __ENV.DURATION || '60s',
      preAllocatedVUs: 20,
      maxVUs: 60,
    },
  },
  thresholds: {
    // A failed request is a failed journey, not a slow one.
    http_req_failed: ['rate<0.01'],
    // NFR-PERF-01: the rules + template path, end to end.
    clarity_why_duration: ['p(95)<2500'],
    // NFR-PERF-05: the public verification page.
    clarity_verify_duration: ['p(95)<800'],
  },
};

function signIn(msisdn) {
  const started = http.post(
    `${BASE_URL}/v1/auth/otp/request`,
    JSON.stringify({ msisdn }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  if (started.status !== 200) throw new Error(`otp request for ${msisdn}: ${started.status}`);

  const inbox = http.get(`${BASE_URL}/v1/demo/inbox?msisdn=${encodeURIComponent(msisdn)}`);
  if (inbox.status !== 200) throw new Error(`inbox for ${msisdn}: ${inbox.status}`);

  const verified = http.post(
    `${BASE_URL}/v1/auth/otp/verify`,
    JSON.stringify({ challenge_id: started.json('challenge_id'), code: inbox.json('code') }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  if (verified.status !== 200) throw new Error(`otp verify for ${msisdn}: ${verified.status}`);
  return String(verified.json('token'));
}

/** Sign in once, outside the measured load. Real customers stay signed in. */
export function setup() {
  return SUBSCRIBERS.map((subscriber) => ({ ...subscriber, token: signIn(subscriber.msisdn) }));
}

export default function (sessions) {
  const subscriber = sessions[__ITER % sessions.length];
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${subscriber.token}`,
  };
  const MSISDN = subscriber.msisdn;

  let caseId;
  let receiptId;

  group('why', function () {
    const opened = http.post(`${BASE_URL}/v1/cases`, JSON.stringify({ msisdn: MSISDN }), { headers });
    check(opened, { 'case opened': (r) => r.status === 201 });
    if (opened.status !== 201) return;
    caseId = opened.json('case_id');

    const decided = http.post(`${BASE_URL}/v1/cases/${caseId}/evaluate`, null, { headers });
    check(decided, {
      'decided': (r) => r.status === 200,
      'decision has a cause': (r) => r.status === 200 && String(r.json('explanation') || '').length > 0,
      // Not pinned to one outcome: sustained load on a single subscriber
      // escalates them by policy (see the note on the fix group below), and a
      // load test must not read correct policy as a regression.
      'a real outcome': (r) => r.status === 200 && String(r.json('outcome') || '').length > 0,
    });
    // NFR-PERF-01 is the whole Why?: open plus evaluate, as the customer waits.
    whyDuration.add(opened.timings.duration + decided.timings.duration);
  });

  // Only the one-tap subscriber has a fix to confirm; the others are an
  // auto-fix, an explanation and a staff approval, and forcing a confirm on
  // them would measure a refusal path as if it were the money path.
  if (!caseId || !subscriber.pays) return;

  group('fix', function () {
    const plan = http.post(
      `${BASE_URL}/v1/cases/${caseId}/proposals`,
      JSON.stringify({ created_by: 'load-test' }),
      { headers },
    );
    if (plan.status !== 201) return;

    /**
     * 403 is an expected answer here, not a failure.
     *
     * Repeatedly refunding one subscriber is what the refund-velocity policy
     * exists to stop (plan 11 TH2). After a few one-tap fixes the same
     * subscriber's next case is decided STAFF_APPROVAL, and the customer
     * confirm is then correctly refused with CONFIRMATION_REQUIRED. A first
     * version of this scenario counted those refusals as errors and reported
     * a 90% failure rate against a system that was behaving exactly as
     * designed.
     *
     * What must never happen is a 5xx, or a refusal with no reason.
     */
    const confirmed = http.post(
      `${BASE_URL}/v1/cases/${caseId}/confirm`,
      JSON.stringify({ plan_id: plan.json('plan_id') }),
      { headers, responseCallback: http.expectedStatuses(200, 403) },
    );
    check(confirmed, {
      'fix applied, or refused for a stated reason': (r) =>
        r.status === 200 || (r.status === 403 && String(r.json('code') || '').length > 0),
      'never a server error on the money path': (r) => r.status < 500,
    });
    if (confirmed.status === 200) receiptId = confirmed.json('receipt_id');
  });

  if (!receiptId) return;

  group('verify', function () {
    // No credentials: this is what the QR code opens (NFR-PERF-05).
    const verified = http.post(`${BASE_URL}/v1/receipts/${receiptId}/verify`);
    check(verified, {
      'receipt verifies': (r) => r.status === 200 && r.json('valid') === true,
    });
    verifyDuration.add(verified.timings.duration);
  });
}
