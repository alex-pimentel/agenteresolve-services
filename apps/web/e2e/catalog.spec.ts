import { expect, test } from '@playwright/test';

test('catalog loads and lists the 16 tools by category', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Ferramentas de IA' })).toBeVisible();
  await expect(page.getByTestId('tool-card')).toHaveCount(16);

  await expect(page.getByRole('heading', { name: 'No navegador' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Texto e LLM' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Visão' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Áudio' })).toBeVisible();
});

test('shows a beta badge for stubbed tools', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Beta').first()).toBeVisible();
});
