import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './specs',
  timeout: 45_000,
  fullyParallel: false,
  reporter: [['line'], ['json', { outputFile: 'e2e-artifacts/browser-report.json' }], ['html', { outputFolder: 'e2e-artifacts/html', open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:3000', screenshot: 'only-on-failure', video: 'retain-on-failure', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop-1440', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'desktop-1280', use: { viewport: { width: 1280, height: 800 } } },
    { name: 'mobile-390', use: { viewport: { width: 390, height: 844 }, isMobile: true, reducedMotion: 'reduce' } },
  ],
})
