<script setup lang="ts">
import { ref, computed } from 'vue'
import gsap from 'gsap'
import type { TabKey } from './types'
import { testResults } from './data/testData'
import ThreeBackground from './components/ThreeBackground.vue'
import MouseRippleEffect from './components/MouseRippleEffect.vue'
import TabNavigation from './components/TabNavigation.vue'
import TestResultPanel from './components/TestResultPanel.vue'
import ComingSoon from './components/ComingSoon.vue'

const activeTab = ref<TabKey>('mude-r')
const prevTabIndex = ref(0)

const tabIndexMap: Record<TabKey, number> = {
  'mude-r': 0,
  'mude-t': 1,
  'coming-soon': 2
}

const direction = computed(() => {
  return tabIndexMap[activeTab.value] > prevTabIndex.value ? 'right' : 'left'
})

const currentData = computed(() => {
  if (activeTab.value === 'coming-soon') return null
  return testResults[activeTab.value]
})

function onTabChange(newTab: TabKey) {
  prevTabIndex.value = tabIndexMap[activeTab.value]
  activeTab.value = newTab
}

function onBeforeEnter(el: Element) {
  const htmlEl = el as HTMLElement
  gsap.set(htmlEl, {
    opacity: 0,
    x: direction.value === 'right' ? 80 : -80,
    scale: 0.95
  })
}

function onEnter(el: Element, done: () => void) {
  const htmlEl = el as HTMLElement
  gsap.to(htmlEl, {
    opacity: 1,
    x: 0,
    scale: 1,
    duration: 0.5,
    ease: 'power2.out',
    onComplete: done
  })
}

function onLeave(el: Element, done: () => void) {
  const htmlEl = el as HTMLElement
  gsap.to(htmlEl, {
    opacity: 0,
    x: direction.value === 'right' ? -80 : 80,
    scale: 0.95,
    duration: 0.4,
    ease: 'power2.in',
    onComplete: done
  })
}
</script>

<template>
  <ThreeBackground />
  <MouseRippleEffect />

  <div class="dashboard-wrapper">
    <div class="dashboard-container">
      <header class="dashboard-header">
        <h1 class="dashboard-title">UI 自动化测试监控</h1>
        <p class="dashboard-subtitle">Bug 增量趋势追踪</p>
      </header>

      <TabNavigation
        :active-tab="activeTab"
        @update:active-tab="onTabChange"
      />

      <div class="tab-content-wrapper">
        <Transition
          :css="false"
          mode="out-in"
          @before-enter="onBeforeEnter"
          @enter="onEnter"
          @leave="onLeave"
        >
          <TestResultPanel
            v-if="currentData"
            :key="activeTab"
            :data="currentData"
          />
          <ComingSoon v-else :key="'coming-soon'" />
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 40px 20px;
}

.dashboard-container {
  width: 100%;
  max-width: 1100px;
  background: rgba(22, 23, 29, 0.75);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  padding: 32px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(170, 59, 255, 0.05);
}

.dashboard-header {
  text-align: center;
  margin-bottom: 24px;
}

.dashboard-title {
  font-size: 28px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
  margin: 0 0 4px;
  background: linear-gradient(135deg, #fff 0%, #c084fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.dashboard-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.tab-content-wrapper {
  position: relative;
  min-height: 500px;
}
</style>
