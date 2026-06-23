<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { HistoryRecord } from '../types'

use([LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  history: HistoryRecord[]
}>()

const option = computed(() => {
  const dates = props.history.map(h => h.date)
  const passRates = props.history.map(h => h.passRate)
  const failedCounts = props.history.map(h => h.failed)

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(20, 20, 30, 0.9)',
      borderColor: 'rgba(170, 59, 255, 0.3)',
      textStyle: { color: '#fff' },
      axisPointer: {
        type: 'cross',
        crossStyle: { color: 'rgba(255,255,255,0.3)' }
      }
    },
    legend: {
      data: ['通过率', '失败数'],
      textStyle: { color: 'rgba(255,255,255,0.7)' },
      top: '5%'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '18%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
      axisLabel: { color: 'rgba(255,255,255,0.6)' },
      boundaryGap: false
    },
    yAxis: [
      {
        type: 'value',
        name: '通过率(%)',
        min: 80,
        max: 100,
        nameTextStyle: { color: 'rgba(255,255,255,0.6)' },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
        axisLabel: { color: 'rgba(255,255,255,0.6)', formatter: '{value}%' },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
      },
      {
        type: 'value',
        name: '失败数',
        nameTextStyle: { color: 'rgba(255,255,255,0.6)' },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
        axisLabel: { color: 'rgba(255,255,255,0.6)' },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '通过率',
        type: 'line',
        smooth: true,
        yAxisIndex: 0,
        data: passRates,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 3, color: '#52c41a' },
        itemStyle: { color: '#52c41a', borderWidth: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(82, 196, 26, 0.4)' },
              { offset: 1, color: 'rgba(82, 196, 26, 0.02)' }
            ]
          }
        },
        animationDuration: 1500,
        animationEasing: 'cubicOut'
      },
      {
        name: '失败数',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: failedCounts,
        symbol: 'diamond',
        symbolSize: 8,
        lineStyle: { width: 3, color: '#ff4d4f' },
        itemStyle: { color: '#ff4d4f', borderWidth: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(255, 77, 79, 0.3)' },
              { offset: 1, color: 'rgba(255, 77, 79, 0.02)' }
            ]
          }
        },
        animationDuration: 1500,
        animationEasing: 'cubicOut',
        animationDelay: 300
      }
    ]
  }
})
</script>

<template>
  <VChart :option="option" autoresize class="trend-chart" />
</template>

<style scoped>
.trend-chart {
  width: 100%;
  height: 280px;
}
</style>
