<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  passed: number
  failed: number
  error: number
  skipped: number
}>()

const option = computed(() => ({
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(20, 20, 30, 0.9)',
    borderColor: 'rgba(170, 59, 255, 0.3)',
    textStyle: { color: '#fff' },
    formatter: '{b}: {c} ({d}%)'
  },
  legend: {
    bottom: '5%',
    left: 'center',
    textStyle: { color: 'rgba(255,255,255,0.7)', fontSize: 12 }
  },
  series: [
    {
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 8,
        borderColor: 'rgba(0,0,0,0.3)',
        borderWidth: 2
      },
      label: {
        show: false,
        position: 'center'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 18,
          fontWeight: 'bold',
          color: '#fff'
        },
        itemStyle: {
          shadowBlur: 20,
          shadowColor: 'rgba(170, 59, 255, 0.5)'
        }
      },
      labelLine: { show: false },
      data: [
        { value: props.passed, name: '通过', itemStyle: { color: '#52c41a' } },
        { value: props.failed, name: '失败', itemStyle: { color: '#ff4d4f' } },
        { value: props.error, name: '错误', itemStyle: { color: '#faad14' } },
        { value: props.skipped, name: '跳过', itemStyle: { color: '#8c8c8c' } }
      ],
      animationType: 'scale',
      animationEasing: 'elasticOut',
      animationDelay: () => Math.random() * 200
    }
  ]
}))
</script>

<template>
  <VChart :option="option" autoresize class="pie-chart" />
</template>

<style scoped>
.pie-chart {
  width: 100%;
  height: 240px;
}
</style>
