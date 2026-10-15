import { expect, test } from '@playwright/test';

const user = { id: 'presentation-patient', role: 'patient', email: 'patient@example.test', is_active: true, patient_profile: { id: 'patient-profile', full_name: 'Browser Patient' } };
const success = (data: unknown) => JSON.stringify({ success: true, data });

test('rich replies remain readable on mobile and tool preambles do not duplicate the final answer', async ({ page }) => {
  await page.addInitScript(u => { localStorage.setItem('spandan_user', JSON.stringify(u)); localStorage.setItem('spandan_access_token', 'isolated-browser-token'); }, user);
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (path.endsWith('/auth/me')) data = user;
    else if (path.endsWith('/service-capabilities')) data = { chat: true };
    else if (path.endsWith('/chat/conversations') && route.request().method() === 'POST') data = { id: 'presentation' };
    else if (path.endsWith('/messages')) {
      const items = Array.from({ length: 5 }, (_, i) => ({ id: String(i), full_name: `Dr Specialist ${i + 1}`, specialties: ['Cardiology'], current_workplace: 'Dhaka Specialist Hospital', availability_note: 'Hospital-sourced profile. Contact the hospital to confirm availability.', href: `/doctors/${i}` }));
      const events = [['text_delta', { text: 'Temporary tool preamble' }], ['tool_start', { name: 'search_doctors' }], ['tool_result', { tool: 'search_doctors', data: { items, next_offset: null } }], ['text_delta', { text: '## Doctors for your visit\n\nHere are **five matching doctors**.\n\n- Open a profile to review fees.\n- Confirm availability with the chamber.\n\n[See appointments](/dashboard/patient)\n\n![tracking](https://tracker.example/pixel)' }], ['done', {}]];
      return route.fulfill({ contentType: 'text/event-stream', body: events.map(([kind, payload]) => `event: ${kind}\ndata: ${JSON.stringify(payload)}\n\n`).join('') });
    }
    return route.fulfill({ contentType: 'application/json', body: success(data) });
  });
  await page.goto('/privacy');
  await page.getByRole('button', { name: 'Open Spandan Assistant' }).click();
  const panel = page.getByRole('dialog', { name: 'Spandan Assistant' });
  await panel.getByRole('checkbox').check();
  await panel.getByRole('textbox').fill('Find cardiologists in Dhaka');
  await panel.getByRole('button', { name: 'Send message' }).click();
  await expect(panel.getByRole('heading', { name: 'Doctors for your visit' })).toBeVisible();
  await expect(panel.locator('strong')).toHaveText('five matching doctors');
  await expect(panel.getByText('Temporary tool preamble')).toHaveCount(0);
  await expect(panel.locator('img')).toHaveCount(0);
  await expect(panel.getByRole('link', { name: 'View doctor & sessions' })).toHaveCount(3);
  await panel.getByRole('button', { name: 'Show 2 more in this reply' }).click();
  await expect(panel.getByRole('link', { name: 'View doctor & sessions' })).toHaveCount(5);
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await panel.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
  }
  const thread = panel.getByRole('log');
  await thread.evaluate(el => { el.scrollTop = 0; });
  await page.screenshot({ path: '/tmp/spandan-refined-chat-desktop.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '/tmp/spandan-refined-chat-results-mobile.png' });
  await panel.getByRole('link', { name: 'See appointments' }).click();
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/dashboard\/patient$/);
});

test('reading earlier messages keeps scroll position when a background reply finishes', async ({ page }) => {
  await page.addInitScript(u => { localStorage.setItem('spandan_user', JSON.stringify(u)); localStorage.setItem('spandan_access_token', 'isolated-browser-token'); }, user);
  let polls = 0;
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (path.endsWith('/auth/me')) data = user;
    else if (path.endsWith('/service-capabilities')) data = { chat: true };
    else if (path.endsWith('/chat/conversations')) data = [{ id: 'history', title: 'Earlier visits', created_at: new Date().toISOString() }];
    else if (path.endsWith('/chat/conversations/history')) {
      polls++;
      const messages = Array.from({ length: 20 }, (_, i) => ({ id: String(i), role: i % 2 ? 'assistant' : 'user', text: `Earlier message ${i}. Your appointment details and next steps remain available in your appointment page.` }));
      if (polls > 1) messages.push({ id: 'latest', role: 'assistant', text: 'Your current appointment is ready to review.' });
      data = { messages, generating: polls === 1 };
    }
    return route.fulfill({ contentType: 'application/json', body: success(data) });
  });
  await page.goto('/privacy');
  await page.getByRole('button', { name: 'Open Spandan Assistant' }).click();
  const panel = page.getByRole('dialog', { name: 'Spandan Assistant' });
  await panel.getByLabel('Conversation history').selectOption('history');
  const thread = panel.getByRole('log');
  await expect(panel.getByText('Earlier message 0.', { exact: false })).toBeAttached();
  await thread.evaluate(el => { el.scrollTop = 0; el.dispatchEvent(new Event('scroll')); });
  await expect(panel.getByText('Your current appointment is ready to review.')).toBeAttached({ timeout: 8000 });
  expect(await thread.evaluate(el => el.scrollTop)).toBeLessThan(10);
  await panel.getByRole('button', { name: 'Latest response' }).click();
  await expect.poll(() => thread.evaluate(el => el.scrollHeight - el.scrollTop - el.clientHeight)).toBeLessThan(72);
});
