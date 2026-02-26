import { createBdd } from 'playwright-bdd';
import { expect } from '@playwright/test';

const { When, Then } = createBdd();

/**
 * Fill a labelled form field.
 * Uses exact label matching so "Password" doesn't also match "Confirm Password".
 * Falls back to placeholder text.
 */
When('I fill in {string} with {string}', async ({ page }, field: string, value: string) => {
  const input = page.getByLabel(field, { exact: true });
  if (await input.count() > 0) {
    await input.fill(value);
  } else {
    await page.getByPlaceholder(field, { exact: false }).first().fill(value);
  }
});

When('I click {string}', async ({ page }, label: string) => {
  // Try button first, then link, then any element with matching text
  const button = page.getByRole('button', { name: new RegExp(label, 'i') });
  if (await button.count() > 0) {
    await button.first().click();
  } else {
    const link = page.getByRole('link', { name: new RegExp(label, 'i') });
    if (await link.count() > 0) {
      await link.first().click();
    } else {
      await page.getByText(label, { exact: false }).first().click();
    }
  }
});

Then('I should see the admin dashboard', async ({ page }) => {
  // Dashboard data loads asynchronously (AuthContext validates token → DataContext fetches settings)
  await expect(page.getByText('System Mode', { exact: false })).toBeVisible({ timeout: 15_000 });
});
