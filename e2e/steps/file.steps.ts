import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { createBdd } from 'playwright-bdd';
import { expect } from '@playwright/test';

const { Given, When, Then } = createBdd();

Given('I am on the file browser page', async ({ page }) => {
  await page.goto('/files');
  await expect(page).toHaveURL(/\/files/);
});

Given('a file named {string} exists', async ({ page }, filename: string) => {
  // Check the file is already visible; if not, upload it
  const fileRow = page.getByText(filename, { exact: false });
  if (await fileRow.count() === 0) {
    await uploadTempFile(page, filename);
  }
});

Given('a folder named {string} exists', async ({ page }, folderName: string) => {
  const folderRow = page.getByText(folderName, { exact: false });
  if (await folderRow.count() === 0) {
    // Skip silently – folder creation via UI is optional for basic tests
    console.warn(`Folder "${folderName}" not found; skipping.`);
  }
});

When('I upload a file named {string}', async ({ page }, filename: string) => {
  await uploadTempFile(page, filename);
});

When('I download the file {string}', async ({ page }, filename: string) => {
  const downloadPromise = page.waitForEvent('download');
  await page.getByText(filename, { exact: false }).click();
  const downloadButton = page.getByRole('button', { name: /download/i });
  if (await downloadButton.isVisible()) {
    await downloadButton.click();
  }
  await downloadPromise;
});

When('I open the folder {string}', async ({ page }, folderName: string) => {
  await page.getByText(folderName, { exact: false }).click();
});

Then('I should see the file browser', async ({ page }) => {
  // The file browser renders a table or list of items
  // The file browser may be rendered as a <table>, a data-testid list, or show
  // an empty-state message.  Each locator is a separate fallback strategy.
  const table = page.getByRole('table');
  const dataList = page.locator('[data-testid="file-list"]');
  const emptyState = page.getByText(/no files/i);
  await expect(table.or(dataList).or(emptyState)).toBeVisible({ timeout: 10_000 });
});

Then('I should see {string} in the file list', async ({ page }, filename: string) => {
  await expect(page.getByText(filename, { exact: false })).toBeVisible({ timeout: 10_000 });
});

Then('the download should start', async () => {
  // The waitForEvent('download') in the When step ensures the download started.
  // Nothing additional to assert here.
});

Then('I should see the contents of {string}', async ({ page }, folderName: string) => {
  // After navigating into a folder the breadcrumb or path indicator should show the folder name
  await expect(page.getByText(folderName, { exact: false })).toBeVisible();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function uploadTempFile(page: import('@playwright/test').Page, filename: string) {
  const tmpFile = path.join(os.tmpdir(), filename);
  if (!fs.existsSync(tmpFile)) {
    fs.writeFileSync(tmpFile, `Test content for ${filename}\n`);
  }

  const fileInput = page.locator('input[type="file"]');
  // The upload input may be hidden; make it visible before setting file
  await fileInput.evaluate((el: HTMLInputElement) => {
    el.style.display = 'block';
    el.style.opacity = '1';
  });
  await fileInput.setInputFiles(tmpFile);

  // Click the upload button if it is separate from the input
  const uploadButton = page.getByRole('button', { name: /upload/i });
  if (await uploadButton.isVisible()) {
    await uploadButton.click();
  }
}
