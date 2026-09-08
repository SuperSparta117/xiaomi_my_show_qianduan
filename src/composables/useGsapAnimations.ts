import gsap from 'gsap'

export function useGsapAnimations() {
  function animateTabEnter(el: HTMLElement, direction: 'left' | 'right') {
    gsap.fromTo(
      el,
      { opacity: 0, x: direction === 'right' ? 80 : -80, scale: 0.95 },
      { opacity: 1, x: 0, scale: 1, duration: 0.5, ease: 'power2.out' }
    )
  }

  function animateTabLeave(el: HTMLElement, direction: 'left' | 'right', done: () => void) {
    gsap.to(el, {
      opacity: 0,
      x: direction === 'right' ? -80 : 80,
      scale: 0.95,
      duration: 0.4,
      ease: 'power2.in',
      onComplete: done
    })
  }

  function animateCardsIn(cards: Element[]) {
    gsap.fromTo(
      cards,
      { opacity: 0, y: 30, scale: 0.9 },
      { opacity: 1, y: 0, scale: 1, duration: 0.6, stagger: 0.08, ease: 'back.out(1.4)' }
    )
  }

  function countUp(
    target: { value: number },
    endValue: number,
    duration: number = 1.5
  ) {
    gsap.fromTo(target, { value: 0 }, { value: endValue, duration, ease: 'power2.out' })
  }

  function createRipple(x: number, y: number, container: HTMLElement) {
    const ripple = document.createElement('div')
    ripple.className = 'mouse-ripple'
    ripple.style.left = `${x}px`
    ripple.style.top = `${y}px`
    container.appendChild(ripple)

    gsap.fromTo(
      ripple,
      { width: 0, height: 0, opacity: 0.7 },
      {
        width: 180,
        height: 180,
        opacity: 0,
        duration: 1.2,
        ease: 'power2.out',
        onComplete: () => ripple.remove()
      }
    )
  }

  function pulseGlow(el: HTMLElement) {
    return gsap.to(el, {
      boxShadow: '0 0 30px rgba(170, 59, 255, 0.4)',
      duration: 1.5,
      repeat: -1,
      yoyo: true,
      ease: 'sine.inOut'
    })
  }

  function floatAnimation(el: HTMLElement) {
    return gsap.to(el, {
      y: -10,
      duration: 2,
      repeat: -1,
      yoyo: true,
      ease: 'sine.inOut'
    })
  }

  return {
    animateTabEnter,
    animateTabLeave,
    animateCardsIn,
    countUp,
    createRipple,
    pulseGlow,
    floatAnimation
  }
}
