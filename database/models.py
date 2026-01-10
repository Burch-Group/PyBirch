"""
PyBirch Database Models
=======================
SQLAlchemy ORM models for the PyBirch laboratory data management system.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, Date,
    ForeignKey, JSON, LargeBinary, Index, UniqueConstraint, Numeric,
    create_engine, event
)
from sqlalchemy.orm import (
    DeclarativeBase, relationship, Mapped, mapped_column, Session
)
from sqlalchemy.ext.hybrid import hybrid_property
import json


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class TrashableMixin:
    """
    Mixin for soft-delete (trash) functionality.
    
    When trashed_at is set, the item is considered "in trash" and should be:
    - Hidden from normal queries (unless show_trashed filter is enabled)
    - Permanently deleted after 30 days
    
    For labs/projects, trashing cascades to all referenced objects.
    For queues, trashing propagates to scans.
    For locations, trashing propagates to child locations.
    """
    trashed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None, index=True)
    trashed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    @property
    def is_trashed(self) -> bool:
        """Check if this item is in the trash."""
        return self.trashed_at is not None
    
    @property
    def days_until_permanent_deletion(self) -> Optional[int]:
        """Days remaining before permanent deletion (30 day retention)."""
        if not self.trashed_at:
            return None
        from datetime import timedelta
        deletion_date = self.trashed_at + timedelta(days=30)
        remaining = (deletion_date - datetime.utcnow()).days
        return max(0, remaining)
    
    @property
    def scheduled_deletion_date(self) -> Optional[datetime]:
        """The date when this item will be permanently deleted."""
        if not self.trashed_at:
            return None
        from datetime import timedelta
        return self.trashed_at + timedelta(days=30)


class ArchivableMixin:
    """
    Mixin for archive functionality.
    
    When archived_at is set, the item is considered "archived" and should be:
    - Hidden from normal queries (unless show_archived filter is enabled)
    - Preserved indefinitely (unlike trash, archived items are never auto-deleted)
    
    Use archiving for old items that are no longer actively used but should
    be kept for historical reference.
    """
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None, index=True)
    archived_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    @property
    def is_archived(self) -> bool:
        """Check if this item is archived."""
        return self.archived_at is not None


# ============================================================
# TEMPLATES - Generic template system for any entity type
# ============================================================

class Template(TrashableMixin, ArchivableMixin, Base):
    """
    Generic template for any entity type.
    Allows users to create presets for samples, procedures, equipment, etc.
    """
    __tablename__ = "templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sample', 'precursor', 'procedure', etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # Stores default values and structure
    status: Mapped[str] = mapped_column(String(20), default='active')  # 'active', 'draft', 'archived'
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    project: Mapped[Optional["Project"]] = relationship("Project", foreign_keys=[project_id])
    
    __table_args__ = (
        UniqueConstraint('name', 'entity_type', name='uq_template_name_type'),
        Index('idx_templates_entity_type', 'entity_type'),
        Index('idx_templates_project', 'project_id'),
    )
    
    def __repr__(self):
        return f"<Template(id={self.id}, name='{self.name}', type='{self.entity_type}')>"


# ============================================================
# LABS & PROJECTS - Organizational structure
# ============================================================

class Lab(TrashableMixin, ArchivableMixin, Base):
    """
    Research laboratory with members, equipment, and projects.
    Provides organizational hierarchy for managing research groups.
    
    WARNING: Trashing a lab will cascade to all related objects (projects,
    samples, equipment, etc.) after the 30-day retention period.
    """
    __tablename__ = "labs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True)  # Short code like "CHEN-LAB"
    university: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # University affiliation
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Lab-specific settings
    # Configurable type options for this lab
    location_types: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ['room', 'cabinet', 'shelf', ...]
    equipment_types: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ['glovebox', 'chamber', ...]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members: Mapped[List["LabMember"]] = relationship("LabMember", back_populates="lab", cascade="all, delete-orphan")
    teams: Mapped[List["Team"]] = relationship("Team", back_populates="lab", cascade="all, delete-orphan")
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="lab")
    equipment: Mapped[List["Equipment"]] = relationship("Equipment", back_populates="lab")
    instruments: Mapped[List["Instrument"]] = relationship("Instrument", back_populates="lab")
    samples: Mapped[List["Sample"]] = relationship("Sample", back_populates="lab")
    locations: Mapped[List["Location"]] = relationship("Location", back_populates="lab", foreign_keys="Location.lab_id")
    
    __table_args__ = (
        Index('idx_labs_university', 'university'),
    )
    
    def __repr__(self):
        return f"<Lab(id={self.id}, name='{self.name}', university='{self.university}')>"


class LabMember(Base):
    """
    Members of a lab with their roles.
    Supports principal investigator, administrators, and regular members.
    """
    __tablename__ = "lab_members"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default='member')  # 'principal_investigator', 'administrator', 'member', 'student', 'visiting'
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'Professor', 'Postdoc', 'PhD Student', etc.
    orcid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ORCID identifier
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    office_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    access_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # When privileges expire (default 6 months after left_at)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", back_populates="members")
    project_memberships: Mapped[List["ProjectMember"]] = relationship("ProjectMember", back_populates="lab_member", cascade="all, delete-orphan")
    team_memberships: Mapped[List["TeamMember"]] = relationship("TeamMember", back_populates="lab_member", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('lab_id', 'email', name='uq_lab_member_email'),
        Index('idx_lab_members_lab', 'lab_id'),
        Index('idx_lab_members_role', 'role'),
    )
    
    def __repr__(self):
        return f"<LabMember(id={self.id}, name='{self.name}', role='{self.role}')>"


class Project(TrashableMixin, ArchivableMixin, Base):
    """
    Research project within a lab.
    Groups related samples, scans, and procedures together.
    
    WARNING: Trashing a project will cascade to all related objects
    (samples, scans, queues, etc.) after the 30-day retention period.
    """
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Short project code
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='active')  # 'planning', 'active', 'paused', 'completed', 'archived'
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    funding_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    grant_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    budget: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", back_populates="projects")
    members: Mapped[List["ProjectMember"]] = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    samples: Mapped[List["Sample"]] = relationship("Sample", back_populates="project")
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="project")
    queues: Mapped[List["Queue"]] = relationship("Queue", back_populates="project")
    procedures: Mapped[List["Procedure"]] = relationship("Procedure", back_populates="project")
    precursors: Mapped[List["Precursor"]] = relationship("Precursor", back_populates="project")
    wastes: Mapped[List["Waste"]] = relationship("Waste", back_populates="project")
    
    __table_args__ = (
        UniqueConstraint('lab_id', 'code', name='uq_project_code'),
        Index('idx_projects_lab', 'lab_id'),
        Index('idx_projects_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"


class ProjectMember(Base):
    """
    Members assigned to a project with specific roles.
    """
    __tablename__ = "project_members"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey('projects.id'), nullable=False)
    lab_member_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('lab_members.id'), nullable=True)
    # For external collaborators not in the lab
    external_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_affiliation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default='member')  # 'lead', 'member', 'collaborator', 'advisor'
    permissions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Fine-grained permissions
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="members")
    lab_member: Mapped[Optional["LabMember"]] = relationship("LabMember", back_populates="project_memberships")
    
    __table_args__ = (
        UniqueConstraint('project_id', 'lab_member_id', name='uq_project_lab_member'),
        Index('idx_project_members_project', 'project_id'),
    )
    
    def __repr__(self):
        name = self.lab_member.name if self.lab_member else self.external_name
        return f"<ProjectMember(id={self.id}, project_id={self.project_id}, name='{name}')>"


class ItemGuest(Base):
    """
    Guest access to individual items (samples, scans, queues, projects).
    Allows collaborators to access a subset of lab data.
    """
    __tablename__ = "item_guests"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sample', 'scan', 'queue', 'project'
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_affiliation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    access_level: Mapped[str] = mapped_column(String(50), default='view')  # 'view', 'edit', 'full'
    access_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # For secure access
    granted_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', 'guest_email', name='uq_item_guest'),
        Index('idx_item_guests_entity', 'entity_type', 'entity_id'),
        Index('idx_item_guests_email', 'guest_email'),
    )
    
    def __repr__(self):
        return f"<ItemGuest(id={self.id}, entity='{self.entity_type}:{self.entity_id}', guest='{self.guest_email}')>"


# ============================================================
# TEAMS
# ============================================================

class Team(TrashableMixin, Base):
    """
    Teams within a lab for grouping members.
    Teams can be granted permissions to projects and other entities,
    avoiding the need to add each member individually.
    """
    __tablename__ = "teams"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Short code like "SYNTH-TEAM"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # For UI display, e.g., '#3b82f6'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", back_populates="teams")
    members: Mapped[List["TeamMember"]] = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    access_grants: Mapped[List["TeamAccess"]] = relationship("TeamAccess", back_populates="team", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('lab_id', 'name', name='uq_team_name'),
        UniqueConstraint('lab_id', 'code', name='uq_team_code'),
        Index('idx_teams_lab', 'lab_id'),
    )
    
    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}', lab_id={self.lab_id})>"


class TeamMember(Base):
    """
    Links lab members to teams with specific roles.
    A lab member can belong to multiple teams.
    """
    __tablename__ = "team_members"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey('teams.id'), nullable=False)
    lab_member_id: Mapped[int] = mapped_column(Integer, ForeignKey('lab_members.id'), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default='member')  # 'lead', 'member'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="members")
    lab_member: Mapped["LabMember"] = relationship("LabMember", back_populates="team_memberships")
    
    __table_args__ = (
        UniqueConstraint('team_id', 'lab_member_id', name='uq_team_member'),
        Index('idx_team_members_team', 'team_id'),
        Index('idx_team_members_lab_member', 'lab_member_id'),
    )
    
    def __repr__(self):
        return f"<TeamMember(id={self.id}, team_id={self.team_id}, lab_member_id={self.lab_member_id})>"


class TeamAccess(Base):
    """
    Grants a team access to an entity (project, sample, queue, etc.).
    All active members of the team inherit this access.
    """
    __tablename__ = "team_access"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey('teams.id'), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'project', 'sample', 'queue', 'equipment'
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    access_level: Mapped[str] = mapped_column(String(50), default='view')  # 'view', 'edit', 'full'
    granted_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="access_grants")
    
    __table_args__ = (
        UniqueConstraint('team_id', 'entity_type', 'entity_id', name='uq_team_access'),
        Index('idx_team_access_team', 'team_id'),
        Index('idx_team_access_entity', 'entity_type', 'entity_id'),
    )
    
    def __repr__(self):
        return f"<TeamAccess(id={self.id}, team_id={self.team_id}, entity='{self.entity_type}:{self.entity_id}')>"


# ============================================================
# USERS & AUTHENTICATION
# ============================================================

class User(Base):
    """
    User accounts for authentication and authorization.
    """
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Optional for OAuth users
    google_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, unique=True)  # Google OAuth ID
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default='user')  # 'admin', 'user', 'viewer'
    lab_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('labs.id'), nullable=True)
    default_lab_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('labs.id'), nullable=True)  # User's preferred lab for autofill
    default_project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)  # User's preferred project for autofill
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    orcid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ORCID identifier
    office_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lab = relationship("Lab", backref="users", foreign_keys=[lab_id])
    default_lab = relationship("Lab", foreign_keys=[default_lab_id])
    default_project = relationship("Project", foreign_keys=[default_project_id])
    issues_created = relationship("Issue", back_populates="reporter", foreign_keys="Issue.reporter_id")
    issues_assigned = relationship("Issue", back_populates="assignee", foreign_keys="Issue.assignee_id")
    pins = relationship("UserPin", back_populates="user", cascade="all, delete-orphan")
    owned_equipment = relationship("Equipment", back_populates="owner")
    equipment_issues_created = relationship("EquipmentIssue", back_populates="reporter", foreign_keys="EquipmentIssue.reporter_id")
    equipment_issues_assigned = relationship("EquipmentIssue", back_populates="assignee", foreign_keys="EquipmentIssue.assignee_id")
    driver_issues_created = relationship("DriverIssue", back_populates="reporter", foreign_keys="DriverIssue.reporter_id")
    driver_issues_assigned = relationship("DriverIssue", back_populates="assignee", foreign_keys="DriverIssue.assignee_id")
    qr_scans = relationship("QrCodeScan", back_populates="user", cascade="all, delete-orphan")
    page_views = relationship("PageView", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class UserPin(Base):
    """
    Tracks items pinned by users for quick access.
    """
    __tablename__ = "user_pins"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sample', 'scan', 'queue', 'project', etc.
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="pins")
    
    __table_args__ = (
        Index('idx_user_pins_user', 'user_id'),
        Index('idx_user_pins_entity', 'entity_type', 'entity_id'),
        # Unique constraint: user can only pin an entity once
        Index('uq_user_pins', 'user_id', 'entity_type', 'entity_id', unique=True),
    )
    
    def __repr__(self):
        return f"<UserPin(user_id={self.user_id}, entity={self.entity_type}:{self.entity_id})>"


class QrCodeScan(Base):
    """
    Tracks QR code scans by users for analytics and statistics.
    """
    __tablename__ = "qr_code_scans"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sample', 'equipment', 'lab', etc.
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scanned_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="qr_scans")
    
    __table_args__ = (
        Index('idx_qr_scans_user', 'user_id'),
        Index('idx_qr_scans_entity', 'entity_type', 'entity_id'),
        Index('idx_qr_scans_timestamp', 'scanned_at'),
    )
    
    def __repr__(self):
        return f"<QrCodeScan(user_id={self.user_id}, entity={self.entity_type}:{self.entity_id})>"


class PageView(Base):
    """
    Tracks page views and time spent on pages for analytics.
    """
    __tablename__ = "page_views"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    page_path: Mapped[str] = mapped_column(String(500), nullable=False)  # URL path (without query string)
    page_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Page title if available
    referrer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Referring page
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Time spent on page
    scroll_pixels: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Total scroll distance in pixels
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Browser session tracking
    
    # Relationships
    user = relationship("User", back_populates="page_views")
    
    __table_args__ = (
        Index('idx_page_views_user', 'user_id'),
        Index('idx_page_views_path', 'page_path'),
        Index('idx_page_views_timestamp', 'viewed_at'),
        Index('idx_page_views_session', 'session_id'),
    )
    
    def __repr__(self):
        return f"<PageView(user_id={self.user_id}, path={self.page_path}, duration={self.duration_seconds}s, scroll={self.scroll_pixels}px)>"


class UserSettings(Base):
    """
    User-specific settings and preferences including theme configuration.
    
    Industry-standard theme implementation:
    - theme_mode: 'light', 'dark', or 'system' (follows OS preference)
    - active_theme_id: Links to custom UserTheme, null means default theme
    - settings stored as JSON for extensibility
    """
    __tablename__ = "user_settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    
    # Theme settings
    theme_mode: Mapped[str] = mapped_column(String(20), default='system')  # 'light', 'dark', 'system'
    active_theme_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('user_themes.id', ondelete='SET NULL'), nullable=True)
    
    # General settings (JSON for extensibility)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    # Example settings stored in JSON:
    # {
    #     "compact_tables": false,
    #     "show_notifications": true,
    #     "default_page_size": 20,
    #     "sidebar_collapsed": false,
    #     "date_format": "YYYY-MM-DD",
    #     "time_format": "24h"
    # }
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="settings_obj", uselist=False)
    active_theme = relationship("UserTheme", foreign_keys=[active_theme_id])
    
    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, theme_mode='{self.theme_mode}')>"


class UserTheme(Base):
    """
    Custom user-defined themes with light and dark palettes.
    
    Industry-standard CSS Custom Properties (CSS Variables) format:
    - Colors stored in HSL format for easy manipulation
    - Separate palettes for light and dark modes
    - Based on CSS Custom Properties specification (W3C)
    
    Palette structure follows Material Design / Tailwind conventions:
    {
        "primary": "#0078d4",
        "primary_dark": "#106ebe",
        "secondary": "#5c6bc0",
        "success": "#28a745",
        "warning": "#ffc107",
        "error": "#dc3545",
        "info": "#17a2b8",
        "bg_primary": "#ffffff",
        "bg_secondary": "#f8f9fa",
        "bg_tertiary": "#e9ecef",
        "text_primary": "#212529",
        "text_secondary": "#6c757d",
        "text_muted": "#adb5bd",
        "border": "#dee2e6"
    }
    """
    __tablename__ = "user_themes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Light mode color palette (CSS custom properties values)
    light_palette: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    # Dark mode color palette (CSS custom properties values)
    dark_palette: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    # Theme metadata
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # Allow sharing with other users
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # User's default theme
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="themes")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_theme_name'),
        Index('idx_user_themes_user', 'user_id'),
        Index('idx_user_themes_public', 'is_public'),
    )
    
    def __repr__(self):
        return f"<UserTheme(id={self.id}, name='{self.name}', user_id={self.user_id})>"


# ============================================================
# ISSUE TRACKING
# ============================================================

class Issue(TrashableMixin, ArchivableMixin, Base):
    """
    Issue reports for tracking bugs, feature requests, and problems.
    """
    __tablename__ = "issues"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps_to_reproduce: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default='bug')  # 'bug', 'feature', 'question', 'enhancement'
    priority: Mapped[str] = mapped_column(String(50), default='medium')  # 'low', 'medium', 'high', 'critical'
    status: Mapped[str] = mapped_column(String(50), default='open')  # 'open', 'in_progress', 'resolved', 'closed', 'wont_fix'
    reporter_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    related_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # URL where issue occurred
    browser_info: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reporter = relationship("User", back_populates="issues_created", foreign_keys=[reporter_id])
    assignee = relationship("User", back_populates="issues_assigned", foreign_keys=[assignee_id])
    
    __table_args__ = (
        Index('idx_issues_status', 'status'),
        Index('idx_issues_reporter', 'reporter_id'),
        Index('idx_issues_assignee', 'assignee_id'),
    )
    
    def __repr__(self):
        return f"<Issue(id={self.id}, title='{self.title}', status='{self.status}')>"


class IssueUpdate(Base):
    """
    Update/comment entries for issues. Supports all issue types (site-wide, equipment, driver).
    Creates a timeline/history of troubleshooting and resolution progress.
    """
    __tablename__ = "issue_updates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Polymorphic link to any issue type
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'issue', 'equipment_issue', 'driver_issue'
    issue_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Update content
    update_type: Mapped[str] = mapped_column(String(50), default='comment')  # 'comment', 'status_change', 'resolution', 'workaround'
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # The actual update text
    
    # Status change tracking (if this update changed status)
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Who made this update
    author_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Denormalized for display
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationship
    author = relationship("User", foreign_keys=[author_id])
    
    __table_args__ = (
        Index('idx_issue_updates_issue', 'issue_type', 'issue_id'),
        Index('idx_issue_updates_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<IssueUpdate(id={self.id}, issue_type='{self.issue_type}', issue_id={self.issue_id})>"


# ============================================================
# INSTRUMENTS (formerly Equipment) - PyBirch-compatible devices
# ============================================================

class Instrument(TrashableMixin, ArchivableMixin, Base):
    """
    Laboratory instruments that interface with PyBirch.
    Maps to PyBirch's Movement and Measurement instruments.
    """
    __tablename__ = "instruments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    instrument_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'movement', 'measurement', 'fabrication'
    pybirch_class: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g., 'Keithley2400', 'NewportStage'
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='available')  # 'available', 'in_use', 'maintenance', 'retired'
    specifications: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Technical specs
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('templates.id'), nullable=True)
    equipment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=True)  # Parent equipment
    driver_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('drivers.id'), nullable=True)  # Link to driver code
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", back_populates="instruments")
    template: Mapped[Optional["Template"]] = relationship("Template", foreign_keys=[template_id])
    equipment: Mapped[Optional["Equipment"]] = relationship("Equipment", back_populates="instruments")
    status_history: Mapped[List["InstrumentStatus"]] = relationship("InstrumentStatus", back_populates="instrument", order_by="InstrumentStatus.updated_at.desc()", cascade="all, delete-orphan")
    driver: Mapped[Optional["Driver"]] = relationship("Driver")
    computer_bindings: Mapped[List["ComputerBinding"]] = relationship("ComputerBinding", back_populates="instrument", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Instrument(id={self.id}, name='{self.name}', type='{self.instrument_type}')>"


class InstrumentStatus(Base):
    """
    Real-time instrument status tracking.
    Captures connection state, settings, and errors for PyBirch instruments.
    """
    __tablename__ = "instrument_status"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey('instruments.id'), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='disconnected')  # 'connected', 'disconnected', 'error', 'busy'
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Current instrument settings
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    instrument: Mapped["Instrument"] = relationship("Instrument", back_populates="status_history")
    
    __table_args__ = (
        Index('idx_instrument_status_instrument', 'instrument_id'),
        Index('idx_instrument_status_status', 'status'),
        Index('idx_instrument_status_updated', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<InstrumentStatus(id={self.id}, instrument_id={self.instrument_id}, status='{self.status}')>"


# ============================================================
# DRIVERS - Stored instrument code
# ============================================================

class Driver(TrashableMixin, ArchivableMixin, Base):
    """
    Stores executable Python code for PyBirch instruments.
    This is the driver code - reusable across multiple physical instruments.
    Enables browser-based instrument creation and per-computer discovery.
    """
    __tablename__ = "drivers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)  # Class name
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Classification
    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'movement' or 'measurement'
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'Lock-In Amplifier', 'Stage', etc.
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # The actual code
    source_code: Mapped[str] = mapped_column(Text, nullable=False)  # Full Python class definition (main file)
    base_class: Mapped[str] = mapped_column(String(100), nullable=False)  # 'FakeMeasurementInstrument', etc.
    dependencies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ['pyvisa', 'numpy', ...]
    
    # Multi-file driver support (for drivers with dependencies)
    # Naming convention: Main file must be named 'driver.py' or '<ClassName>_driver.py'
    driver_files: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{path: str, size: int, modified: str}, ...]
    main_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Path to main file within the folder (e.g., 'driver.py' or 'MyInstrument_driver.py')
    has_folder_upload: Mapped[bool] = mapped_column(Boolean, default=False)  # True if driver was uploaded as a folder
    
    # Configuration schema
    settings_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # JSON Schema for settings
    default_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Metadata for measurement instruments
    data_columns: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ['X', 'Y', 'R']
    data_units: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)    # ['V', 'V', 'V']
    
    # Metadata for movement instruments
    position_column: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    position_units: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Status
    status: Mapped[Optional[str]] = mapped_column(String(50), default='operational')  # operational, development, testing, deprecated, experimental
    
    # Ownership and versioning
    lab_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('labs.id'), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # Shared across labs?
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)  # Shipped with PyBirch?
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)  # Approved for use?
    
    # Audit
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab")
    versions: Mapped[List["DriverVersion"]] = relationship(
        "DriverVersion", back_populates="driver", 
        order_by="DriverVersion.version.desc()", cascade="all, delete-orphan"
    )
    issues: Mapped[List["DriverIssue"]] = relationship(
        "DriverIssue", back_populates="driver",
        order_by="DriverIssue.created_at.desc()", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_driver_type', 'instrument_type'),
        Index('idx_driver_lab', 'lab_id'),
        Index('idx_driver_category', 'category'),
    )
    
    def __repr__(self):
        return f"<Driver(id={self.id}, name='{self.name}', type='{self.instrument_type}')>"


class DriverVersion(Base):
    """
    Version history for drivers.
    Allows rollback and audit trail for code changes.
    """
    __tablename__ = "driver_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(Integer, ForeignKey('drivers.id'), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    driver: Mapped["Driver"] = relationship("Driver", back_populates="versions")
    
    __table_args__ = (
        Index('idx_driver_version_driver', 'driver_id'),
        UniqueConstraint('driver_id', 'version', name='uq_driver_version'),
    )
    
    def __repr__(self):
        return f"<DriverVersion(id={self.id}, driver_id={self.driver_id}, version={self.version})>"


class DriverIssue(TrashableMixin, ArchivableMixin, Base):
    """
    Issue tracking for driver problems, bugs, feature requests, etc.
    Helps track issues with specific instrument code/drivers.
    """
    __tablename__ = "driver_issues"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(Integer, ForeignKey('drivers.id'), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default='bug')  # 'bug', 'feature', 'compatibility', 'documentation', 'performance', 'other'
    priority: Mapped[str] = mapped_column(String(50), default='medium')  # 'low', 'medium', 'high', 'critical'
    status: Mapped[str] = mapped_column(String(50), default='open')  # 'open', 'in_progress', 'resolved', 'closed', 'wont_fix'
    reporter_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps_to_reproduce: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Which version has this issue
    fixed_in_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Which version fixed it
    environment_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # OS, Python version, etc.
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_steps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Steps to resolve/workaround
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    driver: Mapped["Driver"] = relationship("Driver", back_populates="issues")
    reporter = relationship("User", back_populates="driver_issues_created", foreign_keys=[reporter_id])
    assignee = relationship("User", back_populates="driver_issues_assigned", foreign_keys=[assignee_id])
    
    __table_args__ = (
        Index('idx_driver_issues_driver', 'driver_id'),
        Index('idx_driver_issues_status', 'status'),
        Index('idx_driver_issues_priority', 'priority'),
        Index('idx_driver_issues_reporter', 'reporter_id'),
        Index('idx_driver_issues_assignee', 'assignee_id'),
    )
    
    def __repr__(self):
        return f"<DriverIssue(id={self.id}, driver_id={self.driver_id}, title='{self.title}')>"


class Computer(TrashableMixin, ArchivableMixin, Base):
    """
    Represents a physical computer that can have instruments bound to it.
    Stores computer identification info and a user-friendly nickname.
    """
    __tablename__ = "computers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    
    # Computer identification
    computer_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)  # hostname
    computer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # MAC address or UUID
    nickname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Friendly name for searching
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Additional notes about this computer
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Physical location
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    bindings: Mapped[List["ComputerBinding"]] = relationship("ComputerBinding", back_populates="computer")
    
    __table_args__ = (
        Index('idx_computer_name', 'computer_name'),
        Index('idx_computer_nickname', 'nickname'),
        Index('idx_computer_lab', 'lab_id'),
    )
    
    def __repr__(self):
        return f"<Computer(id={self.id}, name='{self.computer_name}', nickname='{self.nickname}')>"


class ComputerBinding(Base):
    """
    Binds instrument instances to specific computers.
    Enables auto-discovery of instruments per PyBirch instance.
    Tracks last adapter and connection info for each computer.
    """
    __tablename__ = "computer_bindings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey('instruments.id'), nullable=False)
    computer_id_fk: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('computers.id'), nullable=True)
    
    # Computer identification (kept for backward compatibility, will be synced from Computer)
    computer_name: Mapped[str] = mapped_column(String(255), nullable=False)  # hostname
    computer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # MAC address or UUID
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # OS username
    
    # Connection info (last known)
    adapter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # VISA address
    adapter_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'GPIB', 'USB', 'Serial', 'TCP'
    
    # Status
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)  # Primary computer for this instrument
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    instrument: Mapped["Instrument"] = relationship("Instrument", back_populates="computer_bindings")
    computer: Mapped[Optional["Computer"]] = relationship("Computer", back_populates="bindings")
    
    __table_args__ = (
        UniqueConstraint('instrument_id', 'computer_name', name='uq_instrument_computer'),
        Index('idx_computer_binding_computer', 'computer_name'),
        Index('idx_computer_binding_instrument', 'instrument_id'),
    )
    
    def __repr__(self):
        return f"<ComputerBinding(id={self.id}, instrument_id={self.instrument_id}, computer='{self.computer_name}')>"


# ============================================================
# EQUIPMENT - Large lab equipment (gloveboxes, chambers, etc.)
# ============================================================

class Equipment(TrashableMixin, ArchivableMixin, Base):
    """
    Large laboratory equipment like gloveboxes, deposition chambers, photolithography machines.
    These are not PyBirch-controlled instruments but contain or support instruments.
    """
    __tablename__ = "equipment"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Configurable per lab
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='operational')  # 'operational', 'maintenance', 'offline', 'retired'
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)  # Responsible person
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    warranty_expiration: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_maintenance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_maintenance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    maintenance_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    specifications: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Technical specs
    documentation_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Manual/docs link
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", back_populates="equipment")
    owner: Mapped[Optional["User"]] = relationship("User", back_populates="owned_equipment")
    instruments: Mapped[List["Instrument"]] = relationship("Instrument", back_populates="equipment")
    procedure_associations: Mapped[List["ProcedureEquipment"]] = relationship("ProcedureEquipment", back_populates="equipment")
    images: Mapped[List["EquipmentImage"]] = relationship("EquipmentImage", back_populates="equipment", cascade="all, delete-orphan")
    issues: Mapped[List["EquipmentIssue"]] = relationship("EquipmentIssue", back_populates="equipment", cascade="all, delete-orphan")
    fabrication_runs: Mapped[List["FabricationRunEquipment"]] = relationship("FabricationRunEquipment", back_populates="equipment")
    maintenance_tasks: Mapped[List["MaintenanceTask"]] = relationship("MaintenanceTask", back_populates="equipment", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_equipment_lab', 'lab_id'),
        Index('idx_equipment_owner', 'owner_id'),
        Index('idx_equipment_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Equipment(id={self.id}, name='{self.name}', type='{self.equipment_type}')>"


class EquipmentImage(Base):
    """Images associated with equipment."""
    __tablename__ = "equipment_images"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)  # Primary/thumbnail image
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="images")
    
    __table_args__ = (
        Index('idx_equipment_images_equipment', 'equipment_id'),
    )


class EquipmentIssue(TrashableMixin, ArchivableMixin, Base):
    """
    Issue tracking for equipment problems, maintenance requests, etc.
    """
    __tablename__ = "equipment_issues"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default='malfunction')  # 'malfunction', 'maintenance', 'safety', 'consumables', 'other'
    priority: Mapped[str] = mapped_column(String(50), default='medium')  # 'low', 'medium', 'high', 'critical'
    status: Mapped[str] = mapped_column(String(50), default='open')  # 'open', 'in_progress', 'resolved', 'closed', 'wont_fix'
    reporter_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps_to_reproduce: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)  # Repair/maintenance cost
    downtime_hours: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)  # Equipment downtime
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="issues")
    reporter = relationship("User", back_populates="equipment_issues_created", foreign_keys=[reporter_id])
    assignee = relationship("User", back_populates="equipment_issues_assigned", foreign_keys=[assignee_id])
    
    __table_args__ = (
        Index('idx_equipment_issues_equipment', 'equipment_id'),
        Index('idx_equipment_issues_status', 'status'),
        Index('idx_equipment_issues_reporter', 'reporter_id'),
        Index('idx_equipment_issues_assignee', 'assignee_id'),
    )
    
    def __repr__(self):
        return f"<EquipmentIssue(id={self.id}, equipment_id={self.equipment_id}, title='{self.title}')>"


class MaintenanceTask(TrashableMixin, Base):
    """
    Recurring maintenance tasks for equipment.
    When a task is due, it automatically creates an EquipmentIssue.
    Once that issue is resolved, the wait period begins again.
    """
    __tablename__ = "maintenance_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)  # Days between maintenance
    
    # Issue template fields - used when creating the maintenance issue
    issue_title: Mapped[str] = mapped_column(String(255), nullable=False)
    issue_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issue_category: Mapped[str] = mapped_column(String(50), default='maintenance')
    issue_priority: Mapped[str] = mapped_column(String(50), default='medium')
    default_assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Tracking fields
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    current_issue_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('equipment_issues.id'), nullable=True)
    
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="maintenance_tasks")
    default_assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[default_assignee_id])
    current_issue: Mapped[Optional["EquipmentIssue"]] = relationship("EquipmentIssue", foreign_keys=[current_issue_id])
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_id])
    
    __table_args__ = (
        Index('idx_maintenance_tasks_equipment', 'equipment_id'),
        Index('idx_maintenance_tasks_active', 'is_active'),
        Index('idx_maintenance_tasks_next_due', 'next_due_date'),
    )
    
    def __repr__(self):
        return f"<MaintenanceTask(id={self.id}, equipment_id={self.equipment_id}, name='{self.name}')>"


# ============================================================
# PRECURSORS & MATERIALS
# ============================================================

class Precursor(TrashableMixin, ArchivableMixin, Base):
    """
    Chemical precursors and materials used in sample fabrication.
    """
    __tablename__ = "precursors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    chemical_formula: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cas_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lot_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    purity: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)  # Percentage
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'solid', 'liquid', 'gas', 'solution'
    status: Mapped[str] = mapped_column(String(50), default='new')  # 'new', 'in_use', 'low', 'empty', 'expired'
    concentration: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    concentration_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    storage_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expiration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    safety_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('templates.id'), nullable=True)
    
    # Relationships
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="precursors")
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    template: Mapped[Optional["Template"]] = relationship("Template", foreign_keys=[template_id])
    inventory: Mapped[List["PrecursorInventory"]] = relationship("PrecursorInventory", back_populates="precursor")
    sample_associations: Mapped[List["SamplePrecursor"]] = relationship("SamplePrecursor", back_populates="precursor")
    procedure_associations: Mapped[List["ProcedurePrecursor"]] = relationship("ProcedurePrecursor", back_populates="precursor")
    
    __table_args__ = (
        Index('idx_precursors_lab', 'lab_id'),
    )
    
    def __repr__(self):
        return f"<Precursor(id={self.id}, name='{self.name}', formula='{self.chemical_formula}')>"


class PrecursorInventory(Base):
    """
    Inventory tracking for precursors.
    """
    __tablename__ = "precursor_inventory"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    precursor_id: Mapped[int] = mapped_column(Integer, ForeignKey('precursors.id'), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    received_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    opened_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    precursor: Mapped["Precursor"] = relationship("Precursor", back_populates="inventory")
    
    def __repr__(self):
        return f"<PrecursorInventory(id={self.id}, precursor_id={self.precursor_id}, qty={self.quantity})>"


# ============================================================
# WASTE
# ============================================================

class Waste(TrashableMixin, ArchivableMixin, Base):
    """
    Waste containers and disposal tracking.
    
    Waste objects link to precursors (source materials) and locations.
    They track the fill level and collection status of waste containers.
    """
    __tablename__ = "wastes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    waste_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'chemical', 'biological', 'sharps', 'general', 'radioactive', 'electronic'
    hazard_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'flammable', 'corrosive', 'toxic', 'oxidizer', 'reactive', 'non-hazardous'
    container_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'bottle', 'drum', 'sharps_container', 'bag', 'box', 'other'
    container_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., '4L', '20L', '55gal'
    
    # Fill level tracking
    current_fill_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True, default=0)  # 0-100%
    fill_status: Mapped[str] = mapped_column(String(50), default='empty')  # 'empty', 'partial', 'nearly_full', 'full', 'overfull'
    
    # Status for lifecycle management
    status: Mapped[str] = mapped_column(String(50), default='active')  # 'active', 'awaiting_collection', 'collected', 'disposed', 'closed'
    
    # Content information
    contents_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Detailed description of waste contents
    contains_chemicals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # List of chemicals in the waste
    ph_range: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., '2-4', 'neutral', '10-12'
    
    # Regulatory and safety
    epa_waste_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # EPA hazardous waste code if applicable
    un_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # UN identification number
    sds_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Reference to safety data sheet
    special_handling: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Special handling instructions
    
    # Dates
    opened_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    full_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # When container became full
    collection_requested_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    collected_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    disposal_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Owner and tracking
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)  # Owner (defaults to creator)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    disposal_vendor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manifest_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Disposal manifest/tracking number
    
    # Additional data
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('templates.id'), nullable=True)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="wastes")
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
    template: Mapped[Optional["Template"]] = relationship("Template", foreign_keys=[template_id])
    precursor_associations: Mapped[List["WastePrecursor"]] = relationship("WastePrecursor", back_populates="waste", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_wastes_lab', 'lab_id'),
        Index('idx_wastes_status', 'status'),
        Index('idx_wastes_fill_status', 'fill_status'),
        Index('idx_wastes_owner', 'owner_id'),
    )
    
    def __repr__(self):
        return f"<Waste(id={self.id}, name='{self.name}', status='{self.status}', fill='{self.fill_status}')>"


class WastePrecursor(Base):
    """
    Junction table linking waste containers to source precursors.
    Tracks which precursors contributed to a waste container.
    """
    __tablename__ = "waste_precursors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    waste_id: Mapped[int] = mapped_column(Integer, ForeignKey('wastes.id'), nullable=False)
    precursor_id: Mapped[int] = mapped_column(Integer, ForeignKey('precursors.id'), nullable=False)
    quantity: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    quantity_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    added_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    waste: Mapped["Waste"] = relationship("Waste", back_populates="precursor_associations")
    precursor: Mapped["Precursor"] = relationship("Precursor")
    
    __table_args__ = (
        UniqueConstraint('waste_id', 'precursor_id', name='uq_waste_precursor'),
        Index('idx_waste_precursors_waste', 'waste_id'),
        Index('idx_waste_precursors_precursor', 'precursor_id'),
    )
    
    def __repr__(self):
        return f"<WastePrecursor(waste_id={self.waste_id}, precursor_id={self.precursor_id})>"


# ============================================================
# PROCEDURES
# ============================================================

class Procedure(TrashableMixin, ArchivableMixin, Base):
    """
    Fabrication procedures for sample preparation.
    """
    __tablename__ = "procedures"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    procedure_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'deposition', 'annealing', etc.
    version: Mapped[str] = mapped_column(String(20), default='1.0')
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Array of step objects
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Default parameters
    failure_modes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Possible failure modes for this procedure
    estimated_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    safety_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('templates.id'), nullable=True)
    
    # Relationships
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="procedures")
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    template: Mapped[Optional["Template"]] = relationship("Template", foreign_keys=[template_id])
    equipment_associations: Mapped[List["ProcedureEquipment"]] = relationship("ProcedureEquipment", back_populates="procedure")
    precursor_associations: Mapped[List["ProcedurePrecursor"]] = relationship("ProcedurePrecursor", back_populates="procedure")
    fabrication_runs: Mapped[List["FabricationRun"]] = relationship("FabricationRun", back_populates="procedure")
    
    __table_args__ = (
        Index('idx_procedures_lab', 'lab_id'),
    )
    
    def __repr__(self):
        return f"<Procedure(id={self.id}, name='{self.name}', type='{self.procedure_type}')>"


class ProcedureEquipment(Base):
    """Junction table: Equipment used in procedures."""
    __tablename__ = "procedure_equipment"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    procedure_id: Mapped[int] = mapped_column(Integer, ForeignKey('procedures.id'), nullable=False)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    procedure: Mapped["Procedure"] = relationship("Procedure", back_populates="equipment_associations")
    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="procedure_associations")
    
    __table_args__ = (
        UniqueConstraint('procedure_id', 'equipment_id', name='uq_procedure_equipment'),
    )


class ProcedurePrecursor(Base):
    """Junction table: Precursors used in procedures."""
    __tablename__ = "procedure_precursors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    procedure_id: Mapped[int] = mapped_column(Integer, ForeignKey('procedures.id'), nullable=False)
    precursor_id: Mapped[int] = mapped_column(Integer, ForeignKey('precursors.id'), nullable=False)
    quantity: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    quantity_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # 'target material', 'solvent', 'dopant'
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    procedure: Mapped["Procedure"] = relationship("Procedure", back_populates="precursor_associations")
    precursor: Mapped["Precursor"] = relationship("Precursor", back_populates="procedure_associations")
    
    __table_args__ = (
        UniqueConstraint('procedure_id', 'precursor_id', name='uq_procedure_precursor'),
    )


# ============================================================
# SAMPLES
# ============================================================

class Sample(TrashableMixin, ArchivableMixin, Base):
    """
    Physical samples on which scans are run.
    Extends the PyBirch Sample class concept with full database support.
    """
    __tablename__ = "samples"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)
    sample_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # User-friendly ID
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    material: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Maps to PyBirch Sample.material
    sample_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'thin_film', 'bulk', etc.
    substrate: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dimensions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"length": 10, "width": 10, "unit": "mm"}
    status: Mapped[str] = mapped_column(String(50), default='active')  # 'active', 'consumed', 'archived'
    parent_sample_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('samples.id'), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    additional_tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Maps to PyBirch Sample.additional_tags
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Path to sample image
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('templates.id'), nullable=True)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", back_populates="samples")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="samples")
    template: Mapped[Optional["Template"]] = relationship("Template", foreign_keys=[template_id])
    parent_sample: Mapped[Optional["Sample"]] = relationship("Sample", remote_side=[id], backref="derived_samples")
    precursor_associations: Mapped[List["SamplePrecursor"]] = relationship("SamplePrecursor", back_populates="sample")
    fabrication_runs: Mapped[List["FabricationRun"]] = relationship("FabricationRun", back_populates="sample")
    queues: Mapped[List["Queue"]] = relationship("Queue", back_populates="sample")
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="sample")
    
    __table_args__ = (
        Index('idx_samples_status', 'status'),
        Index('idx_samples_created', 'created_at'),
    )
    
    def to_pybirch_sample(self):
        """Convert to PyBirch Sample object for compatibility."""
        from pybirch.queue.samples import Sample as PyBirchSample
        import numpy as np
        
        sample = PyBirchSample(
            ID=self.sample_id,
            material=self.material or '',
            additional_tags=self.additional_tags or [],
            image=np.array([])  # Image loading would need separate handling
        )
        return sample
    
    @classmethod
    def from_pybirch_sample(cls, pybirch_sample, **kwargs):
        """Create from PyBirch Sample object."""
        return cls(
            sample_id=pybirch_sample.ID,
            material=pybirch_sample.material,
            additional_tags=pybirch_sample.additional_tags,
            **kwargs
        )
    
    def __repr__(self):
        return f"<Sample(id={self.id}, sample_id='{self.sample_id}', material='{self.material}')>"


class SamplePrecursor(Base):
    """Junction table: Precursors used to make samples."""
    __tablename__ = "sample_precursors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_id: Mapped[int] = mapped_column(Integer, ForeignKey('samples.id'), nullable=False)
    precursor_id: Mapped[int] = mapped_column(Integer, ForeignKey('precursors.id'), nullable=False)
    quantity_used: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    quantity_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'primary', 'dopant', 'solvent'
    composition_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    sample: Mapped["Sample"] = relationship("Sample", back_populates="precursor_associations")
    precursor: Mapped["Precursor"] = relationship("Precursor", back_populates="sample_associations")
    
    __table_args__ = (
        UniqueConstraint('sample_id', 'precursor_id', 'role', name='uq_sample_precursor_role'),
    )


# ============================================================
# SAMPLE FABRICATION HISTORY
# ============================================================

class FabricationRun(TrashableMixin, ArchivableMixin, Base):
    """Records of procedure executions for sample fabrication."""
    __tablename__ = "fabrication_runs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_id: Mapped[int] = mapped_column(Integer, ForeignKey('samples.id'), nullable=False)
    procedure_id: Mapped[int] = mapped_column(Integer, ForeignKey('procedures.id'), nullable=False)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    run_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Order in fabrication sequence
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='pending')  # 'pending', 'in_progress', 'completed', 'failed'
    failure_mode: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Selected failure mode when status is 'failed'
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Operator who ran the fabrication
    actual_parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    results: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Environmental conditions at time of run (can affect results)
    weather_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Expected structure: {
    #   "temperature_c": float,      # Outside temperature in Celsius
    #   "humidity_percent": float,   # Relative humidity %
    #   "pressure_hpa": float,       # Atmospheric pressure in hPa
    #   "weather_description": str,  # e.g., "Clear", "Cloudy", "Rain"
    #   "wind_speed_ms": float,      # Wind speed in m/s
    #   "location": str,             # Location name/coordinates
    #   "recorded_at": str,          # ISO timestamp when weather was fetched
    #   "source": str,               # e.g., "OpenWeatherMap", "manual"
    # }
    
    # Relationships
    sample: Mapped["Sample"] = relationship("Sample", back_populates="fabrication_runs")
    procedure: Mapped["Procedure"] = relationship("Procedure", back_populates="fabrication_runs")
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    equipment_used: Mapped[List["FabricationRunEquipment"]] = relationship("FabricationRunEquipment", back_populates="fabrication_run")
    precursors_consumed: Mapped[List["FabricationRunPrecursor"]] = relationship("FabricationRunPrecursor", back_populates="fabrication_run")
    
    __table_args__ = (
        Index('idx_fabrication_sample', 'sample_id'),
        Index('idx_fabrication_lab', 'lab_id'),
    )


class FabricationRunEquipment(Base):
    """Equipment used in specific fabrication run."""
    __tablename__ = "fabrication_run_equipment"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fabrication_run_id: Mapped[int] = mapped_column(Integer, ForeignKey('fabrication_runs.id'), nullable=False)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=False)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    fabrication_run: Mapped["FabricationRun"] = relationship("FabricationRun", back_populates="equipment_used")
    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="fabrication_runs")


class FabricationRunPrecursor(Base):
    """Precursors consumed in specific fabrication run."""
    __tablename__ = "fabrication_run_precursors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fabrication_run_id: Mapped[int] = mapped_column(Integer, ForeignKey('fabrication_runs.id'), nullable=False)
    precursor_id: Mapped[int] = mapped_column(Integer, ForeignKey('precursors.id'), nullable=False)
    quantity_consumed: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    quantity_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    fabrication_run: Mapped["FabricationRun"] = relationship("FabricationRun", back_populates="precursors_consumed")
    precursor: Mapped["Precursor"] = relationship("Precursor")


# ============================================================
# SCAN & QUEUE TEMPLATES
# ============================================================

class ScanTemplate(TrashableMixin, ArchivableMixin, Base):
    """
    Templates for scan configurations.
    Stores instrument config, parameters, and measurement objects.
    """
    __tablename__ = "scan_templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    scan_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # '1D Scan', '2D Scan', etc.
    job_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'Raman', 'Transport', etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scan_tree_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Serialized ScanTreeModel
    instrument_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Instrument settings
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Scan parameters
    measurement_objects: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of measurement objects
    estimated_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    queue_template_items: Mapped[List["QueueTemplateItem"]] = relationship("QueueTemplateItem", back_populates="scan_template")
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="scan_template")
    
    __table_args__ = (
        Index('idx_scan_templates_lab', 'lab_id'),
    )
    
    def __repr__(self):
        return f"<ScanTemplate(id={self.id}, name='{self.name}', type='{self.scan_type}')>"


class QueueTemplate(TrashableMixin, ArchivableMixin, Base):
    """
    Templates for queue configurations.
    Defines a sequence of scan templates to be executed.
    """
    __tablename__ = "queue_templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(20), default='SERIAL')  # 'SERIAL', 'PARALLEL'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    items: Mapped[List["QueueTemplateItem"]] = relationship("QueueTemplateItem", back_populates="queue_template", order_by="QueueTemplateItem.position")
    queues: Mapped[List["Queue"]] = relationship("Queue", back_populates="queue_template")
    
    __table_args__ = (
        Index('idx_queue_templates_lab', 'lab_id'),
    )
    
    def __repr__(self):
        return f"<QueueTemplate(id={self.id}, name='{self.name}')>"


class QueueTemplateItem(Base):
    """Scans included in a queue template."""
    __tablename__ = "queue_template_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    queue_template_id: Mapped[int] = mapped_column(Integer, ForeignKey('queue_templates.id'), nullable=False)
    scan_template_id: Mapped[int] = mapped_column(Integer, ForeignKey('scan_templates.id'), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # Order in queue
    repeat_count: Mapped[int] = mapped_column(Integer, default=1)
    delay_before_seconds: Mapped[int] = mapped_column(Integer, default=0)
    condition_expression: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Optional conditional execution
    parameter_overrides: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Override scan template params
    
    # Relationships
    queue_template: Mapped["QueueTemplate"] = relationship("QueueTemplate", back_populates="items")
    scan_template: Mapped["ScanTemplate"] = relationship("ScanTemplate", back_populates="queue_template_items")
    
    __table_args__ = (
        UniqueConstraint('queue_template_id', 'position', name='uq_queue_template_position'),
    )


# ============================================================
# EXECUTED QUEUES & SCANS
# ============================================================

class Queue(TrashableMixin, ArchivableMixin, Base):
    """
    Executed queue records.
    Maps to PyBirch Queue class with database persistence.
    
    Note: Trashing a queue will propagate to all associated scans.
    """
    __tablename__ = "queues"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    queue_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # Maps to PyBirch Queue.QID
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sample_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('samples.id'), nullable=True)
    queue_template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('queue_templates.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='pending')  # Maps to QueueState
    execution_mode: Mapped[str] = mapped_column(String(20), default='SERIAL')  # 'SERIAL', 'PARALLEL'
    priority: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_scans: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_scans: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Operator who ran the queue
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wandb_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Link to W&B
    serialized_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Full queue serialization
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="queues")
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    sample: Mapped[Optional["Sample"]] = relationship("Sample", back_populates="queues")
    queue_template: Mapped[Optional["QueueTemplate"]] = relationship("QueueTemplate", back_populates="queues")
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="queue", order_by="Scan.position_in_queue")
    logs: Mapped[List["QueueLog"]] = relationship("QueueLog", back_populates="queue", order_by="QueueLog.timestamp", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_queues_status', 'status'),
        Index('idx_queues_sample', 'sample_id'),
        Index('idx_queues_project', 'project_id'),
        Index('idx_queues_lab', 'lab_id'),
    )
    
    def __repr__(self):
        return f"<Queue(id={self.id}, queue_id='{self.queue_id}', status='{self.status}')>"


class QueueLog(Base):
    """
    Log entries for queue execution.
    Captures events, warnings, and errors during queue operation.
    """
    __tablename__ = "queue_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    queue_id: Mapped[int] = mapped_column(Integer, ForeignKey('queues.id'), nullable=False)
    scan_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Associated scan_id string
    level: Mapped[str] = mapped_column(String(20), default='INFO')  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    queue: Mapped["Queue"] = relationship("Queue", back_populates="logs")
    
    __table_args__ = (
        Index('idx_queue_logs_queue', 'queue_id'),
        Index('idx_queue_logs_level', 'level'),
        Index('idx_queue_logs_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<QueueLog(id={self.id}, queue_id={self.queue_id}, level='{self.level}')>"


class ScanLog(Base):
    """
    Log entries for individual scan execution.
    Captures events, warnings, and errors during scan operation.
    More fine-grained than queue logs - tracks scan phases, instrument operations, etc.
    """
    __tablename__ = "scan_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey('scans.id'), nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'setup', 'running', 'cleanup', 'analysis'
    level: Mapped[str] = mapped_column(String(20), default='INFO')  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    progress: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)  # 0-100 percentage
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    scan: Mapped["Scan"] = relationship("Scan", back_populates="logs")
    
    __table_args__ = (
        Index('idx_scan_logs_scan', 'scan_id'),
        Index('idx_scan_logs_level', 'level'),
        Index('idx_scan_logs_phase', 'phase'),
        Index('idx_scan_logs_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<ScanLog(id={self.id}, scan_id={self.scan_id}, level='{self.level}')>"


class Scan(TrashableMixin, ArchivableMixin, Base):
    """
    Executed scan records.
    Maps to PyBirch Scan class with database persistence.
    """
    __tablename__ = "scans"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # User-friendly ID
    queue_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('queues.id'), nullable=True)
    sample_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('samples.id'), nullable=True)
    scan_template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('scan_templates.id'), nullable=True)
    position_in_queue: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Scan settings from PyBirch ScanSettings
    project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scan_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scan_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    job_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Owner/operator of the scan
    additional_tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Execution info
    status: Mapped[str] = mapped_column(String(50), default='pending')  # Maps to ScanState
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Configuration and results
    scan_tree_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Serialized scan tree
    instrument_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wandb_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="scans")
    lab: Mapped[Optional["Lab"]] = relationship("Lab", foreign_keys=[lab_id])
    queue: Mapped[Optional["Queue"]] = relationship("Queue", back_populates="scans")
    sample: Mapped[Optional["Sample"]] = relationship("Sample", back_populates="scans")
    scan_template: Mapped[Optional["ScanTemplate"]] = relationship("ScanTemplate", back_populates="scans")
    measurement_objects: Mapped[List["MeasurementObject"]] = relationship("MeasurementObject", back_populates="scan", cascade="all, delete-orphan")
    analysis_inputs: Mapped[List["AnalysisInput"]] = relationship("AnalysisInput", back_populates="scan")
    logs: Mapped[List["ScanLog"]] = relationship("ScanLog", back_populates="scan", order_by="ScanLog.timestamp", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_scans_status', 'status'),
        Index('idx_scans_sample', 'sample_id'),
        Index('idx_scans_queue', 'queue_id'),
        Index('idx_scans_project', 'project_id'),
        Index('idx_scans_lab', 'lab_id'),
    )
    
    @classmethod
    def from_pybirch_scan(cls, pybirch_scan, **kwargs):
        """Create from PyBirch Scan object."""
        settings = pybirch_scan.scan_settings
        return cls(
            scan_id=f"{settings.project_name}_{settings.scan_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            project_name=settings.project_name,
            scan_name=settings.scan_name,
            scan_type=settings.scan_type,
            job_type=settings.job_type,
            created_by=getattr(pybirch_scan, 'owner', None),  # Map PyBirch owner to created_by
            additional_tags=settings.additional_tags,
            status=settings.status,
            scan_tree_data=settings.scan_tree.serialize() if settings.scan_tree else None,
            **kwargs
        )
    
    def __repr__(self):
        return f"<Scan(id={self.id}, scan_id='{self.scan_id}', status='{self.status}')>"


# ============================================================
# MEASUREMENT DATA
# ============================================================

class MeasurementObject(Base):
    """
    Measurement objects collected during scans.
    Each scan can have multiple measurement objects (e.g., voltage, current, temperature).
    """
    __tablename__ = "measurement_objects"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey('scans.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g., 'voltage', 'current'
    instrument_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'numeric', 'array', 'image'
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    columns: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Column names for DataFrame
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    scan: Mapped["Scan"] = relationship("Scan", back_populates="measurement_objects")
    data_points: Mapped[List["MeasurementDataPoint"]] = relationship("MeasurementDataPoint", back_populates="measurement_object", cascade="all, delete-orphan")
    data_arrays: Mapped[List["MeasurementDataArray"]] = relationship("MeasurementDataArray", back_populates="measurement_object", cascade="all, delete-orphan")
    analysis_inputs: Mapped[List["AnalysisInput"]] = relationship("AnalysisInput", back_populates="measurement_object")
    
    __table_args__ = (
        Index('idx_measurement_objects_scan', 'scan_id'),
    )
    
    def __repr__(self):
        return f"<MeasurementObject(id={self.id}, name='{self.name}', scan_id={self.scan_id})>"


class MeasurementDataPoint(Base):
    """
    Individual numeric/scalar data points from measurements.
    Optimized for time-series and sequential measurement data.
    """
    __tablename__ = "measurement_data_points"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    measurement_object_id: Mapped[int] = mapped_column(Integer, ForeignKey('measurement_objects.id'), nullable=False)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sequence_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Position in measurement sequence
    
    # Store multiple columns as JSON for flexibility (matches DataFrame rows)
    values: Mapped[dict] = mapped_column(JSON, nullable=False)  # {"voltage": 1.5, "current": 0.001, "temperature": 298}
    
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional metadata
    
    # Relationships
    measurement_object: Mapped["MeasurementObject"] = relationship("MeasurementObject", back_populates="data_points")
    
    __table_args__ = (
        Index('idx_data_points_measurement', 'measurement_object_id'),
        Index('idx_data_points_sequence', 'measurement_object_id', 'sequence_index'),
    )
    
    def __repr__(self):
        return f"<MeasurementDataPoint(id={self.id}, seq={self.sequence_index})>"


class MeasurementDataArray(Base):
    """
    Array/vector data from measurements (for spectra, images, etc.).
    Stores binary data with metadata.
    """
    __tablename__ = "measurement_data_arrays"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    measurement_object_id: Mapped[int] = mapped_column(Integer, ForeignKey('measurement_objects.id'), nullable=False)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sequence_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_blob: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)  # Binary data
    data_format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'numpy', 'json', 'png'
    shape: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Array dimensions
    dtype: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Data type
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Path to external file
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional metadata
    
    # Relationships
    measurement_object: Mapped["MeasurementObject"] = relationship("MeasurementObject", back_populates="data_arrays")
    
    __table_args__ = (
        Index('idx_data_arrays_measurement', 'measurement_object_id'),
    )
    
    def __repr__(self):
        return f"<MeasurementDataArray(id={self.id}, format='{self.data_format}')>"


# ============================================================
# ANALYSIS
# ============================================================

class AnalysisMethod(Base):
    """
    Defined analysis methods/algorithms.
    """
    __tablename__ = "analysis_methods"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    method_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'fitting', 'extraction', 'transformation'
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    algorithm: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Description or reference
    parameters_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # JSON schema for params
    output_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # JSON schema for outputs
    script_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Path to analysis script
    version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    analyses: Mapped[List["Analysis"]] = relationship("Analysis", back_populates="method")
    
    def __repr__(self):
        return f"<AnalysisMethod(id={self.id}, name='{self.name}')>"


class Analysis(TrashableMixin, ArchivableMixin, Base):
    """
    Executed analysis records.
    """
    __tablename__ = "analyses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    analysis_method_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('analysis_methods.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='pending')  # 'pending', 'running', 'completed', 'failed'
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Parameters used
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Operator who ran the analysis
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    method: Mapped[Optional["AnalysisMethod"]] = relationship("AnalysisMethod", back_populates="analyses")
    inputs: Mapped[List["AnalysisInput"]] = relationship("AnalysisInput", back_populates="analysis", cascade="all, delete-orphan")
    results: Mapped[List["AnalysisResult"]] = relationship("AnalysisResult", back_populates="analysis", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_analyses_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Analysis(id={self.id}, analysis_id='{self.analysis_id}', status='{self.status}')>"


class AnalysisInput(Base):
    """Input data for analysis (can be from multiple scans/measurements)."""
    __tablename__ = "analysis_inputs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey('analyses.id'), nullable=False)
    measurement_object_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('measurement_objects.id'), nullable=True)
    scan_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('scans.id'), nullable=True)
    input_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # How this input is used
    data_range: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Subset of data to use
    
    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="inputs")
    measurement_object: Mapped[Optional["MeasurementObject"]] = relationship("MeasurementObject", back_populates="analysis_inputs")
    scan: Mapped[Optional["Scan"]] = relationship("Scan", back_populates="analysis_inputs")
    
    __table_args__ = (
        UniqueConstraint('analysis_id', 'measurement_object_id', 'input_role', name='uq_analysis_input'),
    )


class AnalysisResult(Base):
    """Analysis results."""
    __tablename__ = "analysis_results"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey('analyses.id'), nullable=False)
    result_name: Mapped[str] = mapped_column(String(255), nullable=False)
    result_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'scalar', 'array', 'plot', 'report'
    value: Mapped[Optional[float]] = mapped_column(Numeric(20, 10), nullable=True)  # For scalar results
    value_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    uncertainty: Mapped[Optional[float]] = mapped_column(Numeric(20, 10), nullable=True)
    data_blob: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)  # For array/binary results
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # For file-based results
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="results")
    
    __table_args__ = (
        Index('idx_analysis_results', 'analysis_id'),
    )
    
    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, name='{self.result_name}')>"


# ============================================================
# TAGGING & ORGANIZATION
# ============================================================

class Tag(Base):
    """Tags for organizing entities."""
    __tablename__ = "tags"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color code
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    entity_tags: Mapped[List["EntityTag"]] = relationship("EntityTag", back_populates="tag")
    
    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}')>"


class EntityTag(Base):
    """Polymorphic tagging table for any entity type."""
    __tablename__ = "entity_tags"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey('tags.id'), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sample', 'scan', 'queue', etc.
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Relationships
    tag: Mapped["Tag"] = relationship("Tag", back_populates="entity_tags")
    
    __table_args__ = (
        UniqueConstraint('tag_id', 'entity_type', 'entity_id', name='uq_entity_tag'),
        Index('idx_entity_tags', 'entity_type', 'entity_id'),
    )


# ============================================================
# ATTACHMENTS & FILES
# ============================================================

class EntityImage(TrashableMixin, ArchivableMixin, Base):
    """Images attached to any entity (samples, precursors, equipment, procedures)."""
    __tablename__ = "entity_images"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sample', 'precursor', 'equipment', 'procedure'
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # Original filename
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # UUID-based stored filename
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # User-provided name/title
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_entity_images', 'entity_type', 'entity_id'),
        Index('idx_entity_images_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<EntityImage(id={self.id}, entity='{self.entity_type}:{self.entity_id}', name='{self.name}')>"


class Attachment(TrashableMixin, ArchivableMixin, Base):
    """File attachments for any entity."""
    __tablename__ = "attachments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sample', 'scan', 'analysis', etc.
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # Original filename
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # UUID-based stored filename
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # User-provided name/title
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Legacy field, kept for compatibility
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Legacy field, kept for compatibility
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_attachments', 'entity_type', 'entity_id'),
        Index('idx_attachments_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Attachment(id={self.id}, name='{self.name}', filename='{self.filename}')>"


# ============================================================
# LOCATIONS - Physical locations in the lab
# ============================================================

class Location(TrashableMixin, Base):
    """
    Physical locations in the lab (rooms, cabinets, shelves, drawers, etc.).
    Supports hierarchical organization via parent_location_id.
    
    Note: Trashing a location will propagate to all child locations.
    """
    __tablename__ = "locations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    parent_location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('locations.id'), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'room', 'cabinet', 'shelf', 'drawer', 'fridge', 'freezer', 'bench', 'other'
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    room_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    building: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    floor: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    capacity: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "20 samples", "5 drawers"
    conditions: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g., "Room temp", "-20°C", "N2 atmosphere"
    access_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Instructions for accessing
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", back_populates="locations", foreign_keys=[lab_id])
    parent_location: Mapped[Optional["Location"]] = relationship("Location", remote_side=[id], backref="child_locations")
    object_locations: Mapped[List["ObjectLocation"]] = relationship("ObjectLocation", back_populates="location", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_location_lab', 'lab_id'),
        Index('idx_location_parent', 'parent_location_id'),
        Index('idx_location_type', 'location_type'),
    )
    
    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}', type='{self.location_type}')>"


class ObjectLocation(Base):
    """
    Links physical objects to their locations with optional notes/directions.
    Supports Equipment, Instruments, Samples, Precursors, Computers, and Wastes.
    """
    __tablename__ = "object_locations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey('locations.id'), nullable=False)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'equipment', 'instrument', 'sample', 'precursor', 'computer', 'waste'
    object_id: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # e.g., "in the blue bottle", "top shelf on the left"
    placed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    placed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)  # False for historical placements
    
    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="object_locations")
    
    __table_args__ = (
        Index('idx_object_location_location', 'location_id'),
        Index('idx_object_location_object', 'object_type', 'object_id'),
        Index('idx_object_location_current', 'is_current'),
    )
    
    def __repr__(self):
        return f"<ObjectLocation(id={self.id}, location={self.location_id}, object='{self.object_type}:{self.object_id}')>"


# ============================================================
# SUBSCRIBERS & NOTIFICATIONS
# ============================================================

class Subscriber(TrashableMixin, ArchivableMixin, Base):
    """
    Notification endpoint that can receive alerts about lab events.
    
    Industry-standard pub/sub pattern implementation supporting:
    - Email addresses/groups (SMTP/API)
    - Slack channels (incoming webhooks)
    - Slack users (via Slack API)
    - Generic webhooks (for integrations)
    - User preferences (managed in profile, not shown in subscriber list)
    
    Channel Types:
    - 'email': Email address or group
    - 'slack_channel': Slack channel webhook URL
    - 'slack_user': Slack user ID for DMs
    - 'webhook': Generic HTTP webhook endpoint
    - 'user': User's own notification preferences (internal use)
    """
    __tablename__ = "subscribers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey('labs.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # Display name like "Lab Slack Channel"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Channel configuration
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'email', 'slack_channel', 'slack_user', 'webhook', 'user'
    channel_address: Mapped[str] = mapped_column(String(500), nullable=False)  # Email, webhook URL, Slack user ID, etc.
    
    # For user-type subscribers, link to user
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Slack-specific configuration
    slack_workspace_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Slack workspace/team ID
    slack_channel_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Slack channel ID
    slack_bot_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Encrypted bot token (for user DMs)
    
    # Webhook-specific configuration  
    webhook_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # For webhook signature verification
    webhook_headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Custom headers to send
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # Email/webhook verification status
    last_notification_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)  # Track delivery failures
    
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", backref="subscribers")
    user: Mapped[Optional["User"]] = relationship("User", backref="subscriber_profiles")
    notification_rules: Mapped[List["NotificationRule"]] = relationship("NotificationRule", back_populates="subscriber", cascade="all, delete-orphan")
    notification_logs: Mapped[List["NotificationLog"]] = relationship("NotificationLog", back_populates="subscriber")
    
    __table_args__ = (
        Index('idx_subscriber_lab', 'lab_id'),
        Index('idx_subscriber_channel_type', 'channel_type'),
        Index('idx_subscriber_user', 'user_id'),
        Index('idx_subscriber_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Subscriber(id={self.id}, name='{self.name}', type='{self.channel_type}')>"


class NotificationRule(Base):
    """
    Configuration for which events trigger notifications to which subscribers.
    
    Supports:
    - Lab-wide notifications (project_id = null)
    - Project-specific notifications
    - Owner-only filtering for issues and waste
    - Custom JSON conditions for advanced filtering
    
    Event Types:
    - Scan/Queue: scan_status_change, queue_status_change, scan_completed, scan_failed
    - Issues: issue_created, issue_assigned, issue_status_change, issue_resolved
    - Equipment: equipment_status_change, maintenance_due, maintenance_completed
    - Samples: sample_created, fabrication_run_completed, fabrication_run_failed
    - Waste: waste_status_change, waste_fill_warning, waste_collection_requested
    - Lab: new_member_added, member_left
    """
    __tablename__ = "notification_rules"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscriber_id: Mapped[int] = mapped_column(Integer, ForeignKey('subscribers.id'), nullable=False)
    
    # Scope
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('projects.id'), nullable=True)  # null = lab-wide
    
    # Event configuration
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # The event type to listen for
    
    # Owner-based filtering (for issues and waste)
    owner_only: Mapped[bool] = mapped_column(Boolean, default=False)  # Only notify if user is owner/assignee
    
    # Condition filters (JSON for flexible filtering)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example conditions:
    # {"status": ["failed", "error"]} - Only for these statuses
    # {"priority": "high"} - Only high priority
    # {"equipment_id": 5} - Only for specific equipment
    # {"fill_percent_gte": 80} - Waste fill level threshold
    
    # Notification template customization
    custom_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Custom message template
    include_link: Mapped[bool] = mapped_column(Boolean, default=True)  # Include link to entity
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    subscriber: Mapped["Subscriber"] = relationship("Subscriber", back_populates="notification_rules")
    project: Mapped[Optional["Project"]] = relationship("Project", backref="notification_rules")
    
    __table_args__ = (
        Index('idx_notification_rule_subscriber', 'subscriber_id'),
        Index('idx_notification_rule_event', 'event_type'),
        Index('idx_notification_rule_project', 'project_id'),
        Index('idx_notification_rule_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<NotificationRule(id={self.id}, event='{self.event_type}', subscriber={self.subscriber_id})>"


class NotificationLog(Base):
    """
    Audit trail of sent notifications for debugging and analytics.
    
    Tracks:
    - What was sent
    - When it was sent
    - Success/failure status
    - Any error messages
    """
    __tablename__ = "notification_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscriber_id: Mapped[int] = mapped_column(Integer, ForeignKey('subscribers.id'), nullable=False)
    rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('notification_rules.id', ondelete='SET NULL'), nullable=True)
    
    # Event details
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'scan', 'issue', 'equipment', etc.
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Message sent
    message_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # For emails
    message_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Delivery status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending')  # 'pending', 'sent', 'delivered', 'failed', 'bounced'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timing
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Actor who triggered the event
    triggered_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    subscriber: Mapped["Subscriber"] = relationship("Subscriber", back_populates="notification_logs")
    rule: Mapped[Optional["NotificationRule"]] = relationship("NotificationRule", backref="logs")
    
    __table_args__ = (
        Index('idx_notification_log_subscriber', 'subscriber_id'),
        Index('idx_notification_log_event', 'event_type'),
        Index('idx_notification_log_status', 'status'),
        Index('idx_notification_log_created', 'created_at'),
        Index('idx_notification_log_entity', 'entity_type', 'entity_id'),
    )
    
    def __repr__(self):
        return f"<NotificationLog(id={self.id}, event='{self.event_type}', status='{self.status}')>"


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(Base):
    """Audit log for tracking changes to entities."""
    __tablename__ = "audit_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # 'create', 'update', 'delete'
    changed_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    old_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    performed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_time', 'performed_at'),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, entity='{self.entity_type}:{self.entity_id}', action='{self.action}')>"
