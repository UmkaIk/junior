# -*- coding: utf-8 -*-
"""
Биржевой терминал «Нефтепродукты» — одиночная игра против ботов.

Запуск:  python oil_exchange.py
Нужен только Python 3.9+ (tkinter входит в стандартный установщик с python.org).
Для быстрой проверки можно задать свою длительность:  python oil_exchange.py --minutes 2
"""
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk

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

BOT_NAMES = ["Роснефтетрейд", "СибТопливо", "ВолгаОйл", "Уралнефтепродукт", "Балтбункер",
             "ТрансАвиаТопливо", "АгроТопливо", "ДорСтройБитум", "СеверЭнерго", "ЮгНефтеСбыт",
             "ТК Магистраль", "ПортБункер"]

NEWS_UP = ["Внеплановый ремонт на НПЗ — предложение {p} сократилось",
           "Сезонный рост спроса на {p}", "Экспортные цены на {p} выросли",
           "Железная дорога ограничила отгрузки {p} — дефицит на рынке"]
NEWS_DOWN = ["НПЗ вышел из ремонта — предложение {p} растёт",
             "Крупный трейдер распродаёт запасы {p}", "Спрос на {p} снизился",
             "Правительство ограничило экспорт {p} — излишки на внутреннем рынке"]


def fmt_money(x):
    return f"{x:,.0f}".replace(",", " ") + " ₽"


def fmt_mln(x):
    return f"{x / 1e6:,.1f}".replace(",", " ") + " млн ₽"


def round_tick(x):
    return int(round(x / TICK) * TICK)


def price_limits(product):
    return round_tick(BASE[product] * (1 - CORRIDOR)), round_tick(BASE[product] * (1 + CORRIDOR))


# ---------------------------------------------------------------- модель
class Order:
    _seq = 0

    def __init__(self, player, product, side, price, qty):
        Order._seq += 1
        self.id = Order._seq
        self.player, self.product, self.side = player, product, side
        self.price, self.qty = price, qty
        self.time = time.monotonic()


class Task:
    def __init__(self, product, volume, mult):
        self.product, self.volume, self.mult = product, volume, mult

    def progress(self, player):
        done = player.sold[self.product] if player.role == SELLER else player.bought[self.product]
        return done

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
    def __init__(self):
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
        order = Order(player, product, side, price, qty)
        self._match(order)
        if order.qty > 0:
            book = self.bids[product] if side == "buy" else self.asks[product]
            book.append(order)
            if side == "buy":
                book.sort(key=lambda o: (-o.price, o.id))
            else:
                book.sort(key=lambda o: (o.price, o.id))
        return True, "Заявка принята"

    def _match(self, order):
        p = order.product
        opposite = self.asks[p] if order.side == "buy" else self.bids[p]
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
            if best.qty == 0:
                opposite.pop(0)

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
        self.trades.append((time.monotonic(), p, price, q, b, s))

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
    def __init__(self, name, role, minutes, n_bot_sellers, n_bot_buyers):
        self.market = Market()
        self.duration = minutes * 60
        self.start = time.monotonic()
        self.me = Player(name or "Вы", role, False)
        names = random.sample(BOT_NAMES, n_bot_sellers + n_bot_buyers)
        self.bots = [Player(names.pop(), SELLER, True) for _ in range(n_bot_sellers)]
        self.bots += [Player(names.pop(), BUYER, True) for _ in range(n_bot_buyers)]
        self.players = [self.me] + self.bots
        self.fair = dict(BASE)        # «справедливая» цена, которую видят боты; двигается новостями
        self.news = []
        self.next_news = self.start + self.duration / NEWS_COUNT * random.uniform(0.5, 1.0)
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
            prods = random.sample(list(PNAME), 3)
            tasks = []
            for (frac, mult), prod in zip(levels, prods):
                supply = STOCK[prod] * max(1, len(sellers))
                vol = supply / max(1, len(buyers)) * frac
                tasks.append([prod, vol, mult])
            cost = sum(BASE[t[0]] * t[1] for t in tasks)
            k = min(1.0, BUYER_CASH * 0.6 / cost)   # чтобы на все задания хватало ~60% бюджета
            for prod, vol, mult in tasks:
                pl.tasks.append(Task(prod, max(LOT, int(vol * k / LOT) * LOT), mult))

    def time_left(self):
        return max(0.0, self.duration - (time.monotonic() - self.start))

    def over(self):
        return self.time_left() <= 0

    def step(self):
        """Вызывается интерфейсом ~2 раза в секунду."""
        now = time.monotonic()
        if now >= self.next_news:
            self._make_news()
            self.next_news = now + self.duration / NEWS_COUNT * random.uniform(0.7, 1.3)
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
        self.news.append((time.monotonic() - self.start, text, up))

    def _bot_act(self, bot, passive=False):
        m = self.market
        now = time.monotonic()
        mine = m.orders_of(bot)
        for o in mine:  # снимаем устаревшие заявки
            if now - o.time > random.uniform(25, 60):
                m.cancel(o)
        if len(m.orders_of(bot)) >= 6:
            return
        # темп: боты растягивают торговлю на всю сессию
        t_frac = 1 - self.time_left() / self.duration
        if bot.role == SELLER:
            done = sum(bot.sold.values()) / sum(STOCK.values())
        else:
            done = (BUYER_CASH - bot.cash) / BUYER_CASH
        if done > t_frac * 0.9 + 0.12:
            return
        weights = [3 if any(t.product == p and not t.done(bot) for t in bot.tasks) else 1 for p in PNAME]
        p = random.choices(list(PNAME), weights)[0]
        value = self.fair[p] * (1 + random.gauss(0, 0.01))
        lo, hi = price_limits(p)
        qty = LOT * random.randint(1, 4)
        if bot.role == SELLER:
            qty = min(qty, bot.free_stock(p) // LOT * LOT)
            if qty <= 0:
                return
            bid = m.best_bid(p)
            if not passive and bid and bid >= value * 0.995 and random.random() < 0.5:
                price = bid
            else:
                price = round_tick(value * (1 + random.uniform(0.002, 0.025)))
        else:
            ask = m.best_ask(p)
            if not passive and ask and ask <= value * 1.005 and random.random() < 0.5:
                price = ask
            else:
                price = round_tick(value * (1 - random.uniform(0.002, 0.025)))
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
            tasks_done = sum(t.done(pl) for t in pl.tasks)
            if pl.role == SELLER:
                volume = sum(pl.sold.values())
                money = pl.revenue
                base = pl.revenue
                efficiency = None
            else:
                volume = sum(pl.bought.values())
                money = sum(pl.spent.values())
                # «рыночная стоимость купленного» × (рыночная цена / цена покупки):
                # растёт с объёмом и тем больше, чем дешевле удалось купить относительно рынка
                base = 0.0
                for p in PNAME:
                    if pl.bought[p]:
                        avg = pl.spent[p] / pl.bought[p]
                        base += pl.bought[p] * vwap[p] * (vwap[p] / avg)
                efficiency = base / money if money else None
            rows.append(dict(player=pl, volume=volume, money=money, base=base, mult=mult,
                             tasks=f"{tasks_done}/{len(pl.tasks)}", eff=efficiency,
                             score=base * mult))
        sellers = sorted([r for r in rows if r["player"].role == SELLER], key=lambda r: -r["score"])
        buyers = sorted([r for r in rows if r["player"].role == BUYER], key=lambda r: -r["score"])
        return sellers, buyers, vwap


# ---------------------------------------------------------------- интерфейс
BG, PANEL, FG, MUTED = "#11161c", "#1b232c", "#e6edf3", "#8b98a5"
GREEN, RED, ACCENT, GOLD = "#3fb950", "#f85149", "#2f81f7", "#d29922"
FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
MONO = ("Consolas", 10)


class App:
    def __init__(self, root, minutes_override=None):
        self.root = root
        self.minutes_override = minutes_override
        root.title("Биржевой терминал — Нефтепродукты")
        root.geometry("1420x880")
        root.minsize(1200, 760)
        root.configure(bg=BG)
        self.frame = None
        self.game = None
        self.show_menu()

    def clear(self):
        if self.frame:
            self.frame.destroy()
        self.frame = tk.Frame(self.root, bg=BG)
        self.frame.pack(fill="both", expand=True)
        return self.frame

    # ---------------- главное меню
    def show_menu(self):
        self.game = None
        f = self.clear()
        box = tk.Frame(f, bg=BG)
        box.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(box, text="СЕКЦИЯ «НЕФТЕПРОДУКТЫ»", bg=BG, fg=GOLD, font=("Segoe UI", 12, "bold")).pack()
        tk.Label(box, text="Биржевой терминал", bg=BG, fg=FG, font=("Segoe UI", 28, "bold")).pack(pady=(0, 20))

        row = tk.Frame(box, bg=BG)
        row.pack(pady=4)
        tk.Label(row, text="Ваше имя:", bg=BG, fg=MUTED, font=FONT).pack(side="left")
        self.name_var = tk.StringVar(value="Игрок")
        tk.Entry(row, textvariable=self.name_var, width=22, font=FONT).pack(side="left", padx=6)

        tk.Label(box, text="1. Выберите длительность сессии (роль — во всплывающем меню)",
                 bg=BG, fg=MUTED, font=FONT).pack(pady=(18, 6))
        btns = tk.Frame(box, bg=BG)
        btns.pack()
        self.choice = {"minutes": None, "role": None}
        for title, minutes in DURATIONS:
            b = tk.Button(btns, text=title, width=12, height=2, font=FONT_B, bg=PANEL, fg=FG,
                          activebackground=ACCENT, relief="flat")
            b.configure(command=lambda b=b, t=title, m=minutes: self.role_menu(b, t, m))
            b.pack(side="left", padx=6)

        bots = tk.Frame(box, bg=BG)
        bots.pack(pady=(18, 4))
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

        self.summary = tk.Label(box, text="Не выбрано", bg=BG, fg=FG, font=("Segoe UI", 13))
        self.summary.pack(pady=(20, 8))
        self.start_btn = tk.Button(box, text="СТАРТ", width=20, height=2, font=("Segoe UI", 14, "bold"),
                                   bg=GREEN, fg="white", relief="flat", state="disabled",
                                   command=self.start_game)
        self.start_btn.pack()
        rules = ("Двойной клик по стакану — подать заявку (по строке — с этой ценой). "
                 "Стаканы можно перетаскивать за заголовок.\n"
                 f"Лот {LOT} т, шаг цены {TICK} ₽/т. Сделка — когда цена покупки ≥ цены продажи, "
                 "по цене заявки, стоявшей в стакане раньше.")
        tk.Label(box, text=rules, bg=BG, fg=MUTED, font=FONT, justify="center").pack(pady=18)

    def role_menu(self, button, title, minutes):
        menu = tk.Menu(self.root, tearoff=0, font=FONT_B)
        for role in (SELLER, BUYER):
            menu.add_command(label=ROLE_NAME[role],
                             command=lambda r=role: self.set_choice(title, minutes, r))
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
        role = self.choice["role"]
        # человек занимает одно место своей роли, ботов этой роли на одного меньше (минимум 1)
        if role == SELLER:
            ns = max(1, ns - 1) if ns > 1 else 1
        else:
            nb = max(1, nb - 1) if nb > 1 else 1
        minutes = self.minutes_override or self.choice["minutes"]
        self.game = Game(self.name_var.get().strip(), role, minutes, ns, nb)
        self.show_game()

    # ---------------- игровой экран
    def show_game(self):
        f = self.clear()
        g = self.game
        top = tk.Frame(f, bg=PANEL)
        top.pack(fill="x")
        self.lbl_top = tk.Label(top, bg=PANEL, fg=FG, font=("Segoe UI", 11, "bold"), anchor="w")
        self.lbl_top.pack(side="left", padx=12, pady=8)
        tk.Button(top, text="Завершить досрочно", bg=RED, fg="white", relief="flat", font=FONT,
                  command=self.end_early).pack(side="right", padx=8, pady=6)
        self.lbl_time = tk.Label(top, bg=PANEL, fg=GOLD, font=("Consolas", 16, "bold"))
        self.lbl_time.pack(side="right", padx=16)

        body = tk.Frame(f, bg=BG)
        body.pack(fill="both", expand=True)
        self.work = tk.Frame(body, bg=BG)
        self.work.pack(side="left", fill="both", expand=True)
        side = tk.Frame(body, bg=PANEL, width=400)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)

        self.books = []
        for i, (key, *_rest) in enumerate(PRODUCTS):
            w = BookWidget(self, key)
            w.place(x=10 + (i % 3) * 330, y=10 + (i // 3) * 375)
            self.books.append(w)

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
        tk.Button(side, text="Снять выбранную", bg=BG, fg=FG, relief="flat", font=FONT,
                  command=self.cancel_selected).pack(anchor="e", padx=10, pady=2)
        section("Лента сделок")
        self.lst_trades = tk.Listbox(side, height=9, bg=BG, fg=FG, font=MONO, borderwidth=0, highlightthickness=0)
        self.lst_trades.pack(fill="x", padx=10)
        section("Новости рынка")
        self.lst_news = tk.Listbox(side, height=8, bg=BG, fg=FG, font=FONT, borderwidth=0, highlightthickness=0)
        self.lst_news.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._shown_orders = []
        self.tick()

    def tick(self):
        g = self.game
        if g is None or self.frame is None:
            return
        if g.over():
            self.show_results()
            return
        g.step()
        self.refresh()
        self.root.after(500, self.tick)

    def refresh(self):
        g, me = self.game, self.game.me
        left = int(g.time_left())
        self.lbl_time.configure(text=f"{left // 3600}:{left % 3600 // 60:02d}:{left % 60:02d}")
        if me.role == BUYER:
            res = f"Деньги: {fmt_mln(me.cash)} (свободно {fmt_mln(me.free_cash())})  ·  куплено {sum(me.bought.values())} т"
        else:
            res = (f"Товар: {sum(me.stock.values())} т (свободно {sum(me.free_stock(p) for p in PNAME)} т)  ·  "
                   f"выручка {fmt_mln(me.revenue)}")
        self.lbl_top.configure(text=f"{me.name}  ·  {ROLE_NAME[me.role]}  ·  {res}  ·  множитель ×{me.multiplier():.2f}")
        for w in self.books:
            w.draw()
        lines = []
        for t in me.tasks:
            verb = "Продать" if me.role == SELLER else "Купить"
            mark = "✔" if t.done(me) else "•"
            lines.append(f"{mark} {verb} {PNAME[t.product]}: {t.progress(me)}/{t.volume} т  → ×{t.mult}")
        self.lbl_tasks.configure(text="\n".join(lines))
        orders = g.market.orders_of(me)
        if [(o.id, o.qty) for o in orders] != [(o.id, o.qty) for o in self._shown_orders]:
            self.lst_orders.delete(0, "end")
            for o in orders:
                self.lst_orders.insert("end", f"{'КУП' if o.side == 'buy' else 'ПРД'} {PNAME[o.product][:14]:<14} {o.qty:>5} т × {o.price:>6}")
            self._shown_orders = orders
        self.lst_trades.delete(0, "end")
        for _, p, price, q, b, s in reversed(g.market.trades[-40:]):
            who = " ◀ вы" if me in (b, s) else ""
            self.lst_trades.insert("end", f"{PNAME[p][:14]:<14} {q:>4} т × {price:>6}{who}")
        if self.lst_news.size() != len(g.news):
            self.lst_news.delete(0, "end")
            for sec, text, up in reversed(g.news):
                self.lst_news.insert("end", f"{int(sec) // 60:02d}:{int(sec) % 60:02d}  {'▲' if up else '▼'} {text}")
                self.lst_news.itemconfigure("end", fg=GREEN if up else RED)

    def cancel_selected(self, _event=None):
        sel = self.lst_orders.curselection()
        if sel and sel[0] < len(self._shown_orders):
            self.game.market.cancel(self._shown_orders[sel[0]])
            self._shown_orders = []
            self.refresh()

    def end_early(self):
        if messagebox.askyesno("Завершить", "Завершить сессию и подвести итоги?"):
            self.show_results()

    # ---------------- итоги
    def show_results(self):
        g = self.game
        sellers, buyers, vwap = g.finish()
        self.game = None
        f = self.clear()
        tk.Label(f, text="Итоги торговой сессии", bg=BG, fg=FG, font=("Segoe UI", 22, "bold")).pack(pady=(18, 4))
        tk.Label(f, text="Средневзвешенные цены сессии: " +
                 "  ·  ".join(f"{PNAME[p]} {vwap[p]:,.0f}".replace(",", " ") for p in PNAME),
                 bg=BG, fg=MUTED, font=FONT, wraplength=1300).pack()

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=24, font=FONT)
        style.configure("Treeview.Heading", background=BG, foreground=GOLD, font=FONT_B)

        def table(title, rows, buyer):
            winner = rows[0]["player"].name if rows else "—"
            tk.Label(f, text=f"{title}  —  победитель: {winner}", bg=BG, fg=GOLD,
                     font=("Segoe UI", 13, "bold")).pack(pady=(16, 4))
            cols = ["Место", "Участник", "Объём, т", "Потрачено" if buyer else "Выручка",
                    "Индекс выгоды" if buyer else "", "Задания", "Множитель", "Очки"]
            cols = [c for c in cols if c]
            tv = ttk.Treeview(f, columns=cols, show="headings", height=min(len(rows), 7))
            for c in cols:
                tv.heading(c, text=c)
                tv.column(c, width=200 if c == "Участник" else 120, anchor="center")
            for i, r in enumerate(rows, 1):
                vals = [i, r["player"].name + (" (вы)" if not r["player"].is_bot else ""),
                        r["volume"], fmt_mln(r["money"])]
                if buyer:
                    vals.append(f"{r['eff']:.3f}" if r["eff"] else "—")
                vals += [r["tasks"], f"×{r['mult']:.2f}", f"{r['score'] / 1e6:,.1f}".replace(",", " ")]
                tv.insert("", "end", values=vals, tags=("me",) if not r["player"].is_bot else ())
            tv.tag_configure("me", background="#23384f")
            tv.pack()

        table("Продавцы (больше всего выручки)", sellers, False)
        table("Покупатели (больше товара дешевле рынка)", buyers, True)
        tk.Label(f, text="Очки продавца = выручка × множитель.  Очки покупателя = Σ объём × ср.взвеш. цена сессии × "
                 "(ср.взвеш. цена / ваша средняя цена) × множитель. Индекс выгоды > 1 — купили дешевле рынка.",
                 bg=BG, fg=MUTED, font=FONT, wraplength=1200).pack(pady=12)
        tk.Button(f, text="В главное меню", font=("Segoe UI", 13, "bold"), bg=ACCENT, fg="white",
                  relief="flat", width=20, height=2, command=self.show_menu).pack(pady=8)


class BookWidget(tk.Frame):
    """Стакан заявок по одному товару. Перетаскивается за заголовок, двойной клик — заявка."""
    ROWS, ROW_H, W = 9, 18, 310

    def __init__(self, app, product):
        super().__init__(app.work, bg=PANEL, highlightbackground="#30363d", highlightthickness=1)
        self.app, self.product = app, product
        self.header = tk.Label(self, text=PNAME[product], bg="#243042", fg=FG, font=FONT_B,
                               anchor="w", padx=8, pady=4, cursor="fleur")
        self.header.pack(fill="x")
        self.info = tk.Label(self, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), anchor="w", padx=8)
        self.info.pack(fill="x")
        self.canvas = tk.Canvas(self, width=self.W, height=self.ROWS * 2 * self.ROW_H + 22,
                                bg=PANEL, highlightthickness=0)
        self.canvas.pack()
        for w in (self.header, self.info):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
        for w in (self, self.header, self.info, self.canvas):
            w.bind("<Double-Button-1>", self._double)
        self.row_prices = []

    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.winfo_x(), e.y_root - self.winfo_y()
        self.lift()

    def _drag_move(self, e):
        parent = self.master
        x = min(max(0, e.x_root - self._dx), parent.winfo_width() - 60)
        y = min(max(0, e.y_root - self._dy), parent.winfo_height() - 30)
        self.place(x=x, y=y)

    def _double(self, e):
        price = None
        if e.widget is self.canvas:
            idx = int((e.y - 20) // self.ROW_H)
            if 0 <= idx < len(self.row_prices):
                price = self.row_prices[idx]
        OrderDialog(self.app, self.product, price)

    def draw(self):
        m, me, p = self.app.game.market, self.app.game.me, self.product
        last = m.last[p]
        chg = ((last / BASE[p] - 1) * 100) if last else 0.0
        self.info.configure(text=f"Посл.: {last or '—'}   {chg:+.1f}% к базе {BASE[p]}   объём {m.volume(p)} т",
                            fg=GREEN if chg > 0 else RED if chg < 0 else MUTED)
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
        self.row_prices = []
        y0 = 20 + (self.ROWS - len(ask_prices)) * H
        self.row_prices = [None] * (self.ROWS - len(ask_prices))
        for i, price in enumerate(ask_prices):
            v, mine = asks[price]
            y = y0 + i * H
            c.create_rectangle(W / 2 - 45 - (W / 2 - 50) * v / maxv, y + 2, W / 2 - 45, y + H - 2, fill="#4a1f22", width=0)
            c.create_text(W / 2 - 50, y + H / 2, text=f"{v}{' •' if mine else ''}", anchor="e", fill=RED, font=MONO)
            c.create_text(W / 2, y + H / 2, text=price, fill=FG, font=MONO)
            self.row_prices.append(price)
        y0 = 20 + self.ROWS * H
        c.create_line(10, y0, W - 10, y0, fill="#30363d")
        for i, price in enumerate(bid_prices):
            v, mine = bids[price]
            y = y0 + i * H
            c.create_rectangle(W / 2 + 45, y + 2, W / 2 + 45 + (W / 2 - 50) * v / maxv, y + H - 2, fill="#1b3d27", width=0)
            c.create_text(W / 2 + 50, y + H / 2, text=f"{'• ' if mine else ''}{v}", anchor="w", fill=GREEN, font=MONO)
            c.create_text(W / 2, y + H / 2, text=price, fill=FG, font=MONO)
            self.row_prices.append(price)


class OrderDialog(tk.Toplevel):
    def __init__(self, app, product, price=None):
        super().__init__(app.root)
        self.app, self.product = app, product
        g, me = app.game, app.game.me
        m = g.market
        buy = me.role == BUYER
        self.title("Заявка на покупку" if buy else "Заявка на продажу")
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(app.root)
        lo, hi = price_limits(product)
        if price is None:
            best = m.best_ask(product) if buy else m.best_bid(product)
            price = best or m.last[product] or BASE[product]
        tk.Label(self, text=("ПОКУПКА  " if buy else "ПРОДАЖА  ") + PNAME[product], bg=PANEL,
                 fg=GREEN if buy else RED, font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=2, pady=(12, 4), padx=14)
        tk.Label(self, text=f"Лучшая покупка: {m.best_bid(product) or '—'}   лучшая продажа: {m.best_ask(product) or '—'}\n"
                 f"Коридор цены: {lo} … {hi} ₽/т", bg=PANEL, fg=MUTED, font=FONT).grid(row=1, column=0, columnspan=2, padx=14)
        tk.Label(self, text="Цена, ₽/т:", bg=PANEL, fg=FG, font=FONT).grid(row=2, column=0, sticky="e", pady=6)
        self.price = tk.Spinbox(self, from_=lo, to=hi, increment=TICK, width=12, font=FONT)
        self.price.delete(0, "end")
        self.price.insert(0, str(price))
        self.price.grid(row=2, column=1, sticky="w", padx=8)
        tk.Label(self, text=f"Объём, т (лот {LOT}):", bg=PANEL, fg=FG, font=FONT).grid(row=3, column=0, sticky="e", pady=6)
        self.qty = tk.Spinbox(self, from_=LOT, to=100_000, increment=LOT, width=12, font=FONT)
        self.qty.grid(row=3, column=1, sticky="w", padx=8)
        avail = f"Свободно денег: {fmt_mln(me.free_cash())}" if buy else f"Свободно товара: {me.free_stock(product)} т"
        self.lbl_sum = tk.Label(self, text=avail, bg=PANEL, fg=MUTED, font=FONT)
        self.lbl_sum.grid(row=4, column=0, columnspan=2, pady=4)
        tk.Button(self, text="Купить" if buy else "Продать", bg=GREEN if buy else RED, fg="white",
                  font=FONT_B, relief="flat", width=14, command=self.submit).grid(row=5, column=0, pady=12, padx=10)
        tk.Button(self, text="Отмена", bg=BG, fg=FG, font=FONT, relief="flat", width=10,
                  command=self.destroy).grid(row=5, column=1, pady=12, padx=10)
        self.bind("<Return>", lambda e: self.submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self.geometry(f"+{app.root.winfo_pointerx() - 120}+{app.root.winfo_pointery() - 60}")
        self.qty.focus_set()

    def submit(self):
        if self.app.game is None:
            self.destroy()
            return
        try:
            price, qty = int(float(self.price.get())), int(float(self.qty.get()))
        except ValueError:
            messagebox.showerror("Ошибка", "Введите числа", parent=self)
            return
        ok, msg = self.app.game.market.place(self.app.game.me, self.product, price, qty)
        if not ok:
            messagebox.showerror("Заявка отклонена", msg, parent=self)
            return
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
