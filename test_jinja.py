from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('web_dashboard/app/templates'))
try:
    template = env.get_template('birthday.html')
    print("Template parsed successfully!")
except Exception as e:
    print(f"Jinja Error: {e}")
