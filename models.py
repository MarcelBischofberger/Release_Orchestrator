from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Table, Boolean, Date, DateTime
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

db = SQLAlchemy()

# Enums
class PackageStatus(enum.Enum):
    registered = "registered"
    processing = "processing"
    deployed = "deployed"
    failure = "failure"

class ReleaseDeploymentStatus(enum.Enum):
    open = "open"
    deploying = "deploying"
    deployed = "deployed"

class PackageDeploymentStatus(enum.Enum):
    not_deployed = "not_deployed"
    distributed = "distributed"
    deployed = "deployed"

class TargetStatus(enum.Enum):
    available = "available"
    locked = "locked"

class Role(enum.Enum):
    viewer = 'viewer'
    release_manager = 'release_manager'
    deployer = 'deployer'
    admin = 'admin'

# Association table
package_dependencies = Table('package_dependencies', db.Model.metadata,
    Column('requirer_id', Integer, ForeignKey('package.id'), primary_key=True),
    Column('provider_id', Integer, ForeignKey('package.id'), primary_key=True)
)

# Models
class DeploymentTarget(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    url = Column(String(255), nullable=False)
    status = Column(Enum(TargetStatus), default=TargetStatus.available)

    def __repr__(self):
        return f'<DeploymentTarget {self.name}>'

class Release(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))
    manager = Column(String(100))
    deputy = Column(String(100))
    
    deployment_status = Column(Enum(ReleaseDeploymentStatus), default=ReleaseDeploymentStatus.open)
    
    packages = relationship('Package', backref='release', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Release {self.name}>'

class PackageDeployment(db.Model):
    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey('package.id'), nullable=False)
    target_id = Column(Integer, ForeignKey('deployment_target.id'), nullable=False)
    status = Column(Enum(PackageDeploymentStatus), default=PackageDeploymentStatus.not_deployed)
    deployed_at = Column(DateTime, default=datetime.utcnow)
    
    target = relationship('DeploymentTarget')

    def __repr__(self):
        return f'<StartDeployment Pkg:{self.package_id} Target:{self.target_id} Status:{self.status}>'

class Package(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    url = Column(String(255)) # Nexus URL
    status = Column(Enum(PackageStatus), default=PackageStatus.registered)
    status_message = Column(String(255))
    
    # New Relationship
    deployments = relationship('PackageDeployment', backref='package', lazy=True, cascade="all, delete-orphan")

    release_id = Column(Integer, ForeignKey('release.id'), nullable=False)

    # Self-referential many-to-many relationship
    dependencies = relationship(
        'Package',
        secondary=package_dependencies,
        primaryjoin=(id == package_dependencies.c.requirer_id),
        secondaryjoin=(id == package_dependencies.c.provider_id),
        backref=db.backref('required_by', lazy='dynamic'),
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Package {self.name}>'

class ScheduledDeployment(db.Model):
    id = Column(Integer, primary_key=True)
    release_id = Column(Integer, ForeignKey('release.id'), nullable=False)
    target_id = Column(Integer, ForeignKey('deployment_target.id'), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    release = relationship('Release', backref=db.backref('schedules', lazy=True, cascade="all, delete-orphan"))
    target = relationship('DeploymentTarget', backref='schedules')

class User(db.Model):
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    role = Column(Enum(Role), nullable=False, default=Role.viewer)

    def __repr__(self):
        return f'<User {self.username} ({self.role.name})>'

class EventLog(db.Model):
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    category = Column(String(50), nullable=False)
    operation = Column(String(50), nullable=False)
    description = Column(String(255))
    user = Column(String(50))

    def __repr__(self):
        return f'<Event {self.operation} on {self.category} at {self.timestamp}>'
