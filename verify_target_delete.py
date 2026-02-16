import requests
import sys
import time
import re

# Redirect stdout/stderr to file
sys.stdout = open('verify_target_delete.log', 'w', encoding='utf-8')
sys.stderr = sys.stdout

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def login(user_id):
    # 1=admin, 2=rel_mgr, 3=deployer
    response = SESSION.post(f"{BASE_URL}/login", data={'user_id': user_id})
    return response

def verify_target_delete():
    print("Verifying Target Delete...")
    
    # 1. Admin creates target
    login(1)
    target_name = f"DelTarget_{int(time.time())}"
    r = SESSION.post(f"{BASE_URL}/targets", data={'name': target_name, 'url': 'http://del.target', 'status': 'available'})
    if r.status_code != 200:
        print(f"FAILED: Create Target failed. Status: {r.status_code}")
        with open('target_debug.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        sys.exit(1)
        
    # Get ID
    r = SESSION.get(f"{BASE_URL}/targets")
    match = re.search(r'action="/target/(\d+)/delete"', r.text)
    # The regex might match *any* delete button, but since we just made one and it's likely last...
    # Better: regex search for the specific name's row
    # Row contains: <td>Name</td> ... action="/target/ID/delete"
    # Note: re.DOTALL to match across lines
    
    # Simple check: Does Admin see "Delete" button?
    if 'action="/target/' not in r.text or 'Delete' not in r.text:
        print("FAILED: Delete button not found for Admin.")
        sys.exit(1)

    # Let's try to delete a target we know exists. find the ID of the one we just made
    # Pattern: <tr>...<td>NAME</td>...action="/target/ID/delete"
    pattern = r'<td>' + target_name + r'</td>.*?action="/target/(\d+)/delete"'
    match = re.search(pattern, r.text, re.DOTALL)
    if not match:
        print("FAILED: Could not find Delete action for new target.")
        sys.exit(1)
        
    target_id = match.group(1)
    
    # 2. Non-Admin (Deployer) cannot delete
    login(3)
    r = SESSION.post(f"{BASE_URL}/target/{target_id}/delete")
    # Should redirect to index or show error, but definetely not delete
    # requires_role(Role.admin) should redirect to index with error flash
    
    # Check if target still exists (Admin view)
    login(1)
    r = SESSION.get(f"{BASE_URL}/targets")
    if target_name not in r.text:
        print("FAILED: Deployer was able to delete target (or it disappeared).")
        sys.exit(1)
            
    # 3. Admin deletes target
    print("Admin deleting target...")
    r = SESSION.post(f"{BASE_URL}/target/{target_id}/delete")
    if r.status_code != 200:
        print(f"FAILED: Admin delete request failed. Status: {r.status_code}")
        sys.exit(1)
        
    if "deleted successfully" not in r.text:
         print("FAILED: Success message not found.")
         sys.exit(1)
         
    if target_name in r.text:
        print("FAILED: Target still visible after deletion.")
        # Debug: Write output to file to see why it's there
        with open('delete_debug.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        sys.exit(1)
        
    print("Target Delete Verified.")

if __name__ == "__main__":
    try:
        verify_target_delete()
        print("SUCCESS: Target Delete verification passed.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
