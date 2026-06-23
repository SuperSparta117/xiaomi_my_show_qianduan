<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import gsap from 'gsap'
import type { TabKey } from '../types'

const props = defineProps<{
  activeTab: TabKey
}>()

const emit = defineEmits<{
  'update:activeTab': [value: TabKey]
}>()

const indicatorRef = ref<HTMLElement | null>(null)
const navRef = ref<HTMLElement | null>(null)

const tabs: { key: TabKey; label: string }[] = [
  { key: 'mude-r', label: '-R网站' },
  { key: 'mude-t', label: '-T网站' },
  { key: 'coming-soon', label: '待开发' }
]

function moveIndicator() {
  if (!navRef.value || !indicatorRef.value) return
  const activeBtn = navRef.value.querySelector(`[data-tab="${props.activeTab}"]`) as HTMLElement
  if (!activeBtn) return

  gsap.to(indicatorRef.value, {
    x: activeBtn.offsetLeft,
    width: activeBtn.offsetWidth,
    duration: 0.4,
    ease: 'power2.out'
  })
}

onMounted(() => {
  nextTick(moveIndicator)
})

watch(() => props.activeTab, () => {
  nextTick(moveIndicator)
})

function switchTab(key: TabKey) {
  emit('update:activeTab', key)
}
</script>

<template>
  <nav ref="navRef" class="tab-nav">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      :data-tab="tab.key"
      class="tab-btn"
      :class="{ active: activeTab === tab.key }"
      @click="switchTab(tab.key)"
    >
      {{ tab.label }}
    </button>
    <div ref="indicatorRef" class="tab-indicator"></div>
  </nav>
</template>

<style scoped>
.tab-nav {
  position: relative;
  display: flex;
  gap: 4px;
  padding: 4px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin-bottom: 24px;
}

.tab-btn {
  position: relative;
  z-index: 1;
  flex: 1;
  padding: 12px 24px;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-radius: 8px;
  transition: color 0.3s ease;
}

.tab-btn:hover {
  color: rgba(255, 255, 255, 0.9);
}

.tab-btn.active {
  color: #fff;
}

.tab-indicator {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 0;
  width: 0;
  background: rgba(170, 59, 255, 0.3);
  border-radius: 8px;
  border: 1px solid rgba(170, 59, 255, 0.5);
  box-shadow: 0 0 15px rgba(170, 59, 255, 0.2);
  pointer-events: none;
}
</style>
