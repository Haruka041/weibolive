"""
推流管理模块
支持本地视频推流和 URL 流转播，支持水印叠加

注意：本项目为官方授权的学习项目，仅供学习 Web 自动化和流媒体技术使用。
"""
import asyncio
import subprocess
import logging
import threading
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from collections import deque
from .overlay import (
    WatermarkConfig,
    build_ffmpeg_command_with_watermark,
    build_ffmpeg_command_for_black_screen,
    build_ffmpeg_command_for_local_video,
)

logger = logging.getLogger(__name__)


class StreamStatus(Enum):
    """推流状态"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class StreamType(Enum):
    """推流类型"""
    LOCAL_VIDEO = "local_video"  # 本地视频文件
    BLACK_SCREEN = "black_screen"  # 纯黑画面 + 静音音轨
    URL_STREAM = "url_stream"    # URL 流（如 YouTube 直播）


@dataclass
class StreamConfig:
    """推流配置"""
    # 必需参数
    rtmp_url: str
    stream_key: str
    
    # 输入源（二选一）
    video_path: Optional[Path] = None      # 本地视频路径
    stream_url: Optional[str] = None        # 流 URL（YouTube HLS 等）
    
    # 推流类型
    stream_type: StreamType = StreamType.LOCAL_VIDEO
    
    # 循环播放（仅本地视频有效）
    loop: bool = True
    
    # 水印配置
    watermark: Optional[WatermarkConfig] = None
    
    # 编码设置
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    preset: str = "veryfast"
    maxrate: str = "3000k"
    bandwidth_mode: str = "normal"  # normal / low / ultra_low / extreme_low / extreme_low_1fps / keepalive
    pulse_enabled: bool = False
    pulse_on_seconds: int = 120
    pulse_off_seconds: int = 60
    
    # YouTube 相关
    youtube_video_id: Optional[str] = None
    quality: str = "best"
    auto_reconnect: bool = True
    reconnect_delay_seconds: int = 5
    max_reconnect_attempts: int = 10
    
    @property
    def full_rtmp_url(self) -> str:
        """完整的 RTMP 推流地址"""
        return f"{self.rtmp_url}/{self.stream_key}"
    
    def validate(self) -> tuple[bool, str]:
        """验证配置"""
        if not self.rtmp_url or not self.stream_key:
            return False, "RTMP 地址和推流码不能为空"
        
        if self.stream_type == StreamType.LOCAL_VIDEO:
            if not self.video_path:
                return False, "本地视频路径不能为空"
            if not self.video_path.exists():
                return False, f"视频文件不存在: {self.video_path}"
        elif self.stream_type == StreamType.BLACK_SCREEN:
            # 黑屏模式无需本地输入文件
            pass
        elif self.stream_type == StreamType.URL_STREAM:
            if not self.stream_url:
                return False, "流 URL 不能为空"
        
        # 验证水印配置
        if self.watermark and self.watermark.enabled:
            if self.watermark.image_path and not Path(self.watermark.image_path).exists():
                return False, f"水印图片不存在: {self.watermark.image_path}"

        if self.reconnect_delay_seconds < 1:
            return False, "重连间隔必须大于 0 秒"
        if self.max_reconnect_attempts < 0:
            return False, "最大重连次数不能小于 0"
        if self.bandwidth_mode not in {"normal", "low", "ultra_low", "extreme_low", "extreme_low_1fps", "keepalive"}:
            return False, "bandwidth_mode 仅支持 normal/low/ultra_low/extreme_low/extreme_low_1fps/keepalive"
        if self.pulse_on_seconds < 10:
            return False, "pulse_on_seconds 不能小于 10 秒"
        if self.pulse_off_seconds < 0:
            return False, "pulse_off_seconds 不能小于 0 秒"

        return True, ""


@dataclass
class StreamInfo:
    """推流信息"""
    status: StreamStatus = StreamStatus.IDLE
    config: Optional[StreamConfig] = None
    error_message: str = ""
    uptime_seconds: int = 0
    bytes_sent: int = 0
    reconnect_attempts: int = 0
    last_exit_code: Optional[int] = None
    pulse_enabled: bool = False
    pulse_phase: str = "steady"  # steady / on / off
    pulse_on_seconds: int = 0
    pulse_off_seconds: int = 0
    
    def to_dict(self) -> dict:
        """转换为字典"""
        video_path = str(self.config.video_path) if self.config and self.config.video_path else None
        video_name = self.config.video_path.name if self.config and self.config.video_path else None

        return {
            "status": self.status.value,
            "is_running": self.status == StreamStatus.RUNNING,
            "stream_type": self.config.stream_type.value if self.config else None,
            "error": self.error_message if self.status == StreamStatus.ERROR else None,
            "video": video_name,
            "video_path": video_path,
            "stream_url": self.config.stream_url if self.config else None,
            "rtmp_url": self.config.full_rtmp_url if self.config else None,
            "youtube_video_id": self.config.youtube_video_id if self.config else None,
            "watermark_enabled": self.config.watermark.enabled if self.config and self.config.watermark else False,
            "uptime_seconds": self.uptime_seconds,
            "reconnect_attempts": self.reconnect_attempts,
            "last_exit_code": self.last_exit_code,
            "pulse_enabled": self.pulse_enabled,
            "pulse_phase": self.pulse_phase,
            "pulse_on_seconds": self.pulse_on_seconds,
            "pulse_off_seconds": self.pulse_off_seconds,
        }


class StreamManager:
    """推流管理器"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.info: StreamInfo = StreamInfo()
        self._start_time: Optional[float] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._pulse_task: Optional[asyncio.Task] = None
        self._operation_lock = asyncio.Lock()
        self._status_queues: set[asyncio.Queue] = set()
        self._stop_requested: bool = False
        # 持续消费 FFmpeg stderr，避免 PIPE 填满导致进程阻塞
        self._stderr_buffer: deque[str] = deque(maxlen=200)
        self._stderr_thread: Optional[threading.Thread] = None
    
    @property
    def status(self) -> StreamStatus:
        return self.info.status
    
    @property
    def is_running(self) -> bool:
        return self.status == StreamStatus.RUNNING

    @property
    def error_message(self) -> str:
        return self.info.error_message

    def subscribe_status(self) -> asyncio.Queue:
        """订阅推流状态变更"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._status_queues.add(queue)
        queue.put_nowait(self.get_status())
        return queue

    def unsubscribe_status(self, queue: asyncio.Queue) -> None:
        """取消订阅推流状态变更"""
        self._status_queues.discard(queue)

    def _emit_status(self) -> None:
        """向所有订阅者推送最新状态"""
        status = self.get_status()
        for queue in list(self._status_queues):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(status)
            except asyncio.QueueFull:
                continue
    
    async def start_stream(self, config: StreamConfig) -> tuple[bool, str]:
        """
        开始推流
        
        Args:
            config: 推流配置
            
        Returns:
            tuple[bool, str]: (是否成功, 错误消息)
        """
        async with self._operation_lock:
            if self.is_running or self.status == StreamStatus.STARTING:
                return False, "已有推流正在进行"

            # 验证配置
            valid, error = config.validate()
            if not valid:
                return False, error

            self.info.config = config
            self.info.error_message = ""
            self.info.reconnect_attempts = 0
            self.info.last_exit_code = None
            self.info.uptime_seconds = 0
            self.info.pulse_enabled = config.pulse_enabled
            self.info.pulse_phase = "on" if config.pulse_enabled else "steady"
            self.info.pulse_on_seconds = config.pulse_on_seconds if config.pulse_enabled else 0
            self.info.pulse_off_seconds = config.pulse_off_seconds if config.pulse_enabled else 0
            self._stop_requested = False
            self.info.status = StreamStatus.STARTING
            self._emit_status()

            self._start_time = asyncio.get_event_loop().time()

            if config.pulse_enabled:
                self.info.status = StreamStatus.RUNNING
                self.info.error_message = ""
                self._emit_status()
                if self._monitor_task:
                    self._monitor_task.cancel()
                if self._pulse_task:
                    self._pulse_task.cancel()
                self._pulse_task = asyncio.create_task(self._pulse_stream(config))
                logger.info(
                    f"脉冲保活推流已启动: {config.full_rtmp_url} "
                    f"(on={config.pulse_on_seconds}s/off={config.pulse_off_seconds}s)"
                )
                return True, ""

            success, error = await self._start_process(config)
            if not success:
                self.info.status = StreamStatus.ERROR
                self.info.error_message = error
                self._emit_status()
                return False, error

            self.info.status = StreamStatus.RUNNING
            self.info.error_message = ""
            self.info.pulse_phase = "steady"
            self._emit_status()

            if self._monitor_task:
                self._monitor_task.cancel()
            self._monitor_task = asyncio.create_task(self._monitor_process())

            logger.info(f"推流已启动: {config.full_rtmp_url}")
            return True, ""

    async def _start_process(self, config: StreamConfig) -> tuple[bool, str]:
        """启动 FFmpeg 进程并检测是否正常运行"""
        cmd = self._build_ffmpeg_command(config)
        logger.info(f"FFmpeg 命令: {' '.join(cmd)}")

        self._stderr_buffer.clear()
        self._stderr_thread = None

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )

            if self.process.stderr:
                self._stderr_thread = threading.Thread(
                    target=self._drain_stderr,
                    args=(self.process.stderr,),
                    daemon=True,
                )
                self._stderr_thread.start()
        except FileNotFoundError:
            self.process = None
            return False, "FFmpeg 未安装或不在 PATH 中"
        except Exception as exc:
            self.process = None
            return False, f"启动 FFmpeg 失败: {exc}"

        await asyncio.sleep(2)

        if self.process.poll() is not None:
            stderr = self._stderr_tail()

            self.info.last_exit_code = self.process.returncode
            self.process = None
            details = stderr[-500:] if stderr else "未知错误"
            return False, f"FFmpeg 启动失败: {details}"

        return True, ""

    async def _pulse_stream(self, config: StreamConfig) -> None:
        """脉冲保活模式：推一段时间，停一段时间，循环执行。"""
        loop = asyncio.get_event_loop()
        on_seconds = max(10, config.pulse_on_seconds)
        off_seconds = max(0, config.pulse_off_seconds)
        consecutive_start_failures = 0

        while not self._stop_requested:
            self.info.status = StreamStatus.RUNNING
            self.info.error_message = ""
            self.info.pulse_phase = "on"
            self._emit_status()

            started, error = await self._start_process(config)
            if not started:
                consecutive_start_failures += 1
                self.info.reconnect_attempts += 1

                reached_limit = (
                    config.max_reconnect_attempts > 0
                    and consecutive_start_failures >= config.max_reconnect_attempts
                )

                if reached_limit:
                    self.info.status = StreamStatus.ERROR
                    self.info.error_message = (
                        f"脉冲保活连续启动失败 {consecutive_start_failures} 次，已停止: {error}"
                    )
                    self._emit_status()
                    logger.error(self.info.error_message)
                    return

                self.info.status = StreamStatus.STARTING
                self.info.error_message = (
                    f"脉冲保活启动失败，{config.reconnect_delay_seconds} 秒后重试 "
                    f"({consecutive_start_failures}/"
                    f"{'无限' if config.max_reconnect_attempts == 0 else config.max_reconnect_attempts})"
                )
                self._emit_status()
                logger.warning(f"{self.info.error_message}: {error}")
                await asyncio.sleep(max(1, config.reconnect_delay_seconds))
                continue

            # 只要成功启动过一次，就清零连续失败计数
            consecutive_start_failures = 0

            on_start = loop.time()
            while not self._stop_requested:
                now = loop.time()
                if self._start_time:
                    self.info.uptime_seconds = int(now - self._start_time)
                self._emit_status()

                if self.process and self.process.poll() is not None:
                    self.info.last_exit_code = self.process.returncode
                    self.process = None
                    break

                if now - on_start >= on_seconds:
                    break
                await asyncio.sleep(1)

            if self._stop_requested:
                break

            if self.process:
                await self._terminate_process()
                self.info.last_exit_code = self.process.returncode
                self.process = None

            if off_seconds <= 0:
                continue

            self.info.status = StreamStatus.RUNNING
            self.info.error_message = ""
            self.info.pulse_phase = "off"
            self._emit_status()

            off_start = loop.time()
            while not self._stop_requested and (loop.time() - off_start) < off_seconds:
                if self._start_time:
                    self.info.uptime_seconds = int(loop.time() - self._start_time)
                self._emit_status()
                await asyncio.sleep(1)

        logger.info("脉冲保活任务已结束")
    
    async def stop_stream(self) -> tuple[bool, str]:
        """
        停止推流
        
        Returns:
            tuple[bool, str]: (是否成功, 错误消息)
        """
        async with self._operation_lock:
            self._stop_requested = True

            if (
                not self.process
                and not self._monitor_task
                and not self._pulse_task
                and self.status in (StreamStatus.IDLE, StreamStatus.ERROR)
            ):
                self.info.status = StreamStatus.IDLE
                self.info.error_message = ""
                self._emit_status()
                return True, ""

            self.info.status = StreamStatus.STOPPING
            self._emit_status()

            try:
                # 取消监控任务
                monitor_task = self._monitor_task
                self._monitor_task = None
                pulse_task = self._pulse_task
                self._pulse_task = None

                current_task = asyncio.current_task()
                if monitor_task and monitor_task is not current_task:
                    monitor_task.cancel()
                    try:
                        await monitor_task
                    except asyncio.CancelledError:
                        pass
                if pulse_task and pulse_task is not current_task:
                    pulse_task.cancel()
                    try:
                        await pulse_task
                    except asyncio.CancelledError:
                        pass

                await self._terminate_process()

                self.process = None
                self.info.status = StreamStatus.IDLE
                self.info.error_message = ""
                self.info.uptime_seconds = 0
                self.info.reconnect_attempts = 0
                self.info.last_exit_code = None
                self.info.pulse_enabled = False
                self.info.pulse_phase = "steady"
                self.info.pulse_on_seconds = 0
                self.info.pulse_off_seconds = 0
                self.info.config = None
                self._start_time = None
                self._emit_status()

                logger.info("推流已停止")
                return True, ""

            except Exception as e:
                self.info.status = StreamStatus.ERROR
                self.info.error_message = f"停止推流失败: {str(e)}"
                self._emit_status()
                logger.exception("停止推流失败")
                return False, self.info.error_message

    async def _terminate_process(self) -> None:
        """终止 FFmpeg 进程"""
        if not self.process:
            return

        # 发送 'q' 命令优雅退出
        if self.process.stdin:
            try:
                self.process.stdin.write(b"q")
                self.process.stdin.flush()
            except Exception:
                pass

        # 等待进程退出
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
    
    def _build_ffmpeg_command(self, config: StreamConfig) -> list:
        """构建 FFmpeg 命令"""
        maxrate = config.maxrate
        video_bitrate: Optional[str] = None
        output_size: Optional[str] = None
        output_fps: Optional[int] = None
        audio_bitrate = "128k"
        audio_sample_rate = "44100"
        audio_channels = 2

        if config.bandwidth_mode == "low":
            maxrate = "450k"
            video_bitrate = "350k"
            output_size = "426x240"
            output_fps = 10
            audio_bitrate = "32k"
            audio_sample_rate = "22050"
            audio_channels = 1
        elif config.bandwidth_mode == "ultra_low":
            maxrate = "220k"
            video_bitrate = "180k"
            output_size = "320x180"
            output_fps = 8
            audio_bitrate = "24k"
            audio_sample_rate = "16000"
            audio_channels = 1
        elif config.bandwidth_mode == "extreme_low":
            # 连续推流极限省流：3fps + 更低码率，兼容性风险高于 ultra_low
            maxrate = "95k"
            video_bitrate = "56k"
            output_size = "192x108"
            output_fps = 3
            audio_bitrate = "12k"
            audio_sample_rate = "16000"
            audio_channels = 1
        elif config.bandwidth_mode == "extreme_low_1fps":
            # 连续推流极限省流：1fps，最低带宽但平台兼容性风险最高
            maxrate = "75k"
            video_bitrate = "44k"
            output_size = "192x108"
            output_fps = 1
            audio_bitrate = "12k"
            audio_sample_rate = "16000"
            audio_channels = 1
        elif config.bandwidth_mode == "keepalive":
            # 目标总码率约 80~120 kbps
            maxrate = "120k"
            video_bitrate = "96k"
            output_size = "256x144"
            output_fps = 6
            audio_bitrate = "16k"
            audio_sample_rate = "16000"
            audio_channels = 1

        if config.stream_type == StreamType.LOCAL_VIDEO:
            # 本地视频推流
            return build_ffmpeg_command_for_local_video(
                video_path=str(config.video_path),
                output_url=config.full_rtmp_url,
                loop=config.loop,
                watermark=config.watermark,
                video_codec=config.video_codec,
                audio_codec=config.audio_codec,
                preset=config.preset,
                maxrate=maxrate,
                video_bitrate=video_bitrate,
                output_size=output_size,
                output_fps=output_fps,
                audio_bitrate=audio_bitrate,
                audio_sample_rate=audio_sample_rate,
                audio_channels=audio_channels,
            )
        elif config.stream_type == StreamType.BLACK_SCREEN:
            # 纯黑画面 + 静音推流（无需视频文件）
            return build_ffmpeg_command_for_black_screen(
                output_url=config.full_rtmp_url,
                watermark=config.watermark,
                video_codec=config.video_codec,
                audio_codec=config.audio_codec,
                preset=config.preset,
                maxrate=maxrate,
                video_bitrate=video_bitrate,
                output_size=output_size or "1280x720",
                output_fps=output_fps or 25,
                audio_bitrate=audio_bitrate,
                audio_sample_rate=audio_sample_rate,
                audio_channels=audio_channels,
            )
        else:
            # URL 流转播
            cmd = build_ffmpeg_command_with_watermark(
                input_url=config.stream_url,
                output_url=config.full_rtmp_url,
                watermark=config.watermark,
                video_codec=config.video_codec,
                audio_codec=config.audio_codec,
                preset=config.preset,
                maxrate=maxrate,
                video_bitrate=video_bitrate,
                output_size=output_size,
                output_fps=output_fps,
                audio_bitrate=audio_bitrate,
                audio_sample_rate=audio_sample_rate,
                audio_channels=audio_channels,
            )

            # 对 HTTP/HLS 输入启用 FFmpeg 自带重连参数
            if config.stream_url and config.stream_url.startswith(("http://", "https://")):
                try:
                    input_idx = cmd.index("-i")
                    reconnect_flags = [
                        "-reconnect",
                        "1",
                        "-reconnect_streamed",
                        "1",
                        "-reconnect_delay_max",
                        str(config.reconnect_delay_seconds),
                    ]
                    cmd[input_idx:input_idx] = reconnect_flags
                except ValueError:
                    pass

            return cmd
    
    async def _monitor_process(self):
        """监控推流进程"""
        while self.process:
            # 更新运行时间
            if self._start_time and self.info.status == StreamStatus.RUNNING:
                self.info.uptime_seconds = int(
                    asyncio.get_event_loop().time() - self._start_time
                )
                self._emit_status()

            exit_code = self.process.poll()
            if exit_code is None:
                await asyncio.sleep(1)
                continue

            stderr = self._stderr_tail()

            self.info.last_exit_code = exit_code
            self.process = None

            if self._stop_requested:
                logger.info("推流进程已停止")
                return

            config = self.info.config
            can_reconnect = (
                config is not None
                and config.stream_type == StreamType.URL_STREAM
                and config.auto_reconnect
                and (
                    config.max_reconnect_attempts == 0
                    or self.info.reconnect_attempts < config.max_reconnect_attempts
                )
            )

            if can_reconnect:
                self.info.reconnect_attempts += 1
                retries_text = (
                    "无限"
                    if config.max_reconnect_attempts == 0
                    else str(config.max_reconnect_attempts)
                )
                self.info.status = StreamStatus.STARTING
                self.info.error_message = (
                    f"推流中断，{config.reconnect_delay_seconds} 秒后自动重连 "
                    f"({self.info.reconnect_attempts}/{retries_text})"
                )
                self._emit_status()
                logger.warning(self.info.error_message)

                await asyncio.sleep(config.reconnect_delay_seconds)

                if self._stop_requested:
                    return

                success, error = await self._start_process(config)
                if success:
                    self.info.status = StreamStatus.RUNNING
                    self.info.error_message = ""
                    self._start_time = asyncio.get_event_loop().time()
                    self._emit_status()
                    logger.info("自动重连成功")
                    continue

                self.info.status = StreamStatus.ERROR
                self.info.error_message = error
                self._emit_status()
                logger.error(f"自动重连失败: {error}")
                return

            # 无法重连，标记失败
            details = stderr[-500:] if stderr else "无错误输出"
            self.info.status = StreamStatus.ERROR
            self.info.error_message = f"推流进程意外退出 (code={exit_code}): {details}"
            self._emit_status()
            logger.error(self.info.error_message)
            return

    def _drain_stderr(self, pipe) -> None:
        """后台持续读取 stderr，避免 FFmpeg 因缓冲区满而阻塞"""
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="ignore").replace("\r", "\n")
                for line in text.split("\n"):
                    line = line.strip()
                    if line:
                        self._stderr_buffer.append(line)
        except Exception as exc:
            logger.debug(f"读取 FFmpeg stderr 失败: {exc}")

    def _stderr_tail(self) -> str:
        """获取最近 FFmpeg stderr 片段"""
        if not self._stderr_buffer:
            return ""
        return "\n".join(self._stderr_buffer)
    
    def get_status(self) -> dict:
        """获取推流状态"""
        return self.info.to_dict()
    
    async def update_watermark(self, watermark: WatermarkConfig) -> tuple[bool, str]:
        """
        更新水印（需要重启推流）
        
        Args:
            watermark: 新的水印配置
            
        Returns:
            tuple[bool, str]: (是否成功, 错误消息)
        """
        if not self.info.config:
            return False, "没有活动的推流配置"

        current_config = StreamConfig(**vars(self.info.config))
        current_config.watermark = watermark

        # 如果正在推流，需要重启
        if self.is_running:
            stopped, stop_error = await self.stop_stream()
            if not stopped:
                return False, stop_error
            return await self.start_stream(current_config)

        self.info.config = current_config
        self._emit_status()
        return True, ""


# 全局单例
stream_manager = StreamManager()
