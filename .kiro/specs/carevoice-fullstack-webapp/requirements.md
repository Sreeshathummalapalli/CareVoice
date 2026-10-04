# Requirements Document: CareVoice Full-Stack Web Application

## Introduction

CareVoice Full-Stack Web Application is a complete, modern healthcare management platform built with React frontend, Flask REST API backend, and SQLite database. The system provides medication management, real-time voice reminders, health tracking, and voice assistant capabilities with a professional white background and healthcare green design aesthetic. This is a complete transformation from Python-only code to a production-ready web application.

## Technical Stack

**Frontend:**
- React.js 18+ (Single Page Application)
- TailwindCSS (white #FFFFFF background, green #166534 accents)
- Axios (API communication)
- React Router (navigation)
- Chart.js (health visualizations)
- Web Speech API (voice features)
- Browser Notification API (real reminders)

**Backend:**
- Flask 3.0+ (REST API)
- Flask-CORS (cross-origin requests)
- Flask-JWT-Extended (authentication)
- SQLAlchemy (database ORM)
- Tesseract OCR or cloud OCR API
- Groq LLM API (existing)

**Database:**
- SQLite (existing carevoice.db)
- Reuse existing schema

## Glossary

- **SPA**: Single Page Application - React frontend that runs in browser
- **REST API**: Backend endpoints that frontend calls for data
- **JWT**: JSON Web Token for secure authentication
- **Real-time Notification**: Browser notification that appears at scheduled time with action buttons
- **OCR**: Optical Character Recognition for prescription extraction
- **Voice Assistant**: Browser-based speech recognition and synthesis

## Requirements

### Requirement 1: React Frontend Architecture

**User Story:** As a developer, I want a modern React SPA frontend, so that users have a fast, responsive web application experience.

#### Acceptance Criteria

1. THE System SHALL use React.js with functional components and hooks
2. THE System SHALL use TailwindCSS with custom configuration for white background (#FFFFFF) and green theme (#166534)
3. THE System SHALL implement React Router for client-side navigation
4. THE System SHALL use Axios for all API communication with Flask backend
5. THE System SHALL store JWT tokens in localStorage for authentication
6. THE System SHALL implement responsive design with mobile-first approach
7. THE System SHALL render at breakpoints: mobile (<768px), tablet (768-1024px), desktop (>1024px)

---

### Requirement 2: Flask REST API Backend

**User Story:** As a frontend developer, I want a RESTful API backend, so that the React app can communicate with the database securely.

#### Acceptance Criteria

1. THE System SHALL implement Flask REST API with JSON responses
2. THE System SHALL use Flask-CORS to allow frontend requests from different origin
3. THE System SHALL implement JWT authentication with Flask-JWT-Extended
4. THE System SHALL provide endpoints for: /auth, /medicines, /health, /reminders, /voice
5. THE System SHALL validate all incoming requests with proper error handling
6. THE System SHALL use SQLAlchemy ORM to interact with SQLite database
7. THE System SHALL return appropriate HTTP status codes (200, 201, 400, 401, 404, 500)

---

### Requirement 3: User Authentication System

**User Story:** As a user, I want to register and login securely, so that my health data is protected.

#### Acceptance Criteria

1. WHEN a user submits registration form, THE System SHALL validate email uniqueness and password strength
2. WHEN credentials are valid, THE System SHALL hash password with bcrypt and store in database
3. WHEN a user logs in, THE System SHALL return JWT access token and refresh token
4. THE System SHALL include user_id in JWT payload for authorization
5. THE System SHALL protect all API endpoints except /auth/register and /auth/login with JWT middleware
6. WHEN token expires, THE System SHALL refresh token automatically or prompt re-login
7. THE System SHALL implement logout by clearing tokens from localStorage

---

### Requirement 4: Professional White & Green Design System

**User Story:** As a user, I want a clean, professional interface with white background and green accents, so that the app feels trustworthy and modern.

#### Acceptance Criteria

1. THE System SHALL use pure white (#FFFFFF) as primary background color throughout
2. THE System SHALL use healthcare green (#166534) for primary buttons, links, and accents
3. THE System SHALL use dark green (#14532D) for hover states
4. THE System SHALL use light sage green (#F0FDF4) for highlighted sections
5. THE System SHALL use Inter font family or system fonts for typography
6. THE System SHALL apply subtle shadows (0 2px 10px rgba(0,0,0,0.02)) to cards
7. THE System SHALL use 10px border radius for buttons and 14px for cards
8. THE System SHALL ensure WCAG AA contrast compliance for all text

---

### Requirement 5: Medicine Management with Manual Entry

**User Story:** As a user, I want to add medicines manually with dosage and schedule, so that I can track my medications.

#### Acceptance Criteria

1. WHEN a user clicks "Add Medicine", THE System SHALL display a modal form
2. THE form SHALL include fields: name, dosage, time slot, instructions, frequency
3. WHEN form is submitted, THE System SHALL POST to /api/medicines endpoint
4. THE backend SHALL validate data and save to medicines table with user_id
5. THE System SHALL display medicines in a card grid layout with image, name, dosage, time, status
6. WHEN a user clicks Edit, THE System SHALL pre-populate form and PUT to /api/medicines/{id}
7. WHEN a user clicks Delete, THE System SHALL confirm and DELETE to /api/medicines/{id}
8. THE System SHALL filter medicines by status (All, Pending, Taken, Skipped)

---

### Requirement 6: Prescription OCR Upload and Extraction

**User Story:** As a user, I want to upload a prescription image and extract medicines automatically, so that I can add multiple medicines quickly.

#### Acceptance Criteria

1. WHEN a user uploads an image, THE System SHALL accept JPG, PNG, PDF up to 10MB
2. THE System SHALL POST file to /api/prescriptions/upload endpoint
3. THE backend SHALL use Tesseract OCR or cloud API to extract text from image
4. THE backend SHALL use Groq LLM to parse text into structured medicine data
5. THE System SHALL return extracted medicines array with name, dosage, frequency, instructions
6. THE frontend SHALL display extracted data in editable table for user review
7. WHEN user confirms, THE System SHALL POST all medicines to /api/medicines/bulk
8. THE System SHALL save prescription image reference in database

---

### Requirement 7: Real-Time Browser Notifications for Medicine Reminders

**User Story:** As a user, I want to receive browser notifications at scheduled times with action buttons, so that I don't forget my medicines.

#### Acceptance Criteria

1. WHEN a medicine is added, THE System SHALL create reminder in reminders table with scheduled time
2. THE frontend SHALL request browser notification permission on first load
3. THE System SHALL poll /api/reminders/due endpoint every 30 seconds
4. WHEN current time matches reminder time (±1 minute), THE backend SHALL return due reminders
5. THE frontend SHALL display browser notification with: medicine name, dosage, and action buttons (Take, Snooze, Skip)
6. WHEN user clicks Take, THE System SHALL PUT /api/medicines/{id}/status with status="Taken"
7. WHEN user clicks Snooze, THE System SHALL PUT /api/reminders/{id}/snooze to reschedule +10 minutes
8. WHEN user clicks Skip, THE System SHALL PUT /api/medicines/{id}/status with status="Skipped"
9. WHEN permission denied, THE System SHALL display in-app notification banner as fallback

---

### Requirement 8: Dashboard with Today's Medicine Timeline

**User Story:** As a user, I want to see today's medicine schedule on my dashboard, so that I know what to take and when.

#### Acceptance Criteria

1. WHEN user navigates to dashboard, THE System SHALL GET /api/dashboard endpoint
2. THE backend SHALL return today's medicines sorted by time slot
3. THE System SHALL display timeline grouped by: Morning, Afternoon, Evening, Night
4. WHEN a user has no medicines, THE System SHALL display empty state: "No medicines scheduled today"
5. THE System SHALL show status badges: green (Taken), yellow (Pending), gray (Skipped)
6. THE System SHALL display quick stats: medicines today, health metrics recorded, upcoming reminders
7. THE System SHALL provide quick action buttons: Add Medicine, Record Health, Voice Assistant

---

### Requirement 9: Health Metrics Tracking and Visualization

**User Story:** As a user, I want to record health metrics and view trends, so that I can monitor my health over time.

#### Acceptance Criteria

1. WHEN user navigates to Health page, THE System SHALL display metric input form
2. THE form SHALL include: blood pressure (systolic/diastolic), blood sugar, weight, heart rate
3. WHEN form is submitted, THE System SHALL POST to /api/health endpoint with metric data
4. THE backend SHALL calculate status (Optimal, Normal, High, Low) based on medical thresholds
5. THE System SHALL display historical charts using Chart.js for selected metric
6. THE System SHALL allow date range selection: 7 days, 30 days, 90 days
7. THE System SHALL color-code chart points by status (green=Optimal, yellow=Normal, red=High/Low)
8. WHEN insufficient data, THE System SHALL display "Not enough data to show chart"

---

### Requirement 10: Voice Assistant with Speech Recognition

**User Story:** As a user, I want to interact with the app using voice commands, so that I can use it hands-free.

#### Acceptance Criteria

1. WHEN user clicks microphone button, THE System SHALL use Web Speech API to capture audio
2. THE System SHALL convert speech to text using browser's speech recognition
3. THE System SHALL POST transcribed text to /api/voice/command endpoint
4. THE backend SHALL classify intent: navigation, data entry, or general query
5. WHEN intent is navigation, THE System SHALL return page to navigate to
6. WHEN intent is data entry (e.g., "my blood pressure is 120 over 80"), THE System SHALL extract values and save
7. WHEN intent is query, THE System SHALL use Groq LLM to generate response with medical safety guardrails
8. THE System SHALL use Web Speech Synthesis API to speak response aloud
9. THE System SHALL display conversation history in chat bubbles (user=right, assistant=left)

---

### Requirement 11: Medicine Adherence History Tracking

**User Story:** As a user, I want to see my medicine-taking history, so that I can review my adherence over time.

#### Acceptance Criteria

1. WHEN a medicine status changes to Taken or Skipped, THE System SHALL POST to /api/history endpoint
2. THE backend SHALL log action with timestamp in medicine_history table
3. WHEN user views history page, THE System SHALL GET /api/history?range=week
4. THE System SHALL display chronological log with date, medicine, dosage, action, time
5. THE System SHALL calculate adherence percentage: (taken / (taken + skipped)) * 100
6. THE System SHALL display adherence metrics card on dashboard
7. THE System SHALL allow filtering by date range and specific medicine

---

### Requirement 12: Responsive Mobile-First Layout

**User Story:** As a mobile user, I want the app to work perfectly on my phone, so that I can manage health on-the-go.

#### Acceptance Criteria

1. THE System SHALL implement mobile-first CSS with TailwindCSS responsive utilities
2. THE System SHALL display bottom navigation bar on mobile (<768px) with 5 icons
3. THE System SHALL display sidebar navigation on desktop (≥768px)
4. THE System SHALL use single-column card layout on mobile, multi-column on desktop
5. THE System SHALL ensure touch targets are minimum 44px × 44px
6. THE System SHALL test layouts at: 375px (mobile), 768px (tablet), 1024px (desktop)
7. THE System SHALL ensure images and charts scale responsively without overflow

---

### Requirement 13: Multi-User Data Isolation and Security

**User Story:** As a user, I want my data to be private and secure, so that other users cannot access my health information.

#### Acceptance Criteria

1. THE System SHALL include user_id from JWT in all database queries
2. THE System SHALL filter all GET requests by authenticated user's ID
3. THE System SHALL validate user_id matches JWT payload before UPDATE/DELETE operations
4. THE System SHALL prevent SQL injection using SQLAlchemy parameterized queries
5. THE System SHALL hash passwords with bcrypt (min cost factor 12)
6. THE System SHALL validate JWT signature on every protected endpoint
7. THE System SHALL clear tokens and session data on logout

---

### Requirement 14: Error Handling and User Feedback

**User Story:** As a user, I want clear error messages and feedback, so that I know what went wrong and how to fix it.

#### Acceptance Criteria

1. WHEN API request fails, THE System SHALL display toast notification with error message
2. WHEN form validation fails, THE System SHALL show inline field errors in red
3. WHEN network request is pending, THE System SHALL display loading spinner
4. WHEN OCR extraction fails, THE System SHALL offer retry or manual entry options
5. WHEN voice recognition fails, THE System SHALL display "Couldn't hear clearly, try again"
6. WHEN success action completes, THE System SHALL show green success toast
7. THE System SHALL log all errors to browser console for debugging

---

### Requirement 15: Backend Notification Scheduler

**User Story:** As a system, I want to track due reminders efficiently, so that users receive timely notifications.

#### Acceptance Criteria

1. THE System SHALL implement GET /api/reminders/due endpoint
2. THE endpoint SHALL query reminders where reminder_time matches current time (±1 min window)
3. THE endpoint SHALL filter by active status and return user_id, medicine details
4. THE frontend SHALL poll this endpoint every 30 seconds when user is active
5. THE System SHALL update reminder status to "Completed" after notification is sent
6. WHEN user snoozes, THE System SHALL update reminder_time to current_time + 10 minutes
7. THE System SHALL handle multiple simultaneous reminders for same user

---

## Summary

This specification defines a complete full-stack web application with:
- **Frontend**: React SPA with white/green design
- **Backend**: Flask REST API with JWT auth
- **Database**: SQLite (existing)
- **Key Features**: Medicine management, real voice reminders, health tracking, voice assistant
- **Total Requirements**: 15 (streamlined from 30)
