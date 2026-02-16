import requests
import sys
import time
import re

# Redirect stdout/stderr to file
sys.stdout = open('verify_features.log', 'w', encoding='utf-8')
sys.stderr = sys.stdout

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def login(user_id):
    # Mock login by setting user_id in session via login route
    # 1=admin, 2=rel_mgr, 3=deployer, 4=viewer
    response = SESSION.post(f"{BASE_URL}/login", data={'user_id': user_id})
    return response

def verify_update_release():
    print("Verifying Update Release...")
    login(2) # Rel Mgr
    
    # Create Release
    release_name = f"UpdateTest_{int(time.time())}"
    r = SESSION.post(f"{BASE_URL}/release/new", data={'name': release_name, 'description': 'Initial Desc', 'manager': 'Initial Mgr', 'deputy': 'Initial Dep'})
    if r.status_code != 200:
        print(f"FAILED: Create Release failed. Status: {r.status_code}")
        sys.exit(1)
        
    # Get Release ID (capture redirect URL or parse?)
    # The last request redirected to release_detail, so we can get ID from URL
    release_id = r.url.split('/')[-1]
    
    # Update Release
    new_desc = "Updated Description"
    new_mgr = "Updated Manager"
    new_dep = "Updated Deputy"
    
    r = SESSION.post(f"{BASE_URL}/release/{release_id}/update", data={
        'description': new_desc,
        'manager': new_mgr,
        'deputy': new_dep
    })
    
    if r.status_code != 200:
        print(f"FAILED: Update Release failed. Status: {r.status_code}")
        sys.exit(1)
        
    if new_desc not in r.text or new_mgr not in r.text:
        print("FAILED: Updated details not found in response.")
        sys.exit(1)
        
    print(f"Update Release Verified for Release {release_id}.")
    return release_id

def verify_bulk_distribute(release_id):
    print("Verifying Bulk Distribute...")
    login(1) # Admin to create target
    target_name = f"BulkDistTarget_{int(time.time())}"
    r = SESSION.post(f"{BASE_URL}/targets", data={'name': target_name, 'url': 'http://bulk.dist', 'status': 'available'})
    
    # Needs to find Target ID
    r = SESSION.get(f"{BASE_URL}/targets")
    match = re.search(r'edit/(\d+)">' + target_name, r.text)
    if match:
        target_id = match.group(1)
    else:
        # Try finding in release detail select list
        login(2)
        r = SESSION.get(f"{BASE_URL}/release/{release_id}")
        match = re.search(r'value="(\d+)">' + target_name + r'</option>', r.text)
        if match:
             target_id = match.group(1)
        else:
             print("FAILED: Could not find Target ID.")
             sys.exit(1)

    login(3) # Deployer
    # Add packages
    SESSION.post(f"{BASE_URL}/release/{release_id}/add_package", data={'name': 'Pkg1', 'url': 'u1', 'status': 'registered', 'status_message': 'ok'})
    SESSION.post(f"{BASE_URL}/release/{release_id}/add_package", data={'name': 'Pkg2', 'url': 'u2', 'status': 'registered', 'status_message': 'ok'})
    
    # Distribute All
    r = SESSION.post(f"{BASE_URL}/release/{release_id}/distribute_all", data={'target_id': target_id})
    if r.status_code != 200:
        print(f"FAILED: Distribute All failed. Status: {r.status_code}")
        sys.exit(1)
        
    if f"Distributed 2 packages to {target_name}" not in r.text:
        print("FAILED: Success message not found.")
        print(r.text[:500])
        sys.exit(1)
        
    print("Bulk Distribute Verified.")
    return target_name

def verify_delete_release(release_id):
    print("Verifying Delete Release...")
    login(1) # Admin (or Manager)
    
    r = SESSION.post(f"{BASE_URL}/release/{release_id}/delete")
    if r.status_code != 200:
         print(f"FAILED: Delete Release failed. Status: {r.status_code}")
         sys.exit(1)
         
    # Should redirect to index and show success message
    if "deleted successfully" not in r.text:
        print("FAILED: Delete success message not found.")
        sys.exit(1)
        
    # Verify gone
    r = SESSION.get(f"{BASE_URL}/release/{release_id}")
    if r.status_code != 404:
        print(f"FAILED: Release still exists (Status {r.status_code}).")
        sys.exit(1)
        
    print("Delete Release Verified.")

if __name__ == "__main__":
    try:
        rid = verify_update_release()
        verify_bulk_distribute(rid)
        verify_delete_release(rid)
        print("SUCCESS: All new features verified.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
