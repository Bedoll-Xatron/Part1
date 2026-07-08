import threading
import time
from datetime import datetime, timezone


class PriceCache:
    _instance = None
    _init_lock = threading.Lock()

    def __init__(self):
        self._prices: dict[str, dict] = {}
        self._tracked: set[str] = set()
        self._lock = threading.Lock()
        self._version: int = 0
        self._refresh_thread = None
        self._stop_event = threading.Event()

    @classmethod
    def get_instance(cls) -> "PriceCache":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_tickers(self, tickers: list[str]) -> None:
        """새로운 종목들을 추적 목록에 추가."""
        with self._lock:
            for t in tickers:
                self._tracked.add(t.upper())

    def get_tracked_tickers(self) -> list[str]:
        with self._lock:
            return list(self._tracked)

    def bulk_update(self, prices: dict[str, dict]) -> None:
        """여러 종목의 가격 정보를 한 번에 업데이트하고 버전을 올림."""
        if not prices:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            for ticker, data in prices.items():
                key = ticker.upper()
                self._prices[key] = {
                    "price": data.get("price"),
                    "change_pct": data.get("change_pct"),
                    "volume": data.get("volume"),
                    "updated_at": now,
                }
            self._version += 1

    def get_prices(self, tickers: list[str] | None = None) -> dict[str, dict]:
        with self._lock:
            if tickers is None:
                return dict(self._prices)
            return {
                t.upper(): self._prices[t.upper()]
                for t in tickers
                if t.upper() in self._prices
            }

    def get_version(self) -> int:
        with self._lock:
            return self._version

    def start_refresh_thread(self, refresh_func, interval=30):
        """배경에서 주기적으로 가격을 갱신하는 스레드 시작."""
        if self._refresh_thread is not None:
            return

        def _worker():
            while not self._stop_event.is_set():
                tracked = self.get_tracked_tickers()
                if tracked:
                    try:
                        refresh_func(tracked)
                    except Exception:
                        pass
                time.sleep(interval)

        self._refresh_thread = threading.Thread(target=_worker, daemon=True)
        self._refresh_thread.start()

    def stop_refresh_thread(self):
        self._stop_event.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=2)
            self._refresh_thread = None
