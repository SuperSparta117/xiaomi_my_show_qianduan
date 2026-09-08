import { onMounted, onUnmounted, type Ref } from 'vue'
import * as THREE from 'three'

export function useThreeBackground(canvasRef: Ref<HTMLCanvasElement | null>) {
  let scene: THREE.Scene
  let camera: THREE.PerspectiveCamera
  let renderer: THREE.WebGLRenderer
  let particles: THREE.Points
  let animationId: number
  let clock: THREE.Clock

  const PARTICLE_COUNT = 2000

  function init() {
    if (!canvasRef.value) return

    clock = new THREE.Clock()
    scene = new THREE.Scene()

    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000)
    camera.position.z = 50

    renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.value,
      alpha: true,
      antialias: true
    })
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

    const geometry = new THREE.BufferGeometry()
    const positions = new Float32Array(PARTICLE_COUNT * 3)
    const colors = new Float32Array(PARTICLE_COUNT * 3)

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3
      positions[i3] = (Math.random() - 0.5) * 100
      positions[i3 + 1] = (Math.random() - 0.5) * 100
      positions[i3 + 2] = (Math.random() - 0.5) * 50

      const purple = 0.4 + Math.random() * 0.3
      colors[i3] = 0.5 + Math.random() * 0.3
      colors[i3 + 1] = 0.2 + Math.random() * 0.2
      colors[i3 + 2] = purple + Math.random() * 0.3
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

    const material = new THREE.PointsMaterial({
      size: 0.5,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    })

    particles = new THREE.Points(geometry, material)
    scene.add(particles)

    window.addEventListener('resize', handleResize)
    animate()
  }

  function animate() {
    animationId = requestAnimationFrame(animate)

    const elapsed = clock.getElapsedTime()
    const positions = particles.geometry.attributes.position.array as Float32Array

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3
      const x = positions[i3]
      positions[i3 + 1] += Math.sin(x * 0.05 + elapsed * 0.5) * 0.02
      positions[i3] += Math.cos(elapsed * 0.3 + i * 0.01) * 0.01
    }

    particles.geometry.attributes.position.needsUpdate = true
    particles.rotation.y = elapsed * 0.02

    renderer.render(scene, camera)
  }

  function handleResize() {
    if (!renderer) return
    camera.aspect = window.innerWidth / window.innerHeight
    camera.updateProjectionMatrix()
    renderer.setSize(window.innerWidth, window.innerHeight)
  }

  function dispose() {
    cancelAnimationFrame(animationId)
    window.removeEventListener('resize', handleResize)
    if (particles) {
      particles.geometry.dispose()
      ;(particles.material as THREE.Material).dispose()
    }
    if (renderer) {
      renderer.dispose()
    }
  }

  onMounted(() => init())
  onUnmounted(() => dispose())
}
