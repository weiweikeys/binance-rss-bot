#!/usr/bin/env python3
"""
幣安繁中公告監控Bot
專門監控 https://www.binance.com/zh-TC/support/announcement/list/48
檢測包含特定關鍵字的新公告並發送Telegram通知
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

class BinanceZhTcMonitor:
    """幣安繁中公告監控Bot"""
    
    def __init__(self):
        """初始化Bot"""
        try:
            Config.validate()
            self.telegram_token = Config.TELEGRAM_BOT_TOKEN
            self.chat_id = Config.TELEGRAM_CHAT_ID
            self.check_interval = Config.CHECK_INTERVAL
            
            # 目標網址
            self.target_url = 'https://www.binance.com/zh-TC/support/announcement/list/48'
            
            # 監控關鍵字
            self.keywords = [
                '上線', '新上線', '即將上線', '開始交易', 
                '新增', '支持', '開放', '推出', '啟動',
                'listing', 'new trading', 'support', 'launch'
            ]
            
            # 儲存已處理的公告
            self.seen_posts_file = "seen_announcements.json"
            self.seen_posts = self.load_seen_posts()
            
            # 請求標頭
            self.headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            logger.info("🤖 幣安繁中公告監控Bot初始化完成")
            logger.info(f"🎯 目標網址: {self.target_url}")
            logger.info(f"🔍 監控關鍵字: {', '.join(self.keywords)}")
            logger.info(f"⏰ 檢查間隔: {self.check_interval}秒")
            
        except Exception as e:
            logger.error(f"❌ Bot初始化失敗: {e}")
            raise
    
    def load_seen_posts(self):
        """載入已處理的公告記錄"""
        try:
            if os.path.exists(self.seen_posts_file):
                with open(self.seen_posts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"📚 載入了 {len(data)} 個已處理的公告記錄")
                    return set(data)
            return set()
        except Exception as e:
            logger.error(f"❌ 載入歷史記錄失敗: {e}")
            return set()
    
    def save_seen_posts(self):
        """儲存已處理的公告記錄"""
        try:
            with open(self.seen_posts_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.seen_posts), f, ensure_ascii=False, indent=2)
            logger.debug(f"💾 已儲存 {len(self.seen_posts)} 個公告記錄")
        except Exception as e:
            logger.error(f"❌ 儲存歷史記錄失敗: {e}")
    
    def send_telegram_message(self, message):
        """發送Telegram通知"""
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
                logger.info("✅ Telegram通知發送成功")
                return True
            else:
                logger.error(f"❌ Telegram發送失敗: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Telegram發送錯誤: {e}")
            return False
    
    def contains_target_keywords(self, text):
        """檢查文字是否包含目標關鍵字"""
        if not text:
            return False, []
        
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        return len(found_keywords) > 0, found_keywords
    
    def fetch_announcements(self):
        """抓取幣安公告頁面"""
        try:
            logger.debug(f"🌐 開始抓取: {self.target_url}")
            
            # 發送請求
            response = requests.get(
                self.target_url,
                headers=self.headers,
                timeout=25,
                allow_redirects=True
            )
            response.raise_for_status()
            
            logger.debug(f"📡 HTTP狀態碼: {response.status_code}")
            logger.debug(f"📄 內容長度: {len(response.content)} bytes")
            
            # 解析HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            logger.debug(f"📋 解析完成，頁面標題: {soup.title.string if soup.title else '無標題'}")
            
            # 尋找公告元素 - 多種策略
            announcements = []
            
            # 策略1: 尋找包含announcement的鏈接
            announcement_links = soup.find_all('a', href=lambda x: x and 'announcement' in x)
            logger.debug(f"🔗 策略1找到 {len(announcement_links)} 個announcement鏈接")
            
            for link in announcement_links[:20]:  # 限制處理數量
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                if title and len(title) > 5:
                    announcements.append({
                        'title': title,
                        'link': href,
                        'source': 'announcement_link'
                    })
            
            # 策略2: 尋找標題元素
            title_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
            logger.debug(f"📰 策略2找到 {len(title_elements)} 個標題元素")
            
            for elem in title_elements:
                title = elem.get_text(strip=True)
                parent_link = elem.find_parent('a') or elem.find('a')
                href = parent_link.get('href', '') if parent_link else ''
                
                if title and len(title) > 5:
                    announcements.append({
                        'title': title,
                        'link': href,
                        'source': 'title_element'
                    })
            
            # 策略3: 尋找包含特定class的div
            content_divs = soup.find_all('div', class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['title', 'content', 'announcement', 'news']
            ))
            logger.debug(f"📦 策略3找到 {len(content_divs)} 個內容div")
            
            for div in content_divs[:15]:
                title = div.get_text(strip=True)
                link_elem = div.find('a')
                href = link_elem.get('href', '') if link_elem else ''
                
                if title and len(title) > 10:
                    announcements.append({
                        'title': title,
                        'link': href,
                        'source': 'content_div'
                    })
            
            # 策略4: 尋找所有包含關鍵字的文字
            all_text_elements = soup.find_all(text=True)
            keyword_matches = []
            
            for text in all_text_elements:
                text_clean = text.strip()
                if len(text_clean) > 10:
                    has_keyword, found_kw = self.contains_target_keywords(text_clean)
                    if has_keyword:
                        parent = text.parent
                        parent_link = parent.find_parent('a') if parent else None
                        href = parent_link.get('href', '') if parent_link else ''
                        
                        keyword_matches.append({
                            'title': text_clean,
                            'link': href,
                            'source': 'keyword_match',
                            'keywords': found_kw
                        })
            
            logger.debug(f"🎯 策略4找到 {len(keyword_matches)} 個關鍵字匹配")
            
            # 合併所有結果
            all_announcements = announcements + keyword_matches
            logger.info(f"📊 總共找到 {len(all_announcements)} 個可能的公告")
            
            return all_announcements
            
        except requests.RequestException as e:
            logger.error(f"❌ 網路請求失敗: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 抓取公告時發生錯誤: {e}")
            return []
    
    def process_announcements(self, announcements):
        """處理公告，篩選出包含關鍵字的新內容"""
        new_alerts = []
        
        for announcement in announcements:
            title = announcement.get('title', '').strip()
            link = announcement.get('link', '')
            source = announcement.get('source', '')
            
            if not title or len(title) < 5:
                continue
            
            # 檢查是否包含關鍵字
            has_keyword, found_keywords = self.contains_target_keywords(title)
            
            if has_keyword:
                # 生成唯一ID
                announcement_id = f"zh_tc_{hash(title)}"
                
                # 檢查是否為新公告
                if announcement_id not in self.seen_posts:
                    # 修正鏈接
                    if link and not link.startswith('http'):
                        if link.startswith('/'):
                            link = f"https://www.binance.com{link}"
                        else:
                            link = f"https://www.binance.com/{link}"
                    
                    new_alerts.append({
                        'id': announcement_id,
                        'title': title,
                        'link': link,
                        'keywords': found_keywords,
                        'source': source,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
                    # 標記為已處理
                    self.seen_posts.add(announcement_id)
                    logger.info(f"🆕 發現新的關鍵字匹配: {title[:60]}...")
        
        return new_alerts
    
    def format_alert_message(self, alert):
        """格式化警報訊息"""
        title = alert['title']
        link = alert.get('link', '')
        keywords = alert['keywords']
        timestamp = alert['timestamp']
        
        message = f"""
🚨 <b>幣安新公告警報！</b>

📋 <b>標題:</b> {title}

🎯 <b>匹配關鍵字:</b> {', '.join(keywords)}

{f'🔗 <b>連結:</b> {link}' if link else ''}

⏰ <b>發現時間:</b> {timestamp}
📍 <b>來源:</b> 幣安繁中公告頁面
        """.strip()
        
        return message
    
    def run_once(self):
        """執行一次檢查"""
        logger.info(f"🔍 開始檢查幣安公告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 抓取公告
        announcements = self.fetch_announcements()
        
        if not announcements:
            logger.warning("⚠️ 未能獲取到任何公告內容")
            return
        
        # 處理公告
        new_alerts = self.process_announcements(announcements)
        
        if new_alerts:
            logger.info(f"🎯 發現 {len(new_alerts)} 個新的關鍵字匹配公告")
            
            # 發送通知
            for alert in new_alerts:
                message = self.format_alert_message(alert)
                if self.send_telegram_message(message):
                    time.sleep(2)  # 避免頻率限制
                else:
                    logger.error(f"發送通知失敗: {alert['title'][:30]}...")
            
            # 儲存記錄
            self.save_seen_posts()
            
        else:
            logger.info("✅ 沒有發現包含關鍵字的新公告")
    
    def test_telegram_connection(self):
        """測試Telegram連接"""
        test_message = f"""
🧪 <b>幣安繁中公告監控Bot測試</b>

✅ Bot運行正常
📅 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🎯 監控網址: {self.target_url}
🔍 監控關鍵字: {', '.join(self.keywords[:5])}等

🚀 準備開始監控幣安繁中公告！
        """.strip()
        
        logger.info("🔍 測試Telegram連接...")
        success = self.send_telegram_message(test_message)
        
        if success:
            logger.info("✅ Telegram連接測試成功")
        else:
            logger.error("❌ Telegram連接測試失敗")
        
        return success
    
    def run_daemon(self):
        """持續監控模式"""
        logger.info("🤖 幣安繁中公告監控Bot開始運行！")
        
        # 發送啟動通知
        start_message = f"""
🤖 <b>幣安繁中公告監控Bot已啟動</b>

⏰ 檢查間隔: {self.check_interval}秒
🎯 監控網址: zh-TC公告頁面
🔍 關鍵字: {', '.join(self.keywords)}

📱 一旦發現包含關鍵字的新公告將立即通知您！

開始監控中...
        """.strip()
        
        self.send_telegram_message(start_message)
        
        try:
            while True:
                self.run_once()
                logger.debug(f"💤 等待 {self.check_interval} 秒後繼續...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 收到停止信號")
            stop_message = "🛑 <b>幣安繁中公告監控Bot已停止運行</b>"
            self.send_telegram_message(stop_message)
            logger.info("👋 Bot已安全停止")
            
        except Exception as e:
            logger.error(f"❌ 運行時發生錯誤: {e}")
            error_message = f"❌ <b>監控Bot運行異常</b>\n\n錯誤: {str(e)}"
            self.send_telegram_message(error_message)

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='幣安繁中公告監控Bot')
    parser.add_argument('--test', action='store_true', 
                       help='測試模式：只執行一次檢查')
    parser.add_argument('--test-bot', action='store_true', 
                       help='測試Telegram連接')
    
    args = parser.parse_args()
    
    try:
        bot = BinanceZhTcMonitor()
        
        if args.test_bot:
            success = bot.test_telegram_connection()
            print("✅ 測試成功" if success else "❌ 測試失敗")
            return
        
        if args.test:
            print("🧪 執行測試模式...")
            bot.run_once()
            print("✅ 測試完成")
        else:
            bot.run_daemon()
            
    except KeyboardInterrupt:
        logger.info("👋 程式被用戶中斷")
    except Exception as e:
        logger.error(f"❌ 程式啟動失敗: {e}")
        print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    main()