import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// Custom Prometheus/Grafana k6 Metrics
export const phiLeakRate = new Rate('phi_leak_detected_rate');
export const sagaRollbackRate = new Rate('saga_rollback_rate');
export const priorAuthLatency = new Trend('prior_auth_latency_ms');
export const refillLatency = new Trend('fast_refill_latency_ms');
export const totalRxOrders = new Counter('total_rx_orders_submitted');

// Load Test Configuration: Ramp-up, Steady State, Ramp-down
export const options = {
  stages: [
    { duration: '5s', target: 10 },   // Warm-up ramp to 10 VUs
    { duration: '20s', target: 25 },  // Sustained load with 25 VUs
    { duration: '5s', target: 0 },    // Ramp-down to 0 VUs
  ],
  thresholds: {
    // Quality Gates: SLA Enforcements
    http_req_duration: ['p(95)<2000', 'p(99)<3500'], // p95 must be under 2s, p99 under 3.5s
    http_req_failed: ['rate<0.02'],                   // Error rate must be under 2%
    phi_leak_detected_rate: ['rate==0.0'],            // Zero-tolerance HIPAA PHI leakage
    saga_rollback_rate: ['rate<0.15'],                // Saga rollback rate under 15%
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://127.0.0.1:8000';

export default function () {
  const rand = Math.random();

  // Scenario 1 (50% traffic): Complex E-Rx requiring Prior Auth (GLP-1 Ozempic)
  if (rand < 0.50) {
    const orderNum = Math.floor(Math.random() * 90000) + 10000;
    const payload = JSON.stringify({
      order_id: `K6-RX-${orderNum}`,
      idempotency_key: `IDEMP-K6-${orderNum}`,
      patient_name: `K6 Synthetic Patient ${orderNum}`,
      ndc_code: '00169-4132-12', // Ozempic
      sig: '0.5mg injected subcutaneously once weekly',
      clinical_notes: 'Patient diagnosed with Type 2 Diabetes mellitus (E11.9). Completed 180 days on Metformin 1000mg daily.'
    });

    const params = { headers: { 'Content-Type': 'application/json' } };
    const t0 = new Date();
    const res = http.post(`${BASE_URL}/api/v1/prescriptions`, payload, params);
    priorAuthLatency.add(new Date() - t0);
    totalRxOrders.add(1);

    const success = check(res, {
      'Prior Auth E-Rx Status 200': (r) => r.status === 200,
      'Order Status COMMITTED': (r) => r.json('order_status') === 'COMMITTED',
      'Zero PHI Leaked in Summary': (r) => {
        const summary = r.json('sanitized_summary') || '';
        return !summary.includes('Patient ') && summary.includes('<PATIENT_');
      },
    });

    phiLeakRate.add(!success);
    sagaRollbackRate.add(res.json('order_status') === 'SAGA_EXECUTION_FAILED');

  // Scenario 2 (30% traffic): Fast-Path Formulary Refill (Metformin 500mg, No PA)
  } else if (rand < 0.80) {
    const orderNum = Math.floor(Math.random() * 90000) + 10000;
    const payload = JSON.stringify({
      order_id: `K6-REFILL-${orderNum}`,
      idempotency_key: `IDEMP-K6-REFILL-${orderNum}`,
      patient_name: `Refill Patient ${orderNum}`,
      ndc_code: '00093-7212-01', // Metformin
      sig: 'Take 1 tablet daily with food',
      clinical_notes: 'Routine 90-day maintenance refill.'
    });

    const params = { headers: { 'Content-Type': 'application/json' } };
    const t0 = new Date();
    const res = http.post(`${BASE_URL}/api/v1/prescriptions`, payload, params);
    refillLatency.add(new Date() - t0);
    totalRxOrders.add(1);

    check(res, {
      'Refill Status 200': (r) => r.status === 200,
      'Refill Order COMMITTED': (r) => r.json('order_status') === 'COMMITTED',
    });

  // Scenario 3 (20% traffic): Observability, Metrics & Health Probing
  } else {
    const healthRes = http.get(`${BASE_URL}/health`);
    check(healthRes, {
      'Health check 200': (r) => r.status === 200,
      'System status HEALTHY': (r) => r.json('system_status') === 'HEALTHY',
    });

    const metricsRes = http.get(`${BASE_URL}/metrics`);
    check(metricsRes, {
      'Prometheus /metrics 200': (r) => r.status === 200,
      'Contains agent_latency_ms': (r) => r.body.includes('agent_latency_ms'),
    });
  }

  sleep(0.2); // User think time
}
