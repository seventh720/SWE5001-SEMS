import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Counter, Rate } from 'k6/metrics';
import execution from 'k6/execution';
import crypto from 'k6/crypto';

// Keep JWTs shared across VUs; a single shared object would be copied per VU.
const users = new SharedArray('users', () => JSON.parse(open(__ENV.DATASET)).users);
const events = new SharedArray('events', () => JSON.parse(open(__ENV.DATASET)).events);
const config = new SharedArray('config', () => {
  const data = JSON.parse(open(__ENV.DATASET));
  return [{ base: data.baseUrl, marker: data.runId, hot: data.hotEvent }];
})[0];
const vus = Number(__ENV.VUS || 50);
const hold = __ENV.HOLD || '30s';
const holdSeconds = Number(hold.replace(/s$/, ''));
const mode = __ENV.MODE || 'read';
const run = __ENV.RUN_ID;
if (!run || !['read', 'mixed', 'contention'].includes(mode) ||
    !Number.isInteger(vus) || vus < 1 || vus > users.length || !events.length ||
    !/^\d+s$/.test(hold) || holdSeconds < 1 ||
    (mode === 'contention' && !config.hot)) throw new Error('Invalid run, mode or fixtures');
const errors = new Rate('unexpected_failure');
const created = new Counter('bookings_created');
const soldOut = new Counter('sold_out');
const operations = ['events', 'event-detail', 'me', 'orders',
  ...(mode === 'mixed' ? ['book', 'receipt', 'cancel'] : [])];
export const options = {
  scenarios: {
    load: mode === 'contention'
      ? { executor: 'per-vu-iterations', vus, iterations: 1, maxDuration: '60s', gracefulStop: '10s' }
      : { executor: 'ramping-vus', startVUs: 0, stages: [
        { target: vus, duration: '30s' }, { target: vus, duration: hold },
      ], gracefulRampDown: '10s', gracefulStop: '10s' },
  },
  thresholds: {
    unexpected_failure: [{ threshold: 'rate<0.01', abortOnFail: true, delayAbortEval: '15s' }],
    checks: ['rate==1'],
    http_req_duration: ['p(95)<3000'],
    ...(mode === 'contention' ? {} : {
      'http_req_duration{phase:hold}': ['p(95)<3000'],
      'unexpected_failure{phase:hold}': ['rate<0.01'],
      ...Object.fromEntries(operations.flatMap(name => [
        [`http_req_duration{name:${name},phase:hold}`, ['p(95)<3000']],
        [`http_reqs{name:${name},phase:hold}`, ['count>0']],
      ])),
    }),
  },
  systemTags: ['status', 'method', 'name', 'scenario', 'expected_response'],
};

function request(method, path, name, account, data, predicate, expected = [200]) {
  const elapsed = (Date.now() - execution.scenario.startTime) / 1000;
  const phase = mode === 'contention' ? 'hold' : elapsed < 30 ? 'ramp' : elapsed < 30 + holdSeconds ? 'hold' : 'drain';
  const response = http.request(method, config.base + path, data == null ? null : JSON.stringify(data), {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${account.token}` },
    tags: { name, phase, mode, target_vus: String(vus) }, timeout: '8s',
    responseCallback: http.expectedStatuses(...expected),
  });
  let value = null;
  let ok = false;
  try { value = response.json(); ok = expected.includes(response.status) && predicate(value, response.status); }
  catch (_) { /* Count malformed JSON as failure without logging credentials or tickets. */ }
  check(response, { 'expected status and content': () => ok });
  errors.add(!ok, { name, phase, mode, target_vus: String(vus) });
  return ok ? { value, status: response.status } : null;
}

export default function () {
  const user = users[__VU - 1];
  const event = mode === 'contention' ? config.hot : events[(__VU - 1) % events.length];
  if (mode !== 'contention') {
    const page = __ITER % Math.ceil(events.length / 10);
    request('GET', `/api/v1/events?keyword=${config.marker}&page=${page}&size=10`, 'events', user, null,
      x => Array.isArray(x.items) && x.items.length > 0 && x.totalElements >= events.length);
    request('GET', '/api/v1/events/' + event.eventId, 'event-detail', user, null, x => x.id === event.eventId);
    request('GET', '/api/v1/auth/me', 'me', user, null, x => x.id === user.id);
    request('GET', '/api/v1/bookings?page=0&size=10', 'orders', user, null, x => Array.isArray(x.items));
  }
  if (mode === 'contention' || (mode === 'mixed' && __ITER % 5 === 0 && __ITER < 300)) {
    const key = crypto.sha256(`${run}-${mode}-${vus}-${__VU}-${__ITER}`, 'hex');
    const booking = request('POST', '/api/v1/bookings', 'book', user, {
      eventId: event.eventId, ticketTypeId: event.ticketTypeId, quantity: 1,
      requestKey: `${key.slice(0,8)}-${key.slice(8,12)}-${key.slice(12,16)}-${key.slice(16,20)}-${key.slice(20,32)}`,
    }, (x, status) => status === 409
      ? typeof x.detail === 'string' && /quota|not enough|insufficient|sold out/i.test(x.detail)
      : typeof x.id === 'string' && x.eventId === event.eventId && x.status === 'CONFIRMED' &&
        x.quantity === 1 && x.tickets.length === 1 && x.tickets[0].state === 'VALID',
    mode === 'contention' ? [200, 409] : [200]);
    if (booking && booking.status === 409) soldOut.add(1);
    else if (booking) {
      created.add(1);
      if (mode === 'mixed') {
        request('GET', `/api/v1/bookings/${booking.value.id}`, 'receipt', user, null,
          x => x.id === booking.value.id && x.status === 'CONFIRMED' && x.tickets.length === 1 && x.tickets[0].state === 'VALID');
        request('POST', `/api/v1/bookings/${booking.value.id}/cancel`, 'cancel', user, {},
          x => x.id === booking.value.id && x.status === 'CANCELLED' && x.tickets[0].state === 'CANCELLED');
      }
    }
  }
  if (mode !== 'contention') sleep(1);
}
