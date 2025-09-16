#!/usr/bin/env python3
"""
幣安中文內容監控Bot
監控多個來源，尋找"上線"相關內容
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

class BinanceChineseMonitor:
    """幣安中文內容監控Bot"""
    
    def __init__(self):
        """初始化Bot"""
        try:
            Config.validate()
            self.telegram_token = Config.TELEGRAM_BOT_TOKEN
            self.chat_id = Config.TELEGRAM_CHAT_ID
            self.check_interval = Config.CHECK_INTERVAL
            
            # 監控來源 - 使用可以訪問的中文來源
            self.sources = [
                {
                    'name': '幣安中文公告',
                    'url': 'https://www.binance.com/zh-CN/support/announcement',
                    'type': 'web',
                    'enabled': True
                },
                {
                    'name': '幣安微博',
                    'url': 'https://weibo.com/binance',
                    'type': 'web', 
                    'enabled': False  # 微博也有限制，先禁用
                },
                {
                    'name': 'CoinGecko中文',
                    'url': 'https://www.coingecko.com/zh/new-cryptocurrencies',
                    'type': 'web',
                    'enabled': True
                }
            ]
            
            # 關鍵字設定
            self.keywords = [
                '上線', '新上線', '即將上線', '開始交易',
                '新增', '支持', '開放', '推出',
                'listing', 'new trading', 'support'
            ]
            
            self.seen_posts_file = "seen_posts.json"
            self.seen_posts = self.load_seen_posts()
            
            logger.info("🤖 Bot初始化完成 (中文內容監控版)")
            logger.info(f"🔍 關鍵字: {', '.join(self.keywords)}")
            logger.info(f"⏰ 檢查間隔: {self.check_interval}秒")
            
        except Exception as e:
            logger.error(f"❌ Bot初始化失敗: {e}")
            raise
    
    def load_seen_posts(self):
        """載入已處理的內容"""
        try:
            if os.path.exists(self.seen_posts_file):
                with open(self.seen_posts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"📚 載入了 {len(data)} 個已處理的記錄")
                    return set(data)
            return set()
        except Exception as e:
            logger.error(f"❌ 載入歷史記錄失敗: {e}")
            return set()
    
    def save_seen_posts(self):
        """儲存已處理的內容"""
        try:
            with open(self.seen_posts_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.seen_posts), f, ensure_ascii=False, indent=2)
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
                logger.error(f"❌ 發送失敗: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ 發送錯誤: {e}")
            return False
    
    def contains_keywords(self, text):
        """檢查是否包含關鍵字"""
        if not text:
            return False, []
        
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        return len(found_keywords) > 0, found_keywords
    
    def scrape_binance_chinese(self):
        """抓取幣安中文公告"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            response = requests.get(
                'https://www.binance.com/zh-CN/support/announcement', 
                headers=headers, 
                timeout=15,
                allow_redirects=True
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 查找公告標題
            announcements = []
            
            # 多種可能的選擇器
            selectors = [
                'a[href*="announcement"]',
                '.announcement-title',
                '[class*="title"]',
                'h1, h2, h3, h4',
                'a[href*="support"]'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"使用選擇器找到 {len(elements)} 個元素: {selector}")
                    for elem in elements[:10]:  # 只檢查前10個
                        text = elem.get_text().strip()
                        link = elem.get('href', '')
                        
                        if text and len(text) > 5:  # 過濾太短的文字
                            has_keyword, found_keywords = self.contains_keywords(text)
                            if has_keyword:
                                announcements.append({
                                    'title': text,
                                    'link': link,
                                    'keywords': found_keywords,
                                    'source': '幣安中文公告'
                                })
                    break
            
            return announcements
            
        except Exception as e:
            logger.error(f"❌ 抓取幣安中文公告失敗: {e}")
            return []
    
    def scrape_coingecko_chinese(self):
        """抓取CoinGecko新幣"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(
                'https://www.coingecko.com/zh/new-cryptocurrencies',
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            new_coins = []
            
            # 查找新幣資訊
            coin_elements = soup.select('.coin-name, .tw-text-gray-700, [class*="coin"]')[:5]
            
            for elem in coin_elements:
                text = elem.get_text().strip()
                if text and len(text) > 2:
                    # 檢查是否可能與幣安相關
                    if any(word in text.lower() for word in ['binance', 'bnb', '幣安']):
                        new_coins.append({
                            'title': f"新幣種發現: {text}",
                            'link': 'https://www.coingecko.com/zh/new-cryptocurrencies',
                            'keywords': ['新上線'],
                            'source': 'CoinGecko'
                        })
            
            return new_coins
            
        except Exception as e:
            logger.error(f"❌ 抓取CoinGecko失敗: {e}")
            return []
    
    def format_alert_message(self, item):
        """格式化警報訊息"""
        title = item['title']
        link = item.get('link', '')
        keywords = item.get('keywords', [])
        source = item.get('source', '未知')
        
        # 添加完整URL
        if link and not link.startswith('http'):
            if 'binance' in source.lower():
                link = f"https://www.binance.com{link}"
        
        message = f"""
🚨 <b>發現上線相關內容！</b>

📋 <b>標題:</b> {title}

🔍 <b>關鍵字:</b> {', '.join(keywords)}
📍 <b>來源:</b> {source}

{f'🔗 <b>連結:</b> {link}' if link else ''}

⏰ <b>發現時間:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        return message
    
    def check_all_sources(self):
        """檢查所有來源"""
        all_findings = []
        
        # 檢查幣安中文公告
        try:
            binance_items = self.scrape_binance_chinese()
            for item in binance_items:
                # 生成唯一ID
                item_id = f"binance_{hash(item['title'])}"
                if item_id not in self.seen_posts:
                    all_findings.append(item)
                    self.seen_posts.add(item_id)
                    logger.info(f"🎯 發現新內容: {item['title'][:50]}...")
        except Exception as e:
            logger.error(f"檢查幣安公告時出錯: {e}")
        
        # 檢查CoinGecko
        try:
            gecko_items = self.scrape_coingecko_chinese()
            for item in gecko_items:
                item_id = f"gecko_{hash(item['title'])}"
                if item_id not in self.seen_posts:
                    all_findings.append(item)
                    self.seen_posts.add(item_id)
                    logger.info(f"🎯 發現新幣種: {item['title'][:50]}...")
        except Exception as e:
            logger.error(f"檢查CoinGecko時出錯: {e}")
        
        return all_findings
    
    def run_once(self):
        """執行一次檢查"""
        logger.info(f"🔍 開始檢查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        findings = self.check_all_sources()
        
        if findings:
            logger.info(f"🎯 發現 {len(findings)} 個相關內容")
            
            for item in findings:
                message = self.format_alert_message(item)
                if self.send_telegram_message(message):
                    time.sleep(2)  # 避免頻率限制
                else:
                    logger.error(f"發送失敗: {item['title']}")
            
            self.save_seen_posts()
        else:
            logger.info("✅ 沒有發現相關的上線內容")
    
    def test_telegram_connection(self):
        """測試Telegram連接"""
        test_message = f"""
🧪 <b>Telegram連接測試 (中文內容監控)</b>

✅ Bot運行正常
📅 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔍 監控關鍵字: {', '.join(self.keywords[:5])}...
📍 監控來源: 幣安中文公告、CoinGecko等

🤖 準備開始監控"上線"相關內容！
        """.strip()
        
        logger.info("🔍 測試Telegram連接...")
        return self.send_telegram_message(test_message)
    
    def run_daemon(self):
        """持續監控模式"""
        logger.info("🤖 Bot開始運行 (中文內容監控版)！")
        
        start_msg = f"""
🤖 <b>中文內容監控Bot已啟動</b>

⏰ 檢查間隔: {self.check_interval}秒
🔍 監控關鍵字: {', '.join(self.keywords[:5])}等
📍 監控來源: 多個中文平台

🎯 專門監控"上線"相關內容
開始監控...
        """.strip()
        
        self.send_telegram_message(start_msg)
        
        try:
            while True:
                self.run_once()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("🛑 Bot已停止")
            self.send_telegram_message("🛑 <b>中文內容監控Bot已停止</b>")

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='幣安中文內容監控Bot')
    parser.add_argument('--test', action='store_true', help='測試模式')
    parser.add_argument('--test-bot', action='store_true', help='測試連接')
    
    args = parser.parse_args()
    
    try:
        bot = BinanceChineseMonitor()
        
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