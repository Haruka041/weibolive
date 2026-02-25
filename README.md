# WeiboLive - 微博直播自动挂机系统

一个基于 Docker 的微博直播自动挂机系统，支持循环推流视频文件和 YouTube 直播转播。

## 功能特性

- 🔐 管理员账号密码登录
- 👥 多直播账号管理（RTMP/推流码）
- 🧵 多路并发推流（按账号/stream_id 独立任务）
- ⏱️ 每路独立运行时长（刷新页面不重置）
- 💤 保活脉冲模式（2分钟推流 + 1分钟停流）
- ⬛ 黑屏保活模式（无需上传视频）
- 📉 多档低码率挂机（8fps / 3fps / 1fps）
- 📹 视频文件管理（上传、删除）
- 📡 FFmpeg 循环推流
- 🔄 YouTube 直播/视频转播
- 💧 水印叠加（文字/图片）
- ⚡ WebSocket 实时状态推送
- 🔁 URL 推流断线自动重连
- 🩺 健康检查接口
- 🐳 单容器 Docker 部署

## 快速开始

### 使用 Docker Compose（推荐）

```bash
# 克隆项目
cd weibolive

# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f
```

访问 http://localhost:8887 打开管理界面。

### 手动运行

```bash
# 安装后端依赖
cd backend
pip install -r requirements.txt
python -m playwright install chromium

# 安装前端依赖并构建
cd ../frontend
npm install
npm run build

# 启动服务
cd ../backend
python run.py
```

## 使用说明

### 1. 管理员登录

打开管理界面后，使用管理员账号密码登录（默认账号 `admin`，默认密码 `admin123`，建议上线前修改）。

### 2. 配置直播账号

在「账号管理」页面新增一个或多个直播推流账号，保存 RTMP 地址与推流码。

### 3. 上传视频（本地视频推流）

在「视频管理」页面上传要直播的视频文件。支持 MP4、MKV、AVI、MOV、FLV、WMV 格式。

### 4. 获取推流地址

1. 访问 [微博直播管理](https://me.weibo.com/content/live)
2. 创建直播间
3. 获取 RTMP 推流地址和推流码

### 5. 开始直播

**本地视频直播：**
1. 选择要播放的视频
2. 填写直播标题
3. 选择已配置账号（推荐）或手动填写 RTMP 推流地址和推流码
4. 点击「开始直播」

说明：
- 选择不同账号可并发开播（每个账号对应一条独立推流任务）
- 「总览」页可看到每路任务的状态、运行时长、错误信息与停止按钮
- 挂机建议选择「保活脉冲（2分推/1分停，80~120kbps）」档位，显著降低上行占用

**YouTube 转播：**
1. 切换到「YouTube转播」标签
2. 输入 YouTube 直播或视频链接
3. 点击「解析」获取视频信息
4. 配置水印（可选）
5. 选择已配置账号（推荐）或手动填写微博 RTMP 推流地址和推流码
6. 点击「开始转播」

### 6. 挂机省流档位（参考）

> 实际流量会受平台握手、RTMP/TCP 开销、重连次数影响，以下为经验值范围。

| 档位 | 典型参数 | 预计流量 |
|------|----------|----------|
| ultra_low | 320x180 / 8fps / 180k+24k | 约 100~120 MB/小时 |
| extreme_low | 192x108 / 3fps / 56k+12k | 约 34~42 MB/小时 |
| extreme_low_1fps | 192x108 / 1fps / 44k+12k | 约 28~35 MB/小时 |
| keepalive（脉冲） | 256x144 / 6fps / 2分推1分停 | 约 36~45 MB/小时（平均） |

## YouTube 转播功能

### 支持的链接格式

- 普通视频: `https://www.youtube.com/watch?v=VIDEO_ID`
- 直播: `https://www.youtube.com/live/VIDEO_ID`
- 短链接: `https://youtu.be/VIDEO_ID`

### 画质选择

- 最佳画质：自动选择最高可用画质
- 1080p / 720p / 480p / 360p：指定画质

### 水印功能

支持在转播画面上添加水印：

**文字水印：**
- 自定义文字内容
- 可调字体大小和颜色
- 支持多种位置选择

**图片水印：**
- 支持 PNG、JPG、GIF、WebP 格式
- 推荐 PNG 透明背景
- 可调缩放比例和透明度

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| WEIBOLIVE_HOST | 0.0.0.0 | 监听地址 |
| WEIBOLIVE_PORT | 8887 | 监听端口 |
| WEIBOLIVE_HEADLESS | 1 | 无头模式（Docker 内建议为 1） |
| WEIBOLIVE_ADMIN_USERNAME | admin | 管理员账号（单账号模式） |
| WEIBOLIVE_ADMIN_PASSWORD | admin123 | 管理员密码（单账号模式） |
| WEIBOLIVE_ADMIN_USERS | 空 | 多管理员 JSON，优先级高于单账号配置，例如 `{\"admin\":\"admin123\",\"ops\":\"ops123\"}` |
| WEIBOLIVE_ADMIN_SESSION_TTL_SECONDS | 86400 | 管理员会话有效期（秒） |
| WEIBOLIVE_ADMIN_COOKIE_SECURE | 0 | 是否仅 HTTPS 发送 Cookie（生产建议 1） |

## 目录结构

```
weibolive/
├── Dockerfile
├── docker-compose.yml
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── run.py
│   └── app/
│       ├── main.py
│       ├── api/
│       │   ├── auth.py
│       │   ├── videos.py
│       │   ├── live.py
│       │   └── youtube.py
│       └── core/
│           ├── config.py
│           ├── weibo.py
│           ├── stream.py
│           ├── youtube.py
│           └── overlay.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       └── index.css
└── data/
    ├── cookies/
    ├── videos/
    ├── covers/
    └── watermarks/
```

## API 文档

启动服务后访问 http://localhost:8887/docs 查看 Swagger API 文档。

### 主要接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/admin/status | GET | 管理员登录状态 |
| /api/admin/login | POST | 管理员登录 |
| /api/admin/logout | POST | 管理员退出 |
| /api/accounts | GET | 获取直播账号列表 |
| /api/accounts | POST | 新建直播账号 |
| /api/accounts/{account_id} | PUT | 更新直播账号 |
| /api/accounts/{account_id} | DELETE | 删除直播账号 |
| /api/auth/qrcode | GET | 获取登录二维码 |
| /api/auth/status | GET | 获取登录状态 |
| /api/videos | GET | 获取视频列表 |
| /api/videos/upload | POST | 上传视频 |
| /api/live/streams | GET | 获取全部推流任务状态（多路） |
| /api/live/status | GET | 获取单路状态（可带 stream_id/account_id） |
| /api/live/start | POST | 开始直播 |
| /api/live/stop | POST | 停止直播 |
| /api/live/ws | WS | 实时推流状态 |
| /api/youtube/parse | POST | 解析 YouTube 链接 |
| /api/youtube/status | GET | 获取 YouTube 转播任务状态 |
| /api/youtube/start | POST | 开始 YouTube 转播 |
| /api/youtube/stop | POST | 停止 YouTube 转播 |
| /api/youtube/watermark/upload | POST | 上传水印图片 |
| /api/youtube/watermark/list | GET | 获取水印列表 |
| /api/health | GET | 服务健康检查 |

## GitHub Actions 镜像构建

项目内置工作流：`.github/workflows/docker-image.yml`

- push 到 `main/master`：自动执行以下流程
1. 构建并推送 Docker 镜像到 GHCR
2. 按 commit 自动创建 GitHub Release

版本号规则（按 commit）：
- `commit-<12位短SHA>`

镜像 tag 规则：
- `ghcr.io/<owner>/<repo>:latest`
- `ghcr.io/<owner>/<repo>:<12位短SHA>`
- `ghcr.io/<owner>/<repo>:commit-<12位短SHA>`

GitHub Release：
- Tag：`commit-<12位短SHA>`
- Name：`commit-<12位短SHA>`
- 自动附带 Release Notes 与镜像 digest

## 注意事项

1. 请确保服务器有足够的带宽和 CPU 资源进行视频转码推流
2. 微博直播有内容审核机制，请确保直播内容合规
3. 长时间直播可能会消耗大量服务器资源，建议定期重启
4. YouTube 转播需要服务器能访问 YouTube
5. 转播 YouTube 内容时请遵守相关版权法规

## 免责声明

本项目仅供学习交流使用，请遵守微博平台和 YouTube 平台的相关规定。使用本工具产生的任何后果由使用者自行承担。

## License

MIT
