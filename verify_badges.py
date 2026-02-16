import requests
import sys
import time
import re

# Redirect stdout/stderr to file
sys.stdout = open('verify_badges.log', 'w', encoding='utf-8')
sys.stderr = sys.stdout

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def login(user_id):
    # 1=admin, 2=rel_mgr, 3=deployer
    response = SESSION.post(f"{BASE_URL}/login", data={'user_id': user_id})
    return response

def print_alerts(html):
    alerts = re.findall(r'class="alert alert-.*?">\s*(.*?)\s*<button', html, re.DOTALL)
    for a in alerts:
        print(f"ALERT: {a.strip()}")

def verify_badges():
    print("Verifying Package Badges...")
    
    # 1. Create Release and Targets
    login(1) # Admin
    target1_name = f"BadgeT1_{int(time.time())}"
    target2_name = f"BadgeT2_{int(time.time())}"
    
    SESSION.post(f"{BASE_URL}/targets", data={'name': target1_name, 'url': 'http://t1', 'status': 'available'})
    SESSION.post(f"{BASE_URL}/targets", data={'name': target2_name, 'url': 'http://t2', 'status': 'available'})
    
    # Find IDs (simple regex or assume if clean/new env, but let's be robust)
    r = SESSION.get(f"{BASE_URL}/targets")
    match1 = re.search(r'edit/(\d+)">' + target1_name, r.text) # Wait, edit link doesn't exist?
    # Use delete link or just assume order if needed. Or find in select list.
    
    # Create Release
    rel_name = f"BadgeRel_{int(time.time())}"
    r = SESSION.post(f"{BASE_URL}/release/new", data={'name': rel_name, 'description': 'Desc', 'manager': 'Mgr', 'deputy': 'Dep'})
    release_id = r.url.split('/')[-1]
    
    # Look for targets in select list to get IDs
    match1 = re.search(r'value="(\d+)">' + target1_name, r.text)
    match2 = re.search(r'value="(\d+)">' + target2_name, r.text)
    if not match1 or not match2:
        print("FAILED: Could not find target IDs.")
        sys.exit(1)
    target1_id = match1.group(1)
    target2_id = match2.group(1)

    login(3) # Deployer
    
    # Add 3 packages
    pkg_ids = []
    for i in range(3):
        r = SESSION.post(f"{BASE_URL}/release/{release_id}/add_package", data={'name': f'Pkg{i}', 'url': 'u', 'status': 'registered', 'status_message': 'ok'})
        # Find pkg ID from response? It redirects to detail. We need to parse.
        # Simplification: Distribute/Deploy assumes we click buttons. 
        # But we need IDs for POST.
        # Let's parse the release detail page for package IDs.
        r = SESSION.get(f"{BASE_URL}/release/{release_id}")
        # Pattern: id="heading(\d+)" ... Pkg{i}
        # Be careful with order.
        
    r = SESSION.get(f"{BASE_URL}/release/{release_id}")
    # Extract all package IDs
    # Since we just created them and they are listed in order (or we assume for test)
    # Let's get all headings and take the last 3.
    all_ids = re.findall(r'id="heading(\d+)"', r.text)
    if len(all_ids) < 3:
        print("FAILED: Not enough packages found.")
        sys.exit(1)
    
    # We want the ones corresponding to Pkg0, Pkg1, Pkg2. 
    # Provided no other packages exist or we just take the ones we made. 
    # Ideally we'd map name to ID robustly, but order is likely preserved.
    # Let's try matching Name with ID more tightly.
    pkg_id_map = {}
    for pid in all_ids:
        # Find name associated with this PID
        # Look for the specific block
        block_pattern = f'id="heading{pid}".*?Pkg(\d+)'
        m = re.search(block_pattern, r.text, re.DOTALL)
        if m:
            pkg_num = int(m.group(1))
            pkg_id_map[pkg_num] = pid
            
    pkg_ids = []
    for i in range(3):
        if i in pkg_id_map:
            pkg_ids.append(pkg_id_map[i])
        else:
             # Fallback to simple order if regex fails (e.g. strict matching issues)
             pkg_ids.append(all_ids[-(3-i)])
             
    print(f"DEBUG: IDs found: {pkg_ids}")

    # 2. Distribute & Deploy
    print("Distributing and Deploying...")
    # Pkg0 -> Target 1
    r = SESSION.post(f"{BASE_URL}/package/{pkg_ids[0]}/distribute", data={'target_id': target1_id})
    print_alerts(r.text)
    r = SESSION.post(f"{BASE_URL}/package/{pkg_ids[0]}/deploy")
    print_alerts(r.text)
    
    # Pkg1 -> Target 1
    r = SESSION.post(f"{BASE_URL}/package/{pkg_ids[1]}/distribute", data={'target_id': target1_id})
    print_alerts(r.text)
    r = SESSION.post(f"{BASE_URL}/package/{pkg_ids[1]}/deploy")
    print_alerts(r.text)
    
    # Pkg2 -> Target 2
    r = SESSION.post(f"{BASE_URL}/package/{pkg_ids[2]}/distribute", data={'target_id': target2_id})
    print_alerts(r.text)
    r = SESSION.post(f"{BASE_URL}/package/{pkg_ids[2]}/deploy")
    print_alerts(r.text)
    
    # 3. Check Badges
    r = SESSION.get(f"{BASE_URL}/release/{release_id}")
    
    # Expected: 
    # Target1: 2
    # Target2: 1
    
    print("Checking badges...")
    if f"{target1_name}: 2" not in r.text:
        print(f"FAILED: Badge for {target1_name} (count 2) not found.")
        # Debug
        with open('badge_debug.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        sys.exit(1)

    if f"{target2_name}: 1" not in r.text:
         print(f"FAILED: Badge for {target2_name} (count 1) not found.")
         sys.exit(1)
         
    print("Badges Verified Successfully.")

if __name__ == "__main__":
    try:
        verify_badges()
        print("SUCCESS: Package Badges verified.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
