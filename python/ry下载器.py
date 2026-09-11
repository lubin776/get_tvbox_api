#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析在线本地包（RY 下载器）。

策略：
1. 首次请求使用默认 UA（okhttp），轻量、贴近 TVBox 客户端；
2. 若失败（网络异常 / 非 200 / 403 / 418 等），自动用"模拟浏览器"头重试一次；
3. 浏览器头仍失败则返回最终错误，不影响其他任务。
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LINKS_FILE = REPO_ROOT / "rylinks.txt"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "ry"

# 默认 UA：贴近 TVBox / 盒子客户端
DEFAULT_UA = "okhttp/4.5.0"

# 模拟浏览器 UA + 完整请求头（用于二次重试）
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# 这些状态码视为"被反爬/被拦截"，值得用浏览器头再试一次
RETRY_ON_STATUS = {403, 408, 418, 429, 500, 502, 503, 504}

DEBUG = False


def log(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}", flush=True)


def load_links(path):
    links = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            name = parts[0].strip()
            url = parts[-1].strip()
            if not url:
                continue
            links.append((name, url))
    return links


def _do_request(url, headers, timeout):
    """发起一次 GET，返回 (response, error)。"""
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        return r, None
    except Exception as e:  # 网络异常（超时/SSL/连接失败等）
        return None, str(e)


def fetch(url, ua=DEFAULT_UA, retries=1, timeout=25):
    """抓取 URL。

    第一次用默认头；若失败（异常 / 状态码在 RETRY_ON_STATUS），
    则切换为模拟浏览器头再试一次。
    """
    # 第一轮：默认 UA
    headers_default = {"User-Agent": ua}
    resp, err = _do_request(url, headers_default, timeout)
    status = resp.status_code if resp is not None else None

    need_retry = (resp is None) or (status in RETRY_ON_STATUS)

    if not need_retry:
        log(f"fetch ok (default UA) {url} -> {status}")
        return resp

    # 第二轮：模拟浏览器
    log(f"fetch failed (default UA): status={status}, err={err} -> retry with browser headers")
    time.sleep(1)
    resp2, err2 = _do_request(url, BROWSER_HEADERS, timeout)
    status2 = resp2.status_code if resp2 is not None else None

    if resp2 is not None and status2 == 200:
        log(f"fetch ok (browser UA) {url} -> {status2}")
        return resp2

    # 两轮都失败，抛出明确错误（含两次结果）
    raise RuntimeError(
        f"all failed: default={status or err}; browser={status2 or err2}"
    )


def parse(data):
    """兼容多种在线本地包格式，统一抽出源列表。"""
    if isinstance(data, dict):
        for k in ("list", "data", "sites", "sources"):
            if k in data and isinstance(data[k], list):
                return data[k]
        if "url" in data:
            return [data]
    return data if isinstance(data, list) else []


def download_one(name, url, out_dir):
    info = {"name": name, "url": url, "ok": False}
    try:
        r = fetch(url)
        text = r.text.strip()
        # 尝试 JSON 解析；失败则按行当作文本源
        try:
            data = json.loads(text)
            sources = parse(data)
            payload = json.dumps(sources, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            sources = [{"url": line} for line in text.splitlines() if line.strip()]
            payload = text

        out_path = out_dir / f"{name}.json"
        out_path.write_text(payload, encoding="utf-8")
        info.update(ok=True, size=len(payload.encode("utf-8")), count=len(sources))
        print(f"    ok {len(payload.encode('utf-8'))} bytes, {len(sources)} items")
    except Exception as e:
        info["error"] = str(e)
        print(f"    FAIL: {e}")
    return info


def run(links_file, output_dir, max_workers=4):
    output_dir.mkdir(parents=True, exist_ok=True)
    links = load_links(links_file)
    print(f"loaded config: {links_file} ({len(links)} entries)")
    print(f"output: {output_dir}")
    print(f"total {len(links)} link(s)")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(download_one, n, u, output_dir): n for n, u in links}
        for idx, fut in enumerate(as_completed(futures), 1):
            name = futures[fut]
            print(f"[{idx}/{len(links)}] {name}", flush=True)
            results.append(fut.result())

    ok = [r for r in results if r["ok"]]
    print("=" * 50)
    print(f"summary: {len(ok)}/{len(results)}")
    for r in results:
        if r["ok"]:
            print(f"  ok {r['name']}  ({r.get('count', '?')} items)")
        else:
            print(f"  -- {r['name']}  {r.get('error', 'failed')}")
    print("=" * 50)

    # 部分成功即视为成功（不再因个别失败而整体失败）
    return 0 if ok else 2


def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="RY 在线本地包下载器")
    parser.add_argument("--links-file", default=str(DEFAULT_LINKS_FILE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--debug", action="store_true",
                        help="输出详细调试日志（含两次请求头/状态码）")
    parser.add_argument("--force", action="store_true", help="强制运行（供工作流触发）")
    args = parser.parse_args()

    DEBUG = args.debug
    rc = run(Path(args.links_file), Path(args.output_dir))
    sys.exit(rc)


if __name__ == "__main__":
    main()
