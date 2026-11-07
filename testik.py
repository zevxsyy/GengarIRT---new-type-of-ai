#!/usr/bin/env python3
# zevxsyy: бэк я писал всю ночь, сломаете, найду и накажу
# kiorane: ты каждый раз это пишешь, успокойся
# ah3ova: pip install httpx requests pillow, все три, не ной что долго
import sys, os, re, json, time, html, base64, tempfile, threading, math, random
import tkinter as tk
from collections import Counter
from urllib.parse import quote, unquote, urlparse
HERE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(HERE, "gengar_knowledge.json")
DEPTHS = {"dumb": 3, "normal": 10, "premium": 25}   # kiorane поставила 25 и у нас сгорел ноут, не ставьте больше
LIBS = ("httpx", "requests")
COLORS = {"зелёный": "#7ee787", "голубой": "#79c0ff", "жёлтый": "#f2cc60", "белый": "#ece8f5", "красный": "#ff7b72", "синий": "#8aa2ff", "фиолетовый": "#c9a0ff"}
THEMES = {"фиолетовый": "#8b5cf6", "синий": "#3b82f6", "бирюзовый": "#14b8a6", "зелёный": "#22c55e", "розовый": "#ec4899", "красный": "#ef4444", "оранжевый": "#f97316", "золотой": "#eab308"}
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
HEADERS = {"Accept-Language": "ru-RU,ru;q=0.9"}
WIKI_UA = "GengarIRT/0.11 (personal learning project; contact: you@example.com)"
WORD = re.compile(r"[а-яё]+(?:-[а-яё]+)?")
# zevxsyy: сюда только мусорные слова, умничать тут запрещено, это не википедия
STOP = set("""и в во не на что это как для по из от до или но а же бы ли к ко с со о об у за так его ее её их они он
она оно мы вы был была было были быть при все всё также который которая которое которые такое такой кто чем где когда
там тут уже еще ещё только очень можно нужно будет есть нет да раз ну давай ладно тогда теперь снова опять просто короче""".split())
VERSION = 3   # поменяешь это число и всё выучится заново, так что думай прежде чем лезть
JUNK = re.compile(r"перейти|материал из|викиданн|содержани|cookie|javascript|войти|меню|скачать|реклам|подпис", re.I)
ASK = set("""расскажи объясни скажи значит значение значения слова слову словом слове слово означает определение понятие
синоним синонимы синонимов похожие похожее похожих какой какая какое какие бывает такая такие""".split())
class Store:   # kiorane, json руками не трогай, потом сидим и плачем, я бэкенл блятц
    def __init__(self, path=DB_FILE):
        self.path, self.data = path, {"settings": {"lib": "httpx", "depth": "normal", "color": "зелёный", "theme": "фиолетовый", "anim": "вкл"}, "words": {}}
        try:
            with open(path, encoding="utf-8") as f: saved = json.load(f)
            self.data["settings"].update(saved.get("settings", {})); self.data["words"] = saved.get("words", {})
        except (OSError, ValueError): pass
        self.data["settings"] = {k: str(v).lower() for k, v in self.data["settings"].items()}   # старый json у тебя с большими буквами, я всё привёл, не благодари
    @property
    def settings(self): return self.data["settings"]
    def get(self, word): return self.data["words"].get(word)
    def put(self, word, entry):
        for key, limit in (("defs", 6), ("sents", 6), ("syn", 40), ("rel", 40)): entry[key] = dict(Counter(entry[key]).most_common(limit))
        self.data["words"][word] = entry; self.save()
    def save(self):
        with open(self.path, "w", encoding="utf-8") as f: json.dump(self.data, f, ensure_ascii=False, indent=1)
class Fetcher:   # ah3ova: если сайт не открылся это не я, это интернет
    def __init__(self, lib): self.lib, self.error = lib, None
    def get(self, url, data=None):
        host = urlparse(url).netloc
        agents = [WIKI_UA, BROWSER_UA] if host.endswith(("wikipedia.org", "wiktionary.org")) else [BROWSER_UA]
        for ua in agents:   # zevxsyy: ну давай, пробуй второй юзер агент, не сдавайся на первом
            try:
                lib = __import__(self.lib)
                kw = {"headers": {**HEADERS, "User-Agent": ua}, "timeout": 8}
                if self.lib == "httpx": kw["follow_redirects"] = True
                r = lib.post(url, data=data, **kw) if data else lib.get(url, **kw)
            except ImportError: raise
            except Exception as exc: self.error = f"{host}: {type(exc).__name__} {str(exc)[:70]}"; return None
            if r.status_code == 200 and "html" in r.headers.get("content-type", ""): return r.text[:500_000]
            self.error = f"{host}: http {r.status_code}"
            if r.status_code != 403: break
        return None
class Searcher:   # kiorane: кто добавил vk в скип? а, это я, ладно, пусть будет
    SKIP = ("duckduckgo.com", "bing.com", "microsoft.com", "youtube.com", "facebook.com", "instagram.com", "vk.com", "tiktok.com")
    SEEDS = ("https://ru.wiktionary.org/wiki/{w}", "https://kartaslov.ru/значение-слова/{w}", "https://ru.ruwiki.ru/wiki/{W}",
             "https://sinonim.org/s/{w}", "https://gufo.me/search?term={w}", "https://dic.academic.ru/searchall.php?SWord={w}",
             "https://ru.wikipedia.org/wiki/{W}")
    def __init__(self, fetcher): self.fetcher = fetcher
    def links(self, q):
        page = self.fetcher.get("https://html.duckduckgo.com/html/", data={"q": q, "kl": "ru-ru"}) or ""
        found = [unquote(u) for u in re.findall(r'uddg=([^"&]+)', page)]
        if not found:   # ah3ova: бинг прячет ссылки в base64, кто это придумал вообще
            page = self.fetcher.get("https://www.bing.com/search?setlang=ru&q=" + quote(q)) or ""
            for h in re.findall(r'<h2><a href="(https?://[^"]+)"', page):
                h = html.unescape(h); m = re.search(r"[?&]u=a1([^&]+)", h)
                if m:
                    try: h = base64.urlsafe_b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4)).decode()
                    except ValueError: continue
                found.append(h)
        return found
    def find(self, word, limit):
        urls = [u.format(w=quote(word), W=quote(word.capitalize())) for u in self.SEEDS]; hosts = {urlparse(u).netloc for u in urls}
        for q in (f"{word} значение слова", f"{word} синонимы", f"что такое {word}", f"{word} это", f"{word} определение"):
            if len(urls) >= limit: break
            for url in self.links(q):
                host = urlparse(url).netloc
                if host and host not in hosts and not any(s in host for s in self.SKIP): hosts.add(host); urls.append(url)
        return urls[:limit]
class Morphology:   # zevxsyy: русский язык это боль, но мы справились
    SPELL = "гкхжчшщ"   # после них ы превращается в и, учите правила, фойдки | kiorane: ЕБАТЬ ТЫ ГЕНИЙ ТОЧНО
    @staticmethod
    def pos(w):
        if len(w) > 4 and (w.endswith("ться") or (w.endswith("ть") and not w.endswith(("сть", "ость")))): return "verb"
        if len(w) > 4 and w.endswith(("ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие")): return "adj"
        return "noun"
    @staticmethod
    def gender(w):
        if w.endswith(("а", "я")): return "f"
        if w.endswith(("о", "е", "ё", "мя")): return "n"
        if w.endswith(("ость", "сть", "знь", "жь", "чь", "шь", "щь", "вь")): return "f"
        return "m"
    @classmethod
    def agree(cls, a, gender, plural=False):   # kiorane: я это три раза переписывала и всё равно путаюсь
        stem, end = a[:-2], a[-2:]
        spell = stem[-1] in cls.SPELL
        soft = end == "ий" and not spell
        if plural: return stem + ("ие" if soft or spell else "ые")
        if gender == "f": return stem + ("яя" if soft else "ая")
        if gender == "n": return stem + ("ее" if soft or (spell and stem[-1] in "жчшщ" and end != "ой") else "ое")
        return a
    @staticmethod
    def past(v):
        refl = v.endswith("ться"); base = v[:-4] if refl else v[:-2]
        return [base + e for e in (("лся", "лась", "лось", "лись") if refl else ("л", "ла", "ло", "ли"))]
class Analyzer:   # ah3ova: тут самая жесть, не трогайте регулярки, они живые
    @staticmethod
    def stem(w): return w[:-2] if len(w) > 6 else w[:-1] if len(w) > 4 else w
    @staticmethod
    def clean(raw):
        raw = raw[max(raw.find('id="mw-content-text"'), 0):]
        raw = re.sub(r"(?is)<(script|style|noscript|nav|footer|header|head|aside|form)[^>]*>.*?</\1>", " ", raw)
        text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
        return re.sub(r"\s+", " ", re.sub(r"\[\d+\]|\[[^\]]*править[^\]]*\]", "", text))
    def feed(self, e, word, text):
        st, low = self.stem(word), text.lower()
        for m in re.finditer(r"синоним\w*(?:\s+к\s+(?:слову\s+)?[а-яё-]+)?\s*[:\u2014\u2013]\s*([^.\n;]{3,150})", low):   # zevxsyy: тут длинные тире в виде кодов, потому что сайты их любят а мы нет
            if st in low[max(0, m.start() - 150):m.end()]:
                for p in (x.strip() for x in re.split(r"[,/]", m.group(1))):
                    if re.fullmatch(r"[а-яё]{3,20}( [а-яё]{3,20})?", p) and not p.startswith(st): e["syn"][p] += 1
        m = re.search(r"(?i:з)начени[ея]\s*(?:1\.\s*)?([^◆]{8,150}?)\s*(?:◆|2\.)", text)   # kiorane: тут была заглавная буква, я её спрятал, оно работает, отстаньте
        if m and st in text[:500].lower() and not JUNK.search(m.group(1)): e["defs"][" ".join(m.group(1).split())] += 2
        pat = re.compile(rf"\b{re.escape(st)}\w*\s*(?:[\u2014\u2013-]|это|означает|обозначает)\s+(?:это\s+)?(.{{12,200}}?)(?:[.;!?]|$)", re.I)
        for s in re.split(r"(?<=[.!?])\s+", text):
            if not 12 < len(s) < 400 or st not in s.lower() or JUNK.search(s): continue
            m = pat.search(s)
            if m:
                d = " ".join(re.sub(r"\([^)]*\)", "", m.group(1)).split()[:20]).strip(" ,:;\u2014-")
                if len(d.split()) >= 3 and not JUNK.search(d) and not re.search(r"[\[\]\d]", d): e["defs"][d] += 1
            toks = WORD.findall(s.lower())
            if toks and toks[0].startswith(st) and 30 <= len(s) <= 180: e["sents"][s] += 1
            e["rel"].update(t for t in toks if len(t) >= 4 and t not in STOP and not t.startswith(st))
class Composer:   # kiorane: если ответ тупой, то виноваты сайты, а не я
    NAMES = {"noun": "существительное", "adj": "прилагательное", "verb": "глагол"}
    RODS = {"m": "мужского", "f": "женского", "n": "среднего"}
    @staticmethod
    def top(d, n, min_count=1):
        d = {k: v for k, v in d.items() if v >= min_count}
        return sorted(d, key=d.get, reverse=True)[:n]
    def define(self, w, e):
        defs, sents = e.get("defs", {}), e.get("sents", {})
        if defs: return f"{w} - {max(defs.items(), key=lambda kv: (kv[1], -abs(len(kv[0]) - 70)))[0]}."
        if sents: return min(sents, key=lambda t: abs(len(t) - 90))
        pos, g = Morphology.pos(w), Morphology.gender(w)
        if pos == "verb": return f"{w} - глагол, прошедшее время: {', '.join(Morphology.past(w))}."
        return f"{w} - {self.NAMES[pos]}" + (f" {self.RODS[g]} рода." if pos == "noun" else ".")
    def synonyms(self, w, e):
        syn = self.top(e.get("syn", {}), 4)
        if not syn: return None
        one = len(syn) == 1
        return f"{Morphology.agree('близкий', 'n' if one else 'm', plural=not one)} по смыслу {'слово' if one else 'слова'} - {', '.join(syn)}."
    def link(self, a, ea, b, eb):
        ra, rb = ea.get("rel", {}), eb.get("rel", {})
        shared = sorted(set(ra) & set(rb), key=lambda k: ra[k] + rb[k], reverse=True)[:3]
        if shared:
            one = len(shared) == 1
            return f"у слов «{a}» и «{b}» {Morphology.agree('общий', 'n', plural=not one)} {'понятие' if one else 'понятия'} - {', '.join(shared)}."
        if any(t.startswith(Analyzer.stem(b)) for t in ra) or any(t.startswith(Analyzer.stem(a)) for t in rb): return f"слова «{a}» и «{b}» встречаются в одних контекстах."
        return f"связи между «{a}» и «{b}» не найдено."
    def answer(self, intent, words, known):
        keys = [w for w in words if w in known]
        if len(keys) > 1:
            a, b = keys[:2]
            return [self.define(a, known[a]), self.define(b, known[b]), self.link(a, known[a], b, known[b])]
        w, e = keys[0], known[keys[0]]
        syn = self.synonyms(w, e)
        out = [syn or f"синонимов к «{w}» не найдено.", self.define(w, e)] if intent == "syn" else [self.define(w, e), syn]
        return [t for t in out if t][:3]
class Brain:   # ah3ova: мозг у нас один на троих, так что аккуратнее
    def __init__(self, store):
        self.store, self.analyzer, self.composer = store, Analyzer(), Composer()
        self.error, self.fresh, self.tried = None, False, set()
    @staticmethod
    def keywords(query):
        ws = re.findall(r"[a-zа-яё]+(?:-[a-zа-яё]+)?", query.lower())
        return [w for i, w in enumerate(ws) if len(w) > 2 and w not in STOP and w not in ASK and w not in ws[:i]]
    def learn(self, word, say):
        n = DEPTHS[self.store.settings["depth"]]
        fetcher = Fetcher(self.store.settings["lib"])
        urls = Searcher(fetcher).find(word, n * 2)   # zevxsyy: берём с запасом, половина сайтов всё равно мёртвая
        e = {"defs": Counter(), "sents": Counter(), "syn": Counter(), "rel": Counter(), "v": VERSION}; ok = 0
        say(f"изучаю «{word}»: нужно сайтов {n}, найдено адресов {len(urls)}" + (f" (поиск: {fetcher.error})" if len(urls) < n * 2 and fetcher.error else ""))
        try:
            for url in urls:
                if ok >= n: break
                page = fetcher.get(url); ok += bool(page)
                say(f"  {'✓' if page else '✗'} {ok}/{n} " + (urlparse(url).netloc if page else fetcher.error or "пустой ответ"))
                if page: self.analyzer.feed(e, word, self.analyzer.clean(page))
        except KeyboardInterrupt: say("поиск прерван, использую найденное.")
        self.error, e["depth"] = fetcher.error, ok
        if ok: self.store.put(word, e); return e
        return None
    @staticmethod
    def intent(query): return "syn" if re.search(r"синоним|похож|как ещё", query.lower()) else "def"
    def ask(self, query, say):
        words = self.keywords(query) or re.findall(r"[a-zа-яё]{2,}", query.lower())[-1:]
        if not words: return "не понял запрос. напиши слово или вопрос, например: «что такое кошка»."
        words = words[-2:] if re.search(r"\bи\b|связ|между|отлич|разниц|сравн|общ", query.lower()) else words[-1:]
        depth, known, self.fresh = DEPTHS[self.store.settings["depth"]], {}, False
        for w in words:
            e = self.store.get(w)
            if e and e.get("v") != VERSION: e = None
            if (not e or e.get("depth", 0) < depth) and w not in self.tried:
                self.tried.add(w); self.fresh = True; e = self.learn(w, say) or e
            if e: known[w] = e
        if not known: return f"по слову «{words[0]}» данных нет. причина: {self.error or 'страницы не найдены'}."
        return " ".join(self.composer.answer(self.intent(query), words, known))
F = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"
# kiorane: тут пробелы между блоками это не пустые строки, не удаляй, а то карточки слипнутся
INFO = """main developer: zevxsis
helper: kiorane, ah2ova

version 0.11
powered by internet requests

backend: zevxsyy
frontend: kiorane, ah3ova
main engineer: zevxsyy, kiorane
idea: zevxsis

first prototype maded by zevxsyy
time working: 30d, 15h ~52min

more information in
telegram chanel: @tembedded
github: zevxsyy / kiorane"""
HH = 160
NAVS = (("чат", "💬"), ("настройки", "⚙️"), ("информация", "ℹ️"))
BG = CARD = SEL = ACC = ACC2 = DIM = TXT = EDGE = HOV = "#000000"
def mix(a, b, t): return "#%02x%02x%02x" % tuple(int(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (1, 3, 5))
def apply_theme(name):   # ah3ova: поменяешь тут цифры и у тебя глаза вытекут, проверено
    global BG, CARD, SEL, ACC, ACC2, DIM, TXT, EDGE, HOV
    ACC = THEMES.get(name, THEMES["фиолетовый"])
    BG, CARD, SEL = mix("#000000", ACC, .07), mix("#000000", ACC, .11), mix("#000000", ACC, .22)
    EDGE, HOV = mix("#000000", ACC, .40), mix("#000000", ACC, .32)
    ACC2, DIM, TXT = mix(ACC, "#ffffff", .38), mix("#8a8a96", ACC, .28), mix("#ffffff", ACC, .06)
def rrect(c, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)
class Pill(tk.Canvas):   # zevxsyy: обычные кнопки на маке красятся как попало, поэтому вот это, не ной
    def __init__(self, parent, text, cmd, w=120, h=38, bg=None, hover=None, pbg=None, size=13, anchor="center"):
        bg, hover, pbg = bg or SEL, hover or HOV, pbg or CARD
        super().__init__(parent, width=w, height=h, bg=pbg, highlightthickness=0, cursor="hand2")
        self.off, self.base, self.hov = bg, bg, hover
        self.shape = rrect(self, 1, 1, w - 1, h - 1, h // 2, fill=bg, outline="")
        self.create_text(w // 2 if anchor == "center" else 20, h // 2, text=text, fill=TXT, font=(F, size, "bold"), anchor="center" if anchor == "center" else "w")
        self.bind("<Button-1>", lambda e: cmd())
        self.bind("<Enter>", lambda e: self.itemconfig(self.shape, fill=self.hov)); self.bind("<Leave>", lambda e: self.itemconfig(self.shape, fill=self.base))
    def active(self, on): self.base, self.hov = (ACC, ACC2) if on else (self.off, HOV); self.itemconfig(self.shape, fill=self.base)
class Dot(tk.Canvas):   # kiorane: кружочки сделала я, поэтому они самые красивые
    def __init__(self, parent, color, cmd):
        super().__init__(parent, width=36, height=36, bg=CARD, highlightthickness=0, cursor="hand2")
        self.ring = self.create_oval(5, 5, 31, 31, fill=color, outline="", width=3); self.bind("<Button-1>", lambda e: cmd())
    def active(self, on): self.itemconfig(self.ring, outline="#ffffff" if on else "")
class App(tk.Tk):   # ah3ova: ребят, а давайте не будем ссориться из за фронта, ладно, я сама всё починю
    def __init__(self):
        super().__init__()
        self.title("GengarIRT"); self.geometry("1100x800"); self.minsize(920, 700)
        self.store = Store(); self.brain = Brain(self.store)
        self.busy, self.result, self.t0, self.gen, self.job, self.page = False, [], 0, 0, None, "чат"
        self.history = [("привет! я генгар 👻 напиши слово или вопрос, я изучу его в интернете и отвечу.", "bot", "")]
        try: self.img, self.err = self.photo(), ""
        except (OSError, tk.TclError) as err: self.img, self.err = None, f"картинка не загрузилась: {err} (tk {tk.TkVersion})"
        self.build(); self.lift(); self.attributes("-topmost", True)
        self.after(400, lambda: (self.attributes("-topmost", False), self.focus_force(), self.entry.focus_set()))   # zevxsyy: на маке окно стартует вообще без фокуса, спасибо яблоку
    def photo(self):
        exts = (".png", ".gif", ".jpg", ".jpeg")
        dirs = [HERE, os.path.dirname(os.path.abspath(sys.argv[0])), os.getcwd()]
        dirs = [d for d in dict.fromkeys(dirs + [os.path.join(d, "assets") for d in dirs]) if os.path.isdir(d) and os.access(d, os.R_OK)]
        files = [os.path.join(d, n) for d in dirs for n in os.listdir(d) if n.lower().startswith("gengar") and n.lower().endswith(exts)]
        if not files: raise FileNotFoundError("нет gengar.png, искал в: " + ", ".join(dirs))
        src = min(files, key=lambda f: exts.index(os.path.splitext(f)[1].lower()))
        try:
            from PIL import Image, ImageTk
            im = Image.open(src); im.thumbnail((300, 110)); return ImageTk.PhotoImage(im)
        except ImportError:
            try: img = tk.PhotoImage(file=src)
            except tk.TclError:   # kiorane: старый tk не читает png, сидим конвертим через sips как в каменном веке
                dst = os.path.join(tempfile.gettempdir(), "gengarirt.gif")
                os.system(f'sips -s format gif "{src}" --out "{dst}" >/dev/null 2>&1'); img = tk.PhotoImage(file=dst)
            return img.subsample(max(1, img.height() // 110))
    def build(self):
        apply_theme(self.store.settings["theme"]); self.configure(bg=BG)
        self.seg, self.nav, self.names, self.glow = {}, {}, {}, []
        self.edge_id = self.gid = None
        self.cv = tk.Canvas(self, bg=BG, highlightthickness=0); self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.cv.bind("<Configure>", lambda e: self.layout())
        self.panel = tk.Frame(self.cv, bg=CARD); self.panel_win = self.cv.create_window(0, 0, window=self.panel, anchor="nw")
        self.pages = {"чат": self.chat_page(self.panel), "настройки": self.settings_page(self.panel), "информация": self.info_page(self.panel)}
        self.make_fx(); self.show(self.page)
        for item in self.history: self.put(*item)
        self.t_anim = time.time(); self.tick()
        if self.page == "чат": self.entry.focus_set()
    def rebuild(self):   # zevxsyy: тему меняем пересборкой, да, лениво, зато работает и не падает
        self.gen += 1
        if self.job: self.after_cancel(self.job)
        for w in self.winfo_children(): w.destroy()
        self.build(); self.layout()
    def make_fx(self):
        c = self.cv; self.orbs, self.parts = [], []
        for col, R in ((ACC, 280), (ACC2, 210), (mix(ACC, "#ffffff", .12), 330)):
            ids = [c.create_oval(0, 0, 1, 1, fill=mix(BG, col, .035 + .028 * k), outline="") for k in range(6)]
            self.orbs.append({"ids": ids, "R": R, "x": random.uniform(0, 1100), "y": random.uniform(0, 800), "vx": random.choice((-1, 1)) * random.uniform(.25, .55), "vy": random.choice((-1, 1)) * random.uniform(.2, .45)})
        for i in range(36):
            star = i % 5 == 0   # ah3ova: каждая пятая это звезда, не спрашивай почему пять
            item = c.create_text(0, 0, text="✦", font=(F, random.choice((9, 12, 15))), fill=ACC2, tags="p") if star else c.create_oval(0, 0, 1, 1, outline="", fill=ACC2, tags="p")
            self.parts.append({"id": item, "star": star, "r": random.uniform(1.5, 3.2), "x": random.uniform(0, 1100), "y": random.uniform(0, 800), "vx": random.uniform(-.25, .25), "vy": -random.uniform(.2, .8), "ph": random.uniform(0, 6.3), "sp": random.uniform(.8, 2.4)})
    def tick(self):
        try: self.animate()
        except tk.TclError: pass
        self.job = self.after(33, self.tick)
    def animate(self):
        if self.store.settings["anim"] != "вкл": return
        c, t = self.cv, time.time() - self.t_anim
        w, h = max(c.winfo_width(), 400), max(c.winfo_height(), 300)
        for o in self.orbs:
            o["x"] += o["vx"]; o["y"] += o["vy"]
            if not -120 < o["x"] < w + 120: o["vx"] *= -1
            if not -120 < o["y"] < h + 120: o["vy"] *= -1
            for k, i in enumerate(o["ids"]):
                r = o["R"] * (1 - k * .14) * (1 + .05 * math.sin(t * .7 + o["R"]))
                c.coords(i, o["x"] - r, o["y"] - r, o["x"] + r, o["y"] + r)
        for p in self.parts:
            p["x"] += p["vx"] + .25 * math.sin(t * .9 + p["ph"]); p["y"] += p["vy"]
            if p["y"] < -20: p["y"], p["x"] = h + 20, random.uniform(0, w)
            p["x"] = (p["x"] + 20) % (w + 40) - 20
            col = mix(BG, ACC2, .22 + .6 * (.5 + .5 * math.sin(t * p["sp"] + p["ph"])))
            if p["star"]: c.coords(p["id"], p["x"], p["y"])
            else: r = p["r"]; c.coords(p["id"], p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r)
            c.itemconfig(p["id"], fill=col)
        c.delete("ln")
        pts = [(p["x"], p["y"]) for p in self.parts if not p["star"]]
        for i, (x1, y1) in enumerate(pts):
            for x2, y2 in pts[i + 1:]:
                d = math.hypot(x1 - x2, y1 - y2)
                if d < 135: c.create_line(x1, y1, x2, y2, fill=mix(BG, ACC, .55 * (1 - d / 135)), tags="ln")
        c.tag_lower("ln", "p")
        c.itemconfig("title", fill=mix(ACC2, "#ffffff", .55 * (.5 + .5 * math.sin(t * 1.6))))
        if self.gid:
            c.coords(self.gid, self.gx, self.gy + 7 * math.sin(t * 1.7))
            for i, pid in enumerate(self.glow): c.itemconfig(pid, fill=mix(mix(BG, ACC, .18), ACC, (.12, .24, .40)[i] + .07 * math.sin(t * 2 + i)))
        if self.edge_id: c.itemconfig(self.edge_id, outline=mix(EDGE, ACC, .5 + .5 * math.sin(t * 1.3)))
    def chip(self, x, y, text):
        wd = 8 * len(text) + 26
        rrect(self.cv, x, y - 14, x + wd, y + 14, 14, fill=SEL, outline=EDGE, tags="static")
        self.cv.create_text(x + wd / 2, y, text=text, fill=TXT, font=(F, 11), tags="static")
        return x + wd + 8
    def navpaint(self, name): self.cv.itemconfig(self.nav[name], fill=ACC if self.page == name else CARD)
    def layout(self):
        c, w, h = self.cv, self.cv.winfo_width(), self.cv.winfo_height()
        if w < 100 or h < 100: return
        c.delete("grad"); c.delete("static"); self.nav = {}
        top = mix(BG, ACC, .22)
        for y in range(0, h, 4): c.create_rectangle(0, y, w, y + 4, fill=mix(top, BG, min(1, y / h * 1.5)), width=0, tags="grad")
        c.tag_lower("grad")
        c.create_text(46, 58, text="GengarIRT", font=(F, 44, "bold"), fill=mix(BG, ACC, .5), anchor="w", tags="static")
        c.create_text(44, 56, text="GengarIRT", font=(F, 44, "bold"), fill=ACC2, anchor="w", tags=("static", "title"))
        c.create_text(46, 98, text="powered by internet requests", font=(F, 14), fill=DIM, anchor="w", tags="static")
        s, x = self.store.settings, 44
        for t in ("v0.11", "by zevxsis", s["lib"], f"{s['depth']} · {DEPTHS[s['depth']]}", f"{len(self.store.data['words'])} слов"): x = self.chip(x, 130, t)
        if self.err: c.create_text(44, 154, text=self.err, fill=DIM, font=(F, 9), anchor="w", width=max(200, w - 380), tags="static")
        self.glow = []
        if self.img:
            iw, ih = self.img.width(), self.img.height(); self.gx, self.gy = w - 50 - iw / 2, HH / 2
            for i in range(3): self.glow.append(rrect(c, self.gx - iw / 2 - 20 + i * 6, self.gy - ih / 2 - 16 + i * 5, self.gx + iw / 2 + 20 - i * 6, self.gy + ih / 2 + 16 - i * 5, 30, fill=mix(top, ACC, .15), outline="", tags="static"))
            self.gid = c.create_image(self.gx, self.gy, image=self.img, tags="static")
        else: self.gx, self.gy = w - 120, HH / 2; self.gid = c.create_text(self.gx, self.gy, text="👻", font=(F, 80), tags="static")
        for i, (name, icon) in enumerate(NAVS):
            y, tag = HH + 16 + i * 58, f"nav{i}"
            self.nav[name] = rrect(c, 24, y, 214, y + 46, 23, fill=ACC if self.page == name else CARD, outline=EDGE, tags=("static", tag))
            c.create_text(48, y + 23, text=f"{icon}  {name}", fill=TXT, font=(F, 14, "bold"), anchor="w", tags=("static", tag))
            c.tag_bind(tag, "<Button-1>", lambda e, n=name: self.show(n))
            c.tag_bind(tag, "<Enter>", lambda e, n=name: (c.itemconfig(self.nav[n], fill=ACC2 if self.page == n else HOV), c.config(cursor="hand2")))
            c.tag_bind(tag, "<Leave>", lambda e, n=name: (self.navpaint(n), c.config(cursor="")))
        c.create_text(119, h - 28, text="v0.11 · by zevxsis", font=(F, 10), fill=DIM, tags="static")
        px, py = 232, HH; pw, ph = w - px - 24, h - py - 24
        self.edge_id = rrect(c, px, py, px + pw, py + ph, 14, fill=CARD, outline=EDGE, width=2, tags="static")
        c.coords(self.panel_win, px + 6, py + 6); c.itemconfigure(self.panel_win, width=max(100, pw - 12), height=max(100, ph - 12))
    def show(self, name):
        self.page = name
        for p in self.pages.values(): p.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for n in self.nav: self.navpaint(n)
    def fg(self): return COLORS.get(self.store.settings["color"], TXT)
    def title_label(self, parent, text): tk.Label(parent, text=text, font=(F, 24, "bold"), fg=ACC2, bg=CARD).pack(anchor="w", padx=30, pady=(22, 4))
    def chat_page(self, parent):
        f = tk.Frame(parent, bg=CARD)
        bar = tk.Canvas(f, height=58, bg=CARD, highlightthickness=0); bar.pack(side="bottom", fill="x", padx=18, pady=(6, 16))
        self.status = tk.Label(f, text="", bg=CARD, fg=ACC2, font=(F, 12), anchor="w"); self.status.pack(side="bottom", fill="x", padx=26)
        self.log = tk.Text(f, bg=CARD, fg=TXT, font=(F, 14), wrap="word", bd=0, padx=8, pady=14, height=8, state="disabled", highlightthickness=0, cursor="arrow"); self.log.pack(fill="both", expand=True, padx=10)
        for tag, kw in (("me", dict(background=ACC, foreground="#ffffff", justify="right", lmargin1=280, lmargin2=280, rmargin=14)),
                        ("bot", dict(background=SEL, foreground=self.fg(), lmargin1=14, lmargin2=14, rmargin=280)),
                        ("dim", dict(foreground=DIM, font=(F, 10), lmargin1=18)), ("gap", dict(font=(F, 6)))): self.log.tag_config(tag, spacing1=5, spacing3=5, **kw)
        self.entry = tk.Entry(bar, bg=SEL, fg="#ffffff", insertbackground="#ffffff", font=(F, 14), bd=0, highlightthickness=0); self.entry.bind("<Return>", lambda e: self.send())
        ew, sw = bar.create_window(26, 29, window=self.entry, anchor="w"), bar.create_window(0, 29, anchor="e", window=Pill(bar, "➤", self.send, w=46, h=42, bg=ACC, hover=ACC2, pbg=SEL, size=16))
        def lay(e):   #kiorane: капсула растягивается, я гений, можете хлопать
            bar.delete("bg"); rrect(bar, 1, 1, e.width - 1, 57, 28, fill=SEL, outline=EDGE, tags="bg"); bar.tag_lower("bg")
            bar.coords(sw, e.width - 12, 29); bar.itemconfigure(ew, width=max(50, e.width - 110))
        bar.bind("<Configure>", lay)
        return f
    def put(self, text, tag, note="", typing=False):
        self.log.config(state="normal")
        if typing and self.store.settings["anim"] == "вкл": self.log.insert("end", "  ", tag); self.log.config(state="disabled"); self.type_out(text, tag, note, 0, self.gen); return
        self.log.insert("end", f"  {text}  \n", tag, f"  {note}\n" if note else "", "dim", "\n", "gap")
        self.log.config(state="disabled"); self.log.see("end")
        if typing: self.busy = False
    def type_out(self, text, tag, note, i, gen):
        if gen != self.gen: self.busy = False; return   # ah3ova: если окно пересобрали, то печатать уже некуда, всё, расходимся
        self.log.config(state="normal")
        if i < len(text): self.log.insert("end-1c", text[i:i + 3], tag); self.log.config(state="disabled"); self.log.see("end"); self.after(14, self.type_out, text, tag, note, i + 3, gen)
        else: self.log.insert("end-1c", "  \n", tag, f"  {note}\n" if note else "", "dim", "\n", "gap"); self.log.config(state="disabled"); self.log.see("end"); self.busy = False
    def say(self, text, tag, note="", typing=False): self.history.append((text, tag, note)); self.put(text, tag, note, typing)
    def send(self):
        q = self.entry.get().strip()
        if not q or self.busy: return
        self.entry.delete(0, "end"); self.say(q, "me")
        self.busy, self.result, self.t0 = True, [], time.time()
        threading.Thread(target=self.work, args=(q,), daemon=True).start()   # zevxsyy: поток нужен, иначе окно зависнет и вы опять напишете в чат что всё сломано
        self.think(0)
    def work(self, q):
        try: self.result.append(self.brain.ask(q, lambda m: None))
        except ImportError as err: self.result.append(f"не установлена библиотека {err.name}: pip install {err.name}")
        except Exception as err: self.result.append(f"ошибка: {err}")
    def think(self, n):
        try:
            if self.result: self.status.config(text=""); self.say(self.result[0], "bot", f"{time.time() - self.t0:.0f} с{'' if self.brain.fresh else ' · из памяти'}", typing=True); self.layout()
            else: self.status.config(text="👻 генгар думает" + "." * (n % 4)); self.after(350, self.think, n + 1)
        except tk.TclError: self.after(350, self.think, n + 1)
    def settings_page(self, parent):
        f = tk.Frame(parent, bg=CARD); self.title_label(f, "настройки")
        spec = (("theme", "цвет темы", tuple(THEMES)), ("anim", "анимации", ("вкл", "выкл")), ("lib", "библиотека поиска", LIBS), ("depth", "глубина поиска", tuple(DEPTHS)), ("color", "цвет текста ответов", tuple(COLORS)))
        for key, title, opts in spec:
            tk.Label(f, text=title, font=(F, 11, "bold"), fg=DIM, bg=CARD).pack(anchor="w", padx=30, pady=(14, 6))
            row = tk.Frame(f, bg=CARD); row.pack(anchor="w", padx=30)
            for o in opts:
                cmd = lambda k=key, o=o: self.choose(k, o)
                if key in ("theme", "color"): w = Dot(row, (THEMES if key == "theme" else COLORS)[o], cmd)
                else: w = Pill(row, f"{o} · {DEPTHS[o]} сайтов" if key == "depth" else o, cmd, w=190 if key == "depth" else 130, h=40)
                w.pack(side="left", padx=(0, 10)); self.seg.setdefault(key, {})[o] = w
            if key in ("theme", "color"): self.names[key] = tk.Label(row, fg=DIM, bg=CARD, font=(F, 12)); self.names[key].pack(side="left", padx=6)
        tk.Label(f, text="чем глубже поиск, тем дольше ответ. если окно тормозит, выключи анимации.", font=(F, 11), fg=DIM, bg=CARD).pack(anchor="w", padx=30, pady=18)
        self.refresh()
        return f
    def choose(self, key, opt):
        self.store.settings[key] = opt; self.store.save()
        if key in ("theme", "anim"): self.rebuild()
        else: self.refresh(); self.layout()
    def refresh(self):
        s = self.store.settings
        for key, widgets in self.seg.items():
            for opt, w in widgets.items(): w.active(s[key] == opt)
        for key, lab in self.names.items(): lab.config(text=s[key])
        self.log.tag_config("bot", foreground=self.fg())
    def info_page(self, parent):
        f = tk.Frame(parent, bg=CARD); self.title_label(f, "информация")
        grid = tk.Frame(f, bg=CARD); grid.pack(fill="both", padx=24, pady=6)
        for i, block in enumerate(INFO.split("\n\n")):
            card = tk.Frame(grid, bg=SEL, padx=18, pady=14, highlightbackground=EDGE, highlightthickness=1)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6); grid.columnconfigure(i % 2, weight=1)
            for line in block.splitlines():
                k, _, v = line.partition(": ")
                row = tk.Frame(card, bg=SEL); row.pack(anchor="w")
                if v: tk.Label(row, text=k + ":", font=(F, 12), fg=DIM, bg=SEL).pack(side="left"); tk.Label(row, text=v, font=(F, 13, "bold"), fg=TXT, bg=SEL).pack(side="left", padx=(8, 0))
                else: tk.Label(row, text=line, font=(F, 13, "bold"), fg=ACC2, bg=SEL).pack()
        return f
if __name__ == "__main__": App().mainloop()