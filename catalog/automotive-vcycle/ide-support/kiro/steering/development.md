---
inclusion: always
---

# Development Guidelines

## Spec-Driven Development Workflow

When doing spec-driven development or implementing, always reference and align with:

- **Business Requirements Document (BRD)** - Contains stakeholder needs and business objectives
- **Software Requirements Specification (SRS)** - Defines functional and non-functional requirements
- **Technical Design Document (TDD)** - Outlines system architecture and implementation approach

## Code Architecture Patterns

When implementing features, leverage existing codebase patterns:

- **Base and Abstract Classes** - Extend existing base implementations rather than creating new ones
- **Common Modules** - Utilize shared components in `com.androidauto.common` package for:
  - Error handling and circuit breakers
  - Location services and caching
  - Network interceptors and logging
  - Result and model abstractions

## Android Automotive OS UI Guidelines

### Accessibility Requirements
- Use high contrast colors suitable for automotive environments
- Implement large, touch-friendly UI elements (minimum 48dp touch targets)
- Support voice commands and minimal interaction patterns
- Ensure readability in various lighting conditions

### Layout Structure
- Design for landscape orientation and driver distraction guidelines
- Group related information in clear, scannable sections
- Minimize cognitive load with simple, hierarchical layouts
- Use consistent spacing and alignment patterns

### Visual Design
- Apply automotive-specific color schemes and gradients
- Use clear, bold typography optimized for quick reading
- Implement smooth animations that don't distract while driving
- Follow Material Design for Cars guidelines

## Code Quality Standards

- Follow Kotlin coding conventions and Android best practices
- Implement proper error handling using the existing `Result` wrapper
- Use dependency injection patterns consistently
- Write clean, self-documenting code with meaningful variable names
- Ensure thread safety for background operations
