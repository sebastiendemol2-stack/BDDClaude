import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const queryLatency = new Trend('query_latency_ms');

export const options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 500 },
    { duration: '3m', target: 0 },
  ],
  thresholds: {
    errors: ['rate<0.01'],
    query_latency_ms: ['p(95)<5000'],
    http_req_duration: ['p(95)<10000'],
  },
};

const SUPABASE_URL = __ENV.SUPABASE_URL || 'https://ottoqbwctcpzzdfzewdi.supabase.co';
const SUPABASE_KEY = __ENV.SUPABASE_SERVICE_ROLE_KEY || '';

const QUERIES = [
  'machine learning',
  'vector search',
  'architecture electron',
  'agent workflow',
  'cowork app',
  'second brain',
  'cognitive runtime',
  'supabase migration',
  'docker sandbox',
  'browser automation',
];

function pickRandom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

export default function () {
  const query = pickRandom(QUERIES);

  const payload = JSON.stringify({
    query,
    limit: 5,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${SUPABASE_KEY}`,
    },
    timeout: '30s',
  };

  // Test 1: metrics endpoint
  const metricsStart = Date.now();
  const metricsRes = http.post(`${SUPABASE_URL}/functions/v1/metrics`, '{}', params);
  const metricsDur = Date.now() - metricsStart;
  queryLatency.add(metricsDur);
  check(metricsRes, {
    'metrics status 200': (r) => r.status === 200,
    'metrics has entries': (r) => r.body && JSON.parse(r.body).entries,
  });
  errorRate.add(metricsRes.status !== 200);

  // Test 2: memories-store
  const memPayload = JSON.stringify({
    session_id: uuidv4(),
    project_slug: 'load-test',
    summary: `Load test query: ${query}`,
  });
  const memStart = Date.now();
  const memRes = http.post(`${SUPABASE_URL}/functions/v1/memories-store`, memPayload, params);
  queryLatency.add(Date.now() - memStart);
  check(memRes, {
    'memories-store status 200': (r) => r.status === 200,
  });
  errorRate.add(memRes.status !== 200);

  // Test 3: worktree-status
  const wtRes = http.get(`${SUPABASE_URL}/functions/v1/worktree-status`, params);
  check(wtRes, {
    'worktree-status status 200': (r) => r.status === 200,
  });

  sleep(1);
}
