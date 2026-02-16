import requests
import sys
import time
import re

# Redirect stdout/stderr to file
sys.stdout = open('verify_bulk_move.log', 'w', encoding='utf-8')
sys.stderr = sys.stdout

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def login(user_id):
    response = SESSION.post(f"{BASE_URL}/login", data={'user_id': user_id})
    return response

def print_alerts(html):
    alerts = re.findall(r'class="alert alert-.*?">\s*(.*?)\s*<button', html, re.DOTALL)
    for a in alerts:
        print(f"ALERT: {a.strip()}")

def verify_bulk_move():
    print("Verifying Bulk Move & Index Badges...")
    
    # 1. Setup
    login(1) # Admin
    t1_name = f"MoveT1_{int(time.time())}"
    t2_name = f"MoveT2_{int(time.time())}"
    SESSION.post(f"{BASE_URL}/targets", data={'name': t1_name, 'url': 'http://t1', 'status': 'available'})
    SESSION.post(f"{BASE_URL}/targets", data={'name': t2_name, 'url': 'http://t2', 'status': 'available'})
    
    # Get IDs
    r = SESSION.get(f"{BASE_URL}/targets")
    # map name -> id
    # Find row with name, then find Delete form within that row?
    # Logic: <td>Name</td> ... action="/target/ID/delete"
    # Note: re.DOTALL makes .* match newlines.
    
    def get_id_for_target(name, html):
        # Find the specific row for this target
        # <td>NAME</td>
        # Then look ahead for the delete form
        pattern = f'<td>{name}</td>.*?action="/target/(\d+)/delete"'
        m = re.search(pattern, html, re.DOTALL)
        if m: return m.group(1)
        return None

    t1_id = get_id_for_target(t1_name, r.text)
    t2_id = get_id_for_target(t2_name, r.text)
    
    if not t1_id or not t2_id:
        print("FAILED: Could not find target IDs")
        sys.exit(1)
    
    # Create Release
    rel_name = f"MoveRel_{int(time.time())}"
    r = SESSION.post(f"{BASE_URL}/release/new", data={'name': rel_name, 'description': 'Desc', 'manager': 'Mgr', 'deputy': 'Dep'})
    release_id = r.url.split('/')[-1]
    
    login(3) # Deployer
    # Add 2 packages
    SESSION.post(f"{BASE_URL}/release/{release_id}/add_package", data={'name': 'PkgA', 'url': 'u', 'status': 'registered', 'status_message': 'ok'})
    SESSION.post(f"{BASE_URL}/release/{release_id}/add_package", data={'name': 'PkgB', 'url': 'u', 'status': 'registered', 'status_message': 'ok'})
    
    # 2. Deploy to T1
    print(f"Deploying to {t1_name}...")
    # Trigger Distribute All
    r = SESSION.post(f"{BASE_URL}/release/{release_id}/distribute_all", data={'target_id': t1_id})
    print_alerts(r.text)
    # Trigger Deploy All
    r = SESSION.post(f"{BASE_URL}/release/{release_id}/deploy_all", data={'target_id': t1_id})
    print_alerts(r.text)
    
    # Verify Deployed on T1
    r = SESSION.get(f"{BASE_URL}/release/{release_id}")
    if f"Deployed: {t1_name}" not in r.text:
        print("FAILED: Not deployed to T1")
        sys.exit(1)
        
    # 3. Move to T2 (The Fix)
    print(f"Moving to {t2_name}...")
    # Distribute All to T2 (Should work now, even though deployed on T1)
    r = SESSION.post(f"{BASE_URL}/release/{release_id}/distribute_all", data={'target_id': t2_id})
    print_alerts(r.text)
    
    if "No applicable packages" in r.text:
        print("FAILED: Bulk Distribute blocked by existing deployment (Fix not working).")
        sys.exit(1)
        
    # Deploy All to T2
    r = SESSION.post(f"{BASE_URL}/release/{release_id}/deploy_all", data={'target_id': t2_id})
    print_alerts(r.text)
    
    # Verify Deployed on T2
    r = SESSION.get(f"{BASE_URL}/release/{release_id}")
    if f"Deployed: {t2_name}" not in r.text:
        print("FAILED: Not deployed to T2")
        # Debug
        with open('move_debug.html', 'w', encoding='utf-8') as f: f.write(r.text)
        sys.exit(1)

    # 4. Verify Index Badges
    print("Verifying Index Badges...")
    r = SESSION.get(f"{BASE_URL}/")
    # Look for T2 badge for this release
    # Badge format: <span ...>TargetName: Count</span>
    expected_badge = f"{t2_name}: 2"
    if expected_badge not in r.text:
        print(f"FAILED: Index badge '{expected_badge}' not found.")
        with open('index_debug.html', 'w', encoding='utf-8') as f: f.write(r.text)
        sys.exit(1)
        
    print("SUCCESS: Bulk Move and Index Badges verified.")

if __name__ == "__main__":
    try:
        verify_bulk_move()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
