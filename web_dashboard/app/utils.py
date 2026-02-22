from datetime import datetime

def datetimeformat(value, format='%H:%M:%S | %d.%m.%Y'):
    if isinstance(value, (int, float)):
        value = datetime.fromtimestamp(value)
    return value.strftime(format)
