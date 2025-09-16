import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

class Config:
    """設定類別"""
    
    # Telegram設定
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # RSS設定
    RSS_URL = os.getenv('RSS_URL', 'https://www.binance.com/en/support/announcement/c-48?navId=48')
    
    # 檢查間隔（秒）
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 30))
    
    @classmethod
    def validate(cls):
        """驗證必要的環境變數是否已設定"""
        missing = []
        
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append('TELEGRAM_BOT_TOKEN')
        if not cls.TELEGRAM_CHAT_ID:
            missing.append('TELEGRAM_CHAT_ID')
            
        if missing:
            raise ValueError(f"缺少必要的環境變數: {', '.join(missing)}")
        
        return True