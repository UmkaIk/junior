/* Laman — каталог, карусель, корзина и расчёт доставки. Без библиотек. */

/*
 * НАСТРОЙКИ МАГАЗИНА — всё, что меняется, только здесь.
 * ⚠ Значения с пометкой ЗАГЛУШКА не настоящие: заменить на согласованные
 *   до открытия приёма заказов, потом поставить draft: false.
 */
const CONFIG = {
  // ЗАГЛУШКА: номер продавца не предоставлен. Пока здесь нули, кнопка заказа
  // не отправляет сообщение, а показывает его для копирования.
  whatsapp: '70000000000',
  // Ссылка на Instagram ещё не предоставлена. Пустая — в контактах не показывается.
  instagram: '',
  // Пока true — сверху висит честное пояснение про предварительные цены.
  draft: true,
  area: 'по Грозному',
  delivery: {
    fee: 200,        // ЗАГЛУШКА: стоимость доставки, ₽
    freeFrom: 2000,  // ЗАГЛУШКА: бесплатно от этой суммы товаров, ₽ (0 — порога нет)
    sameDay: true,   // «в день заказа» — из согласованного подзаголовка
  },
  payment: [
    'Наличными или переводом при получении', // ЗАГЛУШКА: уточнить способы оплаты
  ],
  // ЗАГЛУШКА: фасовки и цены. weight — граммы, price — ₽ за упаковку.
  products: [
    { id: 'apricot', name: 'Курага',    note: 'Сушёный абрикос без косточки', tint: '#e0913a',
      packs: [{ weight: 250, price: 290 }, { weight: 500, price: 560 }, { weight: 1000, price: 1080 }] },
    { id: 'dates',   name: 'Финики',    note: 'Сушёные финики',               tint: '#8a5530',
      packs: [{ weight: 250, price: 250 }, { weight: 500, price: 480 }, { weight: 1000, price: 920 }] },
    { id: 'fig',     name: 'Инжир',     note: 'Сушёный инжир',                tint: '#7d4c6a',
      packs: [{ weight: 250, price: 390 }, { weight: 500, price: 760 }, { weight: 1000, price: 1480 }] },
    { id: 'prune',   name: 'Чернослив', note: 'Сушёная слива',                tint: '#4a3044',
      packs: [{ weight: 250, price: 270 }, { weight: 500, price: 520 }, { weight: 1000, price: 1000 }] },
    { id: 'raisin',  name: 'Изюм',      note: 'Сушёный виноград',             tint: '#a9822f',
      packs: [{ weight: 250, price: 210 }, { weight: 500, price: 400 }, { weight: 1000, price: 760 }] },
  ],
};

const STORAGE_KEY = 'laman-cart-v1';
const $ = (sel, root = document) => root.querySelector(sel);
const money = (n) => new Intl.NumberFormat('ru-RU').format(n) + ' ₽';
const weightLabel = (g) => (g >= 1000 ? `${g / 1000} кг`.replace('.', ',') : `${g} г`);
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
};
const announce = (text) => {
  const live = $('#live');
  live.textContent = '';
  requestAnimationFrame(() => { live.textContent = text; });
};

const waNumber = () => {
  const digits = String(CONFIG.whatsapp || '').replace(/\D/g, '');
  return digits.length >= 10 && !/^7?0+$/.test(digits) ? digits : '';
};

/* ---------- Картинки ---------- */

// Пока настоящих фото упаковок нет в assets/, рисуем аккуратную заглушку-пакет.
function packFallback(p) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300">
<rect width="300" height="300" fill="#f6eedd"/>
<ellipse cx="150" cy="268" rx="88" ry="10" fill="#000" opacity=".08"/>
<path d="M78 58 Q150 46 222 58 L232 254 Q150 266 68 254 Z" fill="${p.tint}"/>
<path d="M78 58 Q150 46 222 58 L223 74 Q150 62 77 74 Z" fill="#000" opacity=".12"/>
<rect x="96" y="112" width="108" height="96" rx="10" fill="#fffdf8"/>
<path d="M150 124 l9 9 -9 9 -9 -9 Z" fill="#c49a4a"/>
<text x="150" y="172" text-anchor="middle" font-family="Georgia,serif" font-size="19" fill="#1f4d3a">${p.name}</text>
<text x="150" y="194" text-anchor="middle" font-family="Georgia,serif" font-size="11" letter-spacing="2" fill="#8a6420">LAMAN</text>
</svg>`;
  return 'data:image/svg+xml,' + encodeURIComponent(svg);
}

function productImg(p, { eager = false } = {}) {
  const img = document.createElement('img');
  img.src = `assets/${p.id}.webp`;
  img.alt = `${p.name} в упаковке Laman`;
  img.width = 300;
  img.height = 300;
  img.decoding = 'async';
  if (!eager) img.loading = 'lazy';
  img.addEventListener('error', () => { img.src = packFallback(p); }, { once: true });
  return img;
}

/* ---------- Корзина: состояние ---------- */

const productById = Object.fromEntries(CONFIG.products.map((p) => [p.id, p]));
let cart = loadCart(); // { 'apricot:500': 2, ... }

function loadCart() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    const clean = {};
    for (const [key, qty] of Object.entries(raw)) {
      const [id, w] = key.split(':');
      const p = productById[id];
      if (p && p.packs.some((x) => x.weight === Number(w)) && qty > 0) clean[key] = Math.min(99, qty | 0);
    }
    return clean;
  } catch { return {}; }
}
function saveCart() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cart)); } catch { /* приватный режим */ }
}

function lines() {
  return Object.entries(cart).map(([key, qty]) => {
    const [id, w] = key.split(':');
    const p = productById[id];
    const pack = p.packs.find((x) => x.weight === Number(w));
    return { key, p, pack, qty, sum: pack.price * qty };
  });
}

function totals() {
  const ls = lines();
  const items = ls.reduce((s, l) => s + l.sum, 0);
  const count = ls.reduce((s, l) => s + l.qty, 0);
  const { fee, freeFrom } = CONFIG.delivery;
  const free = freeFrom > 0 && items >= freeFrom;
  const delivery = count === 0 ? 0 : free ? 0 : fee;
  return { ls, items, count, delivery, free, total: items + delivery, left: freeFrom > 0 ? Math.max(0, freeFrom - items) : 0 };
}

function setQty(key, qty) {
  if (qty <= 0) delete cart[key];
  else cart[key] = Math.min(99, qty);
  saveCart();
  render();
}

/* ---------- Каталог ---------- */

const selected = {}; // выбранная фасовка в карточке: { apricot: 500 }

function renderCatalog() {
  const grid = $('#catalog-grid');
  grid.innerHTML = '';
  for (const p of CONFIG.products) {
    selected[p.id] ??= p.packs[0].weight;
    const li = document.createElement('li');
    li.className = 'card';
    li.id = `p-${p.id}`;
    li.innerHTML = `
      <div class="card__media"></div>
      <div class="card__body">
        <h3 class="card__title">${p.name}</h3>
        <p class="card__note">${p.note}</p>
        <fieldset class="packs">
          <legend class="sr-only">Фасовка: ${p.name}</legend>
          ${p.packs.map((x) => `
            <label class="pack">
              <input type="radio" name="pack-${p.id}" value="${x.weight}" ${x.weight === selected[p.id] ? 'checked' : ''}>
              <span>${weightLabel(x.weight)}</span>
            </label>`).join('')}
        </fieldset>
        <div class="card__price">
          <span class="price" data-price></span>
          <span class="per-kg" data-per-kg></span>
        </div>
        <div class="card__action" data-action></div>
      </div>`;
    $('.card__media', li).append(productImg(p));
    li.querySelectorAll('input[type=radio]').forEach((r) =>
      r.addEventListener('change', () => { selected[p.id] = Number(r.value); updateCard(p); }));
    grid.append(li);
    updateCard(p);
  }
}

function updateCard(p) {
  const li = $(`#p-${p.id}`);
  const w = selected[p.id];
  const pack = p.packs.find((x) => x.weight === w);
  $('[data-price]', li).textContent = money(pack.price);
  $('[data-per-kg]', li).textContent = w === 1000 ? '' : `${money(Math.round(pack.price * 1000 / w))} за кг`;

  const key = `${p.id}:${w}`;
  const qty = cart[key] || 0;
  const box = $('[data-action]', li);
  const hadFocus = box.contains(document.activeElement) ? document.activeElement.dataset.role : null;
  const label = `${p.name}, ${weightLabel(w).replace(' ', ' ')}`;
  box.innerHTML = qty
    ? `<div class="stepper" role="group" aria-label="Количество: ${label}">
         <button type="button" class="stepper__btn" data-role="minus" aria-label="Убрать одну упаковку">−</button>
         <span class="stepper__val" aria-live="polite">${qty}&nbsp;шт.</span>
         <button type="button" class="stepper__btn" data-role="plus" aria-label="Добавить ещё одну упаковку">+</button>
       </div>`
    : `<button type="button" class="btn btn--primary btn--wide" data-role="add">В корзину</button>`;
  const on = (role, fn) => { const b = $(`[data-role=${role}]`, box); if (b) b.addEventListener('click', fn); };
  on('add', () => { setQty(key, 1); announce(`${label} — в корзине`); focusRole(box, 'plus'); });
  on('plus', () => setQty(key, qty + 1));
  on('minus', () => { setQty(key, qty - 1); if (qty - 1 === 0) { announce(`${label} убран из корзины`); focusRole(box, 'add'); } });
  if (hadFocus) focusRole(box, hadFocus);
}
function focusRole(box, role) {
  requestAnimationFrame(() => { const b = $(`[data-role=${role}]`, box) || $('button', box); b && b.focus(); });
}

/* ---------- Карусель ---------- */

function renderCarousel() {
  const track = $('#carousel-track');
  const dots = $('#carousel-dots');
  const n = CONFIG.products.length;
  CONFIG.products.forEach((p, i) => {
    const min = Math.min(...p.packs.map((x) => x.price));
    const slide = document.createElement('a');
    slide.className = 'slide';
    slide.href = `#p-${p.id}`;
    slide.setAttribute('role', 'group');
    slide.setAttribute('aria-roledescription', 'слайд');
    slide.setAttribute('aria-label', `${i + 1} из ${n}: ${p.name}, от ${money(min)}`);
    slide.append(productImg(p, { eager: i < 2 }));
    const cap = document.createElement('span');
    cap.className = 'slide__cap';
    cap.innerHTML = `<span class="slide__name">${p.name}</span><span class="slide__price">от ${money(min)}</span>`;
    slide.append(cap);
    track.append(slide);

    const dot = document.createElement('button');
    dot.type = 'button';
    dot.className = 'dot';
    dot.setAttribute('aria-label', `Показать: ${p.name}`);
    dot.addEventListener('click', () => go(i));
    dots.append(dot);
  });

  const slides = [...track.children];
  const step = () => slides[1] ? slides[1].offsetLeft - slides[0].offsetLeft : track.clientWidth;
  const current = () => Math.round(track.scrollLeft / step());
  const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  function go(i) {
    const idx = Math.max(0, Math.min(n - 1, i));
    track.scrollTo({ left: slides[idx].offsetLeft - slides[0].offsetLeft, behavior: reduce() ? 'auto' : 'smooth' });
  }
  function sync() {
    const maxScroll = track.scrollWidth - track.clientWidth;
    const i = track.scrollLeft >= maxScroll - 2 ? n - 1 : current();
    [...dots.children].forEach((d, k) => d.setAttribute('aria-current', k === i ? 'true' : 'false'));
    $('[data-carousel=prev]').disabled = track.scrollLeft <= 2;
    $('[data-carousel=next]').disabled = track.scrollLeft >= maxScroll - 2;
  }
  $('[data-carousel=prev]').addEventListener('click', () => go(current() - 1));
  $('[data-carousel=next]').addEventListener('click', () => go(current() + 1));
  track.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); go(current() + 1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); go(current() - 1); }
  });
  let t;
  track.addEventListener('scroll', () => { clearTimeout(t); t = setTimeout(sync, 60); }, { passive: true });
  addEventListener('resize', sync);
  sync();
}

/* ---------- Корзина: отрисовка ---------- */

function render() {
  const t = totals();

  // счётчики
  const word = plural(t.count, 'упаковка', 'упаковки', 'упаковок');
  document.querySelectorAll('[data-cart-count]').forEach((el) => { el.textContent = t.count; el.hidden = t.count === 0; });
  document.querySelectorAll('.cart-btn').forEach((b) => b.setAttribute('aria-label', `Корзина, ${t.count} ${word}`));
  $('[data-bar-count]').textContent = `${t.count} ${word}`;
  $('[data-bar-total]').textContent = money(t.total);
  $('#cart-bar').hidden = t.count === 0;
  document.body.classList.toggle('has-bar', t.count > 0);

  // карточки каталога
  CONFIG.products.forEach(updateCard);

  // строки корзины
  const list = $('#cart-items');
  list.innerHTML = '';
  for (const l of t.ls) {
    const li = document.createElement('li');
    li.className = 'line';
    const label = `${l.p.name}, ${weightLabel(l.pack.weight).replace(' ', ' ')}`;
    li.innerHTML = `
      <div class="line__info">
        <span class="line__name">${l.p.name}</span>
        <span class="line__meta">${weightLabel(l.pack.weight)} · ${money(l.pack.price)}</span>
      </div>
      <div class="stepper stepper--sm" role="group" aria-label="Количество: ${label}">
        <button type="button" class="stepper__btn" data-d="-1" aria-label="Убрать одну упаковку: ${label}">−</button>
        <span class="stepper__val">${l.qty}</span>
        <button type="button" class="stepper__btn" data-d="1" aria-label="Добавить ещё одну: ${label}">+</button>
      </div>
      <span class="line__sum">${money(l.sum)}</span>`;
    li.querySelectorAll('[data-d]').forEach((b) => b.addEventListener('click', () => {
      const next = l.qty + Number(b.dataset.d);
      setQty(l.key, next);
      const again = list.querySelector(`[data-key="${l.key}"] [data-d="${b.dataset.d}"]`);
      (again || $('[data-close-cart]')).focus();
      if (next === 0) announce(`${label} убран из корзины`);
    }));
    li.dataset.key = l.key;
    list.append(li);
  }

  const empty = t.count === 0;
  $('#cart-empty').hidden = !empty;
  $('#cart-summary').hidden = empty;
  $('#order-form').hidden = empty || !$('#prepared').hidden;
  if (empty) $('#prepared').hidden = true;

  $('#sum-items').textContent = money(t.items);
  $('#sum-delivery').textContent = t.free ? 'бесплатно' : money(t.delivery);
  $('#sum-total').textContent = money(t.total);
  $('#sum-hint').textContent = CONFIG.delivery.freeFrom > 0
    ? (t.free ? 'Доставка бесплатная.' : `До бесплатной доставки: ${money(t.left)}.`)
    : '';
}

function renderDelivery() {
  const d = CONFIG.delivery;
  const facts = [
    ['Где', `Доставляем ${CONFIG.area}.`],
    ['Когда', d.sameDay ? 'В день заказа.' : 'Срок уточним при подтверждении.'],
    ['Сколько', d.freeFrom > 0
      ? `${money(d.fee)}. При заказе от ${money(d.freeFrom)} — бесплатно.`
      : `${money(d.fee)}.`],
    ['Оплата', CONFIG.payment.join('. ') + '.'],
    ['Без регистрации', 'Соберите корзину, укажите адрес — и всё.'],
  ];
  $('#delivery-facts').innerHTML = facts
    .map(([k, v]) => `<li class="fact"><span class="fact__k">${k}</span><span class="fact__v">${v}</span></li>`)
    .join('');
}

function renderContacts() {
  const items = [];
  const wa = waNumber();
  if (wa) items.push(`<li><a href="https://wa.me/${wa}">WhatsApp: +${wa}</a></li>`);
  if (CONFIG.instagram) items.push(`<li><a href="${CONFIG.instagram}" rel="noopener">Instagram</a></li>`);
  $('#contacts-list').innerHTML = items.join('');
  $('#contacts').hidden = items.length === 0;
}

function renderNotice() {
  const parts = [];
  if (!waNumber()) parts.push('Приём заказов пока не открыт.');
  if (CONFIG.draft) parts.push('Цены и условия доставки предварительные.');
  const n = $('#notice');
  n.textContent = parts.join(' ');
  n.hidden = parts.length === 0;
}

/* ---------- Оформление ---------- */

function orderText(form) {
  const t = totals();
  const f = new FormData(form);
  const rows = t.ls.map((l) => `• ${l.p.name}, ${weightLabel(l.pack.weight)} × ${l.qty} — ${money(l.sum)}`);
  const opt = (label, name) => { const v = f.get(name).trim(); return v ? `${label}: ${v}` : null; };
  return [
    'Здравствуйте! Хочу заказать:',
    ...rows,
    '',
    `Товары: ${money(t.items)}`,
    `Доставка: ${t.free ? 'бесплатно' : money(t.delivery)}`,
    `Итого: ${money(t.total)}`,
    '',
    `Адрес: ${f.get('address').trim()}`,
    opt('Имя', 'name'),
    opt('Комментарий', 'comment'),
  ].filter((x) => x !== null).join('\n').replace(/ /g, ' ');
}

function initOrder() {
  const form = $('#order-form');
  const addr = $('#f-address');
  const err = $('#f-address-err');
  const wa = waNumber();
  $('#order-submit').textContent = wa ? 'Отправить заказ в WhatsApp' : 'Подготовить сообщение';
  $('#order-note').textContent = wa
    ? 'Откроется WhatsApp с готовым сообщением. Мы подтвердим заказ.'
    : 'Приём заказов пока не открыт: номер для заказов ещё не добавлен. Сообщение с заказом можно будет скопировать.';

  addr.addEventListener('input', () => { if (addr.value.trim()) { err.hidden = true; addr.removeAttribute('aria-invalid'); } });
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!addr.value.trim()) {
      err.hidden = false;
      addr.setAttribute('aria-invalid', 'true');
      addr.focus();
      return;
    }
    const text = orderText(form);
    if (wa) {
      window.open(`https://wa.me/${wa}?text=${encodeURIComponent(text)}`, '_blank', 'noopener');
      return;
    }
    $('#prepared-text').value = text;
    form.hidden = true;
    $('#prepared').hidden = false;
    $('#copy-btn').focus();
  });

  $('#copy-btn').addEventListener('click', async () => {
    const ta = $('#prepared-text');
    let ok = false;
    try { await navigator.clipboard.writeText(ta.value); ok = true; } catch {
      ta.select();
      try { ok = document.execCommand('copy'); } catch { ok = false; }
    }
    $('#copy-btn').textContent = ok ? 'Скопировано' : 'Выделите текст и скопируйте';
    announce(ok ? 'Сообщение скопировано' : 'Не получилось скопировать автоматически');
    setTimeout(() => { $('#copy-btn').textContent = 'Скопировать сообщение'; }, 2500);
  });
  $('#back-btn').addEventListener('click', () => {
    $('#prepared').hidden = true;
    form.hidden = false;
    addr.focus();
  });
}

function initDialog() {
  const dlg = $('#cart');
  document.querySelectorAll('[data-open-cart]').forEach((b) => b.addEventListener('click', () => {
    dlg.showModal();
    document.documentElement.classList.add('locked');
  }));
  $('[data-close-cart]').addEventListener('click', () => dlg.close());
  dlg.addEventListener('close', () => document.documentElement.classList.remove('locked'));
  // клик по затемнению вокруг окна закрывает его
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
}

/* ---------- Наклон карточек на компьютере ---------- */

function initTilt() {
  const fine = matchMedia('(hover: hover) and (pointer: fine)');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const grid = $('#catalog-grid');
  grid.addEventListener('pointermove', (e) => {
    if (!fine.matches || reduce.matches) return;
    const card = e.target.closest('.card');
    if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty('--rx', `${((e.clientY - r.top) / r.height - 0.5) * -4}deg`);
    card.style.setProperty('--ry', `${((e.clientX - r.left) / r.width - 0.5) * 5}deg`);
  });
  grid.addEventListener('pointerout', (e) => {
    const card = e.target.closest('.card');
    if (card && !card.contains(e.relatedTarget)) { card.style.removeProperty('--rx'); card.style.removeProperty('--ry'); }
  });
}

/* ---------- Старт ---------- */

renderNotice();
renderCarousel();
renderCatalog();
renderDelivery();
renderContacts();
initOrder();
initDialog();
initTilt();
render();
