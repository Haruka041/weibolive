from .config import CONFIG
from .weibo import weibo_client
from .stream import stream_manager as single_stream_manager, StreamConfig, StreamType, StreamStatus
from .multi_stream import multi_stream_manager
from .youtube import youtube_parser, YouTubeStreamInfo
from .overlay import WatermarkConfig, WatermarkPosition
from .admin_auth import admin_auth_manager, require_admin, get_admin_from_token, ADMIN_COOKIE_NAME
from .stream_accounts import stream_account_manager, StreamAccount

# 默认导出多路推流管理器，兼容旧导入名
stream_manager = multi_stream_manager

__all__ = [
    'CONFIG', 
    'weibo_client', 
    'stream_manager',
    'single_stream_manager',
    'multi_stream_manager',
    'StreamConfig',
    'StreamType',
    'StreamStatus',
    'youtube_parser',
    'YouTubeStreamInfo',
    'WatermarkConfig',
    'WatermarkPosition',
    'admin_auth_manager',
    'require_admin',
    'get_admin_from_token',
    'ADMIN_COOKIE_NAME',
    'stream_account_manager',
    'StreamAccount',
]
