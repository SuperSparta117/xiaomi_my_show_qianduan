<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import gsap from 'gsap'
import type { TestResult } from '../types'

const props = defineProps<{
  data: TestResult
}>()

const displayValues = ref({
  total: 0,
  passed: 0,
  failed: 0,
  error: 0,
  skipped: 0
})

const cardsRef = ref<HTMLElement | null>(null)

function animateNumbers() {
  gsap.to(displayValues.value, {
    total: props.data.totalCases,
    passed: props.data.passed,
    failed: props.data.failed,
    error: props.data.error,
    skipped: props.data.skipped,
    duration: 1.5,
    ease: 'power2.out'
  })
}

function animateCardsEntrance() {
  if (!cardsRef.value) return
  const cards = cardsRef.value.querySelectorAll('.stat-card')
  gsap.fromTo(
    cards,
    { opacity: 0, y: 30, scale: 0.9 },
    { opacity: 1, y: 0, scale: 1, duration: 0.6, stagger: 0.08, ease: 'back.out(1.4)' }
  )
}

onMounted(() => {
  nextTick(() => {
    animateNumbers()
    animateCardsEntrance()
  })
})

watch(() => props.data, () => {
  displayValues.value = { total: 0, passed: 0, failed: 0, error: 0, skipped: 0 }
  nextTick(() => {
    animateNumbers()
    animateCardsEntrance()
  })
})

const cards = [
  { key: 'total', label: '总用例数', color: '#1890ff' },
  { key: 'passed', label: '通过', color: '#52c41a' },
  { key: 'failed', label: '失败', color: '#ff4d4f' },
  { key: 'error', label: '错误', color: '#faad14' },
  { key: 'skipped', label: '跳过', color: '#8c8c8c' }
] as const
</script>

<template>
  <div ref="cardsRef" class="stats-grid">
    <div
      v-for="card in cards"
      :key="card.key"
      class="stat-card"
      :style="{ '--card-accent': card.color }"
    >
      <div class="stat-value">{{ Math.round(displayValues[card.key]) }}</div>
      <div class="stat-label">{{ card.label }}</div>
      <div class="stat-glow"></div>
    </div>
  </div>
</template>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  position: relative;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 16px 12px;
  text-align: center;
  overflow: hidden;
  transition: transform 0.3s ease, border-color 0.3s ease;
  cursor: default;
}

.stat-card:hover {
  transform: translateY(-4px) scale(1.02);
  border-color: var(--card-accent);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--card-accent);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
}

.stat-glow {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--card-accent);
  opacity: 0.6;
  filter: blur(2px);
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
