import requests
import sys
import re
import time

# Redirect stdout/stderr to file
sys.stdout = open('verify.log', 'w', encoding='utf-8')
sys.stderr = sys.stdout

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def login(user_id):
    # Mock login by setting user_id in session via login route
    # We need to find the user_id first. 
    # Since we seeded: 1=admin, 2=rel_mgr, 3=deployer, 4=viewer
    response = SESSION.post(f"{BASE_URL}/login", data={'user_id': user_id})
    return response

def verify_rbac_admin():
    print("Verifying Admin Access...")
    login(1) # Admin
    r = SESSION.get(f"{BASE_URL}/targets")
    if r.status_code != 200:
        print(f"FAILED: Admin cannot access targets. Status: {r.status_code}")
        sys.exit(1)
    # create target - use unique name too
    target_name = f"DistTarget_{int(time.time())}"
    r = SESSION.post(f"{BASE_URL}/targets", data={'name': target_name, 'url': 'http://dist.target', 'status': 'available'})
    if r.status_code != 200: 
         print(f"FAILED: Admin failed to create target. Status: {r.status_code}")
         if target_name not in r.text:
             print("FAILED: Target not found in list.")
             sys.exit(1)
    print("Admin Verified.")
    return target_name

def verify_distribute_flow(target_name):
    print("Verifying Distribute Flow...")
    # 1. Create Release as Manager
    login(2) # Rel Mgr
    release_name = f"Dist Release {time.time()}"
    r = SESSION.post(f"{BASE_URL}/release/new", data={'name': release_name, 'description': 'desc', 'manager': 'mgr', 'deputy': 'dep'})
    if r.status_code != 200 or release_name not in r.text:
         print(f"FAILED: Create Release failed. Status: {r.status_code}")
         with open('debug_error.html', 'w', encoding='utf-8') as f:
             f.write(r.text)
         sys.exit(1)
    print("Release Created.")

    # parse release ID from response history or current url if using Session
    # Requests automatically follows redirects. r.url should be .../release/<id>
    # Check if we are on release detail page
    if "/release/" in r.url:
        release_id = r.url.split("/")[-1]
        print(f"Captured Release ID: {release_id}")
    else:
        print(f"FAILED: Could not capture Release ID from URL: {r.url}")
        sys.exit(1)
    
    # 2. Add Package as Deployer
    login(3) # Deployer
    url = f"{BASE_URL}/release/{release_id}/add_package"
    login(3) # Deployer
    url = f"{BASE_URL}/release/{release_id}/add_package"
    r = SESSION.post(url, data={'name': 'Pkg1', 'url': 'url', 'status': 'registered', 'status_message': 'msg'})
    if r.status_code != 200 or "Pkg1" not in r.text:
         print(f"FAILED: Add Package failed. Status: {r.status_code}")
         with open('debug_error.html', 'w', encoding='utf-8') as f:
             f.write(r.text)
         sys.exit(1)
    print("Package Added.")
    
    # Capture Package ID
    # We are on release detail page. Look for link to package or fallback form action.
    # format: action="/package/<id>/fallback" (if deployed) or distribute/deploy.
    # We just added it, it's not deployed. It has "Distribute" form?
    # action="/package/<id>/distribute"
    match = re.search(r'/package/(\d+)/distribute', r.text)
    if match:
        package_id = match.group(1)
        print(f"Captured Package ID: {package_id}")
    else:
        # Maybe deploy button?
        match = re.search(r'/package/(\d+)/deploy', r.text)
        if match: 
            package_id = match.group(1)
        else:
             print("FAILED: Could not capture Package ID from page.")
             print(r.text[:500])
             sys.exit(1)

    # 3. Distribute
    # First, get target id. We created 'DistToTarget'.
    # We can assume Target ID is 1 or parse it too? 
    # Let's assume 1 for target as Admin creates it cleanly usually. 
    # But better to parse target value from option?
    # <option value="1">DistToTarget</option>
    match_target = re.search(r'value="(\d+)">' + re.escape(target_name) + r'</option>', r.text)
    if match_target:
        target_id = match_target.group(1)
    else:
        # Fallback to 1 if not found (maybe different name normalization)
        target_id = 1
        print(f"Warning: Could not parse Target ID for {target_name}, using 1.")
        
    print(f"Distributing Package {package_id} to Target {target_id}...")
    r = SESSION.post(f"{BASE_URL}/package/{package_id}/distribute", data={'target_id': target_id})
    if f"Package Pkg1 distributed to {target_name}" not in r.text:
        print("FAILED: Distribute message not found.")
        print(r.text[:500])
        sys.exit(1)
        
    # 4. Deploy
    print("Deploying Package...")
    r = SESSION.post(f"{BASE_URL}/package/{package_id}/deploy", data={})
    if f"Package Pkg1 deployed to {target_name}" not in r.text:
        print("FAILED: Deploy message not found.")
        print(r.text[:500])
        sys.exit(1)

    # 5. Fallback
    print("Fallback Package...")
    r = SESSION.post(f"{BASE_URL}/package/{package_id}/fallback", data={})
    if "Fallback executed for Pkg1" not in r.text:
        print("FAILED: Fallback message not found.")
        sys.exit(1)
        
    print("Distribute Flow Verified.")

def verify_event_log_user():
    print("Verifying Event Log User...")
    r = SESSION.get(f"{BASE_URL}/events")
    if "deployer_user" not in r.text:
        print("FAILED: 'deployer_user' not found in event log.")
        sys.exit(1)
    if "rel_mgr" not in r.text:
         print("FAILED: 'rel_mgr' not found in event log.")
         sys.exit(1)
    print("Event Log User Verified.")

if __name__ == "__main__":
    try:
        target_name = verify_rbac_admin()
        verify_distribute_flow(target_name)
        verify_event_log_user()
        print("SUCCESS: All checks passed.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
