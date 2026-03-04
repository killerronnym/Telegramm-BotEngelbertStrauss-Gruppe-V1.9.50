import json, time

f = 'instance/live_config.json'
with open(f, 'r') as file:
    d = json.load(file)

d['trial_expiry'] = int(time.time()) - 3600 # 1 hour ago
key = d.get('activation_key', 'FEHLT_LEIDER')

with open(f, 'w') as file:
    json.dump(d, file)

print(f"Expired trial. Key is: {key}")
