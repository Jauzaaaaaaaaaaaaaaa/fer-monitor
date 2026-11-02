/* ATELIER: mesin layar pembuka, transisi halaman, dan animasi masuk.
   Dipasang di <head> tanpa defer, setelah theme.js proyek.
   theme.js mengisi window.AT:
     label    nama proyek di layar pembuka
     glyph    teks layar pembuka jika tidak memakai intro
     intro    HTML layar pembuka khusus proyek (animasinya di theme.css)
     ms       lama layar pembuka pada kunjungan pertama
     noIntro  true jika proyek sudah punya pembuka sendiri
     cursor   true untuk memakai kursor bawaan
     bg       fungsi(body) untuk memasang latar khusus proyek */
(function () {
  var AT = window.AT || {};
  var opt = function (k, d) { return AT[k] === undefined ? d : AT[k]; };
  var html = document.documentElement;
  var glyph = opt('glyph', 'A');
  var label = opt('label', 'Atelier');
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var storage = { get: function (k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
                  set: function (k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} } };
  if (!reduce) html.classList.add('at-motion');

  /* ---------- Tirai ---------- */
  var curtain = null;
  function makeCurtain() {
    var c = document.createElement('div');
    c.className = 'at-curtain';
    c.setAttribute('aria-hidden', 'true');
    c.innerHTML = '<div class="at-curtain__a"></div><div class="at-curtain__b"></div>' +
      '<div class="at-curtain__mark"><span class="at-curtain__glyph"></span></div>' +
      '<div class="at-curtain__cap"><span class="at-curtain__name"></span><span class="at-curtain__pc"></span></div>';
    if (AT.intro) c.querySelector('.at-curtain__mark').innerHTML = AT.intro;
    else c.querySelector('.at-curtain__glyph').textContent = glyph;
    c.querySelector('.at-curtain__name').textContent = label;
    html.appendChild(c);
    return c;
  }
  function leave(c) {
    c.classList.add('is-leaving');
    setTimeout(function () { if (c.parentNode) c.parentNode.removeChild(c); }, 1400);
    html.classList.add('at-ready');
    observe();
  }

  var key = 'at-seen:' + label;
  var seen = storage.get(key);
  var introOn = !opt('noIntro', false) && !reduce;
  if (introOn) {
    curtain = makeCurtain();
    if (seen) curtain.classList.add('is-short');
    storage.set(key, '1');
    var pc = curtain.querySelector('.at-curtain__pc');
    var firstMs = opt('ms', 1500);
    var minTime = seen ? 380 : firstMs, maxTime = seen ? 1400 : firstMs + 1500, t0 = Date.now(), done = false;
    var tick = function () {
      if (done) return;
      var p = Math.min(100, Math.round((Date.now() - t0) / minTime * 100));
      if (pc) pc.textContent = String(p).padStart(3, '0');
      requestAnimationFrame(tick);
    };
    tick();
    var finish = function () {
      if (done) return;
      done = true;
      leave(curtain);
    };
    var whenLoaded = function () { setTimeout(finish, Math.max(0, minTime - (Date.now() - t0))); };
    if (document.readyState === 'complete') whenLoaded();
    else window.addEventListener('load', whenLoaded);
    setTimeout(finish, maxTime);
  } else {
    document.addEventListener('DOMContentLoaded', function () { html.classList.add('at-ready'); observe(); });
  }

  /* Halaman dari riwayat browser tidak boleh tertutup tirai */
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) {
      document.querySelectorAll('.at-curtain').forEach(function (c) { c.parentNode.removeChild(c); });
    }
  });

  /* ---------- Transisi antarhalaman ---------- */
  var FILE_LINK = /\.(pdf|csv|xlsx?|docx?|zip|sql|md|txt|png|jpe?g|webp|svg)($|\?)|\/(export|download)\b/i;
  document.addEventListener('click', function (e) {
    if (reduce || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || a.target === '_blank' || a.hasAttribute('download') || a.hasAttribute('data-no-at')) return;
    var raw = a.getAttribute('href');
    if (!raw || raw.charAt(0) === '#' || /^(javascript|mailto|tel|data):/i.test(raw)) return;
    var url;
    try { url = new URL(a.href, location.href); } catch (err) { return; }
    if (url.origin !== location.origin || FILE_LINK.test(url.pathname)) return;
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
    e.preventDefault();
    var c = makeCurtain();
    c.classList.add('is-short', 'is-entering');
    var nameEl = c.querySelector('.at-curtain__pc');
    if (nameEl) nameEl.textContent = '';
    c.getBoundingClientRect();
    c.classList.remove('is-entering');
    c.classList.add('is-covering');
    setTimeout(function () { location.href = a.href; }, 620);
    setTimeout(function () { if (c.parentNode) c.parentNode.removeChild(c); }, 5000);
  });

  /* ---------- Setelah DOM siap ---------- */
  function split(el) {
    var i = 0;
    (function walk(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          var frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach(function (w) {
            if (!w) return;
            if (/^\s+$/.test(w)) { frag.appendChild(document.createTextNode(' ')); return; }
            var o = document.createElement('span'), s = document.createElement('span');
            o.className = 'at-w';
            s.textContent = w;
            s.style.setProperty('--at-i', i++);
            o.appendChild(s);
            frag.appendChild(o);
          });
          n.parentNode.replaceChild(frag, n);
        } else if (n.nodeType === 1 && n.tagName !== 'BR') {
          walk(n);
        }
      });
    })(el);
  }

  function scribble(el) {
    el.classList.add('at-scribble');
    var ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg'), p = document.createElementNS(ns, 'path');
    svg.setAttribute('viewBox', '0 0 300 24');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('aria-hidden', 'true');
    p.setAttribute('d', 'M3 16C50 6 96 4 150 9s96 8 147-3c-55 14-112 13-170 12');
    p.setAttribute('pathLength', '1');
    svg.appendChild(p);
    el.appendChild(svg);
  }

  var io = null, ioStarted = false;
  function observe() {
    if (ioStarted) return;
    if (document.readyState === 'loading') return document.addEventListener('DOMContentLoaded', observe);
    ioStarted = true;
    var els = document.querySelectorAll('[data-at],[data-at-split]');
    if (reduce || !('IntersectionObserver' in window)) {
      els.forEach(function (e) { e.classList.add('is-in'); });
      return;
    }
    io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); }
      });
    }, { threshold: .08, rootMargin: '0px 0px -6% 0px' });
    els.forEach(function (e) { io.observe(e); });
    /* Pengaman: konten yang sudah terlihat tidak boleh tertahan jika observer tidak berjalan */
    setTimeout(function () {
      els.forEach(function (e) {
        if (e.getBoundingClientRect().top < innerHeight) { e.classList.add('is-in'); io.unobserve(e); }
      });
    }, 2600);
  }

  function chrome() {
    var fine = window.matchMedia && matchMedia('(hover:hover) and (pointer:fine)').matches;

    /* Progres dan header */
    var bar = document.createElement('div');
    bar.className = 'at-progress';
    document.body.appendChild(bar);
    var top = document.querySelector('.at-top'), last = 0, hero = document.querySelector('.at-hero__media img');
    var marq = document.querySelectorAll('.at-marquee__t');
    var ticking = false;
    function onScroll() {
      ticking = false;
      var y = window.scrollY, max = document.documentElement.scrollHeight - innerHeight;
      bar.style.setProperty('--p', max > 0 ? (y / max).toFixed(4) : 0);
      if (top) {
        top.classList.toggle('is-stuck', y > 30);
        top.classList.toggle('is-hidden', y > last && y > 160);
      }
      if (hero && !reduce) hero.style.transform = 'translateY(' + (y * -.12).toFixed(1) + 'px)';
      var v = Math.min(5, 1 + Math.abs(y - last) / 18);
      marq.forEach(function (m) {
        if (m.getAnimations) m.getAnimations().forEach(function (a) { a.playbackRate = v; });
      });
      last = y;
    }
    window.addEventListener('scroll', function () {
      if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
    }, { passive: true });
    onScroll();

    /* Marquee diulang dua kali supaya menyambung */
    marq.forEach(function (m) { m.innerHTML += m.innerHTML; });

    /* Kursor */
    if (fine && !reduce && opt('cursor', false)) {
      var cur = document.createElement('div');
      cur.className = 'at-cur';
      document.body.appendChild(cur);
      var x = -100, y = -100, tx = -100, ty = -100;
      document.addEventListener('mousemove', function (e) { tx = e.clientX; ty = e.clientY; cur.classList.add('is-on'); }, { passive: true });
      document.addEventListener('mouseover', function (e) {
        cur.classList.toggle('is-big', !!(e.target.closest && e.target.closest('a,button,summary,label,[role=button],input[type=submit]')));
      }, { passive: true });
      (function frame() {
        x += (tx - x) * .22; y += (ty - y) * .22;
        cur.style.transform = 'translate3d(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px,0)';
        requestAnimationFrame(frame);
      })();

      /* Tombol magnetik */
      document.querySelectorAll('.at-btn').forEach(function (b) {
        b.addEventListener('mousemove', function (e) {
          var r = b.getBoundingClientRect();
          b.style.transform = 'translate(' + ((e.clientX - r.left - r.width / 2) * .22).toFixed(1) + 'px,' + ((e.clientY - r.top - r.height / 2) * .3).toFixed(1) + 'px)';
        });
        b.addEventListener('mouseleave', function () { b.style.transform = ''; });
      });
    }
  }

  function ready() {
    document.body.classList.add('at');
    if (typeof AT.bg === 'function') { try { AT.bg(document.body); } catch (e) {} }
    document.querySelectorAll('[data-at-split]').forEach(split);
    document.querySelectorAll('[data-at-scribble]').forEach(scribble);
    /* Elemen selangkah diberi jeda bertahap otomatis */
    document.querySelectorAll('[data-at-stagger]').forEach(function (g) {
      Array.prototype.forEach.call(g.children, function (c, i) {
        c.setAttribute('data-at', '');
        c.style.setProperty('--at-i', Math.min(i, 10));
      });
    });
    /* Tombol: bungkus teks agar efek isi tidak menutupinya */
    document.querySelectorAll('.at-btn').forEach(function (b) {
      if (b.tagName !== 'INPUT' && !b.querySelector(':scope > span')) {
        var s = document.createElement('span');
        while (b.firstChild) s.appendChild(b.firstChild);
        b.appendChild(s);
      }
    });
    chrome();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();
})();
