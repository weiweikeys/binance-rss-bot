#!/usr/bin/env python3
"""
幣安公告監控Telegram Bot (Web Scraping版本)
由於RSS不可用，改用網頁解析方式
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import os
import argparse
import logging
from datetime import datetime
from config import Config

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BinanceWebScraperBot:
    """幣安公告監控Bot (網頁解析版)"""
    
    def __init__(self):
        """初始化Bot"""
        try:
            Config.validate()
            self.telegram_token = Config.TELEGRAM_BOT_TOKEN
            self.chat_id = Config.TELEGRAM_CHAT_ID
            self.check_interval = Config.CHECK_INTERVAL
            
            # 改用網頁URL
            self.web_url = "https://www.binance.com/en/support/announcement/new-listing"
            self.seen_posts_file = "seen_posts.json"
            self.seen_posts = self.load_seen_posts()
            
            logger.info("🤖 Bot初始化完成 (網頁解析版)")
            logger.info(f"🌐 監控網址: {self.web_url}")
            logger.info(f"⏰ 檢查間隔: {self.check_interval}秒")
            
        except Exception as e:
            logger.error(f"❌ Bot初始化失敗: {e}")
            raise
    
    def load_seen_posts(self):
        """載入已處理的文章ID"""
        try:
            if os.path.exists(self.seen_posts_file):
                with open(self.seen_posts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"📚 載入了 {len(data)} 個已處理的文章記錄")
                    return set(data)
            return set()
        except Exception as e:
            logger.error(f"❌ 載入歷史記錄失敗: {e}")
            return set()
    
    def save_seen_posts(self):
        """儲存已處理的文章ID"""
        try:
            with open(self.seen_posts_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.seen_posts), f, ensure_ascii=False, indent=2)
            logger.debug(f"💾 已儲存 {len(self.seen_posts)} 個文章記錄")
        except Exception as e:
            logger.error(f"❌ 儲存歷史記錄失敗: {e}")
    
    def send_telegram_message(self, message):
        """發送Telegram訊息"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code == 200:
                logger.info("✅ 訊息發送成功")
                return True
            else:
                logger.error(f"❌ 發送失敗 ({response.status_code}): {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 網路錯誤: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 發送錯誤: {e}")
            return False
    
    def test_telegram_connection(self):
        """測試Telegram連接"""
        test_message = f"""
🧪 <b>Telegram連接測試 (網頁解析版)</b>

✅ Bot運行正常
📅 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🌐 改用網頁解析方式監控
🤖 準備開始監控幣安公告！
        """.strip()
        
        logger.info("🔍 測試Telegram連接...")
        success = self.send_telegram_message(test_message)
        
        if success:
            logger.info("✅ Telegram連接測試成功！")
        else:
            logger.error("❌ Telegram連接測試失敗！請檢查Token和Chat ID")
        
        return success
    
    def scrape_announcements(self):
        """抓取幣安公告頁面"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            logger.debug(f"🌐 正在抓取網頁: {self.web_url}")
            response = requests.get(self.web_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 查找公告列表 (這部分需要根據實際HTML結構調整)
            announcements = []
            
            # 常見的公告容器選擇器
            selectors = [
                '.announcement-item',
                '.news-item', 
                'article',
                '[class*="announcement"]',
                '[class*="news"]'
            ]
            
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    logger.info(f"📄 找到 {len(items)} 個公告項目 (使用選擇器: {selector})")
                    for item in items[:10]:  # 只取前10個
                        try:
                            # 嘗試提取標題和連結
                            title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'a'])
                            if title_elem:
                                title = title_elem.get_text().strip()
                                link = title_elem.get('href') if title_elem.name == 'a' else item.find('a')
                                if link and hasattr(link, 'get'):
                                    link = link.get('href')
                                if link and not link.startswith('http'):
                                    link = f"https://www.binance.com{link}"
                                
                                # 簡單的ID生成
                                post_id = hash(title + str(link))
                                
                                announcements.append({
                                    'title': title,
                                    'link': link,
                                    'id': post_id,
                                    'published': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                })
                        except Exception as e:
                            logger.debug(f"解析公告項目時出錯: {e}")
                    break
            
            if not announcements:
                logger.warning("⚠️ 未能解析到任何公告")
                
            return announcements
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 網路請求錯誤: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 網頁解析錯誤: {e}")
            return []
    
    def is_listing_announcement(self, title):
        """判斷是否為重要的上幣公告"""
        listing_keywords = [
            'listing', 'new trading', 'adds', 'launches', 
            'will list', 'support', 'trading pairs',
            'opens trading', 'available for trading',
            '上線', '新增', '支持', '開放交易'
        ]
        
        important_keywords = [
            'futures', 'margin', 'spot trading',
            'airdrop', 'promotion', 'competition'
        ]
        
        title_lower = title.lower()
        
        is_listing = any(keyword.lower() in title_lower for keyword in listing_keywords)
        is_important = any(keyword.lower() in title_lower for keyword in important_keywords)
        
        return is_listing, is_important
    
    def format_message(self, announcement):
        """格式化Telegram訊息"""
        title = announcement['title']
        link = announcement['link']
        pub_date = announcement['published']
        
        is_listing, is_important = self.is_listing_announcement(title)
        
        if is_listing:
            emoji = "🚀"
            priority_text = "\n\n🔥 <b>新幣上線公告！立即查看！</b>"
        elif is_important:
            emoji = "⭐"
            priority_text = "\n\n💡 <b>重要公告</b>"
        else:
            emoji = "📢"
            priority_text = ""
        
        message = f"""
{emoji} <b>幣安新公告 (網頁監控)</b>

📋 <b>標題:</b> {title}

🔗 <a href="{link}">查看完整公告</a>

⏰ <b>發現時間:</b> {pub_date}{priority_text}
        """.strip()
        
        return message
    
    def check_new_posts(self):
        """檢查是否有新公告"""
        announcements = self.scrape_announcements()
        if not announcements:
            return []
        
        new_posts = []
        for announcement in announcements:
            post_id = str(announcement['id'])
            
            if post_id not in self.seen_posts:
                new_posts.append(announcement)
                self.seen_posts.add(post_id)
                logger.info(f"📢 發現新公告: {announcement['title'][:60]}...")
        
        return new_posts
    
    def run_once(self):
        """執行一次檢查"""
        logger.info(f"🔍 開始檢查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        new_posts = self.check_new_posts()
        
        if new_posts:
            logger.info(f"📢 發現 {len(new_posts)} 篇新公告")
            
            for post in new_posts:
                message = self.format_message(post)
                if self.send_telegram_message(message):
                    time.sleep(1)
                else:
                    logger.error(f"發送失敗: {post['title']}")
            
            self.save_seen_posts()
        else:
            logger.info("✅ 沒有新公告")
    
    def run_daemon(self):
        """持續監控模式"""
        logger.info(f"🤖 Bot開始運行 (網頁解析版)！")
        logger.info(f"⏰ 每 {self.check_interval} 秒檢查一次")
        logger.info("按 Ctrl+C 停止運行")
        
        start_msg = f"""
🤖 <b>幣安監控Bot已啟動 (網頁解析版)</b>

⏰ 檢查間隔: {self.check_interval}秒
🌐 監控方式: 網頁解析
🎯 專注: 新幣上線公告

準備開始監控...
        """.strip()
        
        self.send_telegram_message(start_msg)
        
        try:
            while True:
                self.run_once()
                logger.debug(f"💤 等待 {self.check_interval} 秒...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 收到停止信號")
            stop_msg = "🛑 <b>幣安監控Bot已停止運行</b>"
            self.send_telegram_message(stop_msg)
            logger.info("👋 Bot已安全停止")
            
        except Exception as e:
            logger.error(f"❌ 運行時發生錯誤: {e}")
            error_msg = f"❌ <b>Bot運行異常</b>\n\n錯誤: {str(e)}"
            self.send_telegram_message(error_msg)

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='幣安公告監控Bot (網頁解析版)')
    parser.add_argument('--test', action='store_true', 
                       help='測試模式：只執行一次檢查')
    parser.add_argument('--test-bot', action='store_true', 
                       help='測試Telegram連接')
    
    args = parser.parse_args()
    
    try:
        bot = BinanceWebScraperBot()
        
        if args.test_bot:
            if bot.test_telegram_connection():
                print("✅ 測試完成：Telegram連接正常")
            else:
                print("❌ 測試失敗：請檢查設定")
            return
        
        if args.test:
            print("🧪 執行測試模式...")
            bot.run_once()
            print("✅ 測試完成")
        else:
            bot.run_daemon()
            
    except KeyboardInterrupt:
        logger.info("👋 程式被使用者中斷")
    except Exception as e:
        logger.error(f"❌ 程式啟動失敗: {e}")
        print(f"❌ 錯誤: {e}")
        print("💡 請檢查設定")

if __name__ == "__main__":
    main()