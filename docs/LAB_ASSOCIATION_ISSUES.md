# Lab Association & Autofill - Known Issues

## Pre-Implementation Issues

### Issue #1: Inconsistent Lab Association
**Status**: To Fix  
**Priority**: High  
**Description**: Not all objects have lab_id field, making it impossible to filter by lab consistently.

**Affected Models**:
- Precursor - No lab_id
- Procedure - No lab_id
- Scan - No lab_id
- Queue - No lab_id
- ScanTemplate - No lab_id
- QueueTemplate - No lab_id
- FabricationRun - No lab_id

**Impact**: Users cannot organize or filter these objects by lab.

---

### Issue #2: No Default Value System
**Status**: To Fix  
**Priority**: High  
**Description**: Users must manually select lab and project for every new object, even though they rarely change.

**User Pain Points**:
- Repetitive form filling
- Easy to forget to set lab/project
- No way to remember last used values

---

### Issue #3: Template Override Behavior Undefined
**Status**: To Define  
**Priority**: Medium  
**Description**: Need to clarify how template values interact with user defaults.

**Questions to Resolve**:
- Should template lab_id override user default?
- Should user be able to override template values?
- What if template has no lab_id but user has default?

**Proposed Behavior**:
1. Template values take precedence over user defaults
2. User can always override in the form
3. If template has no lab_id, use user default

---

### Issue #4: Migration Data Consistency
**Status**: To Address  
**Priority**: Medium  
**Description**: Existing objects without lab_id need sensible defaults.

**Options**:
1. Leave as NULL (simplest)
2. Inherit from associated project's lab_id
3. Require manual assignment

**Recommended**: Option 2 - Inherit from project where possible, leave NULL otherwise.

---

### Issue #5: Cross-Lab Object References
**Status**: To Consider  
**Priority**: Low  
**Description**: Some objects may reference objects from different labs.

**Examples**:
- Precursor used by multiple labs
- Procedure shared across labs
- Equipment used by multiple projects in different labs

**Considerations**:
- Should we enforce same-lab relationships?
- Or allow cross-lab references with warnings?

**Recommended**: Allow cross-lab references (no enforcement), but show warnings in UI.

---

## Implementation Issues (Track During Development)

### Issue #6: Form Validation
**Status**: Pending  
**Priority**: Medium  
**Description**: Ensure lab_id validation is consistent.

- Some forms may require lab_id, others optional
- Decide on required vs optional policy

---

### Issue #7: API Backwards Compatibility  
**Status**: Pending  
**Priority**: Medium  
**Description**: Existing API calls may not include lab_id.

**Solution**: Make lab_id optional in API, use user default if not provided.

---

## Resolved Issues

(Move issues here once fixed)
