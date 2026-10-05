import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { expect, Page } from '@playwright/test';

export async function readCode(email: string) {
  const inbox = process.env.E2E_MAILBOX_DIR || '/tmp/spandan-e2e-mailbox';
  const name = createHash('sha256').update(email.toLowerCase()).digest('hex');
  const message = JSON.parse(await readFile(`${inbox}/${name}.json`, 'utf8'));
  return message.body.match(/code is ([0-9]{6})/)[1] as string;
}

export async function verifyEmail(page: Page, email: string) {
  await page.getByRole('button', { name: 'Send verification code', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'six-digit verification code has been sent' })).toBeVisible();
  await page.getByLabel('Email verification code', { exact: true }).fill(await readCode(email));
}
