"""Google Trends head-to-head: relative search interest of up to five phrases on one scale.
Unofficial endpoint (pytrends), so every call can fail; results are cached and failures return None."""
from __future__ import annotations

import hashlib
import json
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")


class Trends:
    def __init__(self, cache_dir: Path, log=print):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.log = log
        self.client = None
        self.failed = False

    def _client(self):
        if self.client is None and not self.failed:
            try:
                from pytrends.request import TrendReq
                self.client = TrendReq(hl="en-US", tz=300, timeout=(10, 25))
            except Exception as exc:  # not installed, or blocked
                self.failed = True
                self.log(f"[trends] unavailable: {exc}")
        return self.client

    def compare(self, phrases: list[str]) -> dict[str, float] | None:
        """Mean 5-year US interest per phrase (0-100, relative to each other). At most 5 phrases."""
        phrases = list(dict.fromkeys(phrases))[:5]
        key = hashlib.sha1("|".join(sorted(p.lower() for p in phrases)).encode()).hexdigest()[:16]
        path = self.cache_dir / f"trends-{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        client = self._client()
        if not client:
            return None
        try:
            time.sleep(2.0)
            client.build_payload(phrases, timeframe="today 5-y", geo="US")
            df = client.interest_over_time()
        except Exception as exc:
            self.log(f"[trends] failed for {phrases[:2]}...: {type(exc).__name__}")
            return None
        out = {p: (round(float(df[p].mean()), 2) if not df.empty and p in df else 0.0) for p in phrases}
        path.write_text(json.dumps(out))
        return out
