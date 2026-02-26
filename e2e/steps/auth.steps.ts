import { createBdd } from 'playwright-bdd';
import { expect } from '@playwright/test';

const { Given, When, Then } = createBdd();

// ---------------------------------------------------------------------------
// Givens
// ---------------------------------------------------------------------------

Given('I am on the login page', async ({ page }) => {
  await page.goto('/login');
  await expect(page).toHaveURL(/\/login/);
});

Given('I am on the signup page', async ({ page }) => {
  await page.goto('/signup');
  await expect(page).toHaveURL(/\/signup/);
});

Given('I am not logged in', async ({ page }) => {
  // Navigate to the login page first (so we have a browsing context), then clear auth
  await page.goto('/login');
  await page.context().clearCookies();
  await page.evaluate(() => window.localStorage.clear());
});

Given('I am logged in as admin', async ({ page }) => {
  // storageState is loaded for the project; navigate to confirm session
  await page.goto('/admin/dashboard');
  await expect(page).toHaveURL(/\/admin\/dashboard/);
});

Given('I am logged in as a regular user', async ({ page }) => {
  await page.goto('/files');
  await expect(page).toHaveURL(/\/files/);
});

// ---------------------------------------------------------------------------
// Whens
// ---------------------------------------------------------------------------

When('I log out', async ({ page }) => {
  // Use auto-waiting click which waits for the element to be actionable (visible + stable)
  await page.getByRole('button', { name: /log ?out/i }).click();
});

// ---------------------------------------------------------------------------
// Thens
// ---------------------------------------------------------------------------

Then('I should be redirected to {string}', async ({ page }, route: string) => {
  // Escape special regex characters before constructing the pattern
  const escaped = route.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  await expect(page).toHaveURL(new RegExp(escaped), { timeout: 10_000 });
});
