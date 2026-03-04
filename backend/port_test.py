#!/usr/bin/env python3
"""
Cloud Run PORT環境変数テスト

このスクリプトは、Cloud RunがPORT環境変数を正しく設定しているかテストします。
"""

import os
import sys

def test_port_env():
    """PORT環境変数のテスト"""
    print("=== Cloud Run PORT Environment Variable Test ===")
    
    port = os.getenv('PORT')
    
    if port:
        try:
            port_int = int(port)
            if 1 <= port_int <= 65535:
                print(f"✅ Valid PORT detected: {port}")
                return port_int
            else:
                print(f"❌ Invalid PORT range: {port} (should be 1-65535)")
                return None
        except ValueError:
            print(f"❌ Invalid PORT format: {port} (should be integer)")
            return None
    else:
        print("❌ No PORT environment variable found")
        print("This is expected in local development, but required in Cloud Run")
        return 8080  # フォールバック

def main():
    """メインテスト実行"""
    port = test_port_env()
    
    if port:
        print(f"\n🚀 Server would start on port: {port}")
        print(f"🌐 Full address: http://0.0.0.0:{port}")
        
        # 環境判定
        env = os.getenv('ENVIRONMENT', 'development')
        print(f"📋 Environment: {env}")
        
        if env == 'production' and os.getenv('PORT'):
            print("✅ Production environment with Cloud Run PORT detected")
        elif env == 'development':
            print("⚠️ Development environment (local)")
        else:
            print("⚠️ Unknown environment configuration")
            
    else:
        print("❌ Cannot determine valid port")
        sys.exit(1)

if __name__ == "__main__":
    main()