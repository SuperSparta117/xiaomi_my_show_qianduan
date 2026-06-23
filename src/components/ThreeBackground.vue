<script setup lang="ts">
import { ref } from 'vue'
import { useThreeBackground } from '../composables/useThreeBackground'

const canvasRef = ref<HTMLCanvasElement | null>(null)
useThreeBackground(canvasRef)
</script>

<template>
  <canvas ref="canvasRef" class="three-bg"></canvas>
</template>

<style scoped>
.three-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: -1;
  pointer-events: none;
}
</style>
