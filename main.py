#!/usr/bin/env python3
"""
幣安繁中公告監控Bot - 加強debug版
專門監控幣安公告並輸出詳細debug資訊
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
import re

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

class EnhancedBinanceMonitor:
    """加強版幣安監控Bot"""
    
    def __init__(self):
        """初始化Bot"""
        try:
            Config.validate()
            self.telegram_token = Config.TELEGRAM_BOT_TOKEN
            self.chat_id = Config.TELEGRAM_CHAT_ID
            self.check_interval = Config.CHECK_INTERVAL
            
            # 多個可能的網址
            self.target_urls = [
                'https://www.binance.com/zh-TC/support/announcement/list/48',
                'https://www.binance.com/zh-TC/support/announcement',
                'https://www.binance.com/zh-TC/support/announcement/new-listing'
            ]
            
            # 關鍵字
            self.keywords = [
                '上線', '新上線', '即將上線', '開始交易', 
                '新增', '支持', '開放', '推出', '啟動',
                'listing', 'new trading', 'support', 'launch'
            ]
            
            self.seen_posts_file = "seen_announcements.json"
            self.seen_posts = self.load_seen_posts()
            
            # 更強的請求標頭
            self.headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6',
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
            
            logger.info("🤖 加強版幣安監控Bot初始化完成")
            logger.info(f"🎯 目標網址: {len(self.target_urls)} 個")
            logger.info(f"🔍 監控關鍵字: {', '.join(self.keywords)}")
            
        except Exception as e:
            logger.error(f"❌ Bot初始化失敗: {e}")
            raise
    
    def load_seen_posts(self):
        """載入已處理的公告記錄"""
        try:
            if os.path.exists(self.seen_posts_file):
                with open(self.seen_posts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
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
    
    def save_html_debug(self, content, url_index):
        """儲存HTML內容用於debug"""
        try:
            filename = f"debug_page_{url_index}_{datetime.now().strftime('%H%M%S')}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"📄 已儲存debug HTML: {filename}")
        except Exception as e:
            logger.error(f"❌ 儲存HTML debug失敗: {e}")
    
    def extract_all_text_content(self, soup):
        """提取所有可能的文字內容用於debug"""
        all_texts = []
        
        # 提取所有文字內容
        for text in soup.stripped_strings:
            if len(text) > 3:  # 過濾太短的文字
                all_texts.append(text)
        
        return all_texts
    
    def fetch_and_analyze_url(self, url, url_index):
        """抓取並分析單個URL"""
        try:
            logger.info(f"🌐 正在抓取URL {url_index + 1}: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=25, allow_redirects=True)
            response.raise_for_status()
            
            logger.info(f"📡 HTTP狀態碼: {response.status_code}")
            logger.info(f"📄 回應大小: {len(response.content)} bytes")
            logger.info(f"📋 Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            # 檢查是否被重定向
            if response.url != url:
                logger.info(f"🔄 頁面重定向到: {response.url}")
            
            # 解析HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            page_title = soup.title.string if soup.title else '無標題'
            logger.info(f"📋 頁面標題: {page_title}")
            
            # 儲存HTML用於debug (只在測試模式)
            if url_index == 0:  # 只儲存第一個URL
                self.save_html_debug(response.text, url_index)
            
            # 提取所有文字內容
            all_texts = self.extract_all_text_content(soup)
            logger.info(f"📝 提取到 {len(all_texts)} 段文字內容")
            
            # 顯示前10個文字片段用於debug
            logger.info("📖 前10個文字片段:")
            for i, text in enumerate(all_texts[:10]):
                logger.info(f"   {i+1}. {text[:80]}{'...' if len(text) > 80 else ''}")
            
            # 尋找包含關鍵字的內容
            keyword_matches = []
            for text in all_texts:
                has_keyword, found_keywords = self.contains_target_keywords(text)
                if has_keyword:
                    keyword_matches.append({
                        'text': text,
                        'keywords': found_keywords
                    })
                    logger.info(f"🎯 找到關鍵字匹配: {text[:100]}...")
                    logger.info(f"   匹配關鍵字: {', '.join(found_keywords)}")
            
            # 特別尋找鏈接和標題
            links = soup.find_all('a', href=True)
            titles = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            
            logger.info(f"🔗 找到 {len(links)} 個鏈接")
            logger.info(f"📰 找到 {len(titles)} 個標題元素")
            
            # 檢查標題中的關鍵字
            for title in titles:
                title_text = title.get_text(strip=True)
                if title_text:
                    has_keyword, found_keywords = self.contains_target_keywords(title_text)
                    if has_keyword:
                        logger.info(f"🎯 標題包含關鍵字: {title_text}")
                        keyword_matches.append({
                            'text': title_text,
                            'keywords': found_keywords,
                            'type': 'title'
                        })
            
            return keyword_matches
            
        except requests.RequestException as e:
            logger.error(f"❌ 網路請求失敗 (URL {url_index + 1}): {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 分析URL時發生錯誤 (URL {url_index + 1}): {e}")
            return []
    
    def run_once(self):
        """執行一次檢查"""
        logger.info(f"🔍 開始檢查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        all_matches = []
        
        # 檢查每個URL
        for i, url in enumerate(self.target_urls):
            matches = self.fetch_and_analyze_url(url, i)
            all_matches.extend(matches)
            
            # 如果找到匹配就停止檢查其他URL
            if matches:
                logger.info(f"✅ 在URL {i + 1}找到匹配，停止檢查其他URL")
                break
            
            # 避免太快的請求
            if i < len(self.target_urls) - 1:
                time.sleep(2)
        
        # 處理找到的匹配
        new_alerts = []
        for match in all_matches:
            text = match['text']
            keywords = match['keywords']
            
            # 生成唯一ID
            match_id = f"enhanced_{hash(text)}"
            
            if match_id not in self.seen_posts:
                new_alerts.append({
                    'id': match_id,
                    'text': text,
                    'keywords': keywords,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                self.seen_posts.add(match_id)
        
        if new_alerts:
            logger.info(f"🎯 發現 {len(new_alerts)} 個新的關鍵字匹配")
            
            for alert in new_alerts:
                message = f"""
🚨 <b>幣安關鍵字警報！</b>

📋 <b>內容:</b> {alert['text'][:200]}{'...' if len(alert['text']) > 200 else ''}

🎯 <b>匹配關鍵字:</b> {', '.join(alert['keywords'])}

⏰ <b>發現時間:</b> {alert['timestamp']}
                """.strip()
                
                if self.send_telegram_message(message):
                    time.sleep(2)
                else:
                    logger.error(f"發送通知失敗: {alert['text'][:50]}...")
            
            self.save_seen_posts()
        else:
            logger.info("✅ 沒有發現新的關鍵字匹配內容")
    
    def test_telegram_connection(self):
        """測試Telegram連接"""
        test_message = f"""
🧪 <b>加強版幣安監控Bot測試</b>

✅ Bot運行正常
📅 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🎯 監控 {len(self.target_urls)} 個網址
🔍 關鍵字: {', '.join(self.keywords[:5])}等

🚀 準備開始詳細監控！
        """.strip()
        
        logger.info("🔍 測試Telegram連接...")
        return self.send_telegram_message(test_message)
    
    def run_daemon(self):
        """持續監控模式"""
        logger.info("🤖 加強版幣安監控Bot開始運行！")
        
        start_message = f"""
🤖 <b>加強版監控Bot已啟動</b>

⏰ 檢查間隔: {self.check_interval}秒
🎯 監控多個幣安公告網址
🔍 關鍵字: {', '.join(self.keywords)}
📄 詳細debug模式已開啟

開始監控...
        """.strip()
        
        self.send_telegram_message(start_message)
        
        try:
            while True:
                self.run_once()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("🛑 Bot已停止")
            self.send_telegram_message("🛑 <b>加強版監控Bot已停止</b>")

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='加強版幣安監控Bot')
    parser.add_argument('--test', action='store_true', help='測試模式')
    parser.add_argument('--test-bot', action='store_true', help='測試連接')
    
    args = parser.parse_args()
    
    try:
        bot = EnhancedBinanceMonitor()
        
        if args.test_bot:
            success = bot.test_telegram_connection()
            print("✅ 測試成功" if success else "❌ 測試失敗")
        elif args.test:
            bot.run_once()
        else:
            bot.run_daemon()
            
    except Exception as e:
        logger.error(f"❌ 程式錯誤: {e}")

if __name__ == "__main__":
    main()