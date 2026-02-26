import { createBdd } from 'playwright-bdd';
import { expect } from '@playwright/test';

const { When, Then } = createBdd();

When('I navigate to {string}', async ({ page }, route: string) => {
  await page.goto(route);
});

Then('I should see {string}', async ({ page }, text: string) => {
  await expect(page.getByText(text, { exact: false })).toBeVisible({ timeout: 10_000 });
});

Then('I should see an error message', async ({ page }) => {
  // The app renders errors inside an Alert component with role="alert"
  const alert = page.locator('[role="alert"]');
  await expect(alert).toBeVisible();
});
