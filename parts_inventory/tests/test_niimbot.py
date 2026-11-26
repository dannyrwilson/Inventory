"""Replays the recorded NIIMBOT protocol transcripts (from the Distill Log app's
printer tests) against the Python port, byte for byte.

Run: python parts_inventory/tests/test_niimbot.py
"""
import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import niimbot as n  # noqa: E402


class FakePrinter:
    """Mirrors fake_printer_ble.dart: answers like a D11 / D11_H."""

    def __init__(self, model_id, polls_before_done=0, print_status=None, reject=None, malformed=False):
        self.model_id = model_id
        self.writes = []
        self.decoder = n.Decoder()
        self.session = None
        self.page_ended = False
        self.legacy_page = False
        self.label_type_set = False
        self.polls = 0
        self.polls_before_done = polls_before_done
        self.print_status = print_status or [0, 1, 100, 100]
        self.reject = reject
        self.malformed = malformed
        self.is_open = True

    async def write(self, chunk):
        self.writes.append(" ".join(f"{b:02x}" for b in chunk))
        for cmd, data in self.decoder.add(chunk):
            self.answer(cmd, data)

    def accept(self, reply, cmd):
        if cmd == self.reject or (self.model_id == 528 and cmd == 0x21 and not self.label_type_set):
            return reply, ([] if self.malformed else [0])
        return reply, ([1, 0] if self.model_id == 528 and cmd == 0x13 else [1])

    def status(self):
        if not self.page_ended:
            return [0, 0, 0, 0]
        if self.polls < self.polls_before_done:
            self.polls += 1
            return [0, 0, 50, 50]
        self.polls += 1
        return self.print_status

    def answer(self, cmd, data):
        if cmd == 0x23 and cmd != self.reject:
            self.label_type_set = True
        if cmd == 0x01:
            self.page_ended, self.polls = False, 0
        if cmd == 0x13:
            self.legacy_page = len(data) == 2
        if cmd == 0xE3:
            self.page_ended = True
        table = {0x40: lambda: (0x48, [self.model_id >> 8, self.model_id & 255]),
                 0xA3: lambda: (0xB3, self.status())}
        accepts = {0x21: 0x31, 0x23: 0x33, 0x01: 0x02, 0x13: 0x14, 0x20: 0x30, 0x03: 0x04,
                   0x15: 0x16, 0xE3: 0xE4, 0xF3: 0xF4}
        reply = table[cmd]() if cmd in table else self.accept(accepts[cmd], cmd) if cmd in accepts else None
        if cmd == 0xF3:
            self.label_type_set = False
        if reply is None:
            return
        frame = n.encode(*reply)
        # notifications arrive split, like the real printer
        asyncio.get_running_loop().call_soon(self.session.feed, frame[:3])
        asyncio.get_running_loop().call_soon(self.session.feed, frame[3:])
        if cmd == 0xE3 and self.legacy_page:
            asyncio.get_running_loop().call_soon(self.session.feed, n.encode(n.PAGE_INDEX, [0, 1]))


def d11_bitmap():
    stride, height = 12, 40
    px = bytearray(stride * height)
    for y in range(5, 10):
        for x in range(stride):
            px[y * stride + x] = (y * 31 + x * 17) & 0xFF
    px[10 * stride + 3] = 0x10
    for y in range(11, 31):
        for x in range(stride):
            px[y * stride + x] = 0xF0 if x % 2 == 0 else 0x0F
    return n.Bitmap(96, height, px)


def d11_solid():
    return n.Bitmap(96, 450, bytes([0xFF]) * (12 * 450))


def d11h_bitmap():
    stride, height = 18, 30
    px = bytearray(stride * height)
    for y in range(height):
        if y % 7 == 0:
            continue
        for x in range(stride):
            px[y * stride + x] = (y * 13 + x * 29 + 7) & 0xFF
        px[y * stride + stride - 1] &= 0xFC
    return n.Bitmap(144, height, px)


async def nosleep(_):
    await asyncio.sleep(0)


SCENARIOS = [
    ("d11 prints two labels", 512, 23, {}, [None, d11_bitmap, d11_solid]),
    ("d11 older firmware waits for the page report", 512, 23, {}, [n.LEGACY, d11_bitmap]),
    ("d11_h prints two labels", 528, 23, {}, [None, d11h_bitmap, d11h_bitmap]),
    ("d11_h writes 244-byte chunks on a large MTU", 528, 247, {}, [None, d11h_bitmap]),
    ("d11 falls back to 20-byte chunks when the MTU request fails", 512, None, {}, [None, d11_bitmap]),
    ("d11 polls until the page is printed", 512, 23, {"polls_before_done": 2}, [None, d11_bitmap]),
    ("d11 incomplete status ends the job", 512, 23, {"print_status": [0, 1]}, [None, d11_bitmap]),
    ("d11 refused print start sends no print end", 512, 23, {"reject": 0x01}, [None, d11_bitmap]),
    ("d11_h refused page size ends the started job", 528, 23, {"reject": 0x13}, [None, d11h_bitmap]),
]


async def run(model, mtu, opts, steps):
    printer = FakePrinter(model, **opts)
    s = n.Session(printer, mtu=mtu, sleep=nosleep)
    printer.session = s
    await s.start()
    task = steps[0]
    for make in steps[1:]:
        try:
            await s.print_label(make(), task=task)
        except n.PrinterError:
            pass
    return printer.writes


def main():
    fixtures = json.load(open(os.path.join(HERE, "niimbot_transcripts.json")))
    failed = 0
    for name, model, mtu, opts, steps in SCENARIOS:
        got = asyncio.run(run(model, mtu, opts, steps))
        want = fixtures[name]["writes"]
        ok = got == want
        failed += not ok
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  ({len(got)} vs {len(want)} writes)"))
        if not ok:
            for i, (a, b) in enumerate(zip(got, want)):
                if a != b:
                    print("   first diff at write", i, "\n   got ", a, "\n   want", b)
                    break
    # rendering sanity
    for prof in (n.D11, n.D11H):
        bm, _ = n.render_label(prof, "M3 x 10mm socket head cap screw", "Fasteners › Screws", "INV:123", 40)
        assert bm.width == prof.row_pixels and bm.height == round(40 * prof.dpi / 25.4)
        list(bm.packets(prof is n.D11H))
    print("PASS render")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
