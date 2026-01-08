# PyBirch Issues and Feature Requests

This document tracks known issues, bugs, and feature requests for the PyBirch project. Issues are organized by category for better tracking and prioritization.

## User Interface Issues

### Layout and Styling

- **Live Activity Positioning**: Live activity section should be repositioned beneath the information cards for improved visual hierarchy.

- **Quick Actions Spacing**: Increase the top margin for the quick actions section to maintain consistency with other page elements.

- **Instrument Status Badge**: The "Idle" status indicator on the instrument detail page should be rendered as a badge component instead of highlighted text.

## Data Synchronization

### Instrument Management

- **Database-Scan Synchronization**: PyBirch instruments need to be synchronized between the PyBirch database and PyBirch scan modules to ensure data consistency across the application.

## Feature Requests

### Instrument Control Enhancements

- **Movement Settings**: Consider implementing a shift movement setting to complement the existing absolute move functionality, providing more flexible instrument positioning options.

### Scan Architecture Improvements

- **Mid-Scan Processing**: Add support for executing custom processes during scan execution. Use cases include:
  - Autofocusing a laser based on focus scan output
  - Automated device detection using CNN models on 2D reflectance scans
  
- **Conditional Scan Logic**: Extend the PyBirch scan architecture to support conditional objects, enabling scan workflows with `while` loop logic in addition to the current `for` loop implementations.

### Automation System

- **Event-Driven Notifications and Actions**: Implement a comprehensive automation system that links to database objects and their status changes. The system should support:

  **Notification Examples:**
  - Slack notifications upon scan completion
  - Email alerts when precursors are marked as almost empty (with configurable delay to prevent accidental triggers)
  - Slack messages to device channels when equipment status changes
  - Alerts when bug issues are submitted
  - Notifications for assigned equipment issues
  
  **API Integration Examples:**
  - Automated API calls to university systems for precursor replacement when supplies are depleted
  
  **System Requirements:**
  - Dynamic configuration supporting various database objects
  - User-friendly interface for creating and managing automations
  - Scalable architecture allowing easy expansion to new object types, notification channels, and API integrations

---

*Last Updated: January 7, 2026*