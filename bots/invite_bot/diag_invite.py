import sys
import os
import json

# Add project root to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from shared_bot_utils import get_bot_config

def main():
    print("--- DIAGNOSTIC: INVITE BOT CONFIG ---")
    try:
        cfg = get_bot_config('invite')
        print(f"Is Enabled: {cfg.get('is_enabled')}")
        
        fields = cfg.get('form_fields', [])
        print(f"Total form fields: {len(fields)}")
        
        for i, field in enumerate(fields):
            print(f"\nField {i+1}:")
            for k, v in field.items():
                print(f"  {k}: {repr(v)}")
                
    except Exception as e:
        print(f"CRITICAL ERROR loading config: {e}")

if __name__ == '__main__':
    main()
