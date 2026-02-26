/**
 * Auth setup: Logs in as admin and saves storage state for reuse across tests.
 * Runs once before all authenticated test projects.
 *
 * Prerequisites: the seed script (fixtures/seed.ts) must have already run to:
 *   - change the admin password from the default PIN to ADMIN_PASSWORD
 *   - create the regular test user
 */
import { test as setup, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const ADMIN_EMAIL = process.env.ADMIN_EMAIL || 'admin@thumbsup.local';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin-secret-pw';
const AUTH_DIR = path.join(__dirname, '.auth');
const ADMIN_STATE = path.join(AUTH_DIR, 'admin.json');
const USER_STATE = path.join(AUTH_DIR, 'user.json');

setup.beforeAll(() => {
  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  }
});

setup('authenticate as admin', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(ADMIN_EMAIL);
  await page.getByLabel('Password').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: /login/i }).click();

  // Admin is redirected to the dashboard after login
  await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 10_000 });
  await page.context().storageState({ path: ADMIN_STATE });
});

setup('authenticate as regular user', async ({ page }) => {
  const userEmail = process.env.TEST_USER_EMAIL || 'testuser@thumbsup.local';
  const userPassword = process.env.TEST_USER_PASSWORD || 'user-secret-pw';

  await page.goto('/login');
  await page.getByLabel('Email').fill(userEmail);
  await page.getByLabel('Password').fill(userPassword);
  await page.getByRole('button', { name: /login/i }).click();

  // Regular user is redirected to the file browser
  await expect(page).toHaveURL(/\/files/, { timeout: 10_000 });
  await page.context().storageState({ path: USER_STATE });
});
