import { expect, test } from '@playwright/test';

test('navigating from the catalog opens the Translator page', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('link', { name: /translator/i }).click();

  await expect(page).toHaveURL(/\/translate$/);
  await expect(page.getByRole('heading', { name: 'Translator' })).toBeVisible();
  await expect(page.getByLabel('Texto')).toBeVisible();
  await expect(page.getByLabel('Idioma de destino')).toBeVisible();
  await expect(page.getByRole('button', { name: /processar/i })).toBeDisabled();
});

test('client-side Louder route surfaces the standalone app link', async ({ page }) => {
  await page.goto('/louder');
  await expect(page.getByRole('link', { name: /abrir louder/i })).toBeVisible();
});
