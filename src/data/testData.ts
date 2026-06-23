import { reactive } from 'vue'
import type { TestResult } from '../types'

export const testResults = reactive<Record<string, TestResult>>({
  'mude-r': {
    siteName: 'MUDE-R',
    tabLabel: '-R网站',
    env: 'testlmh',
    startTime: '2026-06-23 08:01:19',
    totalCases: 386,
    passed: 344,
    failed: 41,
    error: 0,
    skipped: 1,
    passRate: 89.38,
    duration: '32分51秒',
    reportLink: 'https://test-quality.tsp.mioffice.cn/require-tsp-ui-autotest/#',
    history: [
      { date: '06-17', passRate: 87.5, failed: 48, total: 386 },
      { date: '06-18', passRate: 88.1, failed: 45, total: 386 },
      { date: '06-19', passRate: 86.8, failed: 51, total: 386 },
      { date: '06-20', passRate: 89.1, failed: 42, total: 386 },
      { date: '06-21', passRate: 88.6, failed: 44, total: 386 },
      { date: '06-22', passRate: 90.2, failed: 38, total: 386 },
      { date: '06-23', passRate: 89.38, failed: 41, total: 386 }
    ]
  },
  'mude-t': {
    siteName: 'MUDE-T',
    tabLabel: '-T网站',
    env: 'online',
    startTime: '2026-06-23 09:01:10',
    totalCases: 1146,
    passed: 1029,
    failed: 106,
    error: 1,
    skipped: 10,
    passRate: 90.66,
    duration: '107分43秒',
    reportLink: 'https://test-quality.tsp.mioffice.cn/tsp-ui-autotest/#',
    history: [
      { date: '06-17', passRate: 89.2, failed: 124, total: 1146 },
      { date: '06-18', passRate: 89.8, failed: 117, total: 1146 },
      { date: '06-19', passRate: 88.5, failed: 132, total: 1146 },
      { date: '06-20', passRate: 90.1, failed: 113, total: 1146 },
      { date: '06-21', passRate: 91.0, failed: 103, total: 1146 },
      { date: '06-22', passRate: 90.4, failed: 110, total: 1146 },
      { date: '06-23', passRate: 90.66, failed: 106, total: 1146 }
    ]
  }
})
