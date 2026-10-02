import http from 'k6/http';
import { check, sleep } from 'k6';

/**
 * Minimal smoke: GET /health against the Clarity API.
 *
 *   k6 run tests/load/smoke.js
 *   BASE_URL=http://127.0.0.1:8000 k6 run tests/load/smoke.js
 */
export const options = {
  vus: 2,
  duration: '15s',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<800'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export default function () {
  const res = http.get(`${BASE_URL}/health`);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'body has status': (r) => String(r.body).includes('ok') || String(r.body).includes('status'),
  });
  sleep(0.5);
}
