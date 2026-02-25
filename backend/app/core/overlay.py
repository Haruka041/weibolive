"""
水印叠加处理模块
支持图片水印和文字水印

注意：本项目为官方授权的学习项目，仅供学习 Web 自动化和流媒体技术使用。
"""
import os
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


def _ffmpeg_bin() -> str:
    """
    获取 FFmpeg 可执行文件路径。
    优先读取环境变量，未设置时回退到系统 PATH 中的 ffmpeg。
    """
    return (
        os.getenv("WEIBOLIVE_FFMPEG")
        or os.getenv("FFMPEG_BIN")
        or os.getenv("FFMPEG_BINARY")
        or "ffmpeg"
    )


def _beijing_time_drawtext_filter(video_width: int, video_height: int) -> str:
    """
    黑屏挂机模式默认叠加北京时间动态时间，降低长时间静态黑屏风险。
    注意：时间源使用 drawtext 的 localtime，需要在进程环境中将 TZ 设为 Asia/Shanghai。
    """
    font_size = max(12, min(28, video_height // 14))
    box_border = max(4, video_height // 90)

    # 低分辨率档位（如 192x108 / 256x144）使用短格式，避免文字宽度溢出
    if video_width < 360:
        text_expr = "BJT %{localtime\\:%H\\:%M\\:%S}"
    else:
        text_expr = "BJT %{localtime\\:%Y-%m-%d %H\\:%M\\:%S}"

    return (
        "drawtext="
        f"text='{text_expr}':"
        f"fontsize={font_size}:"
        "fontcolor=white@0.95:"
        "box=1:"
        "boxcolor=black@0.45:"
        f"boxborderw={box_border}:"
        "x=(w-tw)/2:"
        "y=(h-th)/2"
    )


class WatermarkPosition(Enum):
    """水印位置"""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CENTER = "center"


@dataclass
class WatermarkConfig:
    """水印配置"""
    enabled: bool = False
    # 通用配置
    position: WatermarkPosition = WatermarkPosition.BOTTOM_RIGHT
    opacity: float = 0.7  # 0.0 - 1.0
    margin: int = 10  # 边距像素
    
    # 图片水印配置
    image_path: Optional[str] = None
    scale: float = 1.0  # 缩放比例
    
    # 文字水印配置
    text: Optional[str] = None
    font_size: int = 24
    font_color: str = "white"
    font_file: Optional[str] = None  # 自定义字体文件路径
    
    def to_ffmpeg_params(self, video_width: int = 1920, video_height: int = 1080) -> str:
        """
        生成 FFmpeg filter 参数
        
        Args:
            video_width: 视频宽度
            video_height: 视频高度
            
        Returns:
            str: FFmpeg filter_complex 参数
        """
        if not self.enabled:
            return ""
        
        filters = []
        
        if self.image_path and os.path.exists(self.image_path):
            # 图片水印
            filters.append(self._build_image_watermark(video_width, video_height))
        elif self.text:
            # 文字水印
            filters.append(self._build_text_watermark(video_width, video_height))
        
        return ",".join(filters) if filters else ""
    
    def _build_image_watermark(self, video_width: int, video_height: int) -> str:
        """构建图片水印 filter"""
        # 计算缩放
        scale_filter = f"scale=iw*{self.scale}:ih*{self.scale}"
        
        # 计算位置
        x, y = self._calculate_position(video_width, video_height)
        
        # 构建 overlay filter
        # opacity 通过 colorchannelmixer 实现
        opacity_hex = int(self.opacity * 255)
        
        overlay_filter = (
            f"[1:v]{scale_filter},"
            f"colorchannelmixer=aa={self.opacity}[wm];"
            f"[0:v][wm]overlay={x}:{y}"
        )
        
        return overlay_filter
    
    def _build_text_watermark(self, video_width: int, video_height: int) -> str:
        """构建文字水印 filter"""
        # 计算位置
        x, y = self._calculate_position(video_width, video_height, is_text=True)
        
        # 构建字体配置
        fontconfig = f"fontsize={self.font_size}:fontcolor={self.font_color}@{self.opacity}"
        
        # 处理自定义字体
        if self.font_file and os.path.exists(self.font_file):
            fontconfig += f":fontfile='{self.font_file}'"
        
        # 转义特殊字符
        escaped_text = self.text.replace("'", "\\'").replace(":", "\\:")
        
        drawtext_filter = f"drawtext=text='{escaped_text}':{fontconfig}:x={x}:y={y}"
        
        return drawtext_filter
    
    def _calculate_position(
        self, 
        video_width: int, 
        video_height: int,
        is_text: bool = False
    ) -> Tuple[str, str]:
        """
        计算水印位置坐标
        
        Returns:
            Tuple[str, str]: (x, y) 坐标表达式
        """
        margin = self.margin
        
        if self.position == WatermarkPosition.TOP_LEFT:
            return f"{margin}", f"{margin}"
        
        elif self.position == WatermarkPosition.TOP_RIGHT:
            if is_text:
                return f"w-tw-{margin}", f"{margin}"
            else:
                return f"W-w-{margin}", f"{margin}"
        
        elif self.position == WatermarkPosition.BOTTOM_LEFT:
            if is_text:
                return f"{margin}", f"h-th-{margin}"
            else:
                return f"{margin}", f"H-h-{margin}"
        
        elif self.position == WatermarkPosition.BOTTOM_RIGHT:
            if is_text:
                return f"w-tw-{margin}", f"h-th-{margin}"
            else:
                return f"W-w-{margin}", f"H-h-{margin}"
        
        elif self.position == WatermarkPosition.CENTER:
            if is_text:
                return f"(w-tw)/2", f"(h-th)/2"
            else:
                return f"(W-w)/2", f"(H-h)/2"
        
        # 默认右下角
        return f"W-w-{margin}", f"H-h-{margin}"


def build_ffmpeg_command_with_watermark(
    input_url: str,
    output_url: str,
    watermark: Optional[WatermarkConfig] = None,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    preset: str = "veryfast",
    maxrate: str = "3000k",
    video_bitrate: Optional[str] = None,
    bufsize: str = "6000k",
    output_size: Optional[str] = None,
    output_fps: Optional[int] = None,
    audio_bitrate: str = "128k",
    audio_sample_rate: str = "44100",
    audio_channels: int = 2,
    extra_options: Optional[dict] = None
) -> list:
    """
    构建带水印的 FFmpeg 推流命令
    
    Args:
        input_url: 输入流地址
        output_url: 输出 RTMP 地址
        watermark: 水印配置
        video_codec: 视频编码器
        audio_codec: 音频编码器
        preset: 编码预设
        maxrate: 最大码率
        bufsize: 缓冲区大小
        extra_options: 额外选项
        
    Returns:
        list: FFmpeg 命令参数列表
    """
    cmd = [_ffmpeg_bin(), "-re"]
    fps = output_fps if output_fps and output_fps > 0 else 30
    gop = max(2, int(fps) * 2)
    
    # 输入
    if watermark and watermark.enabled and watermark.image_path:
        # 图片水印需要两个输入
        cmd.extend(["-i", input_url])
        cmd.extend(["-i", watermark.image_path])
        
        # 构建 filter_complex
        filter_complex = watermark.to_ffmpeg_params()
        if filter_complex:
            cmd.extend(["-filter_complex", filter_complex])
    else:
        cmd.extend(["-i", input_url])
        
        # 文字水印使用 -vf
        if watermark and watermark.enabled and watermark.text:
            vf = watermark.to_ffmpeg_params()
            if vf:
                cmd.extend(["-vf", vf])
    
    # 视频编码
    cmd.extend([
        "-c:v", video_codec,
        "-preset", preset,
        "-tune", "zerolatency",
        "-bf", "0",
        "-pix_fmt", "yuv420p",
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-g", str(gop),
        "-keyint_min", str(gop),
        "-sc_threshold", "0",
    ])

    if video_bitrate:
        cmd.extend(["-b:v", video_bitrate])
    if output_fps and output_fps > 0:
        cmd.extend(["-r", str(output_fps)])
    if output_size:
        cmd.extend(["-s", output_size])
    
    # 音频编码
    cmd.extend([
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        "-ar", audio_sample_rate,
        "-ac", str(audio_channels),
    ])
    
    # 输出格式
    cmd.extend([
        "-f", "flv",
        "-flvflags", "no_duration_filesize",
    ])
    
    # 额外选项
    if extra_options:
        for key, value in extra_options.items():
            cmd.extend([key, value])
    
    # 输出地址
    cmd.append(output_url)
    
    return cmd


def build_ffmpeg_command_for_local_video(
    video_path: str,
    output_url: str,
    loop: bool = True,
    watermark: Optional[WatermarkConfig] = None,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    preset: str = "veryfast",
    maxrate: str = "3000k",
    video_bitrate: Optional[str] = None,
    output_size: Optional[str] = None,
    output_fps: Optional[int] = None,
    audio_bitrate: str = "128k",
    audio_sample_rate: str = "44100",
    audio_channels: int = 2,
) -> list:
    """
    构建本地视频推流命令（支持循环）
    
    Args:
        video_path: 本地视频路径
        output_url: 输出 RTMP 地址
        loop: 是否循环播放
        watermark: 水印配置
        video_codec: 视频编码器
        audio_codec: 音频编码器
        preset: 编码预设
        maxrate: 最大码率
        
    Returns:
        list: FFmpeg 命令参数列表
    """
    cmd = [_ffmpeg_bin(), "-re"]
    fps = output_fps if output_fps and output_fps > 0 else 30
    gop = max(2, int(fps) * 2)
    
    # 循环选项
    if loop:
        cmd.extend(["-stream_loop", "-1"])
    
    # 输入
    if watermark and watermark.enabled and watermark.image_path:
        cmd.extend(["-i", video_path])
        cmd.extend(["-i", watermark.image_path])
        
        filter_complex = watermark.to_ffmpeg_params()
        if filter_complex:
            cmd.extend(["-filter_complex", filter_complex])
    else:
        cmd.extend(["-i", video_path])
        
        if watermark and watermark.enabled and watermark.text:
            vf = watermark.to_ffmpeg_params()
            if vf:
                cmd.extend(["-vf", vf])
    
    # 视频编码
    try:
        maxrate_k = int(maxrate.replace("k", ""))
    except ValueError:
        maxrate_k = 3000

    cmd.extend([
        "-c:v", video_codec,
        "-preset", preset,
        "-tune", "zerolatency",
        "-bf", "0",
        "-pix_fmt", "yuv420p",
        "-maxrate", maxrate,
        "-bufsize", f"{maxrate_k * 2}k",
        "-g", str(gop),
        "-keyint_min", str(gop),
        "-sc_threshold", "0",
    ])

    if video_bitrate:
        cmd.extend(["-b:v", video_bitrate])
    if output_fps and output_fps > 0:
        cmd.extend(["-r", str(output_fps)])
    if output_size:
        cmd.extend(["-s", output_size])
    
    # 音频编码
    cmd.extend([
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        "-ar", audio_sample_rate,
        "-ac", str(audio_channels),
    ])
    
    # 输出格式
    cmd.extend([
        "-f", "flv",
        "-flvflags", "no_duration_filesize",
    ])
    
    # 输出地址
    cmd.append(output_url)
    
    return cmd


def build_ffmpeg_command_for_black_screen(
    output_url: str,
    watermark: Optional[WatermarkConfig] = None,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    preset: str = "veryfast",
    maxrate: str = "3000k",
    video_bitrate: Optional[str] = None,
    output_size: str = "1280x720",
    output_fps: int = 25,
    audio_bitrate: str = "128k",
    audio_sample_rate: str = "44100",
    audio_channels: int = 2,
) -> list:
    """
    构建纯黑画面 + 静音音轨推流命令（无需本地视频文件）

    Args:
        output_url: 输出 RTMP 地址
        watermark: 水印配置
        video_codec: 视频编码器
        audio_codec: 音频编码器
        preset: 编码预设
        maxrate: 最大码率
        video_bitrate: 视频码率
        output_size: 输出分辨率，如 1280x720
        output_fps: 输出帧率
        audio_bitrate: 音频码率
        audio_sample_rate: 音频采样率
        audio_channels: 音频声道数

    Returns:
        list: FFmpeg 命令参数列表
    """
    fps = max(1, int(output_fps))
    cmd = [
        _ffmpeg_bin(),
        "-re",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={output_size}:r={fps}",
    ]

    image_watermark_enabled = (
        bool(watermark)
        and bool(watermark.enabled)
        and bool(watermark.image_path)
        and os.path.exists(watermark.image_path)
    )
    text_watermark_enabled = bool(watermark) and bool(watermark.enabled) and bool(watermark.text)

    if image_watermark_enabled:
        # 图片水印作为第二路视频输入
        cmd.extend(["-loop", "1", "-i", watermark.image_path])

    # 补一条静音音轨，确保平台端识别为完整 AV 流
    channel_layout = "mono" if audio_channels == 1 else "stereo"
    cmd.extend(
        [
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout={channel_layout}:sample_rate={audio_sample_rate}",
        ]
    )

    width = 1280
    height = 720
    if "x" in output_size:
        try:
            width_str, height_str = output_size.split("x", 1)
            width = int(width_str)
            height = int(height_str)
        except ValueError:
            pass
    bjt_filter = _beijing_time_drawtext_filter(video_width=width, video_height=height)

    if image_watermark_enabled:
        filter_complex = watermark.to_ffmpeg_params(video_width=width, video_height=height)
        if filter_complex:
            cmd.extend(["-filter_complex", f"{filter_complex},{bjt_filter}"])
        else:
            cmd.extend(["-vf", bjt_filter])
    elif text_watermark_enabled:
        vf = watermark.to_ffmpeg_params(video_width=width, video_height=height)
        if vf:
            cmd.extend(["-vf", f"{vf},{bjt_filter}"])
        else:
            cmd.extend(["-vf", bjt_filter])
    else:
        cmd.extend(["-vf", bjt_filter])

    try:
        maxrate_k = int(maxrate.replace("k", ""))
    except ValueError:
        maxrate_k = 3000

    # 直播平台通常要求 2 秒关键帧，低帧率下也尽量保持此规则
    gop = max(2, fps * 2)
    minrate = video_bitrate or maxrate

    cmd.extend(
        [
            "-c:v",
            video_codec,
            "-preset",
            preset,
            "-tune",
            "zerolatency",
            "-bf",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-maxrate",
            maxrate,
            "-minrate",
            minrate,
            "-bufsize",
            f"{maxrate_k * 2}k",
            "-g",
            str(gop),
            "-keyint_min",
            str(gop),
            "-sc_threshold",
            "0",
            "-r",
            str(fps),
        ]
    )

    if video_bitrate:
        cmd.extend(["-b:v", video_bitrate])

    cmd.extend(
        [
            "-c:a",
            audio_codec,
            "-b:a",
            audio_bitrate,
            "-ar",
            audio_sample_rate,
            "-ac",
            str(audio_channels),
            "-f",
            "flv",
            "-flvflags",
            "no_duration_filesize",
        ]
    )

    cmd.append(output_url)
    return cmd
