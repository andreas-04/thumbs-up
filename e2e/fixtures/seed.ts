/**
 * Test data seeding script.
 * 1. Logs in as the default admin (using ADMIN_PIN) and changes the password
 *    so that `is_default_pin` is cleared and the frontend won't redirect to
 *    the password-reset page.
 * 2. Registers a regular test user via /api/v1/auth/signup.
 *
 * Usage:
 *   BASE_URL=http://localhost npx tsx fixtures/seed.ts
 */

import * as https from 'https';
import * as http from 'http';

const BASE_URL = process.env.BASE_URL || 'http://localhost';

async function request(
  url: string,
  method: string,
  body?: object,
  headers?: Record<string, string>,
): Promise<{ status: number; data: Record<string, unknown> }> {
  return new Promise((resolve, reject) => {
    const json = body ? JSON.stringify(body) : undefined;
    const parsedUrl = new URL(url);
    const options: http.RequestOptions = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
      path: parsedUrl.pathname,
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(json ? { 'Content-Length': Buffer.byteLength(json) } : {}),
        ...headers,
      },
    };

    const mod = parsedUrl.protocol === 'https:' ? https : http;
    const req = mod.request(options, (res: http.IncomingMessage) => {
      let data = '';
      res.on('data', (chunk: Buffer) => (data += chunk.toString()));
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode ?? 0, data: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode ?? 0, data: { raw: data } });
        }
      });
    });

    req.on('error', reject);
    if (json) req.write(json);
    req.end();
  });
}

async function seed() {
  // ── Step 1: Change admin password so is_default_pin is cleared ──────────
  const adminEmail = process.env.ADMIN_EMAIL || 'admin@thumbsup.local';
  const adminPin = process.env.ADMIN_PIN || '0000';
  const adminPassword = process.env.ADMIN_PASSWORD || 'admin-secret-pw';

  // Login as admin using the default PIN password
  const loginResult = await request(`${BASE_URL}/api/v1/auth/login`, 'POST', {
    email: adminEmail,
    password: adminPin,
  });

  if (loginResult.status === 200 && loginResult.data.token) {
    console.log(`✓ Logged in as admin (${adminEmail})`);
    const token = loginResult.data.token as string;

    // Change password (is_default_pin=True allows skipping current password)
    const changePwResult = await request(
      `${BASE_URL}/api/v1/auth/change-password`,
      'POST',
      { newPassword: adminPassword },
      { Authorization: `Bearer ${token}` },
    );

    if (changePwResult.status === 200) {
      console.log(`✓ Admin password changed (is_default_pin cleared)`);
    } else {
      console.warn(`⚠ Could not change admin password: HTTP ${changePwResult.status}`, changePwResult.data);
    }
  } else if (loginResult.status === 401) {
    // Admin password may already have been changed (re-run scenario)
    console.log(`~ Admin password already changed or PIN mismatch — skipping`);
  } else {
    console.warn(`⚠ Could not log in as admin: HTTP ${loginResult.status}`, loginResult.data);
  }

  // ── Step 2: Create regular test user ────────────────────────────────────
  const users = [
    {
      email: process.env.TEST_USER_EMAIL || 'testuser@thumbsup.local',
      password: process.env.TEST_USER_PASSWORD || 'user-secret-pw',
      username: 'testuser',
    },
  ];

  for (const user of users) {
    const result = await request(`${BASE_URL}/api/v1/auth/signup`, 'POST', user);
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
