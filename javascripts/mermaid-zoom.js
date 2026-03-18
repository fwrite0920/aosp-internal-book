// Mermaid diagram click-to-zoom with pan and scroll-zoom.
// Works with Material theme's native mermaid rendering (open shadow DOM,
// patched from closed via overrides/main.html).
;(function () {
  var overlay = document.createElement('div')
  overlay.id = 'mermaid-zoom-overlay'
  overlay.innerHTML =
    '<div class="mermaid-zoom-toolbar">' +
      '<button id="mzm-in" title="Zoom in">+</button>' +
      '<span id="mzm-level">100%</span>' +
      '<button id="mzm-out" title="Zoom out">\u2212</button>' +
      '<button id="mzm-reset" title="Reset">\u21BA</button>' +
      '<button id="mzm-close" title="Close (Esc)">\u2715</button>' +
    '</div>' +
    '<div id="mzm-box"></div>'
  document.body.appendChild(overlay)

  var box = document.getElementById('mzm-box')
  var lvl = document.getElementById('mzm-level')
  var s = 1, dx = 0, dy = 0, drag = false, ox = 0, oy = 0

  function upd () {
    var g = box.querySelector('svg')
    if (g) g.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(' + s + ')'
    lvl.textContent = Math.round(s * 100) + '%'
  }

  // Find SVG inside element — check shadow root first, then inline
  function findSvg (el) {
    if (el.shadowRoot) {
      var svg = el.shadowRoot.querySelector('svg')
      if (svg) return svg
    }
    return el.querySelector('svg')
  }

  function show (el) {
    var svg = findSvg(el)
    if (!svg) return

    // Clone SVG preserving internal styles and viewBox
    var c = svg.cloneNode(true)

    // Give clone a unique id so its internal #mermaid-N CSS rules still work
    var origId = c.getAttribute('id') || ''
    var newId = origId + '-zoom'
    c.setAttribute('id', newId)

    // Update CSS rules inside the clone to use the new id
    var styleEl = c.querySelector('style')
    if (styleEl && origId) {
      styleEl.textContent = styleEl.textContent.split(origId).join(newId)
    }

    if (!c.getAttribute('viewBox') && svg.getBBox) {
      try {
        var bb = svg.getBBox()
        c.setAttribute('viewBox', '0 0 ' + (bb.width + bb.x) + ' ' + (bb.height + bb.y))
      } catch (e) {}
    }

    c.style.cssText = 'cursor:grab;max-width:90vw;max-height:80vh;width:auto;height:auto;transform-origin:center center'

    box.innerHTML = ''
    box.appendChild(c)
    s = 1; dx = 0; dy = 0; upd()

    overlay.style.display = 'flex'
    document.documentElement.style.overflow = 'hidden'
    document.body.style.overflow = 'hidden'
  }

  function hide () {
    overlay.style.display = 'none'
    document.documentElement.style.overflow = ''
    document.body.style.overflow = ''
    box.innerHTML = ''
  }

  function zm (d) { s = Math.max(0.2, Math.min(6, s + d)); upd() }

  document.getElementById('mzm-close').onclick = hide
  document.getElementById('mzm-in').onclick = function () { zm(0.25) }
  document.getElementById('mzm-out').onclick = function () { zm(-0.25) }
  document.getElementById('mzm-reset').onclick = function () { s = 1; dx = 0; dy = 0; upd() }

  overlay.addEventListener('wheel', function (e) {
    e.preventDefault()
    e.stopPropagation()
    zm(e.deltaY < 0 ? 0.15 : -0.15)
  }, { passive: false })

  box.addEventListener('mousedown', function (e) {
    drag = true; ox = e.clientX - dx; oy = e.clientY - dy
    var g = box.querySelector('svg'); if (g) g.style.cursor = 'grabbing'
    e.preventDefault()
  })
  document.addEventListener('mousemove', function (e) {
    if (!drag) return; dx = e.clientX - ox; dy = e.clientY - oy; upd()
  })
  document.addEventListener('mouseup', function () {
    if (!drag) return; drag = false
    var g = box.querySelector('svg'); if (g) g.style.cursor = 'grab'
  })

  overlay.addEventListener('click', function (e) {
    if (e.target === overlay || e.target === box) hide()
  })

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') hide()
    if (overlay.style.display !== 'flex') return
    if (e.key === '+' || e.key === '=') zm(0.25)
    if (e.key === '-') zm(-0.25)
    if (e.key === '0') { s = 1; dx = 0; dy = 0; upd() }
  })

  function attach () {
    var els = document.querySelectorAll('div.mermaid')
    for (var i = 0; i < els.length; i++) {
      var el = els[i]
      if (el.getAttribute('data-zoomable')) continue
      if (!findSvg(el)) continue
      el.setAttribute('data-zoomable', '1')
      el.style.cursor = 'pointer'
      el.title = 'Click to zoom diagram'
      ;(function (target) {
        target.addEventListener('click', function (e) {
          e.preventDefault()
          e.stopPropagation()
          show(target)
        })
      })(el)
    }
  }

  setInterval(attach, 1000)
  setTimeout(attach, 500)
  setTimeout(attach, 2000)
  setTimeout(attach, 5000)
})()
