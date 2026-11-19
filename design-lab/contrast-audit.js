// Dev tool: WCAG 2.1 AA text contrast audit for the current page.
// Paste into the console (or inject) and call auditContrast(document).
// Colours are resolved through a canvas, so oklch() and color-mix() work.
// Returns the failures: text, ratio, required ratio, colours, selector.
(function () {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 1
  const ctx = canvas.getContext('2d', { willReadFrequently: true })

  const rgba = (color) => {
    ctx.clearRect(0, 0, 1, 1)
    ctx.fillStyle = '#000'
    ctx.fillStyle = color
    ctx.fillRect(0, 0, 1, 1)
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data
    return [r, g, b, a / 255]
  }

  const lum = ([r, g, b]) => {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }

  const blend = (top, bottom) => {
    const a = top[3]
    return [0, 1, 2].map((i) => Math.round(top[i] * a + bottom[i] * (1 - a))).concat(1)
  }

  const backgroundOf = (el, win) => {
    const layers = []
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
      const cs = win.getComputedStyle(node)
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null // image or gradient: skip
      const c = rgba(cs.backgroundColor)
      if (c[3] > 0) layers.push(c)
      if (c[3] >= 1) break
    }
    let result = [255, 255, 255, 1]
    for (let i = layers.length - 1; i >= 0; i -= 1) result = blend(layers[i], result)
    return result
  }

  window.auditContrast = (doc = document) => {
    const win = doc.defaultView
    const failures = []
    const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT)
    const seen = new Set()
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent.trim()) continue
      const el = node.parentElement
      if (!el || seen.has(el)) continue
      seen.add(el)
      const cs = win.getComputedStyle(el)
      const rect = el.getBoundingClientRect()
      if (cs.visibility === 'hidden' || cs.display === 'none' || rect.width === 0 || rect.height === 0) continue
      if (el.closest('.sr-only, [aria-hidden="true"], .skip-link')) continue
      if (parseFloat(cs.opacity) === 0) continue
      const bg = backgroundOf(el, win)
      if (!bg) continue
      const fg = blend(rgba(cs.color), bg)
      const l1 = lum(fg); const l2 = lum(bg)
      const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
      const size = parseFloat(cs.fontSize)
      const bold = parseInt(cs.fontWeight, 10) >= 700
      const large = size >= 24 || (bold && size >= 18.66)
      const need = large ? 3 : 4.5
      const disabled = el.closest(':disabled, [aria-disabled="true"]')
      if (ratio < need && !disabled) {
        failures.push({
          text: node.textContent.trim().slice(0, 40),
          ratio: Math.round(ratio * 100) / 100,
          need,
          fg: `rgb(${fg.slice(0, 3)})`,
          bg: `rgb(${bg.slice(0, 3)})`,
          el: `${el.tagName.toLowerCase()}.${[...el.classList].join('.')}`,
        })
      }
    }
    return failures
  }
})()
