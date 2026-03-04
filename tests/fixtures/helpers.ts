import { Page, expect } from '@playwright/test';

const API_BASE = process.env.REACT_APP_BACKEND_URL || 'https://merchant-integration-1.preview.emergentagent.com';

export async function waitForAppReady(page: Page) {
  await page.waitForLoadState('domcontentloaded');
}

export async function dismissToasts(page: Page) {
  await page.addLocatorHandler(
    page.locator('[data-sonner-toast], .Toastify__toast, [role="status"].toast, .MuiSnackbar-root'),
    async () => {
      const close = page.locator('[data-sonner-toast] [data-close], [data-sonner-toast] button[aria-label="Close"], .Toastify__close-button, .MuiSnackbar-root button');
      await close.first().click({ timeout: 2000 }).catch(() => {});
    },
    { times: 10, noWaitAfter: true }
  );
}

export async function checkForErrors(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const errorElements = Array.from(
      document.querySelectorAll('.error, [class*="error"], [id*="error"]')
    );
    return errorElements.map(el => el.textContent || '').filter(Boolean);
  });
}

export async function loginAsTrader(page: Page, login: string = '111', password: string = '000000') {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  
  // Click login button in header
  const loginBtn = page.getByRole('button', { name: /войти/i });
  if (await loginBtn.isVisible()) {
    await loginBtn.click();
  }
  
  // Wait for login form
  await page.waitForLoadState('domcontentloaded');
  
  // Fill login credentials
  await page.getByPlaceholder(/логин|login/i).first().fill(login);
  await page.getByPlaceholder(/пароль|password/i).first().fill(password);
  
  // Submit login
  const submitBtn = page.getByRole('button', { name: /войти/i }).first();
  await submitBtn.click();
  
  // Wait for navigation after login
  await page.waitForLoadState('domcontentloaded');
}

export async function navigateToMyOffers(page: Page) {
  // Navigate to trader's My Offers page
  await page.goto('/trader/offers');
  await page.waitForLoadState('domcontentloaded');
}

export async function getApiToken(login: string = '111', password: string = '000000'): Promise<string> {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password })
  });
  const data = await response.json();
  return data.token;
}
