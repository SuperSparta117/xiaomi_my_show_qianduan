<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'

use([GaugeChart, CanvasRenderer])

const props = defineProps<{
  passRate: number
}>()

const option = computed(() => ({
  series: [
    {
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 10,
      itemStyle: {
        color: '#aa3bff'
      },
      progress: {
        show: true,
        width: 20,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: '#ff4d4f' },
              { offset: 0.5, color: '#faad14' },
              { offset: 1, color: '#52c41a' }
            ]
          }
        }
      },
      pointer: {
        icon: 'path://M2090.36389,615.30999 L2## 90.36389,615.30999 C2## 078.50903,124.519 L2## 076.70498,-0.01 C2## 051.44695,-0.01 L2031.20498,-0.01 C2## 014.45,124.519 L2## 090.36389,615.30999 Z',
        length: '75%',
        width: 8,
        offsetCenter: [0, '5%']
      },
      axisLine: {
        lineStyle: {
          width: 20,
          color: [
            [0.7, '#ff4d4f'],
            [0.85, '#faad14'],
            [1, '#52c41a']
          ]
        }
      },
      axisTick: {
        distance: -25,
        splitNumber: 5,
        lineStyle: {
          width: 1,
          color: 'rgba(255,255,255,0.3)'
        }
      },
      splitLine: {
        distance: -30,
        length: 10,
        lineStyle: {
          width: 2,
          color: 'rgba(255,255,255,0.5)'
        }
      },
      axisLabel: {
        distance: -20,
        color: 'rgba(255,255,255,0.6)',
        fontSize: 10
      },
      anchor: {
        show: true,
        size: 16,
        itemStyle: {
          color: '#aa3bff',
          borderWidth: 3,
          borderColor: 'rgba(170, 59, 255, 0.4)'
        }
      },
      title: {
        show: true,
        offsetCenter: [0, '70%'],
        fontSize: 14,
        color: 'rgba(255,255,255,0.7)'
      },
      detail: {
        valueAnimation: true,
        fontSize: 32,
        fontWeight: 'bold',
        offsetCenter: [0, '45%'],
        formatter: '{value}%',
        color: '#fff'
      },
      data: [
        {
          value: props.passRate,
          name: '通过率'
        }
      ]
    }
  ]
}))
</script>

<template>
  <VChart :option="option" autoresize class="gauge-chart" />
</template>

<style scoped>
.gauge-chart {
  width: 100%;
  height: 240px;
}
</style>
