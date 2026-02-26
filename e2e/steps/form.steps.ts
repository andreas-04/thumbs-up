import { createBdd } from 'playwright-bdd';
import { expect } from '@playwright/test';

const { When, Then } = createBdd();

/**
 * Fill a labelled form field.
 * Tries <label> text match first; falls back to placeholder text.
 */
When('I fill in {string} with {string}', async ({ page }, field: string, value: string) => {
  const input = page.getByLabel(field, { exact: false });
  if (await input.count() > 0) {
    await input.fill(value);
  } else {
    await page.getByPlaceholder(field, { exact: false }).fill(value);
  }
});

When('I click {string}', async ({ page }, label: string) => {
  // Try button first, then link, then any element with matching text
  const button = page.getByRole('button', { name: new RegExp(label, 'i') });
  if (await button.count() > 0) {
    await button.click();
  } else {
    const link = page.getByRole('link', { name: new RegExp(label, 'i') });
    if (await link.count() > 0) {
      await link.click();
    } else {
      await page.getByText(label, { exact: false }).first().click();
    }
  }
});

Then('I should see the admin dashboard', async ({ page }) => {
  await expect(page.getByText('System Mode', { exact: false })).toBeVisible();
});
