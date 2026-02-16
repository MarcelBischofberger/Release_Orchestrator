from app import app

with open('routes_dump.txt', 'w') as f:
    f.write("Listing Routes:\n")
    for rule in app.url_map.iter_rules():
        f.write(f"{rule} -> {rule.endpoint}\n")
