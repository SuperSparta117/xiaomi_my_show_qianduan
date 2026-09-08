<script setup lang="ts">
import type { TestResult } from '../types'
import StatsCards from './StatsCards.vue'
import PassRateGauge from './PassRateGauge.vue'
import ResultPieChart from './ResultPieChart.vue'
import TrendLineChart from './TrendLineChart.vue'

const props = defineProps<{
  data: TestResult
}>()
</script>

<template>
  <div class="result-panel">
    <div class="panel-header">
      <div class="header-left">
        <h2 class="site-name">{{ data.siteName }}: UI自动化测试结果</h2>
        <div class="meta-info">
          <span class="env-badge">{{ data.env }}</span>
          <span class="time">开始时间: {{ data.startTime }}</span>
          <span class="duration">耗时: {{ data.duration }}</span>
        </div>
      </div>
      <a :href="data.reportLink" target="_blank" class="report-link">
        查看详细报告 →
      </a>
    </div>

    <StatsCards :data="data" />

    <div class="charts-row">
      <div class="chart-card">
        <h3 class="chart-title">通过率</h3>
        <PassRateGauge :pass-rate="data.passRate" />
      </div>
      <div class="chart-card">
        <h3 class="chart-title">结果分布</h3>
        <ResultPieChart
          :passed="data.passed"
          :failed="data.failed"
          :error="data.error"
          :skipped="data.skipped"
        />
      </div>
    </div>

    <div class="chart-card trend-card">
      <h3 class="chart-title">历史趋势（近7天）</h3>
      <TrendLineChart :history="data.history" />
    </div>
  </div>
</template>

<style scoped>
.result-panel {
  padding: 4px 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.site-name {
  font-size: 20px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
  margin: 0 0 8px;
}

.meta-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.env-badge {
  padding: 2px 10px;
  background: rgba(170, 59, 255, 0.2);
  border: 1px solid rgba(170, 59, 255, 0.4);
  border-radius: 12px;
  font-size: 12px;
  color: #c084fc;
  font-weight: 500;
}

.time,
.duration {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.report-link {
  padding: 8px 16px;
  background: rgba(170, 59, 255, 0.15);
  border: 1px solid rgba(170, 59, 255, 0.4);
  border-radius: 8px;
  color: #c084fc;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.report-link:hover {
  background: rgba(170, 59, 255, 0.3);
  box-shadow: 0 0 20px rgba(170, 59, 255, 0.3);
  transform: translateY(-1px);
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.chart-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 16px;
}

.chart-title {
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
  margin: 0 0 8px;
}

.trend-card {
  margin-top: 0;
}

@media (max-width: 768px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
}
</style>
