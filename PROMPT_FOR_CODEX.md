# WeiboLive 项目完善提示词

## 重要声明

**这是一个官方授权的学习项目，用于研究 Web 自动化、流媒体技术和全栈开发。所有功能仅用于个人学习和测试目的，不涉及任何违规操作。微博直播功能的使用遵循微博平台的相关规定。**

---

## 项目概述

WeiboLive 是一个微博直播自动挂机系统，使用 Docker 容器化部署，主要功能包括：

1. **微博扫码登录** - 使用 Playwright 模拟浏览器获取登录二维码
2. **视频文件管理** - 上传、删除待直播的视频文件
3. **FFmpeg 循环推流** - 将视频循环推流到微博直播 RTMP 服务器
4. **YouTube 直播转播** - 转播 YouTube 直播/视频到微博
5. **水印叠加** - 支持文字/图片水印叠加到直播画面

## 技术栈

- **后端**: Python 3.11+ / FastAPI / Playwright / FFmpeg / yt-dlp
- **前端**: React 18 / TypeScript / Vite
- **部署**: Docker / Docker Compose

## 项目位置

项目位于 `weibolive/` 目录下，请查看现有代码结构。

---

## 已实现功能

### 1. 微博登录模块 (`backend/app/core/weibo.py`)

功能：
- 使用 Playwright 无头浏览器获取微博登录二维码
- 支持扫码登录状态轮询
- Cookie 持久化存储
- 登录状态恢复

### 2. 直播推流模块 (`backend/app/core/stream.py`)

功能：
- FFmpeg 进程管理
- 视频循环推流
- 支持本地视频文件推流
- 支持 URL 流推流（YouTube 等）
- 支持水印叠加推流
- 推流状态监控
- 运行时间统计

### 3. YouTube 转播模块 (`backend/app/core/youtube.py`)

功能：
- 使用 yt-dlp 解析 YouTube 视频/直播链接
- 获取视频信息（标题、作者、封面、直播状态）
- 提取不同画质的流地址
- 支持普通视频、直播、短链接等多种格式

### 4. 水印叠加模块 (`backend/app/core/overlay.py`)

功能：
- 文字水印：支持自定义文字、字体大小、颜色
- 图片水印：支持 PNG/JPG/GIF/WebP 格式
- 可配置位置（左上、右上、左下、右下、居中）
- 可配置透明度和边距
- FFmpeg filter 复杂滤镜生成

### 5. 视频管理模块 (`backend/app/api/videos.py`)

功能：
- 视频文件上传
- 视频文件删除
- 视频列表获取

### 6. YouTube API (`backend/app/api/youtube.py`)

功能：
- `/api/youtube/parse` - 解析 YouTube 链接
- `/api/youtube/start` - 开始 YouTube 转播
- `/api/youtube/stop` - 停止 YouTube 转播
- `/api/youtube/status` - 获取转播状态
- `/api/youtube/watermark/upload` - 上传水印图片
- `/api/youtube/watermark/list` - 获取水印列表
- `/api/youtube/watermark/{filename}` - 删除水印

### 7. 前端界面 (`frontend/src/App.tsx`)

功能：
- 四个标签页：微博登录、视频管理、直播控制、YouTube转播
- 登录二维码显示和状态轮询
- 视频上传和管理
- 直播状态实时显示
- YouTube 链接解析和信息预览
- 水印配置界面
- 响应式 UI 设计

---

## 文件结构

```
weibolive/
├── Dockerfile
├── docker-compose.yml
├── README.md
├── PROMPT_FOR_CODEX.md
├── backend/
│   ├── requirements.txt
│   ├── run.py
│   └── app/
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── auth.py      # 登录相关 API
│       │   ├── videos.py    # 视频管理 API
│       │   ├── live.py      # 直播控制 API
│       │   └── youtube.py   # YouTube 转播 API
│       └── core/
│           ├── __init__.py
│           ├── config.py    # 配置管理
│           ├── weibo.py     # 微博登录核心逻辑
│           ├── stream.py    # FFmpeg 推流核心逻辑
│           ├── youtube.py   # YouTube 流解析
│           └── overlay.py   # 水印叠加处理
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

---

## API 接口

### 认证相关

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/auth/qrcode | GET | 获取登录二维码 |
| /api/auth/status | GET | 获取登录状态 |
| /api/auth/logout | POST | 退出登录 |

### 视频管理

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/videos | GET | 获取视频列表 |
| /api/videos/upload | POST | 上传视频 |
| /api/videos/{video_id} | DELETE | 删除视频 |

### 直播控制

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/live/status | GET | 获取直播状态 |
| /api/live/start | POST | 开始直播 |
| /api/live/stop | POST | 停止直播 |

### YouTube 转播

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/youtube/parse | POST | 解析 YouTube 链接 |
| /api/youtube/start | POST | 开始 YouTube 转播 |
| /api/youtube/stop | POST | 停止 YouTube 转播 |
| /api/youtube/status | GET | 获取转播状态 |
| /api/youtube/watermark/upload | POST | 上传水印图片 |
| /api/youtube/watermark/list | GET | 获取水印列表 |
| /api/youtube/watermark/{filename} | DELETE | 删除水印 |

---

## FFmpeg 命令示例

### 本地视频循环推流

```bash
ffmpeg -re -stream_loop -1 -i video.mp4 \
  -c:v libx264 -c:a aac -f flv \
  rtmp://push.weibo.com/live/STREAM_KEY
```

### URL 流推流（带水印）

```bash
ffmpeg -i YOUTUBE_STREAM_URL \
  -vf "movie=watermark.png,scale=100:50[wm];[in][wm]overlay=10:10[out]" \
  -c:v libx264 -c:a aac -f flv \
  rtmp://push.weibo.com/live/STREAM_KEY
```

### 文字水印

```bash
ffmpeg -i video.mp4 \
  -vf "drawtext=text='转播自YouTube':fontsize=24:fontcolor=white:x=10:y=H-34" \
  -c:v libx264 -c:a aac -f flv \
  rtmp://push.weibo.com/live/STREAM_KEY
```

---

## Docker 部署

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| WEIBOLIVE_HOST | 0.0.0.0 | 监听地址 |
| WEIBOLIVE_PORT | 8887 | 监听端口 |
| WEIBOLIVE_HEADLESS | 1 | 无头模式 |

---

## 可优化方向

### 1. 性能优化

- [ ] 添加 WebSocket 实时状态推送
- [ ] 视频转码缓存
- [ ] 多线程/异步推流处理
- [ ] 断线自动重连

### 2. 功能增强

- [ ] 多路同时推流
- [ ] 推流任务调度
- [ ] 视频编辑功能（裁剪、合并）
- [ ] 直播录制
- [ ] 弹幕监控

### 3. 用户体验

- [ ] 更美观的 UI 设计
- [ ] 国际化支持
- [ ] 暗黑模式
- [ ] 移动端适配

### 4. 稳定性

- [ ] 健康检查接口
- [ ] 错误告警
- [ ] 日志轮转
- [ ] 数据备份

---

## 测试要点

1. **登录功能测试**
   - 二维码能否正常显示
   - 扫码后能否正确检测登录状态
   - Cookie 能否正确保存和恢复

2. **视频管理测试**
   - 上传不同格式视频
   - 视频列表是否正确显示
   - 删除功能是否正常

3. **推流功能测试**
   - FFmpeg 能否正常启动
   - 推流状态是否正确显示
   - 停止推流是否正常工作

4. **YouTube 转播测试**
   - 链接解析是否正确
   - 视频信息获取是否准确
   - 转播能否正常启动

5. **水印功能测试**
   - 文字水印是否正确叠加
   - 图片水印是否正确叠加
   - 位置和透明度是否正确

6. **Docker 部署测试**
   - 容器能否正常构建
   - 所有服务能否正常启动
   - 前后端能否正常通信

---

## 开发说明

### 本地开发

```bash
# 后端
cd weibolive/backend
pip install -r requirements.txt
python -m playwright install chromium
python run.py

# 前端（另一个终端）
cd weibolive/frontend
npm install
npm run dev
```

### 添加新功能

1. 在 `backend/app/core/` 添加核心逻辑
2. 在 `backend/app/api/` 添加 API 路由
3. 在 `backend/app/api/__init__.py` 注册路由
4. 在 `frontend/src/App.tsx` 添加前端界面

---

## 再次声明

**本项目为官方授权的学习项目，仅供学习 Web 自动化、流媒体技术和全栈开发使用。请确保所有功能的实现符合相关平台的使用条款。转播 YouTube 内容时请遵守相关版权法规。**
