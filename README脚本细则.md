# TVBox 资源自动化采集项目

> TVBox 接口 + 本地包 + 直播源 的全自动采集、解析、聚合方案。
> GitHub Actions 定时驱动，产物直接落地仓库，可配合静态网页 / Cloudflare Pages 展示。

---

## 一、项目简介

本项目由 **三个独立又联动的采集脚本** 组成，配合 **三个 GitHub Actions 工作流** 实现"无人值守"运行：

| 脚本 | 职责 | 产物目录 |
|---|---|---|
| `tvbox_get_api.py` | 抓取 TVBox 接口 JSON（支持 AES/壳/base64 解密、多 URL 容灾） | `tvbox/*.json` |
| `ry下载器.py` | 解析在线"本地包"（推荐页 / 站点 / 资源） | `ry/*.json` |
| `live下载器.py` | 聚合直播源（从接口提取 `lives`，下载 m3u/txt） | `tvbox/live/` |

三者**输出目录互不重叠**，可并行设计；通过统一的 `concurrency` 组串行提交，避免同时 push 冲突。

---

## 二、目录结构

```
仓库根/
├── .github/workflows/
│   ├── rydaily.yml          # 每日解析本地包
│   ├── livedownload.yml     # 每日聚合直播源
│   └── 2daytvboxapi.yml     # 两日一更接口抓取（仅奇日执行）
├── python/                  # 采集脚本
│   ├── tvbox_get_api.py
│   ├── ry下载器.py
│   └── live下载器.py
├── tvbox/                   # API 接口 JSON + 直播聚合
│   ├── live/                # .m3u + .txt 直播源
│   └── *.json               # 各接口文件
├── ry/                      # 本地包产物
├── api_list.json            # 接口配置模板（旧别名，兼容）
├── tvboxapilinks.txt        # ★API 配置（JSON：API_LIST + API_MIRRORS）
├── rylinks.txt              # ★RY 下载源（名称, 链接）
├── list.txt                 # ★API 清单（仓库根目录，网页数据源）
└── livelist.txt             # 直播源清单（仓库根目录）
```

> ⚠️ **重要约定**：`list.txt` 与 `livelist.txt` 均落在**仓库根目录**——这是网页（如 `index.html`）直接读取的数据源，请勿挪进子目录。

---

## 三、配置文件说明

配置与脚本**分离**，只需维护根目录的两个 txt 文件。

### 1. `tvboxapilinks.txt`（API 接口地址）

JSON 格式，脚本运行时自动读取：

```json
{
  "API_LIST": [
    ["接口A", "https://example.com/api"],
    ["接口B", "https://backup.com/api"]
  ],
  "API_MIRRORS": {
    "接口A": ["https://mirror1.com/api", "https://mirror2.com/api"]
  }
}
```

- `API_LIST`：主接口列表 `[名称, URL]`
- `API_MIRRORS`：可选镜像，同名接口多域名容灾

### 2. `rylinks.txt`（本地包下载源）

一行一条，`名称, 链接`，`#` 开头为注释，名称可省略：

```
潇洒下载, https://9877.kstore.space/single.json
奇奇下载, http://bd.qiqiv.cn/666.json
```

---

## 四、三个脚本的联动关系

```
┌─────────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ tvbox_get_api.py    │      │ ry下载器.py      │      │ live下载器.py    │
│ (接口抓取)          │      │ (本地包解析)     │      │ (直播源聚合)     │
└────────┬────────────┘      └────────┬─────────┘      └────────┬─────────┘
         │                            │                          │
         ▼                            ▼                          ▼
   tvbox/*.json                  ry/*.json                  tvbox/live/*
         │                                                     │
         │  被 live下载器.py 扫描提取 lives                    │
         └──────────────────────┬───────────────────────────────┘
                                ▼
                   list.txt (根) + livelist.txt (根)
                                │
                                ▼
                        index.html 展示（后续）
```

**关键联动**：`live下载器.py` 会扫描 `tvbox/*.json`，自动提取其中的 `lives` 直播模块。也就是说——**先跑接口抓取，再跑直播聚合**，直播源会自然包含接口里的直播线路。

### 产物索引格式

**`list.txt`**（API 清单，抓取脚本合并写入）：
```
接口名, 更新时间, 文件大小, 文件路径, 来源URL
```

**`livelist.txt`**（直播清单，`名称|更新时间|大小|链接|来源|UA`）：
```
CCTV1综合|20260911|128K|http://example.com/cctv1.m3u|饭太硬.json|Mozilla/5.0
```

---

## 五、GitHub Actions 工作流

| 文件 | 触发时间（UTC） | 北京时间 | 说明 |
|---|---|---|---|
| `2daytvboxapi.yml` | 16:05 | 次日 00:05 | 仅**奇日**执行（日期奇偶控制） |
| `rydaily.yml` | 17:00 | 次日 01:00 | 每日 |
| `livedownload.yml` | 18:00 | 次日 02:00 | 每日，依赖接口产物 |

**三个工作流均配置**：
- `concurrency: tvbox-repo-write`（串行 push，防冲突）
- `permissions: contents: write`（允许提交）
- 支持 `workflow_dispatch`（手动触发）

### ⚙️ 部署前提（一次性设置）

1. Fork / 推送本仓库到 GitHub
2. **开启 Actions 写权限**：
   `Settings → Actions → General → Workflow permissions → Read and write permissions`
3. （可选）Cloudflare Pages 部署：`构建命令留空，输出目录 /`

---

## 六、本地开发与调试

```bash
# 安装依赖
pip install requests

# 检查配置是否正确（不实际抓取）
python python/tvbox_get_api.py --check-config
python python/ry下载器.py --check-config

# 调试模式（详细日志）
python python/tvbox_get_api.py --debug

# 指定配置文件
python python/tvbox_get_api.py --config /path/to/tvboxapilinks.txt
```

> 脚本均在**仓库根目录**运行（工作流默认 CWD = 仓库根），确保 `tvbox/`、`ry/` 等相对路径正确解析。

---

## 七、常见问题排查

**Q：工作流 push 报权限错误？**
A：确认已开启 `Read and write permissions`（见第五章）。

**Q：三个工作流会互相冲突吗？**
A：不会。`concurrency.group` 相同，GitHub 会自动排队串行执行。

**Q：`livelist.txt` 里没有新条目？**
A：检查 `tvbox/*.json` 是否含 `lives` 字段，且 `type=0`（直播类型）、URL 为公网地址（非 `127.0.0.1`/`localhost`）。

**Q：接口抓取返回 HTML（疑似 WAF 拦截）？**
A：`ry下载器.py` 会自动切换 UA 并重试；可在配置里增减镜像域名。

**Q：`list.txt` / `livelist.txt` 路径不对？**
A：两文件均应在**仓库根目录**。脚本用 `Path(__file__).resolve().parent.parent` 定位根，不受 CWD 影响。

---

## License

MIT
