import requests
import re
import sys

BASE_URL = 'http://127.0.0.1:5000'

def get_admin_id(session):
    print("DEBUG: Finding Admin User ID...")
    response = session.get(f'{BASE_URL}/login')
    # Look for admin_user in the form or list. 
    # login.html: <option value="{{ user.id }}">{{ user.username }} ...
    # Pattern: value="(\d+)">admin_user
    match = re.search(r'value="(\d+)">admin_user', response.text)
    if match:
        print(f"DEBUG: Found Admin ID: {match.group(1)}")
        return match.group(1)
    return '1' # Fallback

def get_target_id(session, name):
    print(f"DEBUG: Extracting ID for target '{name}'")
    response = session.get(f'{BASE_URL}/targets')
    
    if "delete_target" not in response.text:
         print("WARNING: 'delete_target' action not found in HTML. Check user role?")
    
    # regex for action="/target/ID/delete"
    # Matches any form action for deleting THIS target
    # We first find the name, then look for the NEAREST delete form?
    # Or just iterate matches.
    
    # Split by rows to be safe
    rows = response.text.split('<tr>')
    for row in rows:
        if f'<td>{name}</td>' in row:
            # Found the row, look for delete action in this row
            match = re.search(r'/target/(\d+)/delete', row)
            if match:
                print(f"DEBUG: Found ID {match.group(1)} for target {name}")
                return match.group(1)
            
    print(f"ERROR: Could not find target ID for {name}")
    with open('debug_targets.html', 'w') as f:
        f.write(response.text)
    print("DEBUG: Saved response to debug_targets.html")
    return None

import traceback

# ... (omitting early parts)

def verify_multi_target():
    try:
        session = requests.Session()
        
        # Login
        admin_id = get_admin_id(session)
        print(f"Logging in as {admin_id}...")
        session.post(f'{BASE_URL}/login', data={'user_id': admin_id}) 
        
        # Verify Login
        resp = session.get(f'{BASE_URL}/')
        if "Logged in as" not in resp.text:
            print("WARNING: Login might have failed. 'Logged in as' not found.")
        
        # Create Targets
        print("Creating Targets...")
        t1_name = 'MultiT1'
        t2_name = 'MultiT2'
        session.post(f'{BASE_URL}/targets', data={'name': t1_name, 'url': 'http://t1.com', 'status': 'available'})
        session.post(f'{BASE_URL}/targets', data={'name': t2_name, 'url': 'http://t2.com', 'status': 'available'})
        
        # Get IDs
        t1_id = get_target_id(session, t1_name)
        if not t1_id:
            print("FAILED: Could not find T1 ID. Exiting.")
            sys.exit(1)
            
        t2_id = get_target_id(session, t2_name)
        if not t2_id:
             print("FAILED: Could not find T2 ID. Exiting.")
             sys.exit(1)
             
        # ... rest of the script ...
        
        # Create Release
        print("Creating Release...")
        r_name = 'MultiRel'
        import time
        r_name += str(int(time.time()))
        
        response = session.post(f'{BASE_URL}/release/new', data={
            'name': r_name,
            'description': 'Test Multi Target',
            'manager': 'Me',
            'deputy': 'You'
        })
        
        # Extract Release ID
        match = re.search(r'/release/(\d+)$', response.url)
        if not match:
            print("FAILED: Could not create release")
            with open('debug_release.html', 'w') as f:
                f.write(response.text)
            sys.exit(1)
        release_id = match.group(1)
        print(f"Release ID: {release_id}")
        
        # Add Package
        print("Adding Package...")
        session.post(f'{BASE_URL}/release/{release_id}/add_package', data={
            'name': 'PkgMulti',
            'url': 'http://nexus',
            'status': 'registered',
            'status_message': 'Init'
        })
        
        # Get Package ID
        print("Getting Package ID...")
        response = session.get(f'{BASE_URL}/release/{release_id}')
        # Pattern: /package/(\d+)/distribute
        match = re.search(r'/package/(\d+)/distribute', response.text)
        if not match:
            print("FAILED: No package found (Distribute link missing?)")
            with open('debug_pkg.html', 'w') as f:
                f.write(response.text)
            sys.exit(1)
        pkg_id = match.group(1)
        print(f"Package ID: {pkg_id}")
        
        # Distribute / Deploy verification...
        # ... (rest of logic) ...
        # Distribute to T1
        print(f"Distributing Pkg {pkg_id} to T1 ({t1_id})...")
        session.post(f'{BASE_URL}/package/{pkg_id}/distribute', data={'target_id': t1_id})
        
        print(f"Distributing Pkg {pkg_id} to T2 ({t2_id})...")
        session.post(f'{BASE_URL}/package/{pkg_id}/distribute', data={'target_id': t2_id})
        
        # Check
        response = session.get(f'{BASE_URL}/release/{release_id}')
        dist_t1_ok = f"Distributed: {t1_name}" in response.text
        dist_t2_ok = f"Distributed: {t2_name}" in response.text
        
        if dist_t1_ok and dist_t2_ok:
            print("SUCCESS: Distributed to both targets.")
        else:
            print("FAILED: Did not see both distributions.")
            print(f"Missing T1 dist? {not dist_t1_ok}")
            print(f"Missing T2 dist? {not dist_t2_ok}")
            with open('debug_dist_fail.html', 'w') as f:
                f.write(response.text)
            sys.exit(1)
            
        print("Deploying to T1...")
        session.post(f'{BASE_URL}/package/{pkg_id}/deploy', data={'target_id': t1_id})
        
        response = session.get(f'{BASE_URL}/release/{release_id}')
        if f"Deployed: {t1_name}" in response.text and f"Distributed: {t2_name}" in response.text:
            print("SUCCESS: T1 Deployed, T2 Distributed.")
        else:
             print("FAILED: State Mismatch after T1 deploy.")
             sys.exit(1)
             
        print("Deploying to T2...")
        session.post(f'{BASE_URL}/package/{pkg_id}/deploy', data={'target_id': t2_id})
        
        response = session.get(f'{BASE_URL}/release/{release_id}')
        if f"Deployed: {t1_name}" in response.text and f"Deployed: {t2_name}" in response.text:
            print("SUCCESS: Both Deployed.")
        else:
             print("FAILED: Both targets not deployed.")
             sys.exit(1)
             
        print("VERIFICATION COMPLETE")

    except Exception:
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    verify_multi_target()
