# Walkthrough - Release Orchestrator Prototype (Update 7)

I have implemented advanced Release Management features and improved the User Experience for role switching.

## New Features

### 1. Release Management
-   **Edit Release**: You can now update the Description, Manager, and Deputy of an existing release.
    -   *Access*: Release Manager, Admin.
    -   *Location*: "Edit Details" button next to Release Title.
-   **Delete Release**: You can permanently delete a release and all its packages.
    -   *Access*: Release Manager, Admin.
    -   *Location*: "Delete Release" button next to Release Title.

### 2. Bulk Operations
-   **Distribute Release**: One-click distribution of all non-deployed packages to a target.
    -   *Access*: Deployer.
    -   *Location*: "Distribute Release" button in the Packages toolbar.
    -   *Workflow*: Opens a modal to select the target -> Distributes all applicable packages.

### 3. Role Switcher
-   **Dropdown Menu**: The user name in the top right is now a dropdown menu.
-   **functionality**: Quickly switch between `Admin`, `Release Manager`, `Deployer`, and `Viewer` roles without needing to log out and log back in manually.

## Verification Results

### Automatic Verification
I ran a verification script (`verify_features.py`) which confirmed:
1.  **Update Flow**: Created a release, updated its details, and verified the changes persisted.
2.  **Bulk Distribute**: Created a release with multiple packages, ran "Distribute Release", and verified all packages moved to `distributed` status on the correct target.
3.  **Delete Flow**: Deleted a release and verified it was removed from the system (404 response).

### Manual Verification Steps
1.  **Switch Role**: Use the new dropdown in the navbar to switch to **Release Manager**.
2.  **Edit**: Go to a release, click **Edit Details**, change the description, and save.
3.  **Distribute**: Switch to **Deployer**. Click **Distribute Release**, select a target, and confirm all packages update.
4.  **Delete**: Switch to **Admin**. Click **Delete Release** and confirm.
