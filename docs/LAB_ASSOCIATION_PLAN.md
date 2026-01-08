# Lab Association & Autofill Feature Plan

## Overview

This document outlines the implementation plan for:
1. Adding lab associations to all database objects
2. Implementing an autofill feature for Lab and Project fields

## Current State Analysis

### Objects WITH lab_id
| Model | Has lab_id | Has project_id | Notes |
|-------|------------|----------------|-------|
| Template | ✅ | ✅ | Full support |
| Project | ✅ | N/A | Lab contains projects |
| Sample | ✅ | ✅ | Full support |
| Instrument | ✅ | ❌ | Has lab_id only |
| Equipment | ✅ | ❌ | Has lab_id only |
| User | ✅ | ❌ | Users belong to labs |

### Objects WITHOUT lab_id (Need to Add)
| Model | Has lab_id | Has project_id | Action Required |
|-------|------------|----------------|-----------------|
| Precursor | ❌ | ✅ | Add lab_id |
| Procedure | ❌ | ✅ | Add lab_id |
| Scan | ❌ | ✅ | Add lab_id |
| Queue | ❌ | ✅ | Add lab_id |
| ScanTemplate | ❌ | ✅ | Add lab_id |
| QueueTemplate | ❌ | ✅ | Add lab_id |
| FabricationRun | ❌ | ✅ | Add lab_id |

## Implementation Plan

### Phase 1: Database Schema Updates

#### 1.1 Add lab_id to Missing Models
Files to modify:
- `database/models.py` - Add lab_id foreign key and relationship to:
  - Precursor
  - Procedure
  - Scan
  - Queue
  - ScanTemplate
  - QueueTemplate
  - FabricationRun

#### 1.2 Create Migration Script
- Create `database/migrations/add_lab_id_to_all_objects.py`
- Add lab_id column to all affected tables
- Set default lab_id from associated project where possible

### Phase 2: Service Layer Updates

#### 2.1 Update Services (database/services.py)
For each affected model, update:
- Create methods to accept lab_id
- Get/List methods to filter by lab_id
- Update methods to handle lab_id changes
- `_to_dict` methods to include lab_id and lab_name

### Phase 3: User Preferences / Autofill System

#### 3.1 User Preferences Model
Add to User model or create UserPreferences:
```python
class UserPreferences(Base):
    user_id: int  # FK to User
    default_lab_id: Optional[int]  # FK to Lab
    default_project_id: Optional[int]  # FK to Project
    preferences_data: JSON  # Additional preferences
```

Or simpler: Add fields directly to User model:
- `default_lab_id`
- `default_project_id`

#### 3.2 Preferences API Endpoints
- `GET /api/user/preferences` - Get current user's defaults
- `PUT /api/user/preferences` - Update user's defaults
- `POST /api/user/preferences/set-default-lab/<lab_id>`
- `POST /api/user/preferences/set-default-project/<project_id>`

#### 3.3 Session-Based Defaults (Alternative/Complement)
Store in browser session/localStorage:
- Last used lab_id
- Last used project_id
- Auto-populate from these on new forms

### Phase 4: UI Updates

#### 4.1 Form Templates
Update all form templates to:
- Pre-populate lab_id from user defaults (unless template overrides)
- Pre-populate project_id from user defaults (unless template overrides)
- Add "Set as Default" buttons/links next to dropdowns

Forms to update:
- `sample_form.html`
- `precursor_form.html`
- `procedure_form.html`
- `instrument_form.html`
- `equipment_form.html`
- `scan_form.html` (if exists)
- `queue_form.html` (if exists)

#### 4.2 Add Lab Field to Forms Missing It
- `precursor_form.html` - Add lab dropdown
- `procedure_form.html` - Add lab dropdown

#### 4.3 User Preferences UI
- Add "Defaults" section to user profile page
- Quick-set buttons in navigation or header

### Phase 5: Routes Updates

#### 5.1 Update Create/Edit Routes
For each entity:
- Pass user's default lab_id and project_id to templates
- Apply defaults when no template is used
- Template values override defaults

#### 5.2 New API Routes
- User preferences endpoints
- "Set default" quick actions

## Priority Order

1. **High Priority**: Add lab_id to Precursor, Procedure (most commonly created)
2. **High Priority**: Implement user preferences storage
3. **Medium Priority**: Update forms with autofill
4. **Medium Priority**: Add lab_id to Scan, Queue, templates
5. **Lower Priority**: Migration for existing data

## Testing Checklist

- [ ] All objects can be created with lab_id
- [ ] All objects display lab association
- [ ] User defaults are saved and loaded correctly
- [ ] Template values override user defaults
- [ ] Existing objects without lab_id still work
- [ ] Lab filtering works across all entity types

## Rollback Plan

- Migration script includes DOWN migration
- All lab_id fields are nullable to support existing data
- UI gracefully handles missing lab associations
