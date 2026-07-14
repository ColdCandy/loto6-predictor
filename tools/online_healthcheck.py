#!/usr/bin/env python3
"""オンライン版（GitHub Pages / ローカル / トンネル）の健全性チェック"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = "https://coldcandy.github.io/loto6-predictor/"
STREAMLIT = "https://loto6-predictor-nmrmsaoqhebs2wxvbs6oin.streamlit.app/"


def fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Loto6HealthCheck/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)


def check_pages() -> dict:
    status, body = fetch(PAGES)
    ok = False
    rounds = None
    detail = ""
    if status == 200 and "LOTODATA" in body:
        m = re.search(r"const LOTODATA = (\{.*?\});</script>", body, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                rounds = data.get("rounds")
                ok = bool(rounds and data.get("draws"))
                detail = f"rounds={rounds}"
            except json.JSONDecodeError as e:
                detail = f"JSON parse error: {e}"
        else:
            detail = "LOTODATA JSON not found"
    else:
        detail = body[:200] if status == 0 else f"HTTP {status}"
    return {"name": "GitHub Pages", "url": PAGES, "ok": ok, "detail": detail}


def check_streamlit() -> dict:
    # リダイレクトを追わず、公開可否だけ確認（無限リダイレクト防止）
    req = urllib.request.Request(
        STREAMLIT,
        headers={"User-Agent": "Loto6HealthCheck/1.0"},
        method="GET",
    )
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
        # 手動で先頭レスポンスだけ見る
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N803
                return None

        resp = urllib.request.build_opener(NoRedirect).open(req, timeout=20)
        status = resp.status
        body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        loc = e.headers.get("Location", "")
        if "auth" in loc.lower() or "sign" in loc.lower() or status in (303, 302, 301):
            return {
                "name": "Streamlit Cloud",
                "url": STREAMLIT,
                "ok": False,
                "detail": "ログイン必須（非公開）→ Pages URL を使用",
            }
    except Exception as e:
        return {"name": "Streamlit Cloud", "url": STREAMLIT, "ok": False, "detail": str(e)[:200]}

    lower = body.lower()
    needs_auth = "sign in" in lower or "sign up" in lower or "auth/app" in lower
    ok = status == 200 and not needs_auth
    detail = "ログイン必須（非公開）→ Pages URL を使用" if needs_auth else f"HTTP {status}"
    return {"name": "Streamlit Cloud", "url": STREAMLIT, "ok": ok, "detail": detail}


def check_local_data() -> dict:
    csv = ROOT / "data" / "loto6.csv"
    ok = csv.exists() and csv.stat().st_size > 1000
    return {
        "name": "Local CSV",
        "url": str(csv),
        "ok": ok,
        "detail": f"size={csv.stat().st_size if csv.exists() else 0}",
    }


def main() -> int:
    results = [check_local_data(), check_pages(), check_streamlit()]
    print("=" * 56)
    print("  ロト6予想 - オンライン健全性チェック")
    print("=" * 56)
    failed = 0
    for r in results:
        mark = "OK" if r["ok"] else "NG"
        if not r["ok"] and r["name"] != "Streamlit Cloud":
            failed += 1
        print(f"  [{mark}] {r['name']}")
        print(f"       {r['detail']}")
        print(f"       {r['url']}")
    print("=" * 56)
    pages = next(r for r in results if r["name"] == "GitHub Pages")
    if pages["ok"]:
        print("  推奨オンラインURL（PCオフでもOK）:")
        print(f"  {PAGES}")
    else:
        print("  Pages が NG です。GitHub Actions を確認してください。")
    print("=" * 56)
    # Streamlit NG は Pages があれば致命ではない
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
