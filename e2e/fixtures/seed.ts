/**
 * Test data seeding script.
 * Registers default test users via the /api/v1/auth/signup endpoint.
 * Run this before the test suite to ensure test accounts exist.
 *
 * Usage:
 *   BASE_URL=http://localhost npx tsx fixtures/seed.ts
 */

import * as https from 'https';
import * as http from 'http';

const BASE_URL = process.env.BASE_URL || 'http://localhost';

async function post(url: string, body: object): Promise<{ status: number; data: unknown }> {
  return new Promise((resolve, reject) => {
    const json = JSON.stringify(body);
    const parsedUrl = new URL(url);
    const options: http.RequestOptions = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
      path: parsedUrl.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(json),
      },
    };

    const mod = parsedUrl.protocol === 'https:' ? https : http;
    const req = mod.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode ?? 0, data: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode ?? 0, data });
        }
      });
    });

    req.on('error', reject);
    req.write(json);
    req.end();
  });
}

async function seed() {
  const users = [
    {
      email: process.env.TEST_USER_EMAIL || 'testuser@thumbsup.local',
      password: process.env.TEST_USER_PASSWORD || 'user-secret-pw',
      username: 'testuser',
    },
  ];

  for (const user of users) {
    const result = await post(`${BASE_URL}/api/v1/auth/signup`, user);
    if (result.status === 201 || result.status === 200) {
      console.log(`✓ Created user: ${user.email}`);
    } else if (result.status === 409) {
      console.log(`~ User already exists: ${user.email}`);
    } else {
      console.warn(`⚠ Could not create user ${user.email}: HTTP ${result.status}`, result.data);
    }
  }
}

seed().catch((err) => {
  console.error('Seeding failed:', err);
  process.exit(1);
});
