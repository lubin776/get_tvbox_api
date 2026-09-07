# TVBox 接口自动抓取备份

> 通过 GitHub Actions 定时运行抓取脚本，自动备份 TVBox 接口配置到仓库，配合 Cloudflare Pages 实现网页展示。

---

## 📁 项目结构

```
tvbox-api-backup/
├── .github/workflows/daily.yml    # 每两日自动运行的工作流
├── tvbox_get_api.py               # ★ 抓取脚本（核心，不改）
├── api_list.json                  # ★ 接口配置（按需修改）
├── tvbox/                        # 自动生成：抓到的 JSON 文件
├── list.txt                      # 自动生成：接口清单
├── SUMMARY.txt                   # 自动生成：每次运行报告
└── README.md                     # 本文件
```

---

## 🚀 快速开始（5 分钟上线）

### 第一步：创建 GitHub 仓库

1. 在 GitHub 上新建一个仓库（例如 `tvbox-api-backup`）
2. 把本目录所有文件推送到仓库

### 第二步：开启 GitHub Pages / Cloudflare Pages

#### 方案 A：Cloudflare Pages（推荐）

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Pages**
2. 点击 **Create a project** → 选择 **Connect to Git**
3. 授权 GitHub，选择你的仓库
4. 构建设置：
   - **Framework preset**：`None`
   - **Build command**：留空
   - **Build output directory**：`/`（根目录）
   - **Branch**：`main`
5. 点击 **Save and Deploy**

> 💡 CF Pages 监听到 push 自动部署，`index.html` 在根目录即可访问。

#### 方案 B：GitHub Pages

1. 仓库 **Settings → Pages**
2. **Source**：选择 `GitHub Actions`
3. 等待自动部署完成

### 第三步：开启 Actions 写权限

> ⚠️ **必须操作，否则定时任务会 403 报错**

仓库 → **Settings → Actions → General → Workflow permissions** → 勾选 ✅ **Read and write permissions** → Save

### 第四步：确认工作流正常运行

1. 进入仓库 **Actions** 标签页
2. 看到 **"每两日自动运行"** 工作流
3. 点击 **Run workflow** → 手动触发一次测试
4. 运行成功后，检查仓库是否生成了 `tvbox/` 目录和 `list.txt` 文件

---

## ⚙️ 配置说明（api_list.json）

### 基本格式

```json
{
  "API_LIST": [
    ["接口名称", "接口地址"],
    ["接口名称", "接口地址"]
  ],
  "API_MIRRORS": {
    "接口名称": [
      "镜像地址1",
      "镜像地址2"
    ]
  }
}
```

### API_LIST（主接口列表）

- 每个条目是一个数组 `[名称, 地址]`
- **同名条目会自动合并**为一组（带多个镜像源）

### API_MIRRORS（镜像列表）

- 键为接口名称，值为该接口的多个镜像地址
- 脚本会**按名称合并**到 API_LIST 中同名的条目
- 所有地址会**自动去重 + URL 规范化**

### 配置示例

```json
{
  "API_LIST": [
    ["饭太硬", "http://www.饭太硬.net/tv"],
    ["肥猫", "http://肥猫.net/tv"]
  ],
  "API_MIRRORS": {
    "饭太硬": [
      "http://www.饭太硬.net/tv",
      "http://www.饭太硬.cc/tv",
      "http://fty.xxooo.cf/tv"
    ]
  }
}
```

上面的配置最终会生成：

- **饭太硬** → 4 个源（1 主 + 3 镜像），按顺序尝试，成功一个即止
- **肥猫** → 1 个源

---

## 🔄 工作流运行机制

### 定时触发

```
每天北京时间 00:05 触发
  └── gate 步骤判断：
       ├── 奇数日(UTC) → 运行脚本 → 提交结果
       └── 偶数日(UTC) → 跳过
```

即：**每 2 天自动运行一次**（如 UTC 7号运行、8号跳过、9号运行……）

### 手动触发

进入 **Actions → 每两日自动运行 → Run workflow**：

- **Branch**：保持 `main`
- **是否开启调试模式**：
  - `false` → 正常运行
  - `true` → 开启调试日志（`--debug`）

> 手动触发**不受奇偶日限制**，随时可强制运行。

### 脚本执行流程

```
python tvbox_get_api.py
  │
  ├─ 1. 读取 api_list.json
  ├─ 2. 按接口名分组 + 合并镜像 + 去重
  ├─ 3. 逐个接口抓取（多源容错，成功一个即止）
  │     ├─ 下载原始内容
  │     ├─ 自动解密（AES-128-CBC）
  │     ├─ 提取 JSON
  │     ├─ 相对路径转绝对路径
  │     └─ 保存到 tvbox/{名称}.json
  ├─ 4. 更新 list.txt（新旧合并：新替代旧 / 新增加 / 旧保留）
  └─ 5. 生成 SUMMARY.txt（本次运行报告）
```

### 产物说明

| 文件 | 说明 | 示例 |
|------|------|------|
| `tvbox/{名称}.json` | 抓到的接口配置 | `tvbox/饭太硬.json` |
| `list.txt` | 接口清单（日期倒序） | `饭太硬.json\|20260907\|45.2K\|http://...` |
| `SUMMARY.txt` | 本次运行汇总报告 | 每个接口的状态、文件、成功URL |

---

## 🛠️ 本地测试

```bash
# 1. 检查配置（不抓包，只看分组结果）
python tvbox_get_api.py --check-config

# 2. 正常抓取
python tvbox_get_api.py

# 3. 调试模式（详细日志）
python tvbox_get_api.py --debug

# 4. 自测（使用内置测试配置）
python tvbox_get_api.py --selftest
```

---

## 🔧 修改抓取频率

编辑 `.github/workflows/daily.yml`：

```yaml
# 当前：每天 00:05 (BJT) 触发，奇数日运行
schedule:
  - cron: "5 16 * * *"
```

**cron 表达式说明**（GitHub Actions 使用 UTC 时间）：

| 需求 | cron 表达式 | 说明 |
|------|-------------|------|
| 每天一次（北京时间 06:00） | `0 22 * * *` | UTC 22:00 |
| 每天一次（北京时间 00:00） | `0 16 * * *` | UTC 16:00 |
| 每两日一次（当前） | `5 16 * * *` + gate | UTC 16:05 |
| 每周一次（周一） | `0 16 * * 1` | 每周一 UTC 16:00 |

> 如果改成"每天运行"，删除 `gate` 步骤即可。

---

## ❓ 常见问题

### Q1：工作流报 `403 Permission denied`

**原因**：Actions 默认 token 只读。

**解决**：Settings → Actions → General → **Workflow permissions** → 勾选 **Read and write permissions**。

### Q2：脚本运行成功但没有生成文件

**检查**：
- 确认 `api_list.json` 格式正确（JSON 合法）
- 查看 Actions 日志，是否有接口全部失败（网络问题）
- 本地运行 `python tvbox_get_api.py --check-config` 验证配置

### Q3：list.txt 没有更新

**正常行为**：只有**成功抓取 JSON** 的接口才会写入 `list.txt`。如果某接口所有源都失败，它的旧记录会被保留（不会被删除）。

### Q4：CF Pages 部署后页面空白

**检查**：
- Build output directory 是否设为 `/`
- 仓库根目录是否有 `index.html`
- 如果使用本项目的网页展示，确认 `index.html` 已生成并提交

---

## 📄 免责声明

本站接口资源由【误道者】整理。所有资源均来自互联网，版权归原作者所有。仅供测试学习使用，请勿用于违法及商业用途，请勿付费购买。如涉及侵权，请联系删除。 QQ 群：1067685939。

---

## 📝 License

MIT
