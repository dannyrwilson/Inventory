"""NIIMBOT D11 / D11_H label printing over Bluetooth LE from the Pi.

Ported from the Distill Log app's printing feature (Dart). Protocol per the
NIIMBOT community wiki (https://printers.niim.blue/interfacing/print-tasks/)
and niimbluelib. Only print commands are sent: nothing that changes firmware,
calibration or printer settings.
"""
import asyncio
import logging

log = logging.getLogger("inventory.printer")

SERVICE_UUID = "e7810a71-73ae-499d-8c15-faa9aef0c3f2"
CHAR_UUID = "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f"
REPLY_TIMEOUT = 3.0

# command: (code, reply code or None)
CONNECT = (0xC1, None)
HEARTBEAT = (0xDC, None)
PRINTER_INFO = (0x40, 0x48)
SET_DENSITY = (0x21, 0x31)
SET_LABEL_TYPE = (0x23, 0x33)
PRINT_START = (0x01, 0x02)
PRINT_CLEAR = (0x20, 0x30)
PAGE_START = (0x03, 0x04)
SET_PAGE_SIZE = (0x13, 0x14)
PRINT_QUANTITY = (0x15, 0x16)
EMPTY_ROWS = (0x84, None)
BITMAP_ROWS = (0x85, None)
PAGE_END = (0xE3, 0xE4)
PRINT_STATUS = (0xA3, 0xB3)
PRINT_END = (0xF3, 0xF4)
PAGE_INDEX = 0xE0  # older D11 firmware reports printed pages by itself

ORIGINAL, LEGACY, MODERN = "original", "legacy", "modern"

MESSAGES = {
    SET_DENSITY: "The printer refused the print darkness setting. Reconnect the printer and try again.",
    SET_LABEL_TYPE: "The printer refused the label type. Check the label roll and close its cover.",
    PRINT_START: "The printer could not start the label. Check the label roll and close its cover.",
    SET_PAGE_SIZE: "The printer refused the label size. Check that the loaded labels match the selected length.",
    PRINT_CLEAR: "The printer could not prepare the label. Check the paper and reconnect the printer.",
    PAGE_START: "The printer could not prepare the label. Check the paper and reconnect the printer.",
    PRINT_QUANTITY: "The printer refused the number of copies. Reconnect the printer and try again.",
    PAGE_END: "The printer did not accept the finished label. Check the paper before trying again.",
}


class PrinterError(Exception):
    pass


class NoReply(PrinterError):
    def __init__(self):
        super().__init__("The printer did not confirm this step. Check the paper and try reconnecting.")


class Profile:
    def __init__(self, id, name, dpi, head, density, tasks):
        self.id, self.name, self.dpi, self.head, self.density, self.tasks = id, name, dpi, head, density, tasks

    @property
    def row_pixels(self):
        return (self.head + 7) // 8 * 8

    @property
    def task(self):
        return self.tasks[0]


D11 = Profile(512, "D11", 203, 96, 2, [ORIGINAL, LEGACY])
D11H = Profile(528, "D11_H", 300, 142, 3, [MODERN])
PROFILES = {p.id: p for p in (D11, D11H)}


def guess_profile(device_name):
    """Before connecting: D11_H advertises as 'D11_H...'."""
    return D11H if (device_name or "").upper().startswith("D11_H") else D11


# ------------------------------------------------------------------ packets
def encode(command, data):
    data = list(data)
    if not (0 <= command <= 255) or len(data) > 255 or any(not 0 <= v <= 255 for v in data):
        raise ValueError("Invalid printer packet.")
    check = command ^ len(data)
    for v in data:
        check ^= v
    return bytes([0x55, 0x55, command, len(data), *data, check, 0xAA, 0xAA])


def connect_frame():
    return bytes([0x03]) + encode(CONNECT[0], [1])


def be16(data):
    return (data[0] << 8) | data[1]


class Decoder:
    """Reassembles frames from notifications (partial or several per chunk)."""

    def __init__(self):
        self.pending = bytearray()

    def add(self, chunk):
        self.pending += chunk
        out = []
        p = self.pending
        while len(p) >= 7:
            if p[0] != 0x55 or p[1] != 0x55:
                del p[0]
                continue
            length = p[3]
            full = 7 + length
            if len(p) < full:
                break
            check = p[2] ^ length
            for i in range(4, 4 + length):
                check ^= p[i]
            if p[4 + length] != check or p[5 + length] != 0xAA or p[6 + length] != 0xAA:
                del p[0]
                continue
            out.append((p[2], bytes(p[4:4 + length])))
            del p[:full]
        if len(p) > 1024:
            p.clear()
        return out


# ------------------------------------------------------------------ bitmap
class Bitmap:
    """1-bit, MSB first, black=1; width = dots across the head (padded to 8)."""

    def __init__(self, width, height, pixels):
        self.width, self.height, self.pixels = width, height, bytes(pixels)
        if width <= 0 or width > 1024 or height <= 0 or height > 4800 or width % 8 or \
                len(self.pixels) != self.stride * height:
            raise ValueError("Unsupported label bitmap.")

    @property
    def stride(self):
        return (self.width + 7) // 8

    def packets(self, total_counts):
        s, px = self.stride, self.pixels
        y = 0
        while y < self.height:
            row = px[y * s:(y + 1) * s]
            repeat = 1
            while repeat < 200 and y + repeat < self.height and px[(y + repeat) * s:(y + repeat + 1) * s] == row:
                repeat += 1
            if not any(row):
                yield (EMPTY_ROWS[0], [y >> 8, y & 255, repeat])
            else:
                if total_counts:
                    total = _dots(row)
                    a, b, c = 0, total & 255, total >> 8
                else:
                    third = -(-s // 3)
                    a, b, c = _dots(row[:third]), _dots(row[third:third * 2]), _dots(row[third * 2:])
                yield (BITMAP_ROWS[0], [y >> 8, y & 255, a, b, c, repeat, *row])
            y += repeat


def _dots(bs):
    return sum(bin(b).count("1") for b in bs)


# ------------------------------------------------------------------ job steps
def open_job_steps(profile, task):
    steps = []
    if task == MODERN:
        steps.append(("ask", SET_LABEL_TYPE, [1]))
    steps.append(("ask", SET_DENSITY, [profile.density]))
    if task != MODERN:
        steps.append(("ask", SET_LABEL_TYPE, [1]))
    steps.append(("ask", PRINT_START, [1] if task != MODERN else [0, 1, 0, 0, 0, 0, 0, 1, 0]))
    return steps


def page_steps(task, bm):
    h, w = [bm.height >> 8, bm.height & 255], [bm.width >> 8, bm.width & 255]
    if task in (ORIGINAL, LEGACY):
        steps = [("ask", PRINT_CLEAR, [1]), ("ask", PAGE_START, [1]),
                 ("ask", SET_PAGE_SIZE, h + (w if task == ORIGINAL else [])),
                 ("ask", PRINT_QUANTITY, [0, 1])]
    else:
        steps = [("send", PRINT_STATUS[0], [1], 0.03),
                 ("ask", SET_PAGE_SIZE, h + w + [0, 1, 0, 0, 0, 0, 0, 0, 0])]
    for code, data in bm.packets(total_counts=(task == MODERN)):
        steps.append(("send", code, data, 0))
    steps.append(("ask", PAGE_END, [1], 10.0 if task == MODERN else REPLY_TIMEOUT))
    return steps


def close_job_steps(task):
    steps = [("ask", PRINT_END, [1])]
    if task == MODERN:
        steps.append(("send", HEARTBEAT[0], [1], 0))
    return steps


def accepted(command, data):
    if len(data) == 1:
        return data[0] == 1
    # captured success: 55 55 14 02 01 00 17 aa aa (niimblue issue #71)
    return command == SET_PAGE_SIZE and len(data) == 2 and data[0] == 1 and data[1] == 0


# ------------------------------------------------------------------ session
class Session:
    """A printer session over a transport with `write(bytes)` (one BLE write)
    and `is_open`. Feed notifications into `feed()`."""

    def __init__(self, transport, mtu=None, sleep=asyncio.sleep, clock=None):
        self.t = transport
        self.chunk = max(20, min(244, mtu - 3)) if mtu else 20
        self.sleep = sleep
        self.decoder = Decoder()
        self.waiters = []
        self.profile = None
        self.closed = False

    def feed(self, data):
        for pkt in self.decoder.add(data):
            for w in list(self.waiters):
                test, fut = w
                if not fut.done() and test(pkt):
                    fut.set_result(pkt)

    def lost(self):
        self.closed = True
        for _, fut in self.waiters:
            if not fut.done():
                fut.set_exception(PrinterError("The printer disconnected. Turn it on and try again."))

    async def write(self, data):
        for off in range(0, len(data), self.chunk):
            if self.closed:
                raise PrinterError("The printer disconnected. Turn it on and try again.")
            await self.t.write(bytes(data[off:off + self.chunk]))
            await self.sleep(0.01)

    async def send(self, code, data):
        await self.write(encode(code, data))

    async def wait_for(self, test, timeout, prompt=None):
        fut = asyncio.get_running_loop().create_future()
        entry = (test, fut)
        self.waiters.append(entry)
        try:
            if prompt:
                await prompt()
            return await asyncio.wait_for(fut, timeout)
        finally:
            self.waiters.remove(entry)

    async def ask(self, command, data, timeout=REPLY_TIMEOUT):
        code, reply = command
        try:
            return await self.wait_for(lambda p: p[0] == reply, timeout, lambda: self.send(code, data))
        except asyncio.TimeoutError:
            raise NoReply()

    async def start(self):
        await self.sleep(0.2)
        await self.write(connect_frame())
        await self.sleep(0.2)
        _, info = await self.ask(PRINTER_INFO, [8])
        if len(info) < 2:
            raise PrinterError("The printer did not identify its model.")
        mid = be16(info)
        self.profile = PROFILES.get(mid)
        if not self.profile:
            raise PrinterError(f"Printer model {mid} is not supported yet.")
        await self.send(HEARTBEAT[0], [1])  # the original D11 needs this before a job
        await self.sleep(0.15)
        return self.profile

    async def _run(self, steps):
        for st in steps:
            if st[0] == "send":
                _, code, data, pause = st
                await self.send(code, data)
                if pause:
                    await self.sleep(pause)
            else:
                command, data = st[1], st[2]
                timeout = st[3] if len(st) > 3 else REPLY_TIMEOUT
                _, reply = await self.ask(command, data, timeout)
                if not accepted(command, reply):
                    raise PrinterError(MESSAGES.get(command, "The printer refused this job. Check the label roll and close its cover."))

    async def print_label(self, bm, task=None):
        task = task or self.profile.task
        opened = False
        try:
            await self._run(open_job_steps(self.profile, task))
            opened = True
            page = page_steps(task, bm)
            if task == LEGACY:
                await self.wait_for(lambda p: p[0] == PAGE_INDEX and len(p[1]) >= 2 and be16(p[1]) >= 1,
                                    30.0, lambda: self._run(page))
            else:
                await self._run(page)
                await self._poll_until_printed()
        except asyncio.TimeoutError:
            raise PrinterError("The printer did not confirm completion. Check the paper before trying again.")
        finally:
            if opened:
                for st in close_job_steps(task):
                    if self.closed:
                        break
                    try:
                        await self._run([st])
                    except Exception:
                        pass

    async def _poll_until_printed(self):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 30
        while loop.time() < deadline:
            try:
                _, status = await self.ask(PRINT_STATUS, [1])
            except NoReply:
                continue
            if len(status) < 4:
                raise PrinterError("The printer returned an incomplete status. Check the paper before trying again.")
            if len(status) == 10 and status[6] != 0:
                raise PrinterError("The printer reported a problem. Check its paper, cover and battery before trying again.")
            if be16(status) >= 1:
                return
            await self.sleep(0.35)
        raise PrinterError("The printer did not confirm the finished label. Check the paper before trying again.")


# ------------------------------------------------------------------ rendering
_FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(size, bold=True):
    from PIL import ImageFont
    paths = _FONT_PATHS if bold else _FONT_PATHS[::-1]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _fit(d, text, max_w, start, bold):
    """Largest font size <= start that fits text in max_w."""
    size = int(start)
    while size > 7:
        f = _font(size, bold)
        if d.textlength(text, font=f) <= max_w:
            return size
        size -= 1
    return 7


def _split2(d, text, font):
    """Split into two lines of similar width at a word break."""
    words = text.split()
    if len(words) < 2:
        return [text]
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        w = max(d.textlength(a, font=font), d.textlength(b, font=font))
        if best is None or w < best[0]:
            best = (w, [a, b])
    return best[1]


def _layout_text(d, title, sub, x0, length, head):
    """Try title on 1 or 2 lines, with or without the sub line; keep the layout
    that prints the title biggest (a sub line is worth a little title size)."""
    margin = max(2, round(head * 0.07))
    avail_h = head - margin * 2
    max_w = length - x0 - margin * 2
    if max_w < 10 or not (title or sub):
        return
    probe = _font(40, True)
    options = []
    for wrap in (1, 2):
        tl = [title] if wrap == 1 or not title else _split2(d, title, probe)
        if wrap == 2 and len(tl) < 2:
            continue
        for with_sub in ((True, False) if sub else (False,)):
            n_lines = len(tl) + (1 if with_sub else 0)
            line_h = avail_h / n_lines
            tsize = min(_fit(d, t, max_w, line_h * 0.92, True) for t in tl) if title else 0
            ssize = _fit(d, sub, max_w, min(line_h * 0.8, tsize * 0.8 or line_h * 0.8), False) if with_sub else 0
            score = tsize * (1.0 if with_sub else 0.7)
            options.append((score, tl, tsize, ssize if with_sub else 0))
    _, tl, tsize, ssize = max(options, key=lambda o: o[0])
    rows = [(t, _font(tsize, True)) for t in tl if t] + ([(sub, _font(ssize, False))] if ssize else [])
    heights = [sum(f.getmetrics()) for _, f in rows]
    gap = max(0, (avail_h - sum(heights)) / (len(rows) + 1))
    y = margin + gap
    for (text, f), h in zip(rows, heights):
        w = d.textlength(text, font=f)
        d.text((x0 + (length - x0 - w) / 2, y), text, font=f, fill=0)
        y += h + gap


def render_label(profile, title, sub="", code="", length_mm=40):
    """Returns (Bitmap, PIL preview image). Text runs along the label, QR code at the start."""
    from PIL import Image, ImageDraw
    import segno
    if not 20 <= length_mm <= 80:
        raise ValueError("Choose label length between 20 and 80 mm.")
    head = profile.head
    length = round(length_mm * profile.dpi / 25.4)
    img = Image.new("L", (length, head), 255)  # landscape: x along the label, y across the head
    d = ImageDraw.Draw(img)
    text_start = 0
    if code:
        qr = segno.make(code, error="l", boost_error=False)
        matrix = [list(r) for r in qr.matrix]
        n = len(matrix)
        module = max(1, (head - 2) // n)
        size = module * n
        inset = (head - size) // 2
        for r, row in enumerate(matrix):
            for c, v in enumerate(row):
                if v:
                    d.rectangle([inset + c * module, inset + r * module,
                                 inset + (c + 1) * module - 1, inset + (r + 1) * module - 1], fill=0)
        text_start = inset * 2 + size
    _layout_text(d, title, sub, text_start, length, head)
    bw = img.point(lambda v: 0 if v < 140 else 255, "1")
    # rotate so rows run along the feed: width = head dots
    rot = bw.rotate(90, expand=True)  # (head, length)
    row_px = profile.row_pixels
    canvas = Image.new("1", (row_px, length), 1)
    canvas.paste(rot, (0, 0))
    # pack MSB first, black=1
    raw = canvas.tobytes()  # PIL "1": MSB first, 1=white
    pixels = bytes(b ^ 0xFF for b in raw)
    return Bitmap(row_px, length, pixels), bw.convert("L")
