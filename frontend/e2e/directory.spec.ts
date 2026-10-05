import { test, expect } from '@playwright/test';

test('public directory covers Bangladesh and does not offer unconfirmed booking', async ({ page }) => {
  await page.goto('/doctors');
  await expect(page.getByRole('heading', { name: 'Find doctors across Bangladesh' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: '22 public hospital listings' })).toBeVisible();
  await page.getByLabel('Division', { exact: true }).selectOption('Sylhet');
  await expect(page.getByRole('status').filter({ hasText: '3 public hospital listings' })).toBeVisible();
  await page.getByLabel('Doctor, specialty or hospital').fill('Ayesha');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '1 public hospital listings' })).toBeVisible();
  await page.getByRole('link', { name: 'View hospital listing', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Dr. Ayesha Rafiq Chowdhury', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Call hospital: +8809610009640' })).toHaveAttribute('href', 'tel:+8809610009640');
  await expect(page.getByRole('link', { name: 'Official hospital source' })).toHaveAttribute('href', /ibnsinahospitalsylhet.com.bd/);
  await expect(page.getByText('Online booking through Spandan is unavailable', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Book Serial' })).toHaveCount(0);
  await expect(page.getByText('BMDC Verified', { exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('link', { name: 'Back to hospital directory' }).click();
  await page.getByLabel('Division', { exact: true }).selectOption('Khulna');
  await expect(page.getByRole('status').filter({ hasText: '2 public hospital listings' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('administrator can hide and republish a public listing', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email Address', { exact: true }).fill('e2e-admin@example.com');
  await page.getByLabel('Password', { exact: true }).fill('E2EAdminPassword123!');
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
  await page.goto('/dashboard/admin/tools?tab=directory');
  const listing = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Prof. Dr. Md. Atahar Ali', exact: true }) });
  await listing.getByRole('button', { name: 'Hide listing' }).click();
  await expect(listing.getByRole('button', { name: 'Publish listing' })).toBeVisible();
  expect((await (await page.request.get('/api/v1/directory/doctors?query=Atahar')).json()).data.total).toBe(0);
  await listing.getByRole('button', { name: 'Publish listing' }).click();
  await expect(listing.getByRole('button', { name: 'Hide listing' })).toBeVisible();
  expect((await (await page.request.get('/api/v1/directory/doctors?query=Atahar')).json()).data.total).toBe(1);
});
