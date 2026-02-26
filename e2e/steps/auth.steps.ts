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
  // Clear any stored auth so we start unauthenticated
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
  // The logout button is rendered in the page header / nav
  const logoutButton = page.getByRole('button', { name: /log ?out/i });
  if (await logoutButton.isVisible()) {
    await logoutButton.click();
  } else {
    // Fallback: click any logout link
    await page.getByRole('link', { name: /log ?out/i }).click();
  }
});

// ---------------------------------------------------------------------------
// Thens
// ---------------------------------------------------------------------------

Then('I should be redirected to {string}', async ({ page }, route: string) => {
  // Escape special regex characters before constructing the pattern
  const escaped = route.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  await expect(page).toHaveURL(new RegExp(escaped));
});
