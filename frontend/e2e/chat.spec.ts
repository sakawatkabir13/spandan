import { expect, test } from '@playwright/test';

test('assistant consent, streaming cards, confirmation, history and mobile containment', async ({ page }) => {
  const user = { id: 'chat-browser-patient', role: 'patient', email: 'patient@example.test', is_active: true, patient_profile: { id: 'patient-profile', full_name: 'Browser Patient' } };
  const action = { id: 'chat-action', name: 'propose_checkout', status: 'pending', requires_step_up: false, expires_at: new Date(Date.now() + 300000).toISOString(), summary: { doctor_name: 'Dr. A Very Long Specialist Name For Responsive Layout Testing', attendee_name: 'Browser Patient', session_date: '2026-12-01', consultation_fee: '500.00', currency: 'bdt' } };
  let confirmations = 0;
  await page.addInitScript(u => { localStorage.setItem('spandan_user', JSON.stringify(u)); localStorage.setItem('spandan_access_token', 'isolated-browser-token'); }, user);
  const success = (data: unknown) => JSON.stringify({ success: true, data });
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (path.endsWith('/auth/me')) data = user;
    else if (path.endsWith('/service-capabilities')) data = { chat: true };
    else if (path.endsWith('/chat/conversations') && route.request().method() === 'POST') data = { id: 'browser-conversation' };
    else if (path.endsWith('/chat/conversations')) data = [{ id: 'browser-conversation', title: 'Support', created_at: new Date().toISOString() }];
    else if (path.endsWith('/messages')) {
      const events = [['progress', { message: 'Checking the current payment…' }], ['proposal', { tool: 'propose_checkout', data: { proposal: action } }], ['text', { text: 'Review this payment and confirm.' }], ['done', {}]];
      return route.fulfill({ contentType: 'text/event-stream', body: events.map(([kind, payload]) => `event: ${kind}\ndata: ${JSON.stringify(payload)}\n\n`).join('') });
    } else if (path.endsWith('/confirm')) { confirmations++; data = { ...action, status: 'succeeded', result: { message: 'Continue to secure checkout.', checkout_url: 'https://checkout.stripe.com/c/pay/test_fixture' } }; }
    return route.fulfill({ contentType: 'application/json', body: success(data) });
  });
  await page.goto('/privacy');
  await page.getByRole('button', { name: 'Open Spandan Assistant' }).click();
  const panel = page.getByRole('dialog', { name: 'Spandan Assistant' });
  await expect(panel).toBeVisible();
  await panel.getByRole('textbox').fill('Help me pay my consultation fee');
  await expect(panel.getByRole('button', { name: 'Send message' })).toBeDisabled();
  await panel.getByRole('checkbox').check();
  await panel.getByRole('button', { name: 'Send message' }).click();
  await expect(panel.getByText('Review this payment and confirm.')).toBeVisible();
  expect(confirmations).toBe(0);
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 850 });
    const bounds = await panel.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1);
    expect(await panel.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '/tmp/spandan-chat-mobile.png' });
  await panel.getByRole('button', { name: 'Confirm', exact: true }).click();
  await expect(panel.getByRole('link', { name: 'Continue to secure payment' })).toHaveAttribute('href', /checkout.stripe.com/);
  expect(confirmations).toBe(1);
  await panel.getByRole('button', { name: 'Delete conversation' }).click();
  const deletion = page.getByRole('dialog', { name: 'Delete this conversation?' });
  await expect(deletion).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(deletion).toHaveCount(0);
  await expect(panel).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
});
