import asyncio
import json
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from .config import CONFIG

class WeiboClient:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.cookie_file: Path = CONFIG.cookies_dir / "weibo_cookies.json"
        self._playwright = None
        
    async def init_browser(self):
        """Initialize Playwright browser"""
        if self.browser is None:
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(
                headless=CONFIG.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            # Load cookies if exists
            if self.cookie_file.exists():
                cookies = json.loads(self.cookie_file.read_text())
                self.context = await self.browser.new_context()
                await self.context.add_cookies(cookies)
            else:
                self.context = await self.browser.new_context()
            
            self.page = await self.context.new_page()
    
    async def close_browser(self):
        """Close browser and save cookies"""
        if self.context and self.page:
            cookies = await self.context.cookies()
            self.cookie_file.write_text(json.dumps(cookies))
        
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    async def get_login_qrcode(self) -> Optional[bytes]:
        """Get login QR code image bytes"""
        await self.init_browser()
        
        # Navigate to Weibo login page
        await self.page.goto(CONFIG.weibo_login_url, wait_until="networkidle")
        
        # Check if already logged in
        if await self.is_logged_in():
            return None
        
        # Wait for and screenshot QR code
        try:
            # Click to show QR code login if needed
            qr_tab = await self.page.query_selector('text=扫码登录')
            if qr_tab:
                await qr_tab.click()
                await asyncio.sleep(1)
            
            # Find QR code image
            qr_selector = 'img[class*="qrcode"], img[src*="qrcode"], canvas'
            await self.page.wait_for_selector(qr_selector, timeout=10000)
            
            # Take screenshot of QR code area
            qr_element = await self.page.query_selector(qr_selector)
            if qr_element:
                screenshot = await qr_element.screenshot()
                return screenshot
            
        except Exception as e:
            print(f"Error getting QR code: {e}")
            return None
        
        return None
    
    async def is_logged_in(self) -> bool:
        """Check if user is logged in"""
        if not self.page:
            return False
        
        try:
            # Check for login button or user avatar
            login_btn = await self.page.query_selector('text=登录')
            if login_btn and await login_btn.is_visible():
                return False
            
            # Check for user-specific elements
            user_element = await self.page.query_selector('[class*="user"], [class*="avatar"]')
            return user_element is not None
        except:
            return False
    
    async def wait_for_login(self, timeout: int = 120) -> bool:
        """Wait for user to scan QR code and login"""
        if not self.page:
            return False
        
        try:
            # Wait for page to redirect or show logged-in state
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                if await self.is_logged_in():
                    # Save cookies
                    cookies = await self.context.cookies()
                    self.cookie_file.write_text(json.dumps(cookies))
                    return True
                await asyncio.sleep(1)
            
            return False
        except Exception as e:
            print(f"Error waiting for login: {e}")
            return False
    
    async def load_cookies(self) -> bool:
        """Load saved cookies and check if still valid"""
        if not self.cookie_file.exists():
            return False
        
        await self.init_browser()
        cookies = json.loads(self.cookie_file.read_text())
        await self.context.add_cookies(cookies)
        
        # Navigate to verify
        await self.page.goto(CONFIG.weibo_login_url, wait_until="networkidle")
        return await self.is_logged_in()
    
    async def get_live_stream_info(self, title: str, cover_path: str) -> Optional[dict]:
        """
        Create a live stream room and get RTMP push URL
        Returns: dict with 'rtmp_url' and 'stream_key' or None on failure
        """
        await self.init_browser()
        
        try:
            # Navigate to live management page
            await self.page.goto(CONFIG.weibo_live_url, wait_until="networkidle")
            
            # Wait for page to load
            await asyncio.sleep(2)
            
            # TODO: Analyze and implement the actual API calls
            # This requires reverse engineering the Weibo live creation flow
            # For now, return a placeholder
            
            # Take a screenshot for debugging
            screenshot_path = CONFIG.data_dir / "live_page_debug.png"
            await self.page.screenshot(path=str(screenshot_path))
            
            print(f"Debug screenshot saved to {screenshot_path}")
            print("Please provide this screenshot so we can analyze the live creation flow")
            
            return {
                "status": "need_analysis",
                "message": "Need to analyze Weibo live API"
            }
            
        except Exception as e:
            print(f"Error getting live stream info: {e}")
            return None
    
    async def get_user_info(self) -> Optional[dict]:
        """Get logged-in user info"""
        if not self.page or not await self.is_logged_in():
            return None
        
        try:
            # Try to extract user info from page
            # This may need adjustment based on actual Weibo page structure
            user_info = await self.page.evaluate('''
                () => {
                    // Try to get user info from page variables
                    if (window.$CONFIG) {
                        return {
                            uid: window.$CONFIG.uid,
                            nick: window.$CONFIG.nick,
                            avatar: window.$CONFIG.avatar
                        };
                    }
                    return null;
                }
            ''')
            return user_info
        except:
            return None


# Singleton instance
weibo_client = WeiboClient()
