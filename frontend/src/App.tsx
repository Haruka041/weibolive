import { useEffect, useMemo, useRef, useState } from "react";

type TabKey = "dashboard" | "accounts" | "videos" | "live" | "youtube";
type HttpError = Error & { status?: number };

interface AdminStatus {
  logged_in: boolean;
  username: string | null;
}

interface StreamAccount {
  id: string;
  name: string;
  rtmp_url: string;
  stream_key: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

interface VideoInfo {
  id: string;
  filename: string;
  size: number;
}

interface StreamStatusItem {
  stream_id: string;
  account_id: string | null;
  account_name: string | null;
  title: string;
  source: string;
  started_at: string | null;
  status: string;
  is_running: boolean;
  error: string | null;
  video: string | null;
  video_path: string | null;
  stream_url: string | null;
  rtmp_url: string | null;
  stream_type: string | null;
  youtube_video_id: string | null;
  watermark_enabled: boolean;
  uptime_seconds: number;
  reconnect_attempts: number;
  last_exit_code: number | null;
  pulse_enabled: boolean;
  pulse_phase: string;
  pulse_on_seconds: number;
  pulse_off_seconds: number;
}

interface StreamListResponse {
  running_count: number;
  items: StreamStatusItem[];
}

interface YouTubeInfo {
  video_id: string;
  title: string;
  author: string;
  is_live: boolean;
  thumbnail: string;
}

interface Watermark {
  filename: string;
  url: string;
  size: number;
}

interface WatermarkSettings {
  enabled: boolean;
  type: "text" | "image";
  text?: string;
  image_filename?: string;
  position: string;
  opacity: number;
  margin: number;
  font_size: number;
  font_color: string;
  scale: number;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      typeof (data as { detail?: unknown }).detail === "string"
        ? String((data as { detail: string }).detail)
        : `请求失败 (${response.status})`
    ) as HttpError;
    error.status = response.status;
    throw error;
  }
  return data as T;
}

function isAuthError(error: unknown): boolean {
  return typeof error === "object" && error !== null && (error as HttpError).status === 401;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatUptime(seconds = 0): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s
    .toString()
    .padStart(2, "0")}`;
}

function maskSecret(value: string): string {
  if (!value) return "";
  if (value.length <= 4) return "****";
  return `${"*".repeat(Math.max(4, value.length - 4))}${value.slice(-4)}`;
}

function statusClass(status: string, isRunning: boolean): string {
  if (status === "error") return "status-error";
  if (isRunning || status === "running") return "status-running";
  if (status === "starting") return "status-online";
  return "status-offline";
}

const api = {
  getAdminStatus: () => requestJson<AdminStatus>("/api/admin/status"),
  adminLogin: (payload: { username: string; password: string }) =>
    requestJson<{ success: boolean; username: string }>("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  adminLogout: () => requestJson<{ success: boolean }>("/api/admin/logout", { method: "POST" }),

  getAccounts: () => requestJson<StreamAccount[]>("/api/accounts"),
  createAccount: (payload: {
    name: string;
    rtmp_url: string;
    stream_key: string;
    enabled: boolean;
  }) =>
    requestJson<StreamAccount>("/api/accounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  updateAccount: (id: string, payload: Partial<StreamAccount>) =>
    requestJson<StreamAccount>(`/api/accounts/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteAccount: (id: string) => requestJson(`/api/accounts/${id}`, { method: "DELETE" }),

  getVideos: () => requestJson<VideoInfo[]>("/api/videos"),
  uploadVideo: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestJson<VideoInfo>("/api/videos/upload", { method: "POST", body: formData });
  },
  deleteVideo: (id: string) => requestJson(`/api/videos/${id}`, { method: "DELETE" }),

  getStreams: () => requestJson<StreamListResponse>("/api/live/streams"),
  startStream: (payload: {
    video_id?: string;
    black_screen?: boolean;
    title: string;
    loop: boolean;
    bandwidth_mode?:
      | "normal"
      | "low"
      | "ultra_low"
      | "extreme_low"
      | "extreme_low_1fps"
      | "keepalive";
    keepalive_pulse?: boolean;
    pulse_on_seconds?: number;
    pulse_off_seconds?: number;
    account_id?: string;
    stream_id?: string;
    rtmp_url?: string;
    stream_key?: string;
  }) =>
    requestJson<{ status: string; stream_id?: string; message?: string }>("/api/live/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  stopStream: (payload?: { stream_id?: string; account_id?: string }) =>
    requestJson("/api/live/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    }),

  parseYoutube: (url: string) =>
    requestJson<{ success: boolean; data?: YouTubeInfo; detail?: string }>("/api/youtube/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),
  startYoutube: (payload: {
    youtube_url: string;
    quality: string;
    bandwidth_mode?:
      | "normal"
      | "low"
      | "ultra_low"
      | "extreme_low"
      | "extreme_low_1fps"
      | "keepalive";
    keepalive_pulse?: boolean;
    pulse_on_seconds?: number;
    pulse_off_seconds?: number;
    watermark?: WatermarkSettings;
    account_id?: string;
    stream_id?: string;
    rtmp_url?: string;
    stream_key?: string;
  }) =>
    requestJson<{ success: boolean; message?: string; detail?: string; data?: { stream_id?: string } }>(
      "/api/youtube/start",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    ),
  stopYoutube: (payload?: { stream_id?: string; account_id?: string }) =>
    requestJson("/api/youtube/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    }),

  getWatermarks: () =>
    requestJson<{ success: boolean; data?: Watermark[] }>("/api/youtube/watermark/list"),
  uploadWatermark: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestJson<{ success: boolean; data?: Watermark; detail?: string }>(
      "/api/youtube/watermark/upload",
      { method: "POST", body: formData }
    );
  },
  deleteWatermark: (filename: string) =>
    requestJson(`/api/youtube/watermark/${filename}`, { method: "DELETE" }),
};

function App() {
  const [ready, setReady] = useState(false);
  const [admin, setAdmin] = useState<AdminStatus>({ logged_in: false, username: null });
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [loginUser, setLoginUser] = useState("admin");
  const [loginPass, setLoginPass] = useState("");

  const [accounts, setAccounts] = useState<StreamAccount[]>([]);
  const [accountEditingId, setAccountEditingId] = useState<string | null>(null);
  const [accountName, setAccountName] = useState("");
  const [accountRtmp, setAccountRtmp] = useState("");
  const [accountKey, setAccountKey] = useState("");
  const [accountEnabled, setAccountEnabled] = useState(true);

  const [videos, setVideos] = useState<VideoInfo[]>([]);
  const [selectedVideo, setSelectedVideo] = useState("");
  const [streams, setStreams] = useState<StreamStatusItem[]>([]);
  const [runningCount, setRunningCount] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);

  const [liveTitle, setLiveTitle] = useState("");
  const [liveSourceType, setLiveSourceType] = useState<"video" | "black">("video");
  const [liveAccountId, setLiveAccountId] = useState("");
  const [liveRtmp, setLiveRtmp] = useState("");
  const [liveKey, setLiveKey] = useState("");
  const [loopVideo, setLoopVideo] = useState(true);
  const [liveBandwidthMode, setLiveBandwidthMode] = useState<
    "normal" | "low" | "ultra_low" | "extreme_low" | "extreme_low_1fps" | "keepalive"
  >(
    "keepalive"
  );

  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [youtubeInfo, setYoutubeInfo] = useState<YouTubeInfo | null>(null);
  const [youtubeQuality, setYoutubeQuality] = useState("best");
  const [youtubeAccountId, setYoutubeAccountId] = useState("");
  const [youtubeRtmp, setYoutubeRtmp] = useState("");
  const [youtubeKey, setYoutubeKey] = useState("");
  const [youtubeBandwidthMode, setYoutubeBandwidthMode] = useState<
    "normal" | "low" | "ultra_low" | "extreme_low" | "extreme_low_1fps" | "keepalive"
  >(
    "keepalive"
  );

  const [watermarks, setWatermarks] = useState<Watermark[]>([]);
  const [watermarkSettings, setWatermarkSettings] = useState<WatermarkSettings>({
    enabled: false,
    type: "text",
    text: "转播自YouTube",
    position: "bottom_right",
    opacity: 0.7,
    margin: 10,
    font_size: 24,
    font_color: "white",
    scale: 1.0,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const wsRetryRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wmInputRef = useRef<HTMLInputElement>(null);

  const liveAccount = useMemo(
    () => accounts.find((item) => item.id === liveAccountId) || null,
    [accounts, liveAccountId]
  );
  const youtubeAccount = useMemo(
    () => accounts.find((item) => item.id === youtubeAccountId) || null,
    [accounts, youtubeAccountId]
  );
  const liveStreams = useMemo(
    () => streams.filter((item) => item.stream_type === "local_video" || item.stream_type === "black_screen"),
    [streams]
  );
  const youtubeStreams = useMemo(
    () => streams.filter((item) => item.stream_type === "url_stream"),
    [streams]
  );
  const errorStreams = useMemo(() => streams.filter((item) => item.status === "error"), [streams]);

  const handleUnauthorized = () => {
    setAdmin({ logged_in: false, username: null });
    setWsConnected(false);
    if (wsRef.current) wsRef.current.close();
    wsRef.current = null;
  };

  const withAuth = (error: unknown) => {
    if (isAuthError(error)) handleUnauthorized();
    console.error(error);
  };

  const loadAccounts = async () => {
    try {
      const data = await api.getAccounts();
      setAccounts(data);
      setLiveAccountId((curr) => (curr && data.some((x) => x.id === curr) ? curr : ""));
      setYoutubeAccountId((curr) => (curr && data.some((x) => x.id === curr) ? curr : ""));
    } catch (error) {
      withAuth(error);
    }
  };

  const loadVideos = async () => {
    try {
      const data = await api.getVideos();
      setVideos(data);
      setSelectedVideo((curr) => (curr && data.some((x) => x.id === curr) ? curr : ""));
    } catch (error) {
      withAuth(error);
    }
  };

  const loadStreams = async () => {
    try {
      const data = await api.getStreams();
      setStreams(data.items);
      setRunningCount(data.running_count);
    } catch (error) {
      withAuth(error);
    }
  };

  const loadWatermarks = async () => {
    try {
      const result = await api.getWatermarks();
      if (result.success && result.data) setWatermarks(result.data);
    } catch (error) {
      withAuth(error);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        setAdmin(await api.getAdminStatus());
      } catch (error) {
        console.error(error);
      } finally {
        setReady(true);
      }
    })();
  }, []);

  useEffect(() => {
    if (!admin.logged_in) return;
    loadAccounts();
    loadVideos();
    loadStreams();
    loadWatermarks();
  }, [admin.logged_in]);

  useEffect(() => {
    if (!admin.logged_in) return;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${protocol}://${window.location.host}/api/live/ws`);
      wsRef.current = ws;

      ws.onopen = () => setWsConnected(true);
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as Partial<StreamListResponse>;
          if (Array.isArray(payload.items)) {
            setStreams(payload.items);
            setRunningCount(
              typeof payload.running_count === "number"
                ? payload.running_count
                : payload.items.filter((item) => item.is_running).length
            );
          }
        } catch (error) {
          console.error(error);
        }
      };
      ws.onclose = () => {
        setWsConnected(false);
        if (disposed) return;
        if (wsRetryRef.current) clearTimeout(wsRetryRef.current);
        wsRetryRef.current = window.setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    const pollingId = window.setInterval(loadStreams, 8000);

    return () => {
      disposed = true;
      clearInterval(pollingId);
      if (wsRetryRef.current) clearTimeout(wsRetryRef.current);
      if (wsRef.current) wsRef.current.close();
      wsRef.current = null;
    };
  }, [admin.logged_in]);

  const resetAccountForm = () => {
    setAccountEditingId(null);
    setAccountName("");
    setAccountRtmp("");
    setAccountKey("");
    setAccountEnabled(true);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await api.adminLogin({ username: loginUser.trim(), password: loginPass });
      if (result.success) {
        setAdmin({ logged_in: true, username: result.username });
        setLoginPass("");
      }
    } catch (error: unknown) {
      alert(`登录失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const handleLogout = async () => {
    try {
      await api.adminLogout();
    } catch {
      // ignore
    }
    handleUnauthorized();
  };

  const saveAccount = async () => {
    if (!accountName.trim() || !accountRtmp.trim() || !accountKey.trim()) {
      alert("请完整填写账号信息");
      return;
    }
    try {
      if (accountEditingId) {
        await api.updateAccount(accountEditingId, {
          name: accountName,
          rtmp_url: accountRtmp,
          stream_key: accountKey,
          enabled: accountEnabled,
        });
      } else {
        await api.createAccount({
          name: accountName,
          rtmp_url: accountRtmp,
          stream_key: accountKey,
          enabled: accountEnabled,
        });
      }
      await loadAccounts();
      resetAccountForm();
    } catch (error: unknown) {
      withAuth(error);
      alert(`保存账号失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const handleDeleteAccount = async (id: string) => {
    if (!confirm("确定删除这个账号吗？")) return;
    try {
      await api.deleteAccount(id);
      await loadAccounts();
    } catch (error: unknown) {
      withAuth(error);
      alert(`删除账号失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const handleDeleteVideo = async (videoId: string) => {
    if (!confirm("确定删除这个视频吗？")) return;
    try {
      await api.deleteVideo(videoId);
      await loadVideos();
      if (selectedVideo === videoId) setSelectedVideo("");
    } catch (error: unknown) {
      withAuth(error);
      alert(`删除视频失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const stopStreamById = async (streamId: string) => {
    try {
      await api.stopStream({ stream_id: streamId });
      await loadStreams();
    } catch (error: unknown) {
      withAuth(error);
      alert(`停止推流失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const stopYoutubeById = async (streamId: string) => {
    try {
      await api.stopYoutube({ stream_id: streamId });
      await loadStreams();
    } catch (error: unknown) {
      withAuth(error);
      alert(`停止转播失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const startLive = async () => {
    const useBlackScreen = liveSourceType === "black";
    if (!useBlackScreen && !selectedVideo) return alert("请先选择视频");
    const payload: {
      video_id?: string;
      black_screen?: boolean;
      title: string;
      loop: boolean;
      bandwidth_mode?:
        | "normal"
        | "low"
        | "ultra_low"
        | "extreme_low"
        | "extreme_low_1fps"
        | "keepalive";
      keepalive_pulse?: boolean;
      pulse_on_seconds?: number;
      pulse_off_seconds?: number;
      account_id?: string;
      rtmp_url?: string;
      stream_key?: string;
    } = {
      title: liveTitle.trim(),
      loop: useBlackScreen ? false : loopVideo,
      bandwidth_mode: liveBandwidthMode,
    };
    if (useBlackScreen) payload.black_screen = true;
    else payload.video_id = selectedVideo;
    if (liveBandwidthMode === "keepalive") {
      payload.keepalive_pulse = true;
      payload.pulse_on_seconds = 120;
      payload.pulse_off_seconds = 60;
    }
    if (liveAccountId) payload.account_id = liveAccountId;
    else {
      if (!liveRtmp.trim() || !liveKey.trim()) return alert("请选择账号或手动填写 RTMP 与推流码");
      payload.rtmp_url = liveRtmp.trim();
      payload.stream_key = liveKey.trim();
    }
    try {
      await api.startStream(payload);
      await loadStreams();
    } catch (error: unknown) {
      withAuth(error);
      alert(`开播失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const startYoutube = async () => {
    if (!youtubeUrl.trim()) return alert("请输入 YouTube 链接");
    const payload: {
      youtube_url: string;
      quality: string;
      bandwidth_mode?:
        | "normal"
        | "low"
        | "ultra_low"
        | "extreme_low"
        | "extreme_low_1fps"
        | "keepalive";
      keepalive_pulse?: boolean;
      pulse_on_seconds?: number;
      pulse_off_seconds?: number;
      watermark?: WatermarkSettings;
      account_id?: string;
      rtmp_url?: string;
      stream_key?: string;
    } = {
      youtube_url: youtubeUrl.trim(),
      quality: youtubeQuality,
      bandwidth_mode: youtubeBandwidthMode,
      watermark: watermarkSettings.enabled ? watermarkSettings : undefined,
    };
    if (youtubeBandwidthMode === "keepalive") {
      payload.keepalive_pulse = true;
      payload.pulse_on_seconds = 120;
      payload.pulse_off_seconds = 60;
    }
    if (youtubeAccountId) payload.account_id = youtubeAccountId;
    else {
      if (!youtubeRtmp.trim() || !youtubeKey.trim()) return alert("请选择账号或手动填写 RTMP 与推流码");
      payload.rtmp_url = youtubeRtmp.trim();
      payload.stream_key = youtubeKey.trim();
    }
    try {
      const result = await api.startYoutube(payload);
      if (!result.success) return alert(result.detail || "启动失败");
      await loadStreams();
    } catch (error: unknown) {
      withAuth(error);
      alert(`转播失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const uploadVideo = async (file: File) => {
    try {
      await api.uploadVideo(file);
      await loadVideos();
    } catch (error: unknown) {
      withAuth(error);
      alert(`上传失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const uploadWatermark = async (file: File) => {
    try {
      const result = await api.uploadWatermark(file);
      if (!result.success) return alert(result.detail || "上传失败");
      await loadWatermarks();
      if (result.data) {
        setWatermarkSettings((prev) => ({ ...prev, image_filename: result.data?.filename }));
      }
    } catch (error: unknown) {
      withAuth(error);
      alert(`上传水印失败: ${(error as Error)?.message || "未知错误"}`);
    }
  };

  const renderStreamCards = (mode: "all" | "live" | "youtube" = "all") => {
    const visible = mode === "all" ? streams : mode === "live" ? liveStreams : youtubeStreams;
    if (!visible.length) {
      return <div className="empty">暂无推流任务</div>;
    }
    return (
      <div className="stream-grid">
        {visible.map((item) => (
          <div key={item.stream_id} className="stream-card">
            <div className="stream-card-header">
              <div className="stream-card-title">
                {item.account_name || item.title || item.stream_id}
                <span className={`status-badge ${statusClass(item.status, item.is_running)}`}>
                  {item.is_running ? "运行中" : item.status}
                </span>
              </div>
              <div className="stream-card-time">{formatUptime(item.uptime_seconds || 0)}</div>
            </div>
            <div className="stream-meta">
              <span>类型: {item.stream_type || "-"}</span>
              <span>源: {item.source || "-"}</span>
            </div>
            {item.pulse_enabled ? (
              <div className="stream-meta">
                <span>
                  保活脉冲: {item.pulse_on_seconds}s 推 / {item.pulse_off_seconds}s 停
                </span>
                <span>阶段: {item.pulse_phase === "on" ? "推流中" : "停歇中"}</span>
              </div>
            ) : null}
            <div className="stream-meta">
              <span>流 ID: {item.stream_id}</span>
              <span>重连: {item.reconnect_attempts || 0}</span>
            </div>
            {item.video ? <div className="stream-line">视频: {item.video}</div> : null}
            {item.youtube_video_id ? <div className="stream-line">YouTube: {item.youtube_video_id}</div> : null}
            {item.rtmp_url ? <div className="stream-line truncate">推流地址: {item.rtmp_url}</div> : null}
            {item.error ? <div className="stream-error">{item.error}</div> : null}
            <div className="stream-actions">
              {item.stream_type === "url_stream" ? (
                <button className="btn btn-danger" onClick={() => stopYoutubeById(item.stream_id)}>
                  停止转播
                </button>
              ) : (
                <button className="btn btn-danger" onClick={() => stopStreamById(item.stream_id)}>
                  停止直播
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  if (!ready) {
    return (
      <div className="container">
        <div className="loading">加载中...</div>
      </div>
    );
  }

  if (!admin.logged_in) {
    return (
      <div className="container">
        <header className="app-header">
          <div>
            <h1>WeiboLive Console</h1>
            <p>多账号直播管理面板</p>
          </div>
          <span className="status-badge status-offline">管理员未登录</span>
        </header>
        <div className="card auth-card">
          <div className="card-header">管理员登录</div>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>账号</label>
              <input
                type="text"
                value={loginUser}
                onChange={(e) => setLoginUser(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="form-group">
              <label>密码</label>
              <input
                type="password"
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <button className="btn btn-primary auth-submit">登录</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="app-header">
        <div>
          <h1>WeiboLive Console</h1>
          <p>
            多账号直播流管理 | 在线流 {runningCount} 路 | {wsConnected ? "实时同步" : "轮询同步"}
          </p>
        </div>
        <div className="header-actions">
          <span className="status-badge status-online">管理员: {admin.username || "admin"}</span>
          <button className="btn btn-secondary" onClick={handleLogout}>
            退出登录
          </button>
        </div>
      </header>

      <div className="tabs">
        <div className={`tab ${tab === "dashboard" ? "active" : ""}`} onClick={() => setTab("dashboard")}>
          总览
        </div>
        <div className={`tab ${tab === "accounts" ? "active" : ""}`} onClick={() => setTab("accounts")}>
          账号管理
        </div>
        <div className={`tab ${tab === "videos" ? "active" : ""}`} onClick={() => setTab("videos")}>
          视频管理
        </div>
        <div className={`tab ${tab === "live" ? "active" : ""}`} onClick={() => setTab("live")}>
          本地开播
        </div>
        <div className={`tab ${tab === "youtube" ? "active" : ""}`} onClick={() => setTab("youtube")}>
          YouTube 转播
        </div>
      </div>

      {tab === "dashboard" ? (
        <div>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-title">在线推流</div>
              <div className="stat-value">{runningCount}</div>
            </div>
            <div className="stat-card">
              <div className="stat-title">已配置账号</div>
              <div className="stat-value">{accounts.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-title">视频素材</div>
              <div className="stat-value">{videos.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-title">异常任务</div>
              <div className="stat-value">{errorStreams.length}</div>
            </div>
          </div>
          <div className="card">
            <div className="card-header">全部推流任务</div>
            {renderStreamCards("all")}
          </div>
        </div>
      ) : null}

      {tab === "accounts" ? (
        <div className="layout-2col">
          <div className="card">
            <div className="card-header">{accountEditingId ? "编辑账号" : "新增账号"}</div>
            <div className="form-group">
              <label>账号名称</label>
              <input type="text" value={accountName} onChange={(e) => setAccountName(e.target.value)} />
            </div>
            <div className="form-group">
              <label>RTMP 地址</label>
              <input type="text" value={accountRtmp} onChange={(e) => setAccountRtmp(e.target.value)} />
            </div>
            <div className="form-group">
              <label>推流码</label>
              <input type="text" value={accountKey} onChange={(e) => setAccountKey(e.target.value)} />
            </div>
            <label className="check-row">
              <input
                type="checkbox"
                checked={accountEnabled}
                onChange={(e) => setAccountEnabled(e.target.checked)}
              />
              启用账号
            </label>
            <div className="row-actions">
              <button className="btn btn-primary" onClick={saveAccount}>
                {accountEditingId ? "保存修改" : "新增账号"}
              </button>
              {accountEditingId ? (
                <button className="btn btn-secondary" onClick={resetAccountForm}>
                  取消
                </button>
              ) : null}
            </div>
          </div>
          <div className="card">
            <div className="card-header">账号列表 ({accounts.length})</div>
            {accounts.length === 0 ? (
              <div className="empty">暂无账号</div>
            ) : (
              <div className="list">
                {accounts.map((account) => (
                  <div key={account.id} className="list-item">
                    <div className="list-main">
                      <div className="list-title">
                        {account.name}
                        <span className={`status-badge ${account.enabled ? "status-online" : "status-offline"}`}>
                          {account.enabled ? "启用" : "禁用"}
                        </span>
                      </div>
                      <div className="list-sub">{account.rtmp_url}</div>
                      <div className="list-sub">{maskSecret(account.stream_key)}</div>
                    </div>
                    <div className="list-actions">
                      <button
                        className="btn btn-secondary"
                        onClick={() => {
                          setAccountEditingId(account.id);
                          setAccountName(account.name);
                          setAccountRtmp(account.rtmp_url);
                          setAccountKey(account.stream_key);
                          setAccountEnabled(account.enabled);
                        }}
                      >
                        编辑
                      </button>
                      <button className="btn btn-danger" onClick={() => handleDeleteAccount(account.id)}>
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}

      {tab === "videos" ? (
        <div className="layout-2col">
          <div className="card">
            <div className="card-header">上传视频</div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp4,.mkv,.avi,.mov,.flv,.wmv"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                await uploadVideo(file);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
            />
          </div>
          <div className="card">
            <div className="card-header">视频列表 ({videos.length})</div>
            {videos.length === 0 ? (
              <div className="empty">暂无视频</div>
            ) : (
              <div className="list">
                {videos.map((video) => (
                  <div key={video.id} className="list-item">
                    <div className="list-main">
                      <div className="list-title">{video.filename}</div>
                      <div className="list-sub">{formatSize(video.size)}</div>
                    </div>
                    <div className="list-actions">
                      <button
                        className={`btn ${selectedVideo === video.id ? "btn-primary" : "btn-secondary"}`}
                        onClick={() => setSelectedVideo(video.id)}
                      >
                        {selectedVideo === video.id ? "已选择" : "选择"}
                      </button>
                      <button className="btn btn-danger" onClick={() => handleDeleteVideo(video.id)}>
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}

      {tab === "live" ? (
        <div className="layout-2col">
          <div className="card">
            <div className="card-header">本地开播（视频/黑屏）</div>
            <div className="form-group">
              <label>输入源</label>
              <select
                value={liveSourceType}
                onChange={(e) => setLiveSourceType(e.target.value as "video" | "black")}
              >
                <option value="video">本地视频</option>
                <option value="black">黑屏保活（无需视频）</option>
              </select>
            </div>
            {liveSourceType === "black" ? (
              <div className="hint" style={{ marginTop: -4 }}>
                黑屏模式会发送纯黑画面和静音音轨，不需要上传或选择视频文件。
              </div>
            ) : null}
            {liveSourceType === "video" ? (
            <div className="form-group">
              <label>视频</label>
              <select value={selectedVideo} onChange={(e) => setSelectedVideo(e.target.value)}>
                <option value="">请选择</option>
                {videos.map((video) => (
                  <option key={video.id} value={video.id}>
                    {video.filename}
                  </option>
                ))}
              </select>
            </div>
            ) : null}
            <div className="form-group">
              <label>标题</label>
              <input type="text" value={liveTitle} onChange={(e) => setLiveTitle(e.target.value)} />
            </div>
            <div className="form-group">
              <label>挂机省流档位</label>
              <select
                value={liveBandwidthMode}
                onChange={(e) =>
                  setLiveBandwidthMode(
                    e.target.value as
                      | "normal"
                      | "low"
                      | "ultra_low"
                      | "extreme_low"
                      | "extreme_low_1fps"
                      | "keepalive"
                  )
                }
              >
                <option value="normal">正常（较清晰，带宽较高）</option>
                <option value="low">省流（240p/10fps）</option>
                <option value="ultra_low">超省流挂机（180p/8fps）</option>
                <option value="extreme_low">极限省流连续（108p/3fps）</option>
                <option value="extreme_low_1fps">极限省流连续（108p/1fps）</option>
                <option value="keepalive">保活脉冲（2分推/1分停，80~120kbps，推荐）</option>
              </select>
              <div className="hint" style={{ marginTop: 8, marginBottom: 0 }}>
                保活脉冲会自动循环：推流 2 分钟，停流 1 分钟；并将码率压到约 80~120kbps。
              </div>
            </div>
            <div className="form-group">
              <label>直播账号</label>
              <select value={liveAccountId} onChange={(e) => setLiveAccountId(e.target.value)}>
                <option value="">手动输入</option>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id} disabled={!account.enabled}>
                    {account.name}
                    {account.enabled ? "" : "(禁用)"}
                  </option>
                ))}
              </select>
            </div>
            {liveAccount ? (
              <div className="hint">
                已选账号: {liveAccount.name} / {liveAccount.rtmp_url} / {maskSecret(liveAccount.stream_key)}
              </div>
            ) : null}
            <div className="form-group">
              <label>RTMP</label>
              <input
                type="text"
                disabled={!!liveAccountId}
                value={liveRtmp}
                onChange={(e) => setLiveRtmp(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>推流码</label>
              <input
                type="text"
                disabled={!!liveAccountId}
                value={liveKey}
                onChange={(e) => setLiveKey(e.target.value)}
              />
            </div>
            {liveSourceType === "video" ? (
              <label className="check-row">
                <input type="checkbox" checked={loopVideo} onChange={(e) => setLoopVideo(e.target.checked)} />
                循环播放
              </label>
            ) : null}
            <button className="btn btn-primary full-btn" onClick={startLive}>
              开始直播
            </button>
          </div>
          <div className="card">
            <div className="card-header">本地推流任务</div>
            {renderStreamCards("live")}
          </div>
        </div>
      ) : null}

      {tab === "youtube" ? (
        <div className="layout-2col">
          <div>
            <div className="card">
              <div className="card-header">解析 YouTube</div>
              <div className="row-inline">
                <input
                  type="text"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="YouTube 链接"
                />
                <button
                  className="btn btn-secondary"
                  onClick={async () => {
                    try {
                      const result = await api.parseYoutube(youtubeUrl.trim());
                      if (result.success && result.data) setYoutubeInfo(result.data);
                      else alert(result.detail || "解析失败");
                    } catch (error: unknown) {
                      alert((error as Error)?.message || "解析失败");
                    }
                  }}
                >
                  解析
                </button>
              </div>
              {youtubeInfo ? (
                <div className="hint" style={{ marginTop: 10 }}>
                  {youtubeInfo.title} - {youtubeInfo.author} {youtubeInfo.is_live ? "🔴LIVE" : ""}
                </div>
              ) : null}
            </div>

            <div className="card">
              <div className="card-header">转播设置</div>
              <div className="form-group">
                <label>画质</label>
                <select value={youtubeQuality} onChange={(e) => setYoutubeQuality(e.target.value)}>
                  <option value="best">最佳</option>
                  <option value="1080">1080p</option>
                  <option value="720">720p</option>
                  <option value="480">480p</option>
                  <option value="360">360p</option>
                </select>
              </div>
              <div className="form-group">
                <label>挂机省流档位</label>
                <select
                  value={youtubeBandwidthMode}
                  onChange={(e) =>
                    setYoutubeBandwidthMode(
                      e.target.value as
                        | "normal"
                        | "low"
                        | "ultra_low"
                        | "extreme_low"
                        | "extreme_low_1fps"
                        | "keepalive"
                    )
                  }
                >
                  <option value="normal">正常（较清晰，带宽较高）</option>
                  <option value="low">省流（240p/10fps）</option>
                  <option value="ultra_low">超省流挂机（180p/8fps）</option>
                  <option value="extreme_low">极限省流连续（108p/3fps）</option>
                  <option value="extreme_low_1fps">极限省流连续（108p/1fps）</option>
                  <option value="keepalive">保活脉冲（2分推/1分停，80~120kbps，推荐）</option>
                </select>
              </div>
              <div className="form-group">
                <label>直播账号</label>
                <select value={youtubeAccountId} onChange={(e) => setYoutubeAccountId(e.target.value)}>
                  <option value="">手动输入</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id} disabled={!account.enabled}>
                      {account.name}
                      {account.enabled ? "" : "(禁用)"}
                    </option>
                  ))}
                </select>
              </div>
              {youtubeAccount ? (
                <div className="hint">
                  已选账号: {youtubeAccount.name} / {youtubeAccount.rtmp_url} /{" "}
                  {maskSecret(youtubeAccount.stream_key)}
                </div>
              ) : null}
              <div className="form-group">
                <label>RTMP</label>
                <input
                  type="text"
                  disabled={!!youtubeAccountId}
                  value={youtubeRtmp}
                  onChange={(e) => setYoutubeRtmp(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>推流码</label>
                <input
                  type="text"
                  disabled={!!youtubeAccountId}
                  value={youtubeKey}
                  onChange={(e) => setYoutubeKey(e.target.value)}
                />
              </div>
              <button className="btn btn-primary full-btn" onClick={startYoutube}>
                开始转播
              </button>
            </div>

            <div className="card">
              <div className="card-header">水印设置</div>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={watermarkSettings.enabled}
                  onChange={(e) =>
                    setWatermarkSettings((prev) => ({ ...prev, enabled: e.target.checked }))
                  }
                />
                启用水印
              </label>

              {watermarkSettings.enabled ? (
                <>
                  <div className="row-inline" style={{ marginTop: 10 }}>
                    <label className="check-row">
                      <input
                        type="radio"
                        checked={watermarkSettings.type === "text"}
                        onChange={() => setWatermarkSettings((prev) => ({ ...prev, type: "text" }))}
                      />
                      文字
                    </label>
                    <label className="check-row">
                      <input
                        type="radio"
                        checked={watermarkSettings.type === "image"}
                        onChange={() => setWatermarkSettings((prev) => ({ ...prev, type: "image" }))}
                      />
                      图片
                    </label>
                  </div>
                  {watermarkSettings.type === "text" ? (
                    <div className="form-group" style={{ marginTop: 10 }}>
                      <label>文本</label>
                      <input
                        type="text"
                        value={watermarkSettings.text || ""}
                        onChange={(e) =>
                          setWatermarkSettings((prev) => ({ ...prev, text: e.target.value }))
                        }
                      />
                    </div>
                  ) : (
                    <div style={{ marginTop: 10 }}>
                      <input
                        ref={wmInputRef}
                        type="file"
                        accept=".png,.jpg,.jpeg,.gif,.webp"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          await uploadWatermark(file);
                          if (wmInputRef.current) wmInputRef.current.value = "";
                        }}
                      />
                      <div className="mini-tags">
                        {watermarks.map((wm) => (
                          <button
                            key={wm.filename}
                            className={`btn ${
                              watermarkSettings.image_filename === wm.filename
                                ? "btn-primary"
                                : "btn-secondary"
                            }`}
                            onClick={() =>
                              setWatermarkSettings((prev) => ({ ...prev, image_filename: wm.filename }))
                            }
                          >
                            {wm.filename}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>

          <div className="card">
            <div className="card-header">YouTube 转播任务</div>
            {renderStreamCards("youtube")}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default App;
