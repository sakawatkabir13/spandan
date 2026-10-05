import { test, expect, Page } from '@playwright/test';

const password = 'BrowserPassword123!';
const suffix = Date.now().toString();
const doctorEmail = `doctor-${suffix}@example.com`;
const patientEmail = `patient-${suffix}@example.com`;
let doctorId = '', scheduleId = '';

async function login(page: Page, email: string, pass = password) {
  await page.goto('/login');
  await page.getByLabel('Email Address', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(pass);
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
}

test.describe.serial('Full-stack chamber operations', () => {
  test('doctor registration, administrator verification, and staff scheduling', async ({ page, browser }) => {
    await page.goto('/register');
    await page.getByRole('button', { name: 'Doctor Practitioner' }).click();
    await page.getByLabel('Full Name', { exact: true }).fill('Browser Doctor');
    await page.getByLabel('Email Address', { exact: true }).fill(doctorEmail);
    await page.getByLabel('Phone Number', { exact: true }).fill('017' + suffix.slice(-8));
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByLabel('BMDC Registration Number', { exact: true }).fill('TEST-' + suffix);
    await page.getByRole('button', { name: 'Register as Doctor' }).click();
    await expect(page).toHaveURL(/dashboard\/doctor/);
    doctorId = await page.evaluate(() => JSON.parse(localStorage.getItem('spandan_user') || '{}').doctor_profile?.id || '');
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await login(adminPage, 'e2e-admin@example.com', 'E2EAdminPassword123!');
    await adminPage.getByRole('button', { name: 'Approve BMDC' }).click();
    await expect(adminPage.getByRole('button', { name: 'Approve BMDC' })).toHaveCount(0);
    await adminContext.close();
    await page.reload();
    // Use the authenticated real API to create test inventory; verify the editing UI below.
    const data = await page.evaluate(async () => {
      const token = localStorage.getItem('spandan_access_token');
      const headers = { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token };
      const c = await fetch('/api/v1/chambers', { method: 'POST', headers, body: JSON.stringify({ name: 'Browser Chamber', address: 'Test Road 10', district: 'Dhaka', area: 'Test Area', consultation_fee: 500, follow_up_fee: 300 }) }).then(r => r.json());
      const date = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
      const s = await fetch('/api/v1/schedules', { method: 'POST', headers, body: JSON.stringify({ chamber_id: c.data.id, schedule_date: date, start_time: '17:00', end_time: '21:00', maximum_patients: 5 }) }).then(r => r.json());
      const me = await fetch('/api/v1/auth/me', { headers }).then(r => r.json());
      return { schedule: s.data.id, doctor: me.data.doctor_profile.id };
    });
    scheduleId = data.schedule; doctorId = data.doctor;
    await page.reload();
    await expect(page.getByText('Browser Chamber').first()).toBeVisible();
    await page.getByRole('button', { name: 'Edit Chamber' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByRole('dialog').getByLabel('name', { exact: true }).fill('Browser Chamber Updated');
    await page.getByRole('button', { name: 'Save Chamber' }).click();
    await expect(page.getByText('Browser Chamber Updated').first()).toBeVisible();
  });

  test('patient registration, booking, family tools, cancellation and mobile language', async ({ page }) => {
    await page.goto('/register');
    await page.getByLabel('Full Name', { exact: true }).fill('Browser Patient');
    await page.getByLabel('Email Address', { exact: true }).fill(patientEmail);
    await page.getByLabel('Phone Number', { exact: true }).fill('018' + suffix.slice(-8));
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Register as Patient' }).click();
    await expect(page).toHaveURL(/dashboard\/patient/);
    // An expired access token must recover through the real refresh endpoint.
    await page.evaluate(() => localStorage.setItem('spandan_access_token', 'expired-test-token'));
    const refreshed = page.waitForResponse(r => r.url().endsWith('/auth/refresh') && r.status() === 200);
    await page.reload();
    await refreshed;
    await expect(page).toHaveURL(/dashboard\/patient/);
    expect(await page.evaluate(() => localStorage.getItem('spandan_access_token'))).not.toBe('expired-test-token');
    await page.goto(`/doctors/${doctorId}`);
    await page.getByRole('button', { name: 'Book Serial', exact: true }).click();
    await page.getByRole('button', { name: 'Confirm & Get Serial Number', exact: true }).click();
    await expect(page.getByText('Booking Confirmed!', { exact: true })).toBeVisible();
    await page.goto('/dashboard/patient');
    await expect(page.getByText('Browser Chamber Updated').first()).toBeVisible();
    await page.goto('/dashboard/patient/tools?tab=family');
    await page.getByLabel('full name').fill('Browser Child');
    await page.getByLabel('relationship name').fill('Child');
    await page.getByRole('button', { name: 'Add family member' }).click();
    await expect(page.getByText('Browser Child · Child')).toBeVisible();
    await page.goto('/dashboard/patient');
    await page.getByRole('button', { name: /Cancel/i }).first().click();
    await page.getByLabel('Cancellation reason').fill('Browser workflow test');
    await page.getByRole('dialog').getByRole('button', { name: 'Yes, Cancel Serial' }).click();
    await expect(page.getByText('CANCELLED', { exact: true }).first()).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/doctors');
    await page.getByRole('button', { name: 'Change language' }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'bn');
    await expect(page.getByRole('heading', { name: 'যাচাইকৃত ডাক্তারের চেম্বার খুঁজুন' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: '/tmp/spandan-mobile-preview.png', fullPage: true });
  });

  test('staff walk-in intake and queue advance', async ({ page }) => {
    await login(page, doctorEmail);
    await page.goto(`/dashboard/doctor/queue?schedule_id=${scheduleId}`);
    await page.getByLabel('New patient name').fill('Browser Walk-in');
    await page.getByLabel('Phone number', { exact: true }).fill('019' + suffix.slice(-8));
    await page.getByRole('button', { name: 'Register & book walk-in' }).click();
    await expect(page.getByText('Walk-in patient registered and booked.')).toBeVisible();
    await expect(page.getByText('Browser Walk-in').first()).toBeVisible();
    await page.getByRole('button', { name: /Call Next/i }).click();
    await expect(page.getByText('IN CONSULTATION', { exact: true }).first()).toBeVisible();
  });
});
