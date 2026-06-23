<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import gsap from 'gsap'

const containerRef = ref<HTMLElement | null>(null)
const textRef = ref<HTMLElement | null>(null)
let timeline: gsap.core.Timeline | null = null

onMounted(() => {
  if (!textRef.value || !containerRef.value) return

  timeline = gsap.timeline({ repeat: -1 })

  timeline
    .to(textRef.value, {
      y: -15,
      duration: 2,
      ease: 'sine.inOut'
    })
    .to(textRef.value, {
      y: 0,
      duration: 2,
      ease: 'sine.inOut'
    })

  gsap.fromTo(
    containerRef.value.querySelectorAll('.dot'),
    { opacity: 0.3, scale: 0.5 },
    { opacity: 1, scale: 1.2, duration: 0.6, stagger: 0.2, repeat: -1, yoyo: true, ease: 'sine.inOut' }
  )
})

onUnmounted(() => {
  timeline?.kill()
})
</script>

<template>
  <div ref="containerRef" class="coming-soon">
    <div ref="textRef" class="coming-soon-text">
      <span class="icon">🚀</span>
      <h2>待开发</h2>
      <p>功能开发中，敬请期待</p>
      <div class="dots">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    </div>
    <div class="glow-ring"></div>
  </div>
</template>

<style scoped>
.coming-soon {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  position: relative;
}

.coming-soon-text {
  text-align: center;
  z-index: 1;
}

.icon {
  font-size: 48px;
  display: block;
  margin-bottom: 16px;
}

h2 {
  font-size: 32px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  margin: 0 0 8px;
}

p {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 24px;
}

.dots {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #aa3bff;
}

.glow-ring {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  border: 2px solid rgba(170, 59, 255, 0.3);
  box-shadow: 0 0 40px rgba(170, 59, 255, 0.2), inset 0 0 40px rgba(170, 59, 255, 0.1);
  animation: pulse-ring 3s ease-in-out infinite;
}

@keyframes pulse-ring {
  0%, 100% {
    transform: scale(1);
    opacity: 0.5;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.8;
  }
}
</style>
