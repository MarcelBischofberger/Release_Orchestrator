# Release Orchestrator Prototype - Use Cases

This document outlines the key use cases supported by the Release Orchestrator prototype, categorized by user role.

## 1. Administrative Functions
**Role Required:** `Admin`

*   **Create Deployment Target**: Define a new environment (e.g., Staging, Production) where packages can be deployed.
    *   *Input*: Name, URL, Status (Available/Locked).
*   **Delete Deployment Target**: Permanently remove a deployment target.
    *   *Constraint*: Cannot delete if packages are currently distributed or deployed to it.
*   **Manage Users (Mock)**: Implicit capability to manage user roles (currently handled via seeded users).

## 2. Release Management
**Role Required:** `Release Manager` (or `Admin`)

*   **Create New Release**: Initialize a release cycle.
    *   *Input*: Name, Version, Description, Manager Name, Deputy Name.
*   **Edit Release Details**: Update the metadata of an existing release.
    *   *Input*: Description, Manager Name, Deputy Name.
*   **Delete Release**: Remove a release including all its associated packages.
*   **Schedule Release**: Set a planned date for deployment (Mock functionality).

## 3. Package & Deployment Operations
**Role Required:** `Deployer` (or `Admin`)

*   **Add Package**: Register a new software package to a release.
    *   *Input*: Name, Version/URL, Status (Registered/Testing/etc).
*   **Manage Dependencies**: Define relationships between packages.
    *   *Action*: Add or Remove a dependency on another package within the release.
*   **Distribute Package**: Transfer package artifacts to a target environment.
    *   *Pre-requisite*: Target must be `Available`.
    *   *Outcome*: Status moves to `Distributed`.
*   **Deploy Package**: Activate a distributed package on the target.
    *   *Pre-requisite*: Package must be `Distributed`.
*   **Fallback Package**: Revert a deployed package to its previous state.
    *   *Outcome*: Status returns to `Distributed`.
*   **Bulk Distribute**: Distribute all eligible packages in a release to a specific target in one action.
*   **Delete Package**: Remove a package from a release.

## 4. Environment Management
**Role Required:** `Release Manager` (or `Admin`)

*   **Lock/Unlock Target**: Change the status of a deployment target to prevent or allow new deployments.
    *   *Use Case*: Lock "Production" during maintenance windows.

## 5. General Monitoring
**Role Required:** `Viewer` (and all other roles)

*   **View Releases**: Browse all releases and their statuses.
*   **View Release Details**: See packages, dependencies, and deployment status for a specific release.
*   **View Targets**: See list of deployment targets and their status (Available/Locked).
*   **View Event Log**: Audit trail of all actions performed in the system (Who, What, When).
*   **View Calendar**: See scheduled releases (Mock visualization).

## 6. Authentication & User Experience
*   **Role Switching**: Easily switch between `Admin`, `Release Manager`, `Deployer`, and `Viewer` roles via the navigation bar dropdown (for prototype testing).
*   **Login/Logout**: Secure access session management (Mock implementation).
