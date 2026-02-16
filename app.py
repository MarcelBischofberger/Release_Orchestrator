from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, g
from models import db, User, Role, Release, Package, DeploymentTarget, ScheduledDeployment, PackageDeployment, EventLog, ReleaseDeploymentStatus, PackageStatus, PackageDeploymentStatus, TargetStatus
from datetime import datetime, date
import os
from functools import wraps

app = Flask(__name__)
# Use a secret key for flash messages
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///release_orchestrator.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

def update_release_status(release):
    packages = release.packages
    if not packages:
        release.deployment_status = ReleaseDeploymentStatus.open
    else:
        # Check if all packages have at least one successful deployment
        deployed_pkg_count = 0
        for p in packages:
            # Check if any deployment for this package is 'deployed'
            if any(d.status == PackageDeploymentStatus.deployed for d in p.deployments):
                deployed_pkg_count += 1
                
        if deployed_pkg_count == 0:
            release.deployment_status = ReleaseDeploymentStatus.open
        elif deployed_pkg_count == len(packages):
            # Optimistic: All packages are deployed somewhere.
            release.deployment_status = ReleaseDeploymentStatus.deployed
        else:
            release.deployment_status = ReleaseDeploymentStatus.deploying
    db.session.commit()

def log_event(category, operation, description):
    username = g.user.username if g.user else 'system'
    event = EventLog(category=category, operation=operation, description=description, user=username)
    db.session.add(event)
    # We assume commit is handled by the caller or we can do it here. 
    # Better to do it here to ensure logs are saved even if other things fail? 
    # Or attached to the transaction. Let's attach to transaction, but for now app has auto-commit on routes mostly.
    # Safe to just add, the route will commit.
    # ACTUALLY: If route fails, we might want log? But usually we log successful ops.
    # Let's trust route commit.
    
    # Let's trust route commit.

# Authentication Logic
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)

def requires_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user is None:
                flash('You need to be logged in.', 'error')
                return redirect(url_for('login'))
            
            if g.user.role not in roles:
                 # Check if admin is one of the allowed roles? 
                 # Usually Admin should be allowed to do most things or we strictly follow the roles.
                 # Let's stick to the requested matrix. 
                 # However, usually Admin > all. 
                 # But user asked for specific roles.
                 # "admin role, can create deployment targets" - implies ONLY targets?
                 # Let's implement EXACTLY what was asked to avoid assumption.
                 pass

            if g.user.role == Role.admin:
                return f(*args, **kwargs)

            # Logic: If one of the required roles matches current user role
            if g.user.role not in roles:
                 flash(f'Access denied. Role {g.user.role.name} cannot perform this action.', 'error')
                 return redirect(url_for('index'))
                 
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        session['user_id'] = user_id
        user = User.query.get(user_id)
        flash(f'Logged in as {user.username} ({user.role.name})', 'success')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('login.html', users=users)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'success')
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def index():
    search_query = request.args.get('search', '')
    if search_query:
        releases = Release.query.filter(Release.name.contains(search_query)).all()
    else:
        releases = Release.query.all()
        
    # Calculate deployed package counts per release
    release_counts = {}
    for release in releases:
        counts = {}
        for pkg in release.packages:
            for d in pkg.deployments:
                if d.status == PackageDeploymentStatus.deployed:
                     t = d.target.name
                     counts[t] = counts.get(t, 0) + 1
        release_counts[release.id] = counts
        
    return render_template('index.html', releases=releases, search_query=search_query, release_counts=release_counts)

@app.route('/release/new', methods=['GET', 'POST'])
@requires_role(Role.release_manager)
def new_release():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        manager = request.form['manager']
        deputy = request.form['deputy']
        
        existing = Release.query.filter_by(name=name).first()
        if existing:
            flash(f'Release "{name}" already exists!', 'error')
            return redirect(url_for('new_release'))

        new_rel = Release(name=name, description=description, manager=manager, deputy=deputy)
        db.session.add(new_rel)
        log_event('release', 'create', f'Created release {name}')
        db.session.commit()
        flash(f'Release "{name}" created successfully!', 'success')
        return redirect(url_for('release_detail', release_id=new_rel.id))
    return render_template('new_release.html')

@app.route('/target/<int:target_id>/delete', methods=['POST'])
@requires_role(Role.admin)
def delete_target(target_id):
    target = DeploymentTarget.query.get_or_404(target_id)
    
    # Check for active deployments or distributions
    # 1. Check Packages distributed or deployed here
    count = PackageDeployment.query.filter_by(target_id=target_id).count()
    if count > 0:
        flash(f'Cannot delete target "{target.name}". {count} packages are distributed/deployed to it.', 'error')
        return redirect(url_for('targets'))
        
    # 2. Check Schedules?
    scheduled_count = ScheduledDeployment.query.filter_by(target_id=target_id).count()
    if scheduled_count > 0:
         flash(f'Cannot delete target "{target.name}". It is used in {scheduled_count} scheduled deployments.', 'error')
         return redirect(url_for('targets'))

    name = target.name
    db.session.delete(target)
    log_event('target', 'delete', f'Deleted target {name}')
    db.session.commit()
    
    flash(f'Target "{name}" deleted successfully.', 'success')
    return redirect(url_for('targets'))

@app.route('/release/<int:release_id>/delete', methods=['POST'])
@requires_role(Role.release_manager)
def delete_release(release_id):
    release = Release.query.get_or_404(release_id)
    name = release.name
    
    db.session.delete(release)
    log_event('release', 'delete', f'Deleted release {name}')
    db.session.commit()
    
    flash(f'Release "{name}" deleted successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/release/<int:release_id>/update', methods=['POST'])
@requires_role(Role.release_manager)
def update_release(release_id):
    release = Release.query.get_or_404(release_id)
    release.description = request.form['description']
    release.manager = request.form['manager']
    release.deputy = request.form['deputy']
    
    log_event('release', 'update', f'Updated details for release {release.name}')
    db.session.commit()
    
    flash(f'Release "{release.name}" updated successfully.', 'success')
    return redirect(url_for('release_detail', release_id=release.id))

@app.route('/release/<int:release_id>/distribute_all', methods=['POST'])
@requires_role(Role.deployer)
def distribute_release_all(release_id):
    release = Release.query.get_or_404(release_id)
    target_id = request.form.get('target_id')
    
    if not target_id:
        flash('No target selected for distribution.', 'error')
        return redirect(url_for('release_detail', release_id=release_id))
        
    target = DeploymentTarget.query.get_or_404(target_id)
    
    if target.status != TargetStatus.available:
        flash(f'Target {target.name} is LOCKED. Distribution prevented.', 'error')
        return redirect(url_for('release_detail', release_id=release_id))
        
    count = 0
    count = 0
    for pkg in release.packages:
        # Check if already distributed/deployed to this target
        deployment = PackageDeployment.query.filter_by(package_id=pkg.id, target_id=target.id).first()
        
        if not deployment:
            # Create new deployment
            deployment = PackageDeployment(package_id=pkg.id, target_id=target.id, status=PackageDeploymentStatus.distributed)
            db.session.add(deployment)
            count += 1
            log_event('package', 'distribute', f'Distributed {pkg.name} to {target.name} (Bulk)')
        elif deployment.status == PackageDeploymentStatus.not_deployed:
            # Re-distribute (e.g. from fallback)
            deployment.status = PackageDeploymentStatus.distributed
            deployment.deployed_at = datetime.utcnow()
            count += 1
            log_event('package', 'distribute', f'Re-distributed {pkg.name} to {target.name} (Bulk)')
            
    db.session.commit()
    update_release_status(release)
    
    if count > 0:
        flash(f'Distributed {count} packages to {target.name}.', 'success')
    else:
        flash('No applicable packages to distribute.', 'warning')
        
    return redirect(url_for('release_detail', release_id=release_id))

@app.route('/release/<int:release_id>')
def release_detail(release_id):
    release = Release.query.get_or_404(release_id)
    packages = release.packages
    # Get all packages in the release to allow dependency selection
    all_packages = Package.query.filter_by(release_id=release_id).all()
    # Get available targets for deployment (for the dropdown)
    targets = DeploymentTarget.query.filter_by(status=TargetStatus.available).all()
    # Get all targets for scheduling (can schedule even if locked, maybe? Let's allow all)
    all_targets = DeploymentTarget.query.all()
    # Calculate deployed package counts per target
    deployed_counts = {}
    for pkg in packages:
        for d in pkg.deployments:
            if d.status == PackageDeploymentStatus.deployed:
                target_name = d.target.name
                deployed_counts[target_name] = deployed_counts.get(target_name, 0) + 1
            
    return render_template('release_detail.html', release=release, packages=packages, all_packages=all_packages, PackageStatus=PackageStatus, targets=targets, all_targets=all_targets, PackageDeploymentStatus=PackageDeploymentStatus, deployed_counts=deployed_counts)

@app.route('/release/<int:release_id>/add_package', methods=['POST'])
@requires_role(Role.deployer)
def add_package(release_id):
    release = Release.query.get_or_404(release_id)
    name = request.form['name']
    url = request.form['url']
    status = request.form['status']
    status_message = request.form['status_message']

    new_pkg = Package(
        name=name, 
        url=url, 
        status=PackageStatus[status], 
        status_message=status_message, 
        release_id=release_id
    )
    db.session.add(new_pkg)
    log_event('package', 'create', f'Added package {name} to {release.name}')
    db.session.commit()
    
    # Update release status
    update_release_status(new_pkg.release)
    
    flash('Package added successfully!', 'success')
    return redirect(url_for('release_detail', release_id=release_id))

@app.route('/package/<int:package_id>/delete', methods=['POST'])
@requires_role(Role.deployer)
def delete_package(package_id):
    pkg = Package.query.get_or_404(package_id)
    release = pkg.release
    release_id = pkg.release_id
    pkg_name = pkg.name
    db.session.delete(pkg)
    log_event('package', 'delete', f'Deleted package {pkg_name}')
    db.session.commit()
    
    update_release_status(release)
    
    flash('Package removed successfully!', 'success')
    return redirect(url_for('release_detail', release_id=release_id))

@app.route('/package/<int:package_id>/dependency', methods=['POST'])
@requires_role(Role.deployer)
def add_dependency(package_id):
    pkg = Package.query.get_or_404(package_id)
    dependency_id = request.form.get('dependency_id')
    
    if not dependency_id:
        flash('No dependency selected', 'error')
        return redirect(url_for('release_detail', release_id=pkg.release_id))

    dependency = Package.query.get_or_404(dependency_id)
    
    if dependency == pkg:
        flash('A package cannot depend on itself', 'error')
    elif dependency in pkg.dependencies:
        flash('Dependency already exists', 'warning')
    else:
        pkg.dependencies.append(dependency)
        db.session.commit()
        flash(f'Dependency on {dependency.name} added!', 'success')
        
    return redirect(url_for('release_detail', release_id=pkg.release_id))

@app.route('/package/<int:package_id>/remove_dependency', methods=['POST'])
@requires_role(Role.deployer)
def remove_dependency(package_id):
    pkg = Package.query.get_or_404(package_id)
    dependency_id = request.form.get('dependency_id')
    dependency = Package.query.get_or_404(dependency_id)
    
    if dependency in pkg.dependencies:
        pkg.dependencies.remove(dependency)
        db.session.commit()
        flash(f'Dependency on {dependency.name} removed!', 'success')
        
    return redirect(url_for('release_detail', release_id=pkg.release_id))

# Deployment Targets Routes

@app.route('/targets', methods=['GET', 'POST'])
def targets():
    if request.method == 'POST':
        # Manually check role for POST, as GET is allowed for all to see list? 
        # Requirement: "admin role, can create deployment targets"
        # "viewer role, can query data"
        # So Viewer can SEE targets, but only Admin can CREATE.
        if not g.user or g.user.role != Role.admin:
             flash('Only Admin can create targets', 'error')
             return redirect(url_for('targets'))
             
        name = request.form['name']
        url_input = request.form['url']
        status = request.form['status']
        
        # Simple validation
        if not name or not url_input:
            flash('Name and URL are required', 'error')
            return redirect(url_for('targets'))
            
        existing = DeploymentTarget.query.filter_by(name=name).first()
        if existing:
            flash(f'Target "{name}" already exists', 'error')
            return redirect(url_for('targets'))
            
        new_target = DeploymentTarget(name=name, url=url_input, status=TargetStatus[status])
        db.session.add(new_target)
        log_event('target', 'create', f'Created target {name}')
        db.session.commit()
        flash(f'Deployment Target "{name}" created!', 'success')
        return redirect(url_for('targets'))
        
    targets = DeploymentTarget.query.all()
    return render_template('targets.html', targets=targets, TargetStatus=TargetStatus)

@app.route('/target/<int:target_id>/toggle_status', methods=['POST'])
@requires_role(Role.admin)
def toggle_target_status(target_id):
    target = DeploymentTarget.query.get_or_404(target_id)
    if target.status == TargetStatus.available:
        target.status = TargetStatus.locked
        flash(f'Target {target.name} is now LOCKED', 'warning')
    else:
        target.status = TargetStatus.available
        target.status = TargetStatus.available
        flash(f'Target {target.name} is now AVAILABLE', 'success')
    log_event('target', 'status_change', f'Changed status of {target.name} to {target.status.name}')
    db.session.commit()
    return redirect(url_for('targets'))


@app.route('/package/<int:package_id>/distribute', methods=['POST'])
@requires_role(Role.deployer)
def distribute_package(package_id):
    pkg = Package.query.get_or_404(package_id)
    target_id = request.form.get('target_id')
    
    if not target_id:
        flash('No target selected for distribution', 'error')
        return redirect(url_for('release_detail', release_id=pkg.release_id))
        
    target = DeploymentTarget.query.get_or_404(target_id)
    
    if target.status != TargetStatus.available:
        flash(f'Target {target.name} is LOCKED. Distribution prevented.', 'error')
        return redirect(url_for('release_detail', release_id=pkg.release_id))

    # Check/Create Deployment
    deployment = PackageDeployment.query.filter_by(package_id=pkg.id, target_id=target.id).first()
    if not deployment:
        deployment = PackageDeployment(package_id=pkg.id, target_id=target.id, status=PackageDeploymentStatus.distributed)
        db.session.add(deployment)
    elif deployment.status == PackageDeploymentStatus.not_deployed:
        deployment.status = PackageDeploymentStatus.distributed
        deployment.deployed_at = datetime.utcnow()
    else:
        # Already distributed or deployed
        flash(f'Package {pkg.name} is already {deployment.status.name} on {target.name}', 'info')
        return redirect(url_for('release_detail', release_id=pkg.release_id))

    log_event('package', 'distribute', f'Distributed {pkg.name} to {target.name}')
    db.session.commit()
    
    update_release_status(pkg.release)
    flash(f'Package {pkg.name} distributed to {target.name}', 'success')
    return redirect(url_for('release_detail', release_id=pkg.release_id))

@app.route('/package/<int:package_id>/deploy', methods=['POST'])
@requires_role(Role.deployer)
def deploy_package(package_id):
    pkg = Package.query.get_or_404(package_id)
    # Target is required for lookup, but maybe passed or inferred?
    # In old flow, target was inferred from `pkg.deployed_target`.
    # In new flow, we MUST know which target we are deploying to.
    # The form in `release_detail` must send `target_id`.
    target_id = request.form.get('target_id')
    
    if not target_id:
        flash('Target ID missing for deployment.', 'error')
        return redirect(url_for('release_detail', release_id=pkg.release_id))
        
    target = DeploymentTarget.query.get_or_404(target_id)
    
    deployment = PackageDeployment.query.filter_by(package_id=pkg.id, target_id=target.id).first()
    
    if not deployment or deployment.status != PackageDeploymentStatus.distributed:
        flash(f'Package must be DISTRIBUTED to {target.name} before deployment.', 'error')
        return redirect(url_for('release_detail', release_id=pkg.release_id))
        
    if target.status != TargetStatus.available:
        flash(f'Target {target.name} is LOCKED. Deployment prevented.', 'error')
        return redirect(url_for('release_detail', release_id=pkg.release_id))
 
    # Check dependencies
    missing_deps = []
    for dep in pkg.dependencies:
        # Check if dependency has a DEPLOYED status on THIS target
        dep_deployment = PackageDeployment.query.filter_by(package_id=dep.id, target_id=target.id).first()
        if not dep_deployment or dep_deployment.status != PackageDeploymentStatus.deployed:
            missing_deps.append(dep.name)
    
    if missing_deps:
        flash(f"Deployment Failed. Dependency requirements not met on {target.name}. Missing: {', '.join(missing_deps)}", 'error')
        return redirect(url_for('release_detail', release_id=pkg.release_id))

    deployment.status = PackageDeploymentStatus.deployed
    deployment.deployed_at = datetime.utcnow()
    
    log_event('package', 'deploy', f'Deployed {pkg.name} to {target.name}')
    db.session.commit()
    
    update_release_status(pkg.release)
    
    flash(f'Package {pkg.name} deployed to {target.name}', 'success')
    return redirect(url_for('release_detail', release_id=pkg.release_id))

@app.route('/package/<int:package_id>/fallback', methods=['POST'])
@requires_role(Role.deployer)
def fallback_package(package_id):
    pkg = Package.query.get_or_404(package_id)
    # We need to know WHICH target to fallback from.
    target_id = request.form.get('target_id')
    
    # If no target_id provided, can we infer? 
    # If there is only one deployed target, maybe? 
    # But checking form is safer.
    if not target_id:
        flash('Target ID missing for fallback.', 'error')
        return redirect(url_for('release_detail', release_id=pkg.release_id))

    target = DeploymentTarget.query.get_or_404(target_id)
    
    deployment = PackageDeployment.query.filter_by(package_id=pkg.id, target_id=target.id).first()
    
    if not deployment or deployment.status != PackageDeploymentStatus.deployed:
        flash(f'Package is not deployed to {target.name}', 'warning')
        return redirect(url_for('release_detail', release_id=pkg.release_id))
    
    # Check if target is locked
    if target.status != TargetStatus.available:
         flash(f'Target {target.name} is LOCKED. Fallback prevented.', 'error')
         return redirect(url_for('release_detail', release_id=pkg.release_id))
        
    # Revert to Distributed
    deployment.status = PackageDeploymentStatus.distributed
    deployment.deployed_at = datetime.utcnow()
    
    log_event('package', 'fallback', f'Fallback {pkg.name} (reverted to distributed on {target.name})')
    db.session.commit()
    
    update_release_status(pkg.release)
    
    flash(f'Fallback executed for {pkg.name} on {target.name}', 'success')
    return redirect(url_for('release_detail', release_id=pkg.release_id))

# Schedule Routes

@app.route('/release/<int:release_id>/schedule', methods=['POST'])
@requires_role(Role.release_manager)
def add_schedule(release_id):
    release = Release.query.get_or_404(release_id)
    target_id = request.form.get('target_id')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    
    if not target_id or not start_date or not end_date:
        flash('All fields are required.', 'error')
        return redirect(url_for('release_detail', release_id=release_id))
        
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if start > end:
             flash('Start date must be before end date.', 'error')
             return redirect(url_for('release_detail', release_id=release_id))

        schedule = ScheduledDeployment(release_id=release_id, target_id=target_id, start_date=start, end_date=end)
        db.session.add(schedule)
        db.session.commit()
        
        log_event('release', 'schedule', f'Scheduled Release {release.name} on Target {schedule.target.name} ({start} to {end})')
        flash('Schedule added.', 'success')
    except Exception as e:
        flash(f'Error adding schedule: {str(e)}', 'error')
        
    return redirect(url_for('release_detail', release_id=release_id))

@app.route('/schedule/<int:schedule_id>/delete', methods=['POST'])
@requires_role(Role.release_manager)
def delete_schedule(schedule_id):
    schedule = ScheduledDeployment.query.get_or_404(schedule_id)
    release_id = schedule.release_id
    target_name = schedule.target.name
    
    db.session.delete(schedule)
    db.session.commit()
    
    log_event('release', 'unschedule', f'Removed schedule for Release {schedule.release.name} on {target_name}')
    flash('Schedule removed.', 'success')
    return redirect(url_for('release_detail', release_id=release_id))

# Calendar

@app.route('/calendar')
def calendar():
    return render_template('calendar.html')

@app.route('/api/calendar_events')
def calendar_events():
    schedules = ScheduledDeployment.query.all()
    events = []
    for s in schedules:
        events.append({
            'title': f"{s.release.name} @ {s.target.name}",
            'start': s.start_date.isoformat(),
            'end': s.end_date.isoformat(), # FullCalendar end date is exclusive, might need +1 day if user expects inclusive
            'allDay': True,
            'url': url_for('release_detail', release_id=s.release.id)
        })
    return jsonify(events)

# Helper for Topological Sort
def get_sorted_packages(packages):
    """
    Returns a list of packages in topological order (dependencies first).
    """
    sorted_packages = []
    visited = set()
    temp_visited = set() # For cycle detection

    def visit(pkg):
        if pkg in temp_visited:
            return # Cycle detected, or just handle gracefully by ignoring
        if pkg in visited:
            return
        
        temp_visited.add(pkg)
        
        # Visit dependencies first
        for dep in pkg.dependencies:
            # Only consider dependencies that are part of the same release 
            # (Requirement says "from one package to another", usually implies within release or system. 
            # Our model allow cross-release deps, but for "Deploy Release" we usually care about the current release content's dependencies.
            # However, if a package depends on something outside, we should probably check that too. 
            # For simplicity, we check all dependencies.)
            visit(dep)
            
        temp_visited.remove(pkg)
        visited.add(pkg)
        sorted_packages.append(pkg)

    for p in packages:
        visit(p)
        
    return sorted_packages

@app.route('/release/<int:release_id>/deploy_all', methods=['POST'])
@requires_role(Role.deployer)
def deploy_release_all(release_id):
    release = Release.query.get_or_404(release_id)
    target_id = request.form.get('target_id')
    
    if not target_id:
        flash('No target selected for deployment', 'error')
        return redirect(url_for('release_detail', release_id=release_id))
    
    target = DeploymentTarget.query.get_or_404(target_id)
    if target.status != TargetStatus.available:
        flash(f'Target {target.name} is LOCKED. Deployment prevented.', 'error')
        return redirect(url_for('release_detail', release_id=release_id))

    # Get all packages in topological order
    packages = get_sorted_packages(release.packages)
    
    errors = []
    deployed_count = 0
    
    for pkg in packages:
        # Check current deployment on this target
        deployment = PackageDeployment.query.filter_by(package_id=pkg.id, target_id=target.id).first()
        
        if deployment and deployment.status == PackageDeploymentStatus.deployed:
            continue # Already deployed here
        
        # If not distributed, we should distribute it first? 
        # Requirement: "deploy... only... on packages which are already distributed"
        # So if not distributed to this target (deployment doesn't exist or status is not distributed), we skip or fail?
        # `distribute_release_all` handles distribution. 
        # If user runs `deploy_all`, they expect distributed packages to be deployed.
        # If package is NOT distributed to this target, we can either:
        # 1. Skip (strict)
        # 2. Auto-distribute (lenient)
        # Let's be strict as per single package logic.
        if not deployment or deployment.status != PackageDeploymentStatus.distributed:
            # Skip validly? Or warn? 
            # If we skip, the loop continues. Dependencies check might fail for others.
            # But if it's not distributed, it can't be deployed.
            continue

        # Check dependencies
        missing_deps = []
        for dep in pkg.dependencies:
            # Check dependency deployment on THIS target
            dep_deployment = PackageDeployment.query.filter_by(package_id=dep.id, target_id=target.id).first()
            if not dep_deployment or dep_deployment.status != PackageDeploymentStatus.deployed:
                missing_deps.append(dep.name)
        
        if missing_deps:
            errors.append(f"Package {pkg.name} cannot be deployed because dependencies are missing on {target.name}: {', '.join(missing_deps)}")
            continue # Skip this package
            
        # Deploy
        deployment.status = PackageDeploymentStatus.deployed
        deployment.deployed_at = datetime.utcnow()
        deployed_count += 1
        log_event('package', 'deploy', f'Deployed {pkg.name} to {target.name} (Bulk)')
        
    db.session.commit()
    update_release_status(release)

    if errors:
        flash(f"Partial Deployment Completed. {len(errors)} errors occurred: <br>" + "<br>".join(errors), 'warning')
    else:
        flash(f'All {deployed_count} packages deployed to {target.name} successfully!', 'success')
        
    return redirect(url_for('release_detail', release_id=release_id))

@app.route('/release/<int:release_id>/fallback_all', methods=['POST'])
@requires_role(Role.release_manager)
def fallback_release_all(release_id):
    release = Release.query.get_or_404(release_id)
    # We need to know WHICH target to fallback from? 
    # Or fallback ALL targets? 
    # The requirement didn't specify target for fallback_all, but usually bulk ops are per target?
    # `deploy_release_all` takes `target_id`. `fallback_release_all` currently does NOT.
    # It loops all packages and checks `deployment_status`.
    # In multi-target world, "Fallback All" is ambiguous.
    # I should add `target_id` to fallback_all form!
    # But for now, let's look at the old code: `pkg.deployed_target`.
    # If I don't change the form (which I should), I can't know the target.
    # However, if the user says "Fallback Release", do they mean specific target?
    # LIMITATION: Previous code allowed fallback from WHEREVER it was.
    # Now it can be on multiple.
    # I will assume "Fallback All" means "Fallback on ALL targets" for now? 
    # Or better: "Fallback on specific target".
    # I'll update it to check `target_id` if provided, else maybe fallback all?
    # Let's check `request.form`.
    
    target_id = request.form.get('target_id')
    
    # Reverse topological order
    packages = get_sorted_packages(release.packages)
    packages.reverse()
    
    count = 0
    errors = []
    
    for pkg in packages:
         # Find ALL deployments or Specific one? 
         if target_id:
             deployments = PackageDeployment.query.filter_by(package_id=pkg.id, target_id=target_id).all()
         else:
             deployments = pkg.deployments
             
         for d in deployments:
             if d.status == PackageDeploymentStatus.deployed:
                 if d.target.status != TargetStatus.available:
                     errors.append(f"Package {pkg.name} stuck on LOCKED target {d.target.name}")
                     continue
                 
                 d.status = PackageDeploymentStatus.distributed
                 d.deployed_at = datetime.utcnow() # Updated time
                 count += 1
                 log_event('package', 'fallback', f'Fallback {pkg.name} on {d.target.name} (Bulk)')
              
    db.session.commit()
    update_release_status(release)
    
    if errors:
        flash(f"Partial Fallback. {len(errors)} errors: " + ", ".join(errors), 'warning')
    else:
        flash(f'Fallback executed for {count} packages.', 'success')

    return redirect(url_for('release_detail', release_id=release_id))

@app.route('/events')
def events():
    category = request.args.get('category')
    if category:
        events = EventLog.query.filter_by(category=category).order_by(EventLog.timestamp.desc()).all()
    else:
        events = EventLog.query.order_by(EventLog.timestamp.desc()).all()
    return render_template('events.html', events=events, category=category)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Seed Users if not exist
        if not User.query.first():
            print("Seeding Users...")
            db.session.add(User(username='admin_user', role=Role.admin))
            db.session.add(User(username='rel_mgr', role=Role.release_manager))
            db.session.add(User(username='deployer_user', role=Role.deployer))
            db.session.add(User(username='view_only', role=Role.viewer))
            db.session.commit()
            print("Users seeded.")

    app.run(debug=True, use_reloader=False)
