#!/usr/bin/env python3
"""
幣安RSS監控Telegram Bot
即時監控幣安公告並推送到Telegram

使用方法:
python main.py              # 持續監控
python main.py --test       # 測試一次
python main.py --test-bot   # 測試Telegram連接
"""

import requests
import feedparser
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

class BinanceRSSBot:
    """幣安RSS監控Bot"""
    
    def __init__(self):
        """初始化Bot"""
        try:
            Config.validate()
            self.telegram_token = Config.TELEGRAM_BOT_TOKEN
            self.chat_id = Config.TELEGRAM_CHAT_ID
            self.rss_url = Config.RSS_URL
            self.check_interval = Config.CHECK_INTERVAL
            self.seen_posts_file = "seen_posts.json"
            self.seen_posts = self.load_seen_posts()
            
            logger.info("🤖 Bot初始化完成")
            logger.info(f"📡 RSS URL: {self.rss_url}")
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
🧪 <b>Telegram連接測試</b>

✅ Bot運行正常
📅 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 準備開始監控幣安公告！
        """.strip()
        
        logger.info("🔍 測試Telegram連接...")
        success = self.send_telegram_message(test_message)
        
        if success:
            logger.info("✅ Telegram連接測試成功！")
        else:
            logger.error("❌ Telegram連接測試失敗！請檢查Token和Chat ID")
        
        return success
    
    def fetch_rss_feed(self):
        """獲取RSS feed內容"""
        try:
            logger.debug(f"📡 正在獲取RSS: {self.rss_url}")
            feed = feedparser.parse(self.rss_url)
            
            if not feed.entries:
                logger.warning("⚠️ RSS feed為空或無法解析")
                return []
            
            logger.debug(f"📄 獲取到 {len(feed.entries)} 篇文章")
            return feed.entries
            
        except Exception as e:
            logger.error(f"❌ RSS獲取失敗: {e}")
            return []
    
    def is_listing_announcement(self, title):
        """判斷是否為重要的上幣公告"""
        # 新幣上線關鍵字
        listing_keywords = [
            'listing', 'new trading', 'adds', 'launches', 
            'will list', 'support', 'trading pairs',
            'opens trading', 'available for trading',
            '上線', '新增', '支持', '開放交易'
        ]
        
        # 重要公告關鍵字
        important_keywords = [
            'futures', 'margin', 'spot trading',
            'airdrop', 'promotion', 'competition'
        ]
        
        title_lower = title.lower()
        
        is_listing = any(keyword.lower() in title_lower for keyword in listing_keywords)
        is_important = any(keyword.lower() in title_lower for keyword in important_keywords)
        
        return is_listing, is_important
    
    def format_message(self, entry):
        """格式化Telegram訊息"""
        title = entry.title
        link = entry.link
        pub_date = getattr(entry, 'published', '未知時間')
        
        is_listing, is_important = self.is_listing_announcement(title)
        
        # 選擇表情符號
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
{emoji} <b>幣安新公告</b>

📋 <b>標題:</b> {title}

🔗 <a href="{link}">查看完整公告</a>

⏰ <b>發布時間:</b> {pub_date}{priority_text}
        """.strip()
        
        return message
    
    def check_new_posts(self):
        """檢查是否有新文章"""
        entries = self.fetch_rss_feed()
        if not entries:
            return []
        
        new_posts = []
        for entry in entries:
            # 使用link作為唯一ID
            post_id = entry.link
            
            if post_id not in self.seen_posts:
                new_posts.append(entry)
                self.seen_posts.add(post_id)
                logger.info(f"📢 發現新文章: {entry.title[:60]}...")
        
        return new_posts
    
    def run_once(self):
        """執行一次檢查"""
        logger.info(f"🔍 開始檢查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        new_posts = self.check_new_posts()
        
        if new_posts:
            logger.info(f"📢 發現 {len(new_posts)} 篇新公告")
            
            # 按發布時間排序（最舊的先發）
            for post in reversed(new_posts):
                message = self.format_message(post)
                if self.send_telegram_message(message):
                    time.sleep(1)  # 避免頻率限制
                else:
                    logger.error(f"發送失敗: {post.title}")
            
            self.save_seen_posts()
        else:
            logger.info("✅ 沒有新公告")
    
    def run_daemon(self):
        """持續監控模式"""
        logger.info(f"🤖 Bot開始運行！")
        logger.info(f"⏰ 每 {self.check_interval} 秒檢查一次")
        logger.info("按 Ctrl+C 停止運行")
        
        # 發送啟動通知
        start_msg = f"""
🤖 <b>幣安監控Bot已啟動</b>

⏰ 檢查間隔: {self.check_interval}秒
📡 監控來源: 幣安官方公告
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
    parser = argparse.ArgumentParser(description='幣安RSS監控Telegram Bot')
    parser.add_argument('--test', action='store_true', 
                       help='測試模式：只執行一次檢查')
    parser.add_argument('--test-bot', action='store_true', 
                       help='測試Telegram連接')
    
    args = parser.parse_args()
    
    try:
        bot = BinanceRSSBot()
        
        if args.test_bot:
            # 測試Telegram連接
            if bot.test_telegram_connection():
                print("✅ 測試完成：Telegram連接正常")
            else:
                print("❌ 測試失敗：請檢查設定")
            return
        
        if args.test:
            # 測試模式
            print("🧪 執行測試模式...")
            bot.run_once()
            print("✅ 測試完成")
        else:
            # 正常運行模式
            bot.run_daemon()
            
    except KeyboardInterrupt:
        logger.info("👋 程式被使用者中斷")
    except Exception as e:
        logger.error(f"❌ 程式啟動失敗: {e}")
        print(f"❌ 錯誤: {e}")
        print("💡 請檢查 .env 檔案是否正確設定")

if __name__ == "__main__":
    main()