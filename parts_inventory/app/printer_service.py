"""Runs NIIMBOT print jobs on the Pi's Bluetooth (BlueZ via bleak) in a background event loop."""
import asyncio
import logging
import threading

import niimbot as n

log = logging.getLogger("inventory.printer")


class _Transport:
    def __init__(self, client):
        self.client = client

    @property
    def is_open(self):
        return self.client.is_connected

    async def write(self, chunk):
        await self.client.write_gatt_char(n.CHAR_UUID, chunk, response=False)


class PrinterService:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.lock = threading.Lock()

    @staticmethod
    def available():
        try:
            import bleak  # noqa: F401
            return True
        except ImportError:
            return False

    def _run(self, coro, timeout):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    # ------------------------------------------------------------- discovery
    def scan(self, seconds=6):
        return self._run(self._scan(seconds), seconds + 15)

    async def _scan(self, seconds):
        from bleak import BleakScanner
        found = await BleakScanner.discover(timeout=seconds, return_adv=True)
        out = []
        for dev, adv in found.values():
            name = adv.local_name or dev.name or ""
            if name.upper().startswith("D11"):
                out.append({"address": dev.address, "name": name, "rssi": adv.rssi})
        return sorted(out, key=lambda d: -(d["rssi"] or -999))

    # --------------------------------------------------------------- printing
    def print_labels(self, address, labels, length_mm=40, task_pref="auto"):
        """labels: [{title, sub, code}]. Raises n.PrinterError with a user-facing message."""
        with self.lock:  # one job at a time
            return self._run(self._print(address, labels, length_mm, task_pref), 60 + 25 * len(labels))

    async def _print(self, address, labels, length_mm, task_pref):
        from bleak import BleakClient
        from bleak.exc import BleakError
        holder = {}
        client = BleakClient(address, timeout=15.0,
                             disconnected_callback=lambda _c: holder.get("s") and holder["s"].lost())
        try:
            await client.connect()
        except (BleakError, asyncio.TimeoutError, OSError) as e:
            log.warning("Printer connect failed: %s", e)
            raise n.PrinterError("Could not connect to the printer. Turn it on, keep it near the Pi, and try again.")
        try:
            try:  # BlueZ only reports the real MTU once acquired
                await client._backend._acquire_mtu()  # noqa: SLF001
            except Exception:
                pass
            session = n.Session(_Transport(client), mtu=getattr(client, "mtu_size", None))
            holder["s"] = session
            await client.start_notify(n.CHAR_UUID, lambda _h, data: session.feed(bytes(data)))
            profile = await session.start()
            task = n.LEGACY if task_pref == "legacy" and profile is n.D11 else None
            printed = 0
            for lab in labels:
                bm, _ = n.render_label(profile, lab.get("title", ""), lab.get("sub", ""),
                                       lab.get("code", ""), length_mm)
                await session.print_label(bm, task=task)
                printed += 1
            return {"printed": printed, "model": profile.name}
        except BleakError as e:
            log.warning("Printer error: %s", e)
            raise n.PrinterError("The printer disconnected. Turn it on and try again.")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
