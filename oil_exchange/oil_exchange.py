# -*- coding: utf-8 -*-
"""
Биржевой терминал «Нефтепродукты» — одиночная игра против ботов.

Запуск:  python oil_exchange.py
Нужен только Python 3.8+ (tkinter входит в стандартный установщик с python.org).
Короткая тестовая игра:  python oil_exchange.py --minutes 2
"""
import csv
import json
import random
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------- настройки
LOT = 60          # 1 лот = 60 т (как на ж/д базисах СПбМТСБ)
TICK = 10         # шаг цены, ₽/т
CORRIDOR = 0.30   # ценовой коридор: ±30% от базовой цены
BUYER_CASH = 300_000_000  # стартовые деньги покупателя, ₽
NEWS_COUNT = 12   # сколько новостей за игру

# key, название, базовая цена ₽/т (ориентир, примерно рынок 2025–2026), стартовый запас продавца, т
PRODUCTS = [
    ("ai92", "Бензин АИ-92", 62_000, 1200),
    ("ai95", "Бензин АИ-95", 68_000, 900),
    ("dt", "Дизель (ДТ)", 64_000, 1500),
    ("ts1", "Авиакеросин ТС-1", 72_000, 600),
    ("mazut", "Мазут М-100", 22_000, 1800),
    ("bitum", "Битум БНД", 34_000, 900),
]
PNAME = {k: n for k, n, _, _ in PRODUCTS}
BASE = {k: p for k, _, p, _ in PRODUCTS}
STOCK = {k: s for k, _, _, s in PRODUCTS}

DURATIONS = [("15 минут", 15), ("30 минут", 30), ("1 час", 60), ("2 часа", 120)]
SELLER, BUYER = "seller", "buyer"
ROLE_NAME = {SELLER: "Продавец", BUYER: "Покупатель"}

# noise — разброс оценок ботов, spread — насколько далеко от своей оценки они ставят заявки,
# react — вероятность сразу забрать выгодную встречную заявку
DIFFICULTY = {
    "Лёгкие": dict(noise=0.025, spread=(0.004, 0.035), react=0.3),
    "Обычные": dict(noise=0.012, spread=(0.002, 0.025), react=0.5),
    "Сильные": dict(noise=0.005, spread=(0.001, 0.012), react=0.75),
}

BOT_NAMES = ["Роснефтетрейд", "СибТопливо", "ВолгаОйл", "Уралнефтепродукт", "Балтбункер",
             "ТрансАвиаТопливо", "АгроТопливо", "ДорСтройБитум", "СеверЭнерго", "ЮгНефтеСбыт",
             "ТК Магистраль", "ПортБункер"]

NEWS_UP = ["Внеплановый ремонт на НПЗ — предложение: {p} сократилось",
           "Сезонный рост спроса: {p}", "Экспортные цены выросли: {p}",
           "Железная дорога ограничила отгрузки — дефицит: {p}"]
NEWS_DOWN = ["НПЗ вышел из ремонта — предложение растёт: {p}",
             "Крупный трейдер распродаёт запасы: {p}", "Спрос снизился: {p}",
             "Ограничен экспорт — излишки на внутреннем рынке: {p}"]

RECORDS_FILE = Path(__file__).with_name("oil_exchange_records.json")

RULES = f"""ЦЕЛЬ
Продавцы соревнуются, кто больше выручит денег. Покупатели — кто купит больше товара и дешевле рынка. Победитель определяется отдельно среди продавцов и среди покупателей.

СТАРТ
Каждый продавец получает одинаковый запас каждого товара, каждый покупатель — {BUYER_CASH // 1_000_000} млн ₽.

ТОРГОВЛЯ
• Двойной клик по стакану — окно заявки. Клик по строке стакана подставляет её цену.
• Стаканы перетаскиваются мышью за заголовок. Кнопка «Расставить» возвращает их по местам.
• Лот — {LOT} т, шаг цены — {TICK} ₽/т, цена в пределах ±{int(CORRIDOR * 100)}% от базовой.
• Сделка проходит, если цена покупки ≥ цены продажи. Цена сделки — цена той заявки, что стояла в стакане раньше. Сначала исполняются лучшие цены, при равной цене — более ранние заявки.
• Деньги и товар под заявкой замораживаются до исполнения или снятия. Снять заявку — двойной клик в списке «Мои заявки».
• Новости двигают рынок: боты быстро на них реагируют.
• Пробел — пауза, F1 — правила.

ЗАДАНИЯ
У каждого участника 3 задания: продать/купить не меньше N тонн конкретного топлива. Каждое выполненное задание умножает очки (×1.2, ×1.35, ×1.5; все три — ×2.43).

ОЧКИ
• Продавец: выручка × множитель.
• Покупатель: Σ по товарам (объём × средневзвешенная цена сессии × средневзвешенная цена сессии / ваша средняя цена) × множитель. Купили больше — больше очков; купили дешевле рынка — ещё больше. «Индекс выгоды» в итогах > 1 значит, что вы покупали дешевле рынка.
• Непроданный товар и непотраченные деньги очков не дают.
• Цены условные, комиссия биржи и доставка не учитываются."""


def fmt_num(x):
    return f"{x:,.0f}".replace(",", " ")


def fmt_money(x):
    return fmt_num(x) + " ₽"


def fmt_mln(x):
    return f"{x / 1e6:,.1f}".replace(",", " ") + " млн ₽"


def fmt_clock(sec):
    sec = max(0, int(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def round_tick(x):
    return int(round(x / TICK) * TICK)


def price_limits(product):
    return round_tick(BASE[product] * (1 - CORRIDOR)), round_tick(BASE[product] * (1 + CORRIDOR))


# ---------------------------------------------------------------- модель
class Order:
    _seq = 0

    def __init__(self, player, product, side, price, qty, t):
        Order._seq += 1
        self.id = Order._seq
        self.player, self.product, self.side = player, product, side
        self.price, self.qty, self.time = price, qty, t


class Task:
    def __init__(self, product, volume, mult):
        self.product, self.volume, self.mult = product, volume, mult

    def progress(self, player):
        return player.sold[self.product] if player.role == SELLER else player.bought[self.product]

    def done(self, player):
        return self.progress(player) >= self.volume


class Player:
    def __init__(self, name, role, is_bot):
        self.name, self.role, self.is_bot = name, role, is_bot
        self.cash = BUYER_CASH if role == BUYER else 0
        self.reserved_cash = 0
        self.stock = {k: (STOCK[k] if role == SELLER else 0) for k in PNAME}
        self.reserved_stock = {k: 0 for k in PNAME}
        self.bought = {k: 0 for k in PNAME}
        self.spent = {k: 0 for k in PNAME}
        self.sold = {k: 0 for k in PNAME}
        self.revenue = 0
        self.tasks = []

    def free_cash(self):
        return self.cash - self.reserved_cash

    def free_stock(self, p):
        return self.stock[p] - self.reserved_stock[p]

    def multiplier(self):
        m = 1.0
        for t in self.tasks:
            if t.done(self):
                m *= t.mult
        return m


class Market:
    def __init__(self, clock):
        self.clock = clock                   # функция: игровое время в секундах
        self.bids = {k: [] for k in PNAME}   # лучшая (самая дорогая) — первая
        self.asks = {k: [] for k in PNAME}   # лучшая (самая дешёвая) — первая
        self.trades = []                     # (время, товар, цена, объём, покупатель, продавец)
        self.last = {k: None for k in PNAME}

    def best_bid(self, p):
        return self.bids[p][0].price if self.bids[p] else None

    def best_ask(self, p):
        return self.asks[p][0].price if self.asks[p] else None

    def vwap(self, p):
        vol = sum(t[3] for t in self.trades if t[1] == p)
        if not vol:
            return BASE[p]
        return sum(t[2] * t[3] for t in self.trades if t[1] == p) / vol

    def volume(self, p):
        return sum(t[3] for t in self.trades if t[1] == p)

    def orders_of(self, player):
        res = []
        for p in PNAME:
            res += [o for o in self.bids[p] + self.asks[p] if o.player is player]
        return res

    def place(self, player, product, price, qty):
        """Подать заявку. Сторона определяется ролью игрока. Возвращает (ok, сообщение)."""
        side = "buy" if player.role == BUYER else "sell"
        lo, hi = price_limits(product)
        if qty <= 0 or qty % LOT:
            return False, f"Объём должен быть кратен лоту ({LOT} т)"
        if price % TICK:
            return False, f"Цена должна быть кратна {TICK} ₽"
        if not lo <= price <= hi:
            return False, f"Цена вне коридора: {fmt_money(lo)} … {fmt_money(hi)}"
        if side == "buy":
            if price * qty > player.free_cash():
                return False, "Не хватает свободных денег"
            player.reserved_cash += price * qty
        else:
            if qty > player.free_stock(product):
                return False, "Не хватает свободного товара"
            player.reserved_stock[product] += qty
        order = Order(player, product, side, price, qty, self.clock())
        filled = self._match(order)
        if order.qty > 0:
            book = self.bids[product] if side == "buy" else self.asks[product]
            book.append(order)
            if side == "buy":
                book.sort(key=lambda o: (-o.price, o.id))
            else:
                book.sort(key=lambda o: (o.price, o.id))
        if filled and order.qty:
            return True, f"Исполнено сразу {filled} т, остаток {order.qty} т стоит в стакане"
        if filled:
            return True, f"Заявка исполнена полностью: {filled} т"
        return True, "Заявка выставлена в стакан"

    def _match(self, order):
        p = order.product
        opposite = self.asks[p] if order.side == "buy" else self.bids[p]
        filled = 0
        while order.qty > 0 and opposite:
            best = opposite[0]
            crosses = best.price <= order.price if order.side == "buy" else best.price >= order.price
            if not crosses:
                break
            q = min(order.qty, best.qty)
            buy, sell = (order, best) if order.side == "buy" else (best, order)
            self._trade(buy, sell, best.price, q)   # цена сделки = цена стоявшей в стакане заявки
            order.qty -= q
            best.qty -= q
            filled += q
            if best.qty == 0:
                opposite.pop(0)
        return filled

    def _trade(self, buy, sell, price, q):
        b, s, p = buy.player, sell.player, buy.product
        b.cash -= price * q
        b.reserved_cash -= buy.price * q
        b.stock[p] += q
        b.bought[p] += q
        b.spent[p] += price * q
        s.stock[p] -= q
        s.reserved_stock[p] -= q
        s.sold[p] += q
        s.revenue += price * q
        s.cash += price * q
        self.last[p] = price
        self.trades.append((self.clock(), p, price, q, b, s))

    def cancel(self, order):
        book = self.bids[order.product] if order.side == "buy" else self.asks[order.product]
        if order in book:
            book.remove(order)
            if order.side == "buy":
                order.player.reserved_cash -= order.price * order.qty
            else:
                order.player.reserved_stock[order.product] -= order.qty


# ---------------------------------------------------------------- игра и боты
class Game:
    def __init__(self, name, role, minutes, n_bot_sellers, n_bot_buyers, difficulty="Обычные"):
        self.elapsed = 0.0            # игровое время: на паузе не идёт
        self.paused = False
        self._last = time.monotonic()
        self.market = Market(lambda: self.elapsed)
        self.minutes = minutes
        self.duration = minutes * 60
        self.difficulty = difficulty
        self.skill = DIFFICULTY[difficulty]
        self.me = Player(name or "Игрок", role, False)
        names = random.sample(BOT_NAMES, n_bot_sellers + n_bot_buyers)
        self.bots = [Player(names.pop(), SELLER, True) for _ in range(n_bot_sellers)]
        self.bots += [Player(names.pop(), BUYER, True) for _ in range(n_bot_buyers)]
        self.players = [self.me] + self.bots
        self.fair = dict(BASE)        # «справедливая» цена, на которую смотрят боты; её двигают новости
        self.news = []
        self.next_news = self.duration / NEWS_COUNT * random.uniform(0.5, 1.0)
        self._make_tasks()
        for _ in range(4):            # наполняем стаканы до старта
            for bot in self.bots:
                self._bot_act(bot, passive=True)

    # --- задания: множитель очков перемножается за каждое выполненное
    def _make_tasks(self):
        sellers = [p for p in self.players if p.role == SELLER]
        buyers = [p for p in self.players if p.role == BUYER]
        levels = [(0.35, 1.2), (0.5, 1.35), (0.65, 1.5)]
        for pl in sellers:
            for (frac, mult), prod in zip(levels, random.sample(list(PNAME), 3)):
                vol = max(LOT, int(STOCK[prod] * frac / LOT) * LOT)
                pl.tasks.append(Task(prod, vol, mult))
        for pl in buyers:
            tasks = []
            for (frac, mult), prod in zip(levels, random.sample(list(PNAME), 3)):
                supply = STOCK[prod] * len(sellers)
                tasks.append([prod, supply / len(buyers) * frac, mult])
            cost = sum(BASE[t[0]] * t[1] for t in tasks)
            k = min(1.0, BUYER_CASH * 0.6 / cost)   # на все задания хватает ~60% бюджета
            for prod, vol, mult in tasks:
                pl.tasks.append(Task(prod, max(LOT, int(vol * k / LOT) * LOT), mult))

    def time_left(self):
        return max(0.0, self.duration - self.elapsed)

    def over(self):
        return self.time_left() <= 0

    def set_paused(self, value):
        self.paused = value
        self._last = time.monotonic()

    def update(self):
        """Вызывается интерфейсом ~2 раза в секунду."""
        now = time.monotonic()
        dt, self._last = now - self._last, now
        if self.paused or self.over():
            return
        self.elapsed = min(self.duration, self.elapsed + dt)
        if self.elapsed >= self.next_news:
            self._make_news()
            self.next_news = self.elapsed + self.duration / NEWS_COUNT * random.uniform(0.7, 1.3)
        for p in PNAME:  # медленный случайный дрейф
            self.fair[p] = self.fair[p] * (1 + random.gauss(0, 0.0007))
            self.fair[p] = min(max(self.fair[p], BASE[p] * 0.8), BASE[p] * 1.2)
        for bot in self.bots:
            if random.random() < 0.18:
                self._bot_act(bot)

    def _make_news(self):
        p = random.choice(list(PNAME))
        up = random.random() < 0.5
        shift = random.uniform(0.02, 0.06) * (1 if up else -1)
        self.fair[p] = min(max(self.fair[p] * (1 + shift), BASE[p] * 0.8), BASE[p] * 1.2)
        text = random.choice(NEWS_UP if up else NEWS_DOWN).format(p=PNAME[p])
        self.news.append((self.elapsed, text, up))

    def _bot_act(self, bot, passive=False):
        m, sk = self.market, self.skill
        # снимаем устаревшие заявки; в длинной сессии они живут дольше, иначе стаканы пустеют,
        # пока боты ждут своего темпа
        life = max(1.0, self.duration / 1800)
        for o in m.orders_of(bot):
            if self.elapsed - o.time > random.uniform(25, 60) * life:
                m.cancel(o)
        if len(m.orders_of(bot)) >= 6:
            return
        # темп: боты растягивают торговлю на всю сессию
        t_frac = self.elapsed / self.duration
        if bot.role == SELLER:
            done = sum(bot.sold.values()) / sum(STOCK.values())
        else:
            done = (BUYER_CASH - bot.cash) / BUYER_CASH
        if done > t_frac * 0.9 + 0.06:
            return
        weights = [3 if any(t.product == p and not t.done(bot) for t in bot.tasks) else 1 for p in PNAME]
        p = random.choices(list(PNAME), weights)[0]
        value = self.fair[p] * (1 + random.gauss(0, sk["noise"]))
        lo, hi = price_limits(p)
        qty = LOT * random.randint(1, 4)
        if bot.role == SELLER:
            qty = min(qty, bot.free_stock(p) // LOT * LOT)
            if qty <= 0:
                return
            bid = m.best_bid(p)
            if not passive and bid and bid >= value * 0.995 and random.random() < sk["react"]:
                price = bid
            else:
                price = round_tick(value * (1 + random.uniform(*sk["spread"])))
        else:
            ask = m.best_ask(p)
            if not passive and ask and ask <= value * 1.005 and random.random() < sk["react"]:
                price = ask
            else:
                price = round_tick(value * (1 - random.uniform(*sk["spread"])))
            qty = min(qty, int(bot.free_cash() // max(price, 1)) // LOT * LOT)
            if qty <= 0:
                return
        price = min(max(price, lo), hi)
        m.place(bot, p, price, qty)

    # --- итоги
    def finish(self):
        for pl in self.players:
            for o in self.market.orders_of(pl):
                self.market.cancel(o)
        vwap = {p: self.market.vwap(p) for p in PNAME}
        rows = []
        for pl in self.players:
            mult = pl.multiplier()
            if pl.role == SELLER:
                volume, money, base, eff = sum(pl.sold.values()), pl.revenue, pl.revenue, None
            else:
                volume, money = sum(pl.bought.values()), sum(pl.spent.values())
                # «рыночная стоимость купленного» × (рыночная цена / цена покупки):
                # растёт с объёмом и тем больше, чем дешевле удалось купить относительно рынка
                base = 0.0
                for p in PNAME:
                    if pl.bought[p]:
                        avg = pl.spent[p] / pl.bought[p]
                        base += pl.bought[p] * vwap[p] * (vwap[p] / avg)
                eff = base / money if money else None
            rows.append(dict(player=pl, volume=volume, money=money, base=base, mult=mult, eff=eff,
                             tasks=f"{sum(t.done(pl) for t in pl.tasks)}/{len(pl.tasks)}",
                             score=base * mult))
        sellers = sorted([r for r in rows if r["player"].role == SELLER], key=lambda r: -r["score"])
        buyers = sorted([r for r in rows if r["player"].role == BUYER], key=lambda r: -r["score"])
        return dict(sellers=sellers, buyers=buyers, vwap=vwap, trades=list(self.market.trades),
                    me=self.me, elapsed=self.elapsed, minutes=self.minutes, difficulty=self.difficulty)


# ---------------------------------------------------------------- рекорды
def load_records():
    try:
        data = json.loads(RECORDS_FILE.read_text(encoding="utf-8"))
        # испорченный файл не должен ломать меню: берём только похожие на записи элементы
        return [r for r in data if isinstance(r, dict) and isinstance(r.get("score"), (int, float))]
    except (OSError, ValueError, TypeError):
        return []


def save_record(result):
    """Сохраняет результат игрока. Возвращает True, если это новый рекорд для его роли."""
    me = result["me"]
    rows = result["sellers"] if me.role == SELLER else result["buyers"]
    row = next(r for r in rows if r["player"] is me)
    records = load_records()
    prev = [r["score"] for r in records if r.get("role") == me.role]   # до этой игры
    records.append(dict(name=me.name, role=me.role, score=row["score"], minutes=result["minutes"],
                        difficulty=result["difficulty"], place=rows.index(row) + 1, of=len(rows),
                        date=time.strftime("%d.%m.%Y %H:%M")))
    try:
        RECORDS_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    # первая игра за роль — не рекорд: побить пока нечего
    return bool(prev) and row["score"] > max(prev)


# ---------------------------------------------------------------- интерфейс
BG, PANEL, BORDER, FG, MUTED = "#11161c", "#1b232c", "#30363d", "#e6edf3", "#8b98a5"
GREEN, RED, ACCENT, GOLD = "#3fb950", "#f85149", "#2f81f7", "#d29922"
FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
MONO = ("Consolas", 10)


class App:
    def __init__(self, root, minutes_override=None):
        self.root = root
        self.minutes_override = minutes_override
        root.title("Биржевой терминал — Нефтепродукты")
        # окно не больше экрана (ноутбук 1366×768), с запасом на панель задач и заголовок
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(1420, sw)}x{min(880, sh - 70)}+0+0")
        root.minsize(min(1000, sw), min(650, sh - 70))
        root.configure(bg=BG)
        try:
            root.state("zoomed")          # на Windows — развернуть на весь экран
        except tk.TclError:
            try:
                root.attributes("-zoomed", True)   # то же на Linux
            except tk.TclError:
                pass
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=24, font=FONT)
        style.configure("Treeview.Heading", background=BG, foreground=GOLD, font=FONT_B)
        style.map("Treeview", background=[("selected", "#2a4466")])
        self.frame = None
        self.game = None
        self.dialogs = set()
        self.result = None
        root.bind("<space>", lambda e: self.toggle_pause())
        root.bind("<F1>", lambda e: self.show_rules())
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_menu()

    def clear(self):
        for d in list(self.dialogs):
            if d.winfo_exists():
                d.destroy()
        self.dialogs.clear()
        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.root, bg=BG)
        self.frame.pack(fill="both", expand=True)
        return self.frame

    def on_close(self):
        if self.game and not messagebox.askyesno("Выход", "Игра ещё идёт. Выйти без подведения итогов?"):
            return
        self.root.destroy()

    def show_rules(self):
        win = tk.Toplevel(self.root)
        win.title("Правила игры")
        win.configure(bg=PANEL)
        win.transient(self.root)
        txt = tk.Text(win, width=90, height=34, bg=PANEL, fg=FG, font=FONT, wrap="word",
                      borderwidth=0, padx=16, pady=12)
        txt.insert("1.0", RULES)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)
        tk.Button(win, text="Понятно", bg=ACCENT, fg="white", relief="flat", font=FONT_B, width=14,
                  command=win.destroy).pack(pady=10)
        self.dialogs.add(win)

    # ---------------- главное меню
    def show_menu(self):
        self.game = None
        f = self.clear()
        box = tk.Frame(f, bg=BG)
        box.place(relx=0.5, rely=0.47, anchor="center")
        tk.Label(box, text="СЕКЦИЯ «НЕФТЕПРОДУКТЫ»", bg=BG, fg=GOLD, font=("Segoe UI", 12, "bold")).pack()
        tk.Label(box, text="Биржевой терминал", bg=BG, fg=FG, font=("Segoe UI", 28, "bold")).pack(pady=(0, 16))

        row = tk.Frame(box, bg=BG)
        row.pack(pady=4)
        tk.Label(row, text="Ваше имя:", bg=BG, fg=MUTED, font=FONT).pack(side="left")
        self.name_var = tk.StringVar(value=getattr(self, "_name", "Игрок"))
        tk.Entry(row, textvariable=self.name_var, width=22, font=FONT).pack(side="left", padx=6)

        tk.Label(box, text="Выберите длительность сессии — роль выбирается во всплывающем меню",
                 bg=BG, fg=MUTED, font=FONT).pack(pady=(16, 6))
        btns = tk.Frame(box, bg=BG)
        btns.pack()
        self.choice = {"minutes": None, "role": None}
        for title, minutes in DURATIONS:
            b = tk.Button(btns, text=title, width=12, height=2, font=FONT_B, bg=PANEL, fg=FG,
                          activebackground=ACCENT, relief="flat")
            b.configure(command=lambda b=b, t=title, m=minutes: self.role_menu(b, t, m))
            b.pack(side="left", padx=6)

        bots = tk.Frame(box, bg=BG)
        bots.pack(pady=(16, 4))
        tk.Label(bots, text="Ботов-продавцов:", bg=BG, fg=MUTED, font=FONT).pack(side="left")
        self.n_sellers = tk.Spinbox(bots, from_=1, to=6, width=4, font=FONT)
        self.n_sellers.delete(0, "end")
        self.n_sellers.insert(0, "4")
        self.n_sellers.pack(side="left", padx=(4, 18))
        tk.Label(bots, text="Ботов-покупателей:", bg=BG, fg=MUTED, font=FONT).pack(side="left")
        self.n_buyers = tk.Spinbox(bots, from_=1, to=6, width=4, font=FONT)
        self.n_buyers.delete(0, "end")
        self.n_buyers.insert(0, "4")
        self.n_buyers.pack(side="left", padx=4)

        diff = tk.Frame(box, bg=BG)
        diff.pack(pady=4)
        tk.Label(diff, text="Боты:", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 6))
        self.diff_var = tk.StringVar(value=getattr(self, "_diff", "Обычные"))
        for name in DIFFICULTY:
            tk.Radiobutton(diff, text=name, value=name, variable=self.diff_var, bg=BG, fg=FG,
                           selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                           font=FONT).pack(side="left", padx=4)

        self.summary = tk.Label(box, text="Не выбрано", bg=BG, fg=FG, font=("Segoe UI", 13))
        self.summary.pack(pady=(16, 8))
        self.start_btn = tk.Button(box, text="СТАРТ", width=20, height=2, font=("Segoe UI", 14, "bold"),
                                   bg=GREEN, fg="white", relief="flat", state="disabled",
                                   command=self.start_game)
        self.start_btn.pack()
        tk.Button(box, text="Правила и подсчёт очков (F1)", bg=PANEL, fg=FG, relief="flat", font=FONT,
                  command=self.show_rules).pack(pady=10)

        records = load_records()
        if records:
            tk.Label(box, text="Рекорды", bg=BG, fg=GOLD, font=FONT_B).pack(pady=(10, 2))
            for role in (SELLER, BUYER):
                top = sorted([r for r in records if r.get("role") == role], key=lambda r: -r["score"])[:3]
                for i, r in enumerate(top, 1):
                    score = f"{r['score'] / 1e6:,.1f}".replace(",", " ")   # пробелы — только в очках, не во всей строке
                    tk.Label(box, bg=BG, fg=MUTED, font=FONT,
                             text=f"{ROLE_NAME[role]} #{i}: {r.get('name', '?')} — {score} очк. "
                                  f"({r.get('minutes', 0):g} мин, боты {str(r.get('difficulty', '')).lower()}, "
                                  f"{r.get('date', '')})").pack()

    def role_menu(self, button, title, minutes):
        menu = tk.Menu(self.root, tearoff=0, font=FONT_B)
        for role in (SELLER, BUYER):
            menu.add_command(label=ROLE_NAME[role], command=lambda r=role: self.set_choice(title, minutes, r))
        menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())

    def set_choice(self, title, minutes, role):
        self.choice = {"minutes": minutes, "role": role}
        self.summary.configure(text=f"{title}  ·  {ROLE_NAME[role]}")
        self.start_btn.configure(state="normal")

    def start_game(self):
        try:
            ns = min(6, max(1, int(self.n_sellers.get())))
            nb = min(6, max(1, int(self.n_buyers.get())))
        except ValueError:
            ns = nb = 4
        self._name, self._diff = self.name_var.get().strip() or "Игрок", self.diff_var.get()
        minutes = self.minutes_override or self.choice["minutes"]
        self.game = Game(self._name, self.choice["role"], minutes, ns, nb, self._diff)
        self.show_game()

    # ---------------- игровой экран
    def show_game(self):
        f = self.clear()
        top = tk.Frame(f, bg=PANEL)
        top.pack(fill="x")
        self.lbl_top = tk.Label(top, bg=PANEL, fg=FG, font=("Segoe UI", 11, "bold"), anchor="w")
        for text, color, cmd in (("Завершить", RED, self.end_early), ("Правила", PANEL, self.show_rules),
                                 ("Расставить", PANEL, self.arrange)):
            tk.Button(top, text=text, bg=color, fg="white" if color == RED else FG, relief="flat", font=FONT,
                      command=cmd).pack(side="right", padx=4, pady=6)
        self.btn_pause = tk.Button(top, text="Пауза", bg=PANEL, fg=FG, relief="flat", font=FONT, width=11,
                                   command=self.toggle_pause)
        self.btn_pause.pack(side="right", padx=4)
        self.lbl_time = tk.Label(top, bg=PANEL, fg=GOLD, font=("Consolas", 16, "bold"))
        self.lbl_time.pack(side="right", padx=16)
        # пакуем последним: на узком экране обрежется сводка, а не таймер и кнопки
        self.lbl_top.pack(side="left", padx=12, pady=8, fill="x", expand=True)

        self.status = tk.Label(f, bg=PANEL, fg=MUTED, font=FONT, anchor="w", padx=12,
                               text="Двойной клик по стакану — заявка. Стаканы двигаются за заголовок. Пробел — пауза.")
        self.status.pack(side="bottom", fill="x")

        body = tk.Frame(f, bg=BG)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=PANEL, width=360)   # 360 — чтобы на 1366 px влезали 3 стакана в ряд
        side.pack(side="right", fill="y")
        side.pack_propagate(False)

        # рабочее поле со стаканами — с прокруткой, чтобы влезать на небольшие экраны
        wsf = tk.Frame(body, bg=BG)
        wsf.pack(side="left", fill="both", expand=True)
        self.ws = tk.Canvas(wsf, bg=BG, highlightthickness=0)
        vs = tk.Scrollbar(wsf, orient="vertical", command=self.ws.yview)
        hs = tk.Scrollbar(wsf, orient="horizontal", command=self.ws.xview)
        self.ws.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        wsf.rowconfigure(0, weight=1)
        wsf.columnconfigure(0, weight=1)
        self.ws.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        self.books = {key: BookWidget(self, key) for key, *_ in PRODUCTS}
        # колесо мыши — и над пустым полем, и над стаканами (Button-4/5 — колесо на Linux)
        for w in [self.ws] + [c for b in self.books.values() for c in [b] + b.winfo_children()]:
            w.bind("<MouseWheel>", lambda e: self.ws.yview_scroll(-1 if e.delta > 0 else 1, "units"))
            w.bind("<Button-4>", lambda e: self.ws.yview_scroll(-1, "units"))
            w.bind("<Button-5>", lambda e: self.ws.yview_scroll(1, "units"))
        self.ws.bind("<Configure>", lambda e: self.update_region())
        self.arrange()

        def section(title):
            tk.Label(side, text=title, bg=PANEL, fg=GOLD, font=FONT_B, anchor="w").pack(fill="x", padx=10, pady=(10, 2))

        section("Задания (множитель очков)")
        self.lbl_tasks = tk.Label(side, bg=PANEL, fg=FG, font=FONT, justify="left", anchor="w")
        self.lbl_tasks.pack(fill="x", padx=10)
        section("Мои заявки (двойной клик — снять)")
        self.lst_orders = tk.Listbox(side, height=7, bg=BG, fg=FG, font=MONO, borderwidth=0,
                                     highlightthickness=0, selectbackground=ACCENT)
        self.lst_orders.pack(fill="x", padx=10)
        self.lst_orders.bind("<Double-Button-1>", self.cancel_selected)
        self.lst_orders.bind("<Delete>", self.cancel_selected)
        row = tk.Frame(side, bg=PANEL)
        row.pack(fill="x", padx=10, pady=2)
        tk.Button(row, text="Снять все", bg=BG, fg=FG, relief="flat", font=FONT,
                  command=self.cancel_all).pack(side="right", padx=(4, 0))
        tk.Button(row, text="Снять выбранную", bg=BG, fg=FG, relief="flat", font=FONT,
                  command=self.cancel_selected).pack(side="right")
        section("Лента сделок")
        self.lst_trades = tk.Listbox(side, height=9, bg=BG, fg=FG, font=MONO, borderwidth=0, highlightthickness=0)
        self.lst_trades.pack(fill="x", padx=10)
        section("Новости рынка")
        # Text, а не Listbox: длинные новости переносятся, а не обрезаются справа
        self.lst_news = tk.Text(side, height=8, bg=BG, fg=FG, font=FONT, borderwidth=0, highlightthickness=0,
                                wrap="word", padx=4, pady=2, cursor="arrow", state="disabled")
        self.lst_news.tag_configure("up", foreground=GREEN, lmargin2=16)
        self.lst_news.tag_configure("down", foreground=RED, lmargin2=16)
        self.lst_news.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._shown_news = 0
        self._shown_orders = []
        self._seen_trades = len(self.game.market.trades)
        self._shown_trades = None
        if getattr(self, "_tick_job", None):     # цикл прошлой игры не должен идти параллельно
            self.root.after_cancel(self._tick_job)
        self.tick()

    def update_region(self):
        w = max(self.ws.winfo_width(), max(b.x + BookWidget.W for b in self.books.values()) + 10)
        h = max(self.ws.winfo_height(), max(b.y + b.winfo_reqheight() for b in self.books.values()) + 10)
        self.ws.configure(scrollregion=(0, 0, w, h))

    def arrange(self):
        """Расставить стаканы сеткой под текущую ширину окна."""
        self.root.update_idletasks()
        cols = max(1, min(3, (self.ws.winfo_width() - 10) // (BookWidget.W + 14)))
        # высоту стаканов подбираем так, чтобы два ряда влезали в окно без прокрутки
        n_rows = min(2, -(-len(self.books) // cols))
        for w in self.books.values():
            w.fit_height((self.ws.winfo_height() - 10) // n_rows - 12)
        self.root.update_idletasks()
        for i, w in enumerate(self.books.values()):
            w.move_to(10 + (i % cols) * (BookWidget.W + 14), 10 + (i // cols) * (w.winfo_reqheight() + 12))
        self.update_region()

    def set_status(self, text, color=MUTED):
        self.status.configure(text=text, fg=color)

    def toggle_pause(self):
        if not self.game:
            return
        self.game.set_paused(not self.game.paused)
        self.btn_pause.configure(text="Продолжить" if self.game.paused else "Пауза",
                                 bg=GOLD if self.game.paused else PANEL)
        self.set_status("Пауза: время и боты остановлены, заявки подавать нельзя." if self.game.paused
                        else "Торги продолжаются.", GOLD if self.game.paused else MUTED)
        self.refresh()

    def tick(self):
        g = self.game
        if g is None:
            return
        g.update()
        if g.over():
            self.show_results()
            return
        self.refresh()
        self._tick_job = self.root.after(500, self.tick)

    def refresh(self):
        g = self.game
        if g is None:
            return
        me = g.me
        self.lbl_time.configure(text=("ПАУЗА " if g.paused else "") + fmt_clock(g.time_left()))
        if me.role == BUYER:
            res = f"Деньги: {fmt_mln(me.cash)} (своб. {fmt_mln(me.free_cash())}) · куплено {sum(me.bought.values())} т"
        else:
            res = (f"Товар: {sum(me.stock.values())} т (своб. {sum(me.free_stock(p) for p in PNAME)} т) · "
                   f"выручка {fmt_mln(me.revenue)}")
        # компактно: на экране 1366 px строка должна влезать рядом с таймером и кнопками
        self.lbl_top.configure(text=f"{ROLE_NAME[me.role]} · {res} · множитель ×{me.multiplier():.2f}")
        for w in self.books.values():
            w.draw()
        for d in list(self.dialogs):    # открытые окна заявок: живые лучшие цены и подсказка
            if not d.winfo_exists():
                self.dialogs.discard(d)
            elif isinstance(d, OrderDialog):
                d.update_info()

        lines = []
        verb = "Продать" if me.role == SELLER else "Купить"
        for t in me.tasks:
            mark = "✔" if t.done(me) else "•"
            lines.append(f"{mark} {verb} {PNAME[t.product]}: {t.progress(me)}/{t.volume} т  → ×{t.mult}")
        self.lbl_tasks.configure(text="\n".join(lines))

        orders = g.market.orders_of(me)
        if [(o.id, o.qty) for o in orders] != [(o.id, o.qty) for o in self._shown_orders]:
            sel = self.lst_orders.curselection()
            self.lst_orders.delete(0, "end")
            for o in orders:
                self.lst_orders.insert("end", f"{'КУП' if o.side == 'buy' else 'ПРД'} {PNAME[o.product][:14]:<14} "
                                              f"{o.qty:>5} т × {o.price:>6}")
            self._shown_orders = list(orders)
            if sel and sel[0] < len(orders):
                self.lst_orders.selection_set(sel[0])

        # уведомления о сделках игрока
        new = g.market.trades[self._seen_trades:]
        self._seen_trades = len(g.market.trades)
        for _, p, price, q, b, s in new:
            if me in (b, s):
                was_task = [t.done(me) for t in me.tasks]
                self.set_status(f"✔ {'Куплено' if b is me else 'Продано'}: {PNAME[p]} — {q} т по {fmt_num(price)} ₽/т",
                                GREEN)
                self.books[p].flash()
        for t in me.tasks:
            if t.done(me) and not getattr(t, "_announced", False):
                t._announced = True
                self.set_status(f"★ Задание выполнено: {PNAME[t.product]} {t.volume} т — множитель ×{me.multiplier():.2f}", GOLD)

        if new or self._shown_trades is None:
            self._shown_trades = True
            self.lst_trades.delete(0, "end")
            for _, p, price, q, b, s in reversed(g.market.trades[-60:]):
                mine = me in (b, s)
                self.lst_trades.insert("end", f"{PNAME[p][:14]:<14} {q:>4} т × {price:>6}{' ◀ вы' if mine else ''}")
                if mine:
                    self.lst_trades.itemconfigure("end", fg=GOLD)
        if self._shown_news != len(g.news):
            self._shown_news = len(g.news)
            self.lst_news.configure(state="normal")
            self.lst_news.delete("1.0", "end")
            for sec, text, up in reversed(g.news):
                self.lst_news.insert("end", f"{int(sec) // 60:02d}:{int(sec) % 60:02d} {'▲' if up else '▼'} {text}\n",
                                     "up" if up else "down")
            self.lst_news.configure(state="disabled")
            if g.news:
                sec, text, up = g.news[-1]
                self.set_status(f"Новость: {text}", GREEN if up else RED)

    def cancel_selected(self, _event=None):
        sel = self.lst_orders.curselection()
        if self.game and sel and sel[0] < len(self._shown_orders):
            self.game.market.cancel(self._shown_orders[sel[0]])
            self.set_status("Заявка снята, деньги/товар разморожены.")
            self.refresh()

    def cancel_all(self):
        if self.game:
            for o in self.game.market.orders_of(self.game.me):
                self.game.market.cancel(o)
            self.set_status("Все ваши заявки сняты.")
            self.refresh()

    def open_order(self, product, price=None):
        if not self.game:
            return
        if self.game.paused:
            self.set_status("Сейчас пауза — продолжите игру, чтобы подать заявку (пробел).", GOLD)
            return
        self.dialogs.add(OrderDialog(self, product, price))

    def end_early(self):
        # пока висел вопрос, время могло кончиться и итоги уже показаны — тогда self.game is None
        if messagebox.askyesno("Завершить", "Завершить сессию и подвести итоги?") and self.game:
            self.show_results()

    # ---------------- итоги
    def show_results(self):
        self.result = res = self.game.finish()
        self.game = None
        new_record = save_record(res)
        me = res["me"]
        f = self.clear()
        tk.Label(f, text="Итоги торговой сессии", bg=BG, fg=FG, font=("Segoe UI", 22, "bold")).pack(pady=(14, 2))
        tk.Label(f, text=f"Время торгов: {fmt_clock(res['elapsed'])}  ·  сделок: {len(res['trades'])}  ·  "
                         f"боты: {res['difficulty'].lower()}  ·  неисполненные заявки сняты",
                 bg=BG, fg=MUTED, font=FONT).pack()
        tk.Label(f, text="Средневзвешенные цены сессии: " +
                 "  ·  ".join(f"{PNAME[p]} {fmt_num(res['vwap'][p])}" for p in PNAME),
                 bg=BG, fg=MUTED, font=FONT, wraplength=1300).pack()
        if new_record:
            tk.Label(f, text="★ Новый рекорд! ★", bg=BG, fg=GOLD, font=("Segoe UI", 14, "bold")).pack(pady=(6, 0))

        body = tk.Frame(f, bg=BG)
        body.pack(pady=6)
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", anchor="n", padx=10)
        col = tk.Frame(body, bg=BG)          # правая колонка: сводка и кнопки под ней — не уезжают за низ экрана
        col.pack(side="left", anchor="n", padx=10, pady=14)
        right = tk.Frame(col, bg=PANEL, padx=14, pady=10)
        right.pack(fill="x")

        def table(title, rows, buyer):
            winner = rows[0]["player"].name if rows and rows[0]["score"] > 0 else "—"
            tk.Label(left, text=f"{title}  —  победитель: {winner}", bg=BG, fg=GOLD,
                     font=("Segoe UI", 13, "bold")).pack(pady=(10, 4))
            cols = ["Место", "Участник", "Объём, т", "Потрачено" if buyer else "Выручка"]
            if buyer:
                cols.append("Индекс выгоды")
            cols += ["Задания", "Множитель", "Очки"]
            tv = ttk.Treeview(left, columns=cols, show="headings", height=max(1, min(len(rows), 7)))
            for c in cols:
                tv.heading(c, text=c)
                tv.column(c, width=190 if c == "Участник" else 60 if c == "Место" else 130 if c == "Индекс выгоды"
                          else 105, anchor="center")
            for i, r in enumerate(rows, 1):
                vals = [i, r["player"].name + (" (вы)" if not r["player"].is_bot else ""), r["volume"], fmt_mln(r["money"])]
                if buyer:
                    vals.append(f"{r['eff']:.3f}" if r["eff"] else "—")
                vals += [r["tasks"], f"×{r['mult']:.2f}", f"{r['score'] / 1e6:,.1f}".replace(",", " ")]
                tv.insert("", "end", values=vals, tags=("me",) if not r["player"].is_bot else ())
            tv.tag_configure("me", background="#23384f")
            tv.pack()

        table("Продавцы (больше всего выручки)", res["sellers"], False)
        table("Покупатели (больше товара дешевле рынка)", res["buyers"], True)
        tk.Label(left, text="Очки — в миллионах. Продавец: выручка × множитель. Покупатель: объём × рыночная цена × "
                            "(рыночная цена / ваша цена) × множитель. Подробно — в правилах.",
                 bg=BG, fg=MUTED, font=FONT, wraplength=850).pack(pady=8)

        # личная сводка
        rows = res["sellers"] if me.role == SELLER else res["buyers"]
        mine = next(r for r in rows if r["player"] is me)
        tk.Label(right, text=f"Ваш результат: {rows.index(mine) + 1} место из {len(rows)}", bg=PANEL, fg=GOLD,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w")
        done = me.sold if me.role == SELLER else me.bought
        lines = []
        for p in PNAME:
            if done[p]:
                if me.role == SELLER:
                    avg = sum(t[2] * t[3] for t in res["trades"] if t[1] == p and t[5] is me) / done[p]
                else:
                    avg = me.spent[p] / done[p]
                diff = (avg / res["vwap"][p] - 1) * 100
                lines.append(f"{PNAME[p]}: {done[p]} т, ср. {fmt_num(avg)} ({diff:+.1f}% к рынку)")
        tk.Label(right, text="\n".join(lines) or "Сделок не было", bg=PANEL, fg=FG, font=FONT,
                 justify="left").pack(anchor="w", pady=6)
        verb = "Продать" if me.role == SELLER else "Купить"
        tasks = "\n".join(f"{'✔' if t.done(me) else '✘'} {verb} {PNAME[t.product]}: {t.progress(me)}/{t.volume} т (×{t.mult})"
                          for t in me.tasks)
        tk.Label(right, text="Задания:\n" + tasks + f"\nИтоговый множитель: ×{me.multiplier():.2f}",
                 bg=PANEL, fg=FG, font=FONT, justify="left").pack(anchor="w", pady=6)

        btns = tk.Frame(col, bg=BG)
        btns.pack(fill="x", pady=(14, 0))
        tk.Button(btns, text="В главное меню", font=("Segoe UI", 13, "bold"), bg=ACCENT, fg="white",
                  relief="flat", height=2, command=self.show_menu).pack(fill="x")
        tk.Button(btns, text="Сохранить итоги в CSV", font=FONT_B, bg=PANEL, fg=FG,
                  relief="flat", height=2, command=self.export_csv).pack(fill="x", pady=(10, 0))

    def export_csv(self):
        res = self.result
        path = filedialog.asksaveasfilename(parent=self.root, title="Сохранить итоги", defaultextension=".csv",
                                            initialfile="итоги_сессии.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:   # utf-8-sig и «;» — чтобы Excel открыл сразу
                w = csv.writer(fh, delimiter=";")
                w.writerow(["Роль", "Место", "Участник", "Объём, т", "Выручка/затраты, ₽", "Индекс выгоды",
                            "Задания", "Множитель", "Очки"])
                for role, rows in ((SELLER, res["sellers"]), (BUYER, res["buyers"])):
                    for i, r in enumerate(rows, 1):
                        # дробные — с запятой, задания — «1 из 3»: иначе русский Excel превратит «1.2» и «1/3» в даты
                        w.writerow([ROLE_NAME[role], i, r["player"].name, r["volume"], round(r["money"]),
                                    f"{r['eff']:.3f}".replace(".", ",") if r["eff"] else "",
                                    r["tasks"].replace("/", " из "), f"{r['mult']:.2f}".replace(".", ","),
                                    round(r["score"])])
                w.writerow([])
                w.writerow(["Время", "Товар", "Цена, ₽/т", "Объём, т", "Покупатель", "Продавец"])
                for t, p, price, q, b, s in res["trades"]:
                    w.writerow([fmt_clock(t), PNAME[p], price, q, b.name, s.name])
        except OSError as e:
            messagebox.showerror("Не удалось сохранить", str(e))
            return
        messagebox.showinfo("Сохранено", path)


class BookWidget(tk.Frame):
    """Стакан заявок по одному товару. Перетаскивается за заголовок, двойной клик — заявка."""
    ROWS, ROW_H, W, SPARK_H = 8, 17, 310, 46

    def __init__(self, app, product):
        super().__init__(app.ws, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        self.app, self.product = app, product
        self.x = self.y = 0
        # ширина фиксирована: длинная подпись не должна наезжать на соседний стакан
        self.item = app.ws.create_window(0, 0, window=self, anchor="nw", width=self.W + 2)
        self.header = tk.Label(self, text=f"{PNAME[product]}   ·   база {fmt_num(BASE[product])} ₽/т",
                               bg="#243042", fg=FG, font=FONT_B,
                               anchor="w", padx=8, pady=4, cursor="fleur")
        self.header.pack(fill="x")
        self.info = tk.Label(self, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), anchor="w", padx=8)
        self.info.pack(fill="x")
        self.canvas = tk.Canvas(self, width=self.W, height=self.ROWS * 2 * self.ROW_H + 20,
                                bg=PANEL, highlightthickness=0)
        self.canvas.pack()
        self.spark = tk.Canvas(self, width=self.W, height=self.SPARK_H, bg=PANEL, highlightthickness=0)
        self.spark.pack()
        self.footer = tk.Label(self, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), anchor="w", padx=8)
        self.footer.pack(fill="x", pady=(0, 3))
        for w in (self.header, self.info):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
        for w in (self, self.header, self.info, self.canvas, self.spark, self.footer):
            w.bind("<Double-Button-1>", self._double)
        self.row_prices = []

    def fit_height(self, height):
        """Подобрать число строк стакана (4…8 на сторону), чтобы весь виджет был не выше height."""
        fixed = self.winfo_reqheight() - int(self.canvas.cget("height"))
        rows = min(8, max(4, (height - fixed - 20) // (2 * self.ROW_H)))
        if rows != self.ROWS:
            self.ROWS = rows
            self.canvas.configure(height=rows * 2 * self.ROW_H + 20)
            if self.app.game:
                self.draw()

    def move_to(self, x, y):
        self.x, self.y = x, y
        self.app.ws.coords(self.item, x, y)

    def _drag_start(self, e):
        self._start = (e.x_root, e.y_root, self.x, self.y)
        self.tkraise()

    def _drag_move(self, e):
        x0, y0, cx, cy = self._start
        x = max(0, cx + e.x_root - x0)
        y = max(0, cy + e.y_root - y0)
        self.move_to(x, y)
        self.app.update_region()

    def flash(self):
        self.header.configure(bg="#2d5a36")
        self.after(900, lambda: self.header.winfo_exists() and self.header.configure(bg="#243042"))

    def _double(self, e):
        price = None
        if e.widget is self.canvas:
            idx = int((e.y - 20) // self.ROW_H)
            if 0 <= idx < len(self.row_prices):
                price = self.row_prices[idx]
        self.app.open_order(self.product, price)

    def draw(self):
        m, me, p = self.app.game.market, self.app.game.me, self.product
        last = m.last[p]
        chg = round(((last / BASE[p] - 1) * 100) if last else 0.0, 1) or 0.0   # без «-0.0%»
        # базовая цена — в заголовке, чтобы строка не распирала стакан при больших объёмах
        self.info.configure(text=f"Посл.: {fmt_num(last) if last else '—'}   {chg:+.1f}% к базе   "
                                 f"объём {fmt_num(m.volume(p))} т",
                            fg=GREEN if chg > 0 else RED if chg < 0 else MUTED)
        if me.role == SELLER:
            self.footer.configure(text=f"У вас: {me.stock[p]} т, свободно {me.free_stock(p)} т · продано {me.sold[p]} т")
        else:
            avg = f", ср. цена {fmt_num(me.spent[p] / me.bought[p])}" if me.bought[p] else ""
            self.footer.configure(text=f"Куплено: {me.bought[p]} т{avg}")

        c = self.canvas
        c.delete("all")
        W, H = self.W, self.ROW_H
        c.create_text(50, 10, text="Продажа, т", fill=MUTED, font=("Segoe UI", 8))
        c.create_text(W / 2, 10, text="Цена, ₽/т", fill=MUTED, font=("Segoe UI", 8))
        c.create_text(W - 50, 10, text="Покупка, т", fill=MUTED, font=("Segoe UI", 8))

        def levels(orders):
            agg = {}
            for o in orders:
                v, mine = agg.get(o.price, (0, False))
                agg[o.price] = (v + o.qty, mine or o.player is me)
            return agg

        asks, bids = levels(m.asks[p]), levels(m.bids[p])
        ask_prices = sorted(asks)[:self.ROWS][::-1]   # сверху дорогие, у середины лучшая
        bid_prices = sorted(bids, reverse=True)[:self.ROWS]
        maxv = max([v for v, _ in asks.values()] + [v for v, _ in bids.values()] + [1])
        self.row_prices = [None] * (self.ROWS - len(ask_prices))
        y0 = 20 + (self.ROWS - len(ask_prices)) * H
        for i, price in enumerate(ask_prices):
            v, mine = asks[price]
            y = y0 + i * H
            c.create_rectangle(W / 2 - 45 - (W / 2 - 50) * v / maxv, y + 2, W / 2 - 45, y + H - 2, fill="#4a1f22", width=0)
            c.create_text(W / 2 - 50, y + H / 2, text=f"{v}{' •' if mine else ''}", anchor="e",
                          fill=GOLD if mine else RED, font=MONO)
            c.create_text(W / 2, y + H / 2, text=price, fill=FG, font=MONO)
            self.row_prices.append(price)
        y0 = 20 + self.ROWS * H
        c.create_line(10, y0, W - 10, y0, fill=BORDER)
        for i, price in enumerate(bid_prices):
            v, mine = bids[price]
            y = y0 + i * H
            c.create_rectangle(W / 2 + 45, y + 2, W / 2 + 45 + (W / 2 - 50) * v / maxv, y + H - 2, fill="#1b3d27", width=0)
            c.create_text(W / 2 + 50, y + H / 2, text=f"{'• ' if mine else ''}{v}", anchor="w",
                          fill=GOLD if mine else GREEN, font=MONO)
            c.create_text(W / 2, y + H / 2, text=price, fill=FG, font=MONO)
            self.row_prices.append(price)
        self._draw_spark()

    def _draw_spark(self):
        s, m, p = self.spark, self.app.game.market, self.product
        s.delete("all")
        prices = [t[2] for t in m.trades if t[1] == p][-60:]
        W, H = self.W, self.SPARK_H
        s.create_line(10, 2, W - 10, 2, fill=BORDER)
        if len(prices) < 2:
            s.create_text(W / 2, H / 2, text="график появится после сделок", fill=MUTED, font=("Segoe UI", 8))
            return
        lo, hi = min(prices), max(prices)
        span = max(hi - lo, TICK)
        x0, x1, top, bot = 10, W - 60, 8, H - 6
        pts = []
        for i, pr in enumerate(prices):
            pts += [x0 + (x1 - x0) * i / (len(prices) - 1), bot - (bot - top) * (pr - lo) / span]
        color = GREEN if prices[-1] >= prices[0] else RED
        s.create_line(*pts, fill=color, width=2)
        s.create_text(W - 8, top, text=fmt_num(hi), anchor="ne", fill=MUTED, font=("Segoe UI", 8))
        s.create_text(W - 8, bot, text=fmt_num(lo), anchor="se", fill=MUTED, font=("Segoe UI", 8))


class OrderDialog(tk.Toplevel):
    def __init__(self, app, product, price=None):
        super().__init__(app.root)
        self.app, self.product = app, product
        self.game = app.game
        g, me, m = self.game, self.game.me, self.game.market
        self.buy = buy = me.role == BUYER
        self.title("Заявка на покупку" if buy else "Заявка на продажу")
        self.configure(bg=PANEL, padx=10)
        self.resizable(False, False)
        self.transient(app.root)
        lo, hi = price_limits(product)
        best_opp = m.best_ask(product) if buy else m.best_bid(product)
        if price is None:
            price = best_opp or m.last[product] or BASE[product]
        tk.Label(self, text=("ПОКУПКА  " if buy else "ПРОДАЖА  ") + PNAME[product], bg=PANEL,
                 fg=GREEN if buy else RED, font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=3, pady=(12, 4))
        self.corridor = f"Коридор цены: {fmt_num(lo)} … {fmt_num(hi)} ₽/т"
        self.lbl_book = tk.Label(self, bg=PANEL, fg=MUTED, font=FONT)   # лучшие цены обновляются в update_info
        self.lbl_book.grid(row=1, column=0, columnspan=3)

        tk.Label(self, text="Цена, ₽/т:", bg=PANEL, fg=FG, font=FONT).grid(row=2, column=0, sticky="e", pady=6)
        self.price_var = tk.StringVar(value=str(price))
        tk.Spinbox(self, from_=lo, to=hi, increment=TICK, width=12, font=FONT,
                   textvariable=self.price_var).grid(row=2, column=1, sticky="w", padx=8)
        self.btn_best = tk.Button(self, text="лучшая встречная", bg=BG, fg=FG, relief="flat", font=("Segoe UI", 9),
                                  command=self.set_best)
        self.btn_best.grid(row=2, column=2, sticky="w")

        tk.Label(self, text=f"Объём, т (лот {LOT}):", bg=PANEL, fg=FG, font=FONT).grid(row=3, column=0, sticky="e", pady=6)
        self.qty_var = tk.StringVar(value=str(LOT))
        self.qty_box = tk.Spinbox(self, from_=LOT, to=100_000, increment=LOT, width=12, font=FONT,
                                  textvariable=self.qty_var)
        self.qty_box.grid(row=3, column=1, sticky="w", padx=8)
        tk.Button(self, text="максимум", bg=BG, fg=FG, relief="flat", font=("Segoe UI", 9),
                  command=self.set_max).grid(row=3, column=2, sticky="w")

        self.lbl_info = tk.Label(self, bg=PANEL, fg=MUTED, font=FONT, justify="left")
        self.lbl_info.grid(row=4, column=0, columnspan=3, pady=4, sticky="w")
        tk.Button(self, text="Купить" if buy else "Продать", bg=GREEN if buy else RED, fg="white",
                  font=FONT_B, relief="flat", width=14, command=self.submit).grid(row=5, column=0, pady=12, padx=10)
        tk.Button(self, text="Отмена", bg=BG, fg=FG, font=FONT, relief="flat", width=10,
                  command=self.destroy).grid(row=5, column=1, pady=12, padx=10)
        self.price_var.trace_add("write", self.update_info)
        self.qty_var.trace_add("write", self.update_info)
        self.update_info()
        self.bind("<Return>", lambda e: self.submit())
        self.bind("<Escape>", lambda e: self.destroy())
        # у курсора, но не за краем экрана
        self.update_idletasks()
        x = min(app.root.winfo_pointerx() - 160, self.winfo_screenwidth() - self.winfo_reqwidth() - 10)
        y = min(app.root.winfo_pointery() - 80, self.winfo_screenheight() - self.winfo_reqheight() - 60)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.qty_box.focus_set()

    def _values(self):
        return int(float(self.price_var.get())), int(float(self.qty_var.get()))

    def _best_opp(self):
        m = self.game.market
        return m.best_ask(self.product) if self.buy else m.best_bid(self.product)

    def set_best(self):
        best = self._best_opp()     # берём текущую, а не ту, что была при открытии окна
        if best:
            self.price_var.set(str(best))

    def set_max(self):
        me = self.game.me
        try:
            price = int(float(self.price_var.get()))
        except ValueError:
            return
        if self.buy:
            q = int(me.free_cash() // max(price, 1)) // LOT * LOT
        else:
            q = me.free_stock(self.product) // LOT * LOT
        self.qty_var.set(str(max(LOT, q)))

    def update_info(self, *_):
        me, m = self.game.me, self.game.market
        self.lbl_book.configure(text=f"Лучшая покупка: {m.best_bid(self.product) or '—'}   "
                                     f"лучшая продажа: {m.best_ask(self.product) or '—'}\n{self.corridor}")
        self.btn_best.configure(state="normal" if self._best_opp() else "disabled")
        avail = (f"Свободно денег: {fmt_mln(me.free_cash())}" if self.buy
                 else f"Свободно товара: {me.free_stock(self.product)} т")
        try:
            price, qty = self._values()
        except ValueError:
            self.lbl_info.configure(text=avail)
            return
        opp = m.best_ask(self.product) if self.buy else m.best_bid(self.product)
        crosses = opp is not None and (price >= opp if self.buy else price <= opp)
        hint = "⚡ исполнится сразу (хотя бы частично)" if crosses else "встанет в стакан и будет ждать встречную заявку"
        self.lbl_info.configure(text=f"{avail}\nСумма заявки: {fmt_money(price * qty)}\n{hint}")

    def submit(self):
        if self.app.game is not self.game:
            self.destroy()
            return
        if self.game.paused:
            messagebox.showinfo("Пауза", "Сейчас пауза — сначала продолжите игру.", parent=self)
            return
        try:
            price, qty = self._values()
        except ValueError:
            messagebox.showerror("Ошибка", "Введите числа", parent=self)
            return
        ok, msg = self.game.market.place(self.game.me, self.product, price, qty)
        if not ok:
            messagebox.showerror("Заявка отклонена", msg, parent=self)
            return
        self.app.set_status(msg, ACCENT)
        self.app.refresh()
        self.destroy()


def main():
    minutes = None
    if "--minutes" in sys.argv:
        minutes = float(sys.argv[sys.argv.index("--minutes") + 1])
    root = tk.Tk()
    App(root, minutes)
    root.mainloop()


if __name__ == "__main__":
    main()
