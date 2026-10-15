import { expect, test } from '@playwright/test';

test('signed-out account controls fit small phones in both languages', async ({ page }) => {
  for (const language of ['en', 'bn']) {
    await page.goto('/privacy');
    await page.evaluate(value => localStorage.setItem('spandan_language', value), language);
    await page.reload();
    for (const width of [320, 360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const layout = await page.locator('header').evaluate(el => {
        const bar = el.firstElementChild!;
        const bounds = bar.getBoundingClientRect();
        const edge = bounds.right - parseFloat(getComputedStyle(bar).paddingRight);
        const controls = bar.lastElementChild!.getBoundingClientRect();
        return { width: innerWidth, page: document.documentElement.scrollWidth, header: el.scrollWidth, edge, controlsRight: controls.right };
      });
      expect(layout.page, `${language}: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(width + 1);
      expect(layout.header, `${language}: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(width + 1);
      expect(layout.controlsRight, `${language}: account controls must preserve the page gutter`).toBeLessThanOrEqual(layout.edge + 1);
    }
  }
});

test('signed-in navigation fits every role at tablet breakpoints in both languages', async ({ page }) => {
  let role = 'patient';
  await page.addInitScript(() => {
    localStorage.setItem('spandan_access_token', 'navigation-fixture-token');
    localStorage.setItem('spandan_user', JSON.stringify({ id: 'navigation-fixture', role: 'patient', full_name: 'Responsiveprofessional Long Name', email: 'navigation@example.test' }));
  });
  await page.route('**/api/v1/**', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true, data: new URL(route.request().url()).pathname.endsWith('/auth/me') ? { id: 'navigation-fixture', role, full_name: 'Responsiveprofessional Long Name', email: 'navigation@example.test' } : {} }) }));
  for (role of ['patient', 'doctor', 'assistant', 'administrator']) {
    for (const language of ['en', 'bn']) {
      await page.goto('/privacy');
      await page.evaluate(value => localStorage.setItem('spandan_language', value), language);
      await page.reload();
      await expect(page.getByRole('button', { name: language === 'en' ? 'Logout' : 'সাইন আউট' })).toBeVisible();
      for (const width of [320, 767, 768, 820, 1024, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        const layout = await page.locator('header').evaluate(el => ({ width: innerWidth, page: document.documentElement.scrollWidth, header: el.scrollWidth }));
        expect(layout.page, `${role}/${language}: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(width + 1);
        expect(layout.header, `${role}/${language}: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(width + 1);
      }
    }
  }
});
