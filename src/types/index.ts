export interface HistoryRecord {
  date: string
  passRate: number
  failed: number
  total: number
}

export interface TestResult {
  siteName: string
  tabLabel: string
  env: string
  startTime: string
  totalCases: number
  passed: number
  failed: number
  error: number
  skipped: number
  passRate: number
  duration: string
  reportLink: string
  history: HistoryRecord[]
}

export type TabKey = 'mude-r' | 'mude-t' | 'coming-soon'
