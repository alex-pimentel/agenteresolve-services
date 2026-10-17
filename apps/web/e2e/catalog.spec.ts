import { expect, test } from '@playwright/test';

test('catalog loads and lists the 18 tools by category', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Ferramentas de IA' })).toBeVisible();
  await expect(page.getByTestId('tool-card')).toHaveCount(18);

  await expect(page.getByRole('heading', { name: 'No navegador' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Texto e LLM' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Visão' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Áudio' })).toBeVisible();
});

test('shows no beta badge while every listed tool is implemented', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('tool-card').getByText('Beta', { exact: true })).toHaveCount(0);
  await expect(page.getByText('o restante em beta')).toHaveCount(0);
});

test('client-side tools surface their standalone app link', async ({ page }) => {
  const clientTools = [
    { slug: 'louder', app: /abrir louder/i },
    { slug: 'qrcode', app: /abrir gerador de qr codes/i },
    { slug: 'imposition', app: /abrir imposition/i },
  ];

  for (const tool of clientTools) {
    await page.goto(`/${tool.slug}`);
    await expect(page.getByRole('link', { name: tool.app })).toBeVisible();
  }
});
