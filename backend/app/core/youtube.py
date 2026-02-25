"""
YouTube 直播流解析模块
用于获取 YouTube 直播流地址和信息

注意：本项目为官方授权的学习项目，仅供学习 Web 自动化和流媒体技术使用。
"""
import asyncio
import json
import re
from typing import Optional, Dict, List
from dataclasses import dataclass
import subprocess
import logging

logger = logging.getLogger(__name__)


@dataclass
class YouTubeStreamInfo:
    """YouTube 直播流信息"""
    video_id: str
    title: str
    description: str
    author: str
    is_live: bool
    thumbnail: str
    duration: Optional[int] = None
    view_count: Optional[int] = None
    formats: List[Dict] = None
    
    def __post_init__(self):
        if self.formats is None:
            self.formats = []


class YouTubeParser:
    """YouTube 直播流解析器"""
    
    def __init__(self):
        self._cache: Dict[str, YouTubeStreamInfo] = {}
    
    async def parse_url(self, url: str) -> YouTubeStreamInfo:
        """
        解析 YouTube URL，获取视频/直播信息
        
        Args:
            url: YouTube 视频或直播链接
            
        Returns:
            YouTubeStreamInfo: 流信息
        """
        # 提取 video_id
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError(f"无法从 URL 提取视频 ID: {url}")
        
        # 使用 yt-dlp 获取信息
        info = await self._fetch_info(video_id)
        return info
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """从 URL 中提取视频 ID"""
        patterns = [
            r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'(?:embed/)([a-zA-Z0-9_-]{11})',
            r'(?:live/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def _fetch_info(self, video_id: str) -> YouTubeStreamInfo:
        """使用 yt-dlp 获取视频信息"""
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        # 构建 yt-dlp 命令
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--no-download',
            '--no-warnings',
            '--quiet',
            url
        ]
        
        try:
            # 异步执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"yt-dlp 错误: {error_msg}")
                raise Exception(f"获取视频信息失败: {error_msg}")
            
            # 解析 JSON 输出
            data = json.loads(stdout.decode('utf-8'))
            
            # 提取格式信息
            formats = []
            for fmt in data.get('formats', []):
                if fmt.get('url'):
                    formats.append({
                        'format_id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'resolution': fmt.get('resolution'),
                        'fps': fmt.get('fps'),
                        'vcodec': fmt.get('vcodec'),
                        'acodec': fmt.get('acodec'),
                        'url': fmt.get('url'),
                        'manifest_url': fmt.get('manifest_url'),
                        'is_live': fmt.get('is_live', False),
                    })
            
            info = YouTubeStreamInfo(
                video_id=video_id,
                title=data.get('title', ''),
                description=data.get('description', '')[:500] if data.get('description') else '',
                author=data.get('uploader', data.get('channel', '')),
                is_live=data.get('is_live', False),
                thumbnail=data.get('thumbnail', data.get('thumbnails', [{}])[-1].get('url', '')),
                duration=data.get('duration'),
                view_count=data.get('view_count'),
                formats=formats,
            )
            
            # 缓存信息
            self._cache[video_id] = info
            
            return info
            
        except json.JSONDecodeError as e:
            logger.error(f"解析 yt-dlp 输出失败: {e}")
            raise Exception("解析视频信息失败")
        except FileNotFoundError:
            raise Exception("yt-dlp 未安装，请先安装: pip install yt-dlp")
    
    async def get_stream_url(
        self, 
        video_id: str, 
        quality: str = 'best'
    ) -> str:
        """
        获取直播流 URL
        
        Args:
            video_id: YouTube 视频 ID
            quality: 画质选择 ('best', '1080', '720', '480', '360')
            
        Returns:
            str: 流 URL
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        # 根据画质选择格式
        if quality == 'best':
            format_selector = 'best'
        else:
            format_selector = f'best[height<={quality}]'
        
        cmd = [
            'yt-dlp',
            '--get-url',
            '--no-warnings',
            '--quiet',
            '-f', format_selector,
            url
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise Exception(f"获取流 URL 失败: {error_msg}")
            
            return stdout.decode('utf-8').strip()
            
        except FileNotFoundError:
            raise Exception("yt-dlp 未安装")
    
    async def check_live_status(self, video_id: str) -> bool:
        """检查直播状态"""
        try:
            info = await self._fetch_info(video_id)
            return info.is_live
        except Exception as e:
            logger.error(f"检查直播状态失败: {e}")
            return False
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 全局实例
youtube_parser = YouTubeParser()
