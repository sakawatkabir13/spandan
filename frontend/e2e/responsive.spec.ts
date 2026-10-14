import { test, expect, Page } from '@playwright/test';
import { readCode } from './mailbox';

const password = 'ResponsiveWorkflow123!';
let doctorEmail = '', patientEmail = '', assistantEmail = '', doctorId = '', scheduleId = '', appointmentId = '';
async function contained(page: Page) {
  await expect(page.locator('main .animate-spin')).toHaveCount(0);
  await expect(page.getByRole('status').filter({ hasText: /^Loading/ })).toHaveCount(0);
  const layout = await page.evaluate(() => ({ width: innerWidth, page: document.documentElement.scrollWidth, offenders: Array.from(document.querySelectorAll('main *')).filter(element => { const rect = element.getBoundingClientRect(); return rect.width > 0 && rect.right > innerWidth + 1 && !element.closest('[class*="overflow-x-auto"]'); }).slice(0, 5).map(element => element.tagName + ':' + element.className) }));
  expect(layout.page, JSON.stringify(layout)).toBeLessThanOrEqual(layout.width + 1);
}
async function login(page: Page, email: string, pass = password) {
  await page.goto('/login');
  await page.getByLabel('Email Address', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(pass);
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
}

test.beforeAll(async ({ request }) => {
  const suffix = Date.now().toString();
  doctorEmail = `ux-doctor-${suffix}@example.com`; patientEmail = `ux-patient-${suffix}@example.com`; assistantEmail = `ux-assistant-${suffix}@example.com`;
  async function create(role: string, email: string, extra: Record<string, unknown> = {}, headers: Record<string, string> = {}) {
    expect((await request.post('/api/v1/auth/registration-code', { data: { email } })).ok()).toBeTruthy();
    const response = await request.post(`/api/v1/auth/register/${role}`, { headers, data: { email, email_otp: await readCode(email), password, full_name: role === 'doctor' ? 'Dr. Responsive Care Specialist With A Long Professional Name' : 'Responsive Browser Patient With A Long Name', phone_number: (role === 'doctor' ? '016' : role === 'patient' ? '015' : '014') + suffix.slice(-8), ...extra } });
    expect(response.ok(), await response.text()).toBeTruthy();
    return (await response.json()).data;
  }
  const doctor = await create('doctor', doctorEmail, { medical_registration_number: `UX-${suffix}` });
  doctorId = doctor.user.doctor_profile.id;
  const headers = { Authorization: `Bearer ${doctor.access_token}` };
  const admin = (await (await request.post('/api/v1/auth/login', { data: { email: 'e2e-admin@example.com', password: 'E2EAdminPassword123!' } })).json()).data;
  expect((await request.post(`/api/v1/doctors/${doctorId}/verify`, { headers: { Authorization: `Bearer ${admin.access_token}` }, data: { status: 'approved' } })).ok()).toBeTruthy();
  const chamber = (await (await request.post('/api/v1/chambers', { headers, data: { name: 'Comprehensive Specialist Consultation and Diagnostic Chamber', address: 'Medical Road, Dhaka', district: 'Dhaka', area: 'Dhanmondi', consultation_fee: 500, follow_up_fee: 300 } })).json()).data;
  scheduleId = (await (await request.post('/api/v1/schedules', { headers, data: { chamber_id: chamber.id, schedule_date: new Date(Date.now() + 86400000).toISOString().slice(0, 10), start_time: '17:00', end_time: '20:00', maximum_patients: 10 } })).json()).data.id;
  await create('assistant', assistantEmail, { doctor_id: doctorId }, headers);
  const patient = await create('patient', patientEmail);
  appointmentId = (await (await request.post('/api/v1/appointments', { headers: { Authorization: `Bearer ${patient.access_token}` }, data: { schedule_id: scheduleId, patient_note: 'Please review my reports before the visit.' } })).json()).data.id;
});

test('public pages fit phones, tablets, and desktop', async ({ page }) => {
  test.setTimeout(180000);
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ['/', '/login', '/register', '/forgot-password', '/doctors', '/doctors?view=booking', `/doctors/${doctorId}`, '/ai-triage', '/privacy', '/terms', '/medical-disclaimer']) {
      await page.goto(path); await expect(page.locator('main')).toBeVisible(); await expect(page.getByRole('heading').first()).toBeVisible(); await contained(page);
    }
  }
});

test('patient payment actions, history, cancellation recovery, and mobile menu', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, patientEmail);
  const card = page.getByTestId('appointment-card').filter({ hasText: 'Dr. Responsive Care Specialist' });
  await expect(card.getByRole('link', { name: 'Pay consultation fee', exact: true })).toBeVisible();
  await contained(page);
  await card.getByRole('link', { name: 'Pay consultation fee', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: '/tmp/spandan-ux-patient-mobile.png' });
  await expect(page.getByRole('navigation', { name: 'Dashboard navigation' })).toBeHidden();
  await page.getByRole('button', { name: /Menu/ }).click();
  await expect(page.getByRole('navigation', { name: 'Dashboard navigation' })).toBeVisible();
  await card.getByRole('link', { name: 'Pay consultation fee', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/dashboard/patient/payments\\?appointment_id=${appointmentId}`));
  await expect(page.getByRole('button', { name: 'Pay consultation fee', exact: true })).toBeVisible(); await contained(page);
  await page.goto(`/dashboard/patient/tools?tab=billing&appointment_id=${appointmentId}&checkout=cancelled`);
  await expect(page).toHaveURL(/patient\/payments\?.*checkout=cancelled/);
  await expect(page.getByRole('status').filter({ hasText: 'Checkout was closed' })).toBeVisible();
  await page.getByRole('link', { name: 'Back to appointments', exact: true }).click();
  await card.getByRole('button', { name: 'Cancel booking', exact: true }).click();
  const dialog = page.getByRole('dialog'); await expect(dialog).toBeVisible();
  expect(await dialog.evaluate(element => element.parentElement?.parentElement?.tagName)).toBe('BODY');
  await dialog.getByLabel('Cancellation reason', { exact: true }).fill('Testing friendly cancellation');
  await page.route(`**/api/v1/appointments/${appointmentId}/status`, route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ success: false, error: { message: 'Please try again shortly.' } }) }));
  await dialog.getByRole('button', { name: 'Yes, Cancel Serial', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('Please try again shortly.');
  await page.unroute(`**/api/v1/appointments/${appointmentId}/status`);
  await dialog.getByRole('button', { name: 'Yes, Cancel Serial', exact: true }).click(); await expect(dialog).toHaveCount(0);
  await page.getByRole('button', { name: /^History/ }).click();
  await expect(card.getByText('Cancelled', { exact: true })).toBeVisible();
  await expect(card.getByRole('link', { name: 'Pay consultation fee', exact: true })).toHaveCount(0);
});

test('all role workspaces fit mobile, tablet, and desktop', async ({ page }) => {
  test.setTimeout(240000);
  for (const role of ['patient', 'doctor', 'assistant', 'admin']) {
    await login(page, role === 'patient' ? patientEmail : role === 'doctor' ? doctorEmail : role === 'assistant' ? assistantEmail : 'e2e-admin@example.com', role === 'admin' ? 'E2EAdminPassword123!' : password);
    const root = `/dashboard/${role}`;
    const paths = [root, `${root}/profile`, `${root}/tools?tab=notifications`, `${root}/tools?tab=security`, `${root}/tools?tab=privacy`, ...(role === 'patient' ? [`${root}/payments?appointment_id=${appointmentId}`, `${root}/tools?tab=family`, `${root}/tools?tab=waitlist`] : [`${root}/queue?schedule_id=${scheduleId}`, `${root}/tools?tab=calendar`, `${root}/tools?tab=analytics`, `${root}/tools?tab=billing`]), ...(role === 'doctor' ? [`${root}/chambers`] : role === 'admin' ? [`${root}/verifications`, `${root}/users`, `${root}/tools?tab=directory`] : [])];
    for (const width of [320, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const path of paths) { await page.goto(path); await expect(page.locator('main')).toBeVisible(); await expect(page.locator('main h1, main h2, main h3').first()).toBeVisible(); await contained(page); }
      if (role === 'doctor' && width === 1440) { await page.goto(`${root}/queue?schedule_id=${scheduleId}`); await contained(page); await page.screenshot({ path: '/tmp/spandan-ux-doctor-desktop.png', fullPage: true }); }
    }
  }
});

test('clearing filters refreshes results and sign-in preserves the selected doctor', async ({ page }) => {
  await page.goto('/doctors?view=booking');
  await page.getByLabel('District', { exact: true }).fill('No such district'); await page.getByRole('button', { name: 'Filter Results', exact: true }).click();
  await expect(page.getByText('No doctors found matching your criteria', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await expect(page.getByLabel('District', { exact: true })).toHaveValue('');
  await expect(page.getByRole('link', { name: 'View Chambers & Book', exact: true }).first()).toBeVisible();
  await page.goto(`/doctors/${doctorId}`); await page.getByRole('button', { name: 'Book Serial', exact: true }).first().click(); await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Email Address', { exact: true }).fill(patientEmail); await page.getByLabel('Password', { exact: true }).fill(password); await page.getByRole('button', { name: 'Sign In', exact: true }).click(); await expect(page).toHaveURL(new RegExp(`/doctors/${doctorId}$`));
});
