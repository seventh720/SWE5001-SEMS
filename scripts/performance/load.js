import http from 'k6/http';
import exec from 'k6/execution';
import crypto from 'k6/crypto';
import { sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Counter, Rate, Trend } from 'k6/metrics';

const dataset = new SharedArray('benchmark', () => [JSON.parse(open(__ENV.DATASET))])[0];
const base = (__ENV.BASE_URL || dataset.baseUrl).replace(/\/$/, '');
const mode = __ENV.MODE || 'catalog';
const vus = Number(__ENV.VUS || 25);
const warmup = Number(__ENV.WARMUP_SECONDS || 60);
const duration = Number(__ENV.DURATION_SECONDS || 600);
const runId = __ENV.RUN_ID;
if (!runId || !['catalog', 'booking'].includes(mode) ||
    !Number.isInteger(vus) || vus < 1 || vus > dataset.users.length || warmup < 1 || duration < 1 ||
    !dataset.events.length || dataset.users.some(u => !u.token)) {
  throw new Error('Require RUN_ID, valid dataset/target, MODE=catalog|booking and enough authenticated users for VUS');
}
const successful = new Counter('successful_requests');
const rejected = new Counter('business_rejections');
const errors = new Rate('unexpected_error_rate');
const latency = new Trend('operation_duration', true);
const rejectedRate = new Rate('business_rejection_rate');
export const options = {
  scenarios: {
    warmup: { executor: 'constant-vus', vus, duration: `${warmup}s`, gracefulStop: '0s' },
    measurement: { executor: 'constant-vus', vus, duration: `${duration}s`, startTime: `${warmup}s`, gracefulStop: '30s' },
  },
  thresholds: {
    'unexpected_error_rate{scenario:measurement}': ['rate<0.01'],
    'business_rejection_rate{scenario:measurement}': ['rate==0'],
    'successful_requests{scenario:measurement}': ['count>0'],
    // Per-operation thresholds prevent fast list reads from hiding slow bookings.
    ...Object.fromEntries((mode === 'catalog' ? ['list', 'detail'] : ['book', 'receipt'])
      .flatMap(op => [
        [`operation_duration{scenario:measurement,operation:${op}}`, ['p(95)<3000']],
        [`successful_requests{scenario:measurement,operation:${op}}`, ['count>0']],
      ])),
  },
  systemTags: ['status', 'method', 'name', 'scenario', 'error_code'],
};
function request(method, path, body, token, operation) {
  const res = http.request(method, base + path, body === null ? null : JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    tags: { name: operation, operation }, timeout: '15s',
  });
  const ok = res.status === 200;
  const business = res.status === 409;
  errors.add(!ok && !business, { operation });
  rejectedRate.add(business, { operation });
  latency.add(res.timings.duration, { operation });
  if (ok) successful.add(1, { operation });
  if (business) rejected.add(1, { operation });
  return res;
}
export function setup() {
  // Validate tokens against Identity before measuring. Fail clearly rather than benchmark 401s.
  for (let i = 0; i < vus; i++) {
    const res = http.get(`${base}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${dataset.users[i].token}` } });
    if (res.status !== 200) throw new Error('Expired or invalid dataset tokens; run seed.py --refresh');
  }
}
export default function () {
  const index = (__VU - 1) % vus;
  const user = dataset.users[index];
  const event = dataset.events[(__ITER * vus + index) % dataset.events.length];
  if (mode === 'catalog') {
    // Fixed 80% filtered directory / 20% details mix, independent of random seeds.
    if (__ITER % 5 !== 4) request('GET', `/api/v1/events?keyword=${dataset.runId}&size=20&page=${__ITER % Math.ceil(dataset.events.length / 20)}`, null, null, 'list');
    else request('GET', `/api/v1/events/${event.eventId}`, null, null, 'detail');
  } else {
    const key = crypto.sha256(`${runId}-${exec.scenario.name}-${__VU}-${__ITER}`, 'hex').slice(0, 32);
    const requestKey = `${key.slice(0,8)}-${key.slice(8,12)}-${key.slice(12,16)}-${key.slice(16,20)}-${key.slice(20)}`;
    const res = request('POST', '/api/v1/bookings', {
      eventId: event.eventId, ticketTypeId: event.ticketTypeId, quantity: 1,
      requestKey,
    }, user.token, 'book');
    if (res.status === 200) request('GET', `/api/v1/bookings/${res.json('id')}`, null, user.token, 'receipt');
  }
  sleep(Number(__ENV.THINK_SECONDS || .1));
}
export function handleSummary(data) {
  return { [__ENV.SUMMARY_FILE || 'summary.json']: JSON.stringify({
    metadata: { runId, dataset: dataset.runId, mode, vus, warmup, duration, base,
      commit: __ENV.COMMIT || 'unrecorded', replicas: __ENV.REPLICAS || 'unrecorded',
      note: 'Read measurement-tagged metrics only; HTTP counts include setup and warmup. No HA claim.' },
    ...data,
  }, null, 2) };
}
