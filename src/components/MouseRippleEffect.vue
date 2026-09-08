<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useGsapAnimations } from '../composables/useGsapAnimations'

const containerRef = ref<HTMLElement | null>(null)
const { createRipple } = useGsapAnimations()

let lastTime = 0
const THROTTLE_MS = 30

function handleMouseMove(e: MouseEvent) {
  const now = Date.now()
  if (now - lastTime < THROTTLE_MS) return
  lastTime = now

  if (containerRef.value) {
    createRipple(e.clientX, e.clientY, containerRef.value)
  }
}

onMounted(() => {
  document.addEventListener('mousemove', handleMouseMove)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove)
})
</script>

<template>
  <div ref="containerRef" class="ripple-container"></div>
</template>

<style scoped>
.ripple-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 9999;
  overflow: hidden;
}

.ripple-container :deep(.mouse-ripple) {
  position: absolute;
  border-radius: 50%;
  border: 3px solid rgba(170, 59, 255, 0.6);
  background: radial-gradient(circle, rgba(170, 59, 255, 0.15) 0%, transparent 70%);
  transform: translate(-50%, -50%);
  pointer-events: none;
  box-shadow: 0 0 12px rgba(170, 59, 255, 0.3);
}
</style>
