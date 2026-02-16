# Implementation Plan - Release Orchestrator (Update 8)

## Goal
Allow Admin role to delete Deployment Targets.

## Proposed Changes

### Backend
#### [MODIFY] [app.py](file:///c:/Users/marce/OneDrive/Code/Release_Orchestrator/app.py)
1.  **Delete Target** (`/target/<id>/delete` POST)
    *   Role: `Role.admin` (Explicit check or `requires_role(Role.admin)`).
    *   Check for dependencies (Packages deployed or distributed to this target? Schedules?). 
    *   If packages are on it, should we block deletion? Yes, for safety. OR set `deployed_target` to None? 
    *   *Decision*: Block deletion if packages are distributed/deployed there to prevent orphaned state or data loss.

### Frontend
#### [MODIFY] [templates/targets.html](file:///c:/Users/marce/OneDrive/Code/Release_Orchestrator/templates/targets.html)
1.  Add "Delete" button to the target list/table.
    *   Protect with `{% if g.user.role.name == 'admin' %}`.

## Verification
*   **Manual**:
    *   Login as Admin.
    *   Create temp target.
    *   Delete it -> Success.
    *   Try to delete target with packages -> Error message.
    *   Login as Deployer -> No delete button.
