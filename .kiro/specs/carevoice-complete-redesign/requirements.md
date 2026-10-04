# Requirements Document

## Introduction

CareVoice is a comprehensive healthcare management application designed to help elderly users and their caregivers manage daily medicine schedules, track health metrics, receive personalized diet guidance, and interact with a bilingual voice assistant. The system provides a professional, accessible interface with features including prescription OCR extraction, real-time medicine reminders, health tracking with visualizations, and multi-user data isolation. The application prioritizes authentic user experiences with no fake data, ensuring that all displayed information comes directly from actual user inputs and database records.

## Glossary

- **System**: The CareVoice healthcare management application
- **User**: A registered individual using the application for personal healthcare management
- **Caregiver**: A family member or healthcare provider with access to a User's health information
- **Medicine**: A pharmaceutical substance with scheduled intake times and dosage information
- **Reminder**: A scheduled notification for medicine intake at a specific time
- **Health_Metric**: A recorded health measurement (blood pressure, blood sugar, weight, heart rate)
- **Prescription**: A medical document containing medicine prescriptions from a doctor
- **OCR_Engine**: Optical Character Recognition system for extracting text from prescription images
- **LLM**: Large Language Model (Groq API) for natural language processing and conversation
- **Voice_Assistant**: Bilingual speech recognition and text-to-speech interface for hands-free interaction
- **Dashboard**: The main application view showing today's health overview and quick actions
- **Elderly_Mode**: Accessibility feature providing larger fonts and touch targets for elderly users
- **Session**: An authenticated user's active application usage period
- **Status**: The current state of a medicine (Pending, Taken, Skipped) or reminder (Active, Snoozed, Completed)

## Requirements

### Requirement 1: User Authentication and Account Management

**User Story:** As a new user, I want to create an account and log in securely, so that I can access my personal health information across sessions.

#### Acceptance Criteria

1. WHEN a user provides name, email, and password, THE System SHALL create a new account with unique email validation
2. WHEN a user attempts to register with an existing email, THE System SHALL reject the registration and display an error message
3. WHEN a user provides valid credentials, THE System SHALL authenticate the user and initialize a session
4. WHEN a user provides invalid credentials, THE System SHALL reject the login and display an appropriate error message
5. THE System SHALL hash all passwords using SHA-256 with salt before storing in the database
6. WHEN a user logs in, THE System SHALL retrieve user preferences including language and elderly mode settings
7. THE System SHALL maintain session state throughout the user's active application usage

### Requirement 2: Onboarding Wizard for First-Time Users

**User Story:** As a first-time user, I want to complete an onboarding process, so that I can configure my language, accessibility preferences, and voice settings.

#### Acceptance Criteria

1. WHEN a new user completes registration, THE System SHALL redirect to the onboarding wizard
2. THE System SHALL present a welcome screen explaining CareVoice features
3. WHEN the user selects a language preference, THE System SHALL support English (en-IN) and Telugu (te-IN)
4. WHEN the user enables elderly mode, THE System SHALL increase font sizes by 33% and increase touch target sizes to 48px minimum
5. WHEN the user selects voice gender preference, THE System SHALL save the choice for text-to-speech output
6. WHEN the user completes all onboarding steps, THE System SHALL mark onboarding as completed and navigate to the dashboard
7. WHEN a returning user logs in with onboarding completed, THE System SHALL navigate directly to the dashboard

### Requirement 3: Public Landing Page with Professional Healthcare Design

**User Story:** As a visitor, I want to see a professional landing page, so that I understand what CareVoice offers before signing up.

#### Acceptance Criteria

1. THE System SHALL display a landing page with healthcare green (#166534) as the primary accent color
2. THE System SHALL use white background (#FFFFFF) with generous whitespace following premium healthcare aesthetic
3. THE System SHALL display human-centered imagery showing elderly users and caregivers
4. THE System SHALL present key features including medicine management, health tracking, diet guidance, and voice assistant
5. THE System SHALL provide clear call-to-action buttons for "Get Started" and "Sign In"
6. THE System SHALL render responsively across mobile, tablet, and desktop screen sizes
7. THE System SHALL use Inter font family with appropriate font sizes and weights per the design system

### Requirement 4: Dashboard Hub with Today's Health Overview

**User Story:** As a user, I want to see today's medicine schedule and health summary on my dashboard, so that I can quickly understand my daily health tasks.

#### Acceptance Criteria

1. WHEN a user navigates to the dashboard, THE System SHALL display today's medicine timeline sorted by scheduled time
2. WHEN a user has no medicines scheduled, THE System SHALL display an empty state message with no fake data
3. WHEN a user has health metrics recorded, THE System SHALL display the latest readings for blood pressure, blood sugar, and weight
4. WHEN a user has no health data, THE System SHALL display an empty state message with no fake data
5. THE System SHALL display upcoming reminders showing the next 3 pending medicine reminders
6. THE System SHALL provide quick action buttons for adding medicines, recording health metrics, and accessing voice assistant
7. THE System SHALL render the dashboard with professional card-based layout using subtle shadows and borders

### Requirement 5: Medicine Management with Manual Entry

**User Story:** As a user, I want to manually add medicines to my schedule, so that I can track my daily medication intake.

#### Acceptance Criteria

1. WHEN a user provides medicine name, dosage, time slot, and instructions, THE System SHALL create a new medicine record
2. THE System SHALL support time slots including Morning, Afternoon, Evening, and Night with specific times
3. THE System SHALL support frequency options including Daily, Weekly, and As Needed
4. THE System SHALL associate each medicine with a visual tablet/pill image representation
5. WHEN a user adds a medicine, THE System SHALL initialize the status as "Pending"
6. THE System SHALL allow users to edit existing medicine details
7. THE System SHALL allow users to delete medicines from their schedule
8. THE System SHALL display all medicines in a list view showing name, dosage, time, and status

### Requirement 6: Prescription OCR Upload and Extraction

**User Story:** As a user, I want to upload a prescription image and have medicines extracted automatically, so that I can quickly add multiple medicines without manual typing.

#### Acceptance Criteria

1. WHEN a user uploads a prescription image, THE System SHALL accept JPG, PNG, and PDF file formats up to 10MB
2. WHEN a valid image is uploaded, THE System SHALL apply OCR to extract text from the prescription
3. WHEN OCR extraction completes, THE System SHALL use LLM to parse structured medicine data including name, dosage, frequency, and instructions
4. THE System SHALL present extracted medicines in an editable table for user review
5. WHEN a user modifies extracted medicine data, THE System SHALL save the edited values
6. WHEN a user confirms extracted medicines, THE System SHALL save all medicines to the database with the user's ID
7. WHEN OCR extraction fails, THE System SHALL display an error message and provide option to retry or switch to manual entry
8. THE System SHALL extract doctor name and prescription date when available

### Requirement 7: Real-Time Medicine Reminder Notifications

**User Story:** As a user, I want to receive browser notifications when it's time to take my medicine, so that I don't forget my scheduled doses.

#### Acceptance Criteria

1. WHEN a medicine is added with a scheduled time, THE System SHALL create a reminder record for that time
2. WHEN the current time matches a reminder's scheduled time within a 1-minute window, THE System SHALL trigger a browser notification
3. THE System SHALL display notifications with medicine name, dosage, and action buttons (Take, Snooze, Skip)
4. WHEN a user clicks Take, THE System SHALL update the medicine status to "Taken" and log the action with timestamp
5. WHEN a user clicks Snooze, THE System SHALL reschedule the reminder for 10 minutes later
6. WHEN a user clicks Skip, THE System SHALL update the medicine status to "Skipped" and log the action with timestamp
7. THE System SHALL request browser notification permissions on first use
8. WHEN notification permission is denied, THE System SHALL display in-app reminders as fallback

### Requirement 8: Health Metrics Tracking and Visualization

**User Story:** As a user, I want to record my daily health metrics and see historical trends, so that I can monitor my health over time.

#### Acceptance Criteria

1. THE System SHALL support recording blood pressure (systolic/diastolic in mmHg)
2. THE System SHALL support recording blood sugar fasting levels (in mg/dL)
3. THE System SHALL support recording weight (in kg)
4. THE System SHALL support recording heart rate (in bpm)
5. WHEN a user records a health metric, THE System SHALL automatically calculate status (Optimal, Normal, High, Low, Critical) based on medical thresholds
6. WHEN a user views health history, THE System SHALL display line charts for selected metrics over 7, 30, or 90 day periods
7. THE System SHALL display empty states when insufficient data exists for chart rendering
8. THE System SHALL color-code chart data based on status (green for optimal, yellow for normal, red for high/low)

### Requirement 9: Personalized Diet Guidance Using LLM

**User Story:** As a user, I want to receive personalized diet advice based on my health data, so that I can make informed nutritional choices.

#### Acceptance Criteria

1. WHEN a user requests diet guidance, THE System SHALL aggregate the user's current medicines and latest health metrics
2. THE System SHALL generate an LLM prompt including user's health context and language preference
3. THE System SHALL use Groq LLM API to generate personalized diet recommendations
4. THE System SHALL display diet guidance with prominent medical disclaimers
5. THE System SHALL include safety warnings stating "This is general guidance, not medical advice"
6. THE System SHALL advise users to consult their doctor before making dietary changes
7. THE System SHALL generate bilingual diet advice based on user's language preference (English or Telugu)

### Requirement 10: Bilingual Voice Assistant Integration

**User Story:** As a user, I want to interact with the application using voice commands in my preferred language, so that I can access features hands-free.

#### Acceptance Criteria

1. WHEN a user activates the voice assistant, THE System SHALL capture audio input using device microphone
2. THE System SHALL convert speech to text using Google Speech Recognition API with language code (en-IN or te-IN)
3. WHEN speech recognition fails, THE System SHALL display an error message and allow retry
4. WHEN voice input contains navigation commands, THE System SHALL route to appropriate pages (Medicines, Dashboard, Diet, Reports)
5. WHEN voice input contains health data, THE System SHALL extract values and record to database
6. WHEN voice input is a general query, THE System SHALL use LLM to generate contextual responses with medical safety guardrails
7. THE System SHALL convert text responses to speech using text-to-speech engine
8. THE System SHALL support Telugu voice commands and responses
9. THE System SHALL never diagnose medical conditions or suggest stopping medications in voice responses

### Requirement 11: Medicine History and Adherence Tracking

**User Story:** As a user, I want to see my medicine-taking history, so that I can review my medication adherence over time.

#### Acceptance Criteria

1. WHEN a user marks a medicine as Taken, THE System SHALL log the action with timestamp to medicine history
2. WHEN a user marks a medicine as Skipped, THE System SHALL log the action with timestamp to medicine history
3. THE System SHALL display medicine history showing date, medicine name, dosage, and action taken
4. THE System SHALL calculate adherence percentage based on taken vs. scheduled doses
5. THE System SHALL allow filtering history by date range and specific medicine
6. THE System SHALL display adherence trends in visual format
7. THE System SHALL maintain complete audit trail of all medicine status changes

### Requirement 12: Multi-User Data Isolation

**User Story:** As a user, I want my health data to remain private and separate from other users, so that my personal information is secure.

#### Acceptance Criteria

1. THE System SHALL include user_id foreign key in all user-scoped database tables
2. WHEN querying medicines, THE System SHALL filter results by authenticated user's ID
3. WHEN querying health metrics, THE System SHALL filter results by authenticated user's ID
4. WHEN querying reminders, THE System SHALL filter results by authenticated user's ID
5. THE System SHALL prevent access to other users' data through all application interfaces
6. WHEN a user logs out, THE System SHALL clear session state and require re-authentication for data access
7. THE System SHALL use parameterized SQL queries to prevent cross-user data leakage

### Requirement 13: Responsive Mobile-First Design

**User Story:** As a mobile user, I want the application to work seamlessly on my smartphone, so that I can manage my health on-the-go.

#### Acceptance Criteria

1. THE System SHALL render layouts optimized for mobile devices (320px - 640px width)
2. THE System SHALL display bottom navigation bar on mobile with 5 primary items
3. THE System SHALL use single-column card layouts on mobile screens
4. WHEN screen width is 768px or larger, THE System SHALL display sidebar navigation
5. WHEN screen width is 1024px or larger, THE System SHALL use multi-column grid layouts
6. THE System SHALL use responsive font sizes that scale appropriately for screen size
7. THE System SHALL ensure touch targets are minimum 44px × 44px on mobile

### Requirement 14: Elderly Mode Accessibility Features

**User Story:** As an elderly user, I want larger text and buttons, so that I can use the application comfortably without straining.

#### Acceptance Criteria

1. WHEN elderly mode is enabled, THE System SHALL increase base font size from 15px to 20px
2. WHEN elderly mode is enabled, THE System SHALL scale all heading sizes proportionally by 33%
3. WHEN elderly mode is enabled, THE System SHALL increase line height to 1.7 for improved readability
4. WHEN elderly mode is enabled, THE System SHALL ensure all touch targets are minimum 48px × 48px
5. THE System SHALL maintain elderly mode preference across sessions
6. THE System SHALL apply elderly mode styling consistently across all application pages
7. THE System SHALL maintain color contrast ratios compliant with WCAG 2.1 Level AA standards

### Requirement 15: Family Caregiver Support

**User Story:** As a caregiver, I want to add family contact information, so that emergency contacts are readily available.

#### Acceptance Criteria

1. WHEN a user adds a family member, THE System SHALL require name, relationship, and phone number
2. THE System SHALL support relationship types including Daughter, Son, Spouse, and Caregiver
3. THE System SHALL allow marking a family member as Primary Caregiver or Emergency Contact
4. THE System SHALL display family contacts in a list view with edit and delete options
5. THE System SHALL associate family members with the authenticated user's account
6. THE System SHALL allow multiple family members per user
7. THE System SHALL display family contacts on a dedicated Family page

### Requirement 16: Medical Reports Management

**User Story:** As a user, I want to upload and store medical reports, so that I can access my health documents when needed.

#### Acceptance Criteria

1. WHEN a user uploads a medical report, THE System SHALL accept PDF and image file formats
2. THE System SHALL require report title, date, and optional doctor name
3. THE System SHALL store uploaded files in a secure location with user_id association
4. THE System SHALL display reports in chronological order with title, date, and doctor name
5. THE System SHALL allow users to view uploaded report files
6. THE System SHALL allow users to delete reports from their account
7. THE System SHALL generate plain-language summaries of report contents when possible

### Requirement 17: Database Schema with Seven Tables

**User Story:** As a system administrator, I want a well-structured database schema, so that user data is organized and queryable efficiently.

#### Acceptance Criteria

1. THE System SHALL maintain a users table with columns: id, name, email, password_hash, phone, language, elderly_mode, onboarding_completed, created_at
2. THE System SHALL maintain a medicines table with columns: id, user_id, name, dosage, time_slot, instructions, image_url, status, frequency
3. THE System SHALL maintain a health_metrics table with columns: id, user_id, metric_name, value, unit, recorded_date, status
4. THE System SHALL maintain a reminders table with columns: id, user_id, medicine_id, medicine_name, dosage, reminder_time, status
5. THE System SHALL maintain a diet_plans table with columns: id, user_id, meal_time, food_item, calories, notes
6. THE System SHALL maintain a reports table with columns: id, user_id, title, date, summary, doctor_name, file_path
7. THE System SHALL maintain a family_members table with columns: id, user_id, name, relationship, phone, caregiver_status
8. THE System SHALL enforce foreign key relationships between tables for data integrity

### Requirement 18: No Fake Data Policy

**User Story:** As a user, I want to see only my actual data, so that I understand the system reflects my real health information.

#### Acceptance Criteria

1. WHEN a new user views the dashboard, THE System SHALL display empty state messages instead of sample data
2. WHEN a user has no medicines, THE System SHALL show "No medicines scheduled today" message
3. WHEN a user has no health metrics, THE System SHALL show "No health data available" message
4. WHEN a user has no reports, THE System SHALL show "No reports uploaded" message
5. THE System SHALL not generate placeholder or demo health data for any user
6. THE System SHALL not display hardcoded sample medicines or metrics in any view
7. WHEN charts have insufficient data, THE System SHALL display "Insufficient data for chart" message

### Requirement 19: Professional UI Design System Implementation

**User Story:** As a user, I want a clean and professional interface, so that the application feels trustworthy and modern.

#### Acceptance Criteria

1. THE System SHALL use healthcare green (#166534) as primary color for CTAs and accents
2. THE System SHALL use pure white (#FFFFFF) as primary background color
3. THE System SHALL use Inter font family with weights 400 (normal), 600 (semibold), and 700 (bold)
4. THE System SHALL use 4px base spacing unit with scale: 4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px, 96px
5. THE System SHALL use rounded corners of 10px for buttons and 14px for cards
6. THE System SHALL apply subtle shadows with rgba(0, 0, 0, 0.02) to rgba(0, 0, 0, 0.08)
7. THE System SHALL use transition duration of 200ms for standard interactions
8. THE System SHALL use professional icon library (Lucide, Heroicons, or Feather) consistently

### Requirement 20: Error Handling and Recovery

**User Story:** As a user, I want clear error messages and recovery options when something goes wrong, so that I can continue using the application.

#### Acceptance Criteria

1. WHEN OCR extraction fails, THE System SHALL display error message and provide retry or manual entry options
2. WHEN speech recognition times out, THE System SHALL display "I couldn't hear clearly" and allow retry
3. WHEN LLM API is unavailable, THE System SHALL try fallback models and display generic message if all fail
4. WHEN browser notification permission is denied, THE System SHALL display instructions for enabling permissions
5. WHEN invalid health metric input is provided, THE System SHALL display format requirements and prevent submission
6. WHEN database connection fails, THE System SHALL display critical error and prevent rendering incomplete data
7. THE System SHALL log all errors for debugging and monitoring purposes

### Requirement 21: Security and Password Protection

**User Story:** As a user, I want my account and health data to be secure, so that my personal information is protected.

#### Acceptance Criteria

1. THE System SHALL hash all passwords using SHA-256 with salt before database storage
2. THE System SHALL never store plaintext passwords in the database
3. THE System SHALL use parameterized SQL queries to prevent SQL injection attacks
4. THE System SHALL normalize email addresses to lowercase before storage and comparison
5. THE System SHALL clear session state on logout to prevent unauthorized access
6. THE System SHALL require authentication for all user-scoped data operations
7. THE System SHALL implement user data isolation using user_id filtering on all queries

### Requirement 22: Navigation System with Bottom Bar and Sidebar

**User Story:** As a user, I want easy navigation between application sections, so that I can quickly access different features.

#### Acceptance Criteria

1. THE System SHALL display bottom navigation bar on mobile with icons for Home, Medicines, Prescriptions, Health, and Voice
2. THE System SHALL display sidebar navigation on desktop with all primary and secondary pages
3. WHEN a user clicks a navigation item, THE System SHALL update the current page and highlight the active item
4. THE System SHALL maintain navigation state in session storage
5. THE System SHALL provide visual feedback for the currently active page
6. THE System SHALL support keyboard navigation using Tab key for accessibility
7. THE System SHALL include a More menu for secondary features including Settings, Family, and Reports

### Requirement 23: Medicine Status Workflow Management

**User Story:** As a user, I want medicines to transition through proper states, so that my adherence tracking is accurate.

#### Acceptance Criteria

1. WHEN a medicine is created, THE System SHALL initialize status as "Pending"
2. WHEN a user marks a medicine as Taken, THE System SHALL update status to "Taken" and record timestamp
3. WHEN a user marks a medicine as Skipped, THE System SHALL update status to "Skipped" and record timestamp
4. THE System SHALL allow status transitions from Pending to Taken or Skipped
5. THE System SHALL allow status transitions from Taken back to Pending for correction
6. THE System SHALL allow status transitions from Skipped back to Pending for correction
7. THE System SHALL maintain status history for audit trail

### Requirement 24: Health Metric Status Calculation

**User Story:** As a user, I want the system to automatically classify my health metrics, so that I understand if my readings are normal.

#### Acceptance Criteria

1. WHEN blood pressure is below 120/80, THE System SHALL classify as "Optimal"
2. WHEN blood pressure is 120-139 / 80-89, THE System SHALL classify as "Normal"
3. WHEN blood pressure is 140-179 / 90-109, THE System SHALL classify as "High"
4. WHEN blood pressure is 180 or higher / 110 or higher, THE System SHALL classify as "Critical"
5. WHEN fasting blood sugar is below 70 mg/dL, THE System SHALL classify as "Low"
6. WHEN fasting blood sugar is 70-99 mg/dL, THE System SHALL classify as "Optimal"
7. WHEN fasting blood sugar is 100-125 mg/dL, THE System SHALL classify as "Normal"
8. WHEN fasting blood sugar is 126 mg/dL or higher, THE System SHALL classify as "High"
9. WHEN heart rate is below 60 bpm, THE System SHALL classify as "Low"
10. WHEN heart rate is 60-100 bpm, THE System SHALL classify as "Normal"
11. WHEN heart rate is above 100 bpm, THE System SHALL classify as "High"

### Requirement 25: LLM Integration for Conversational AI

**User Story:** As a user, I want to have natural conversations about my health, so that I can get informational guidance in a friendly way.

#### Acceptance Criteria

1. THE System SHALL use Groq LLM API with model llama-3.3-70b-versatile as primary model
2. WHEN primary model fails, THE System SHALL try fallback models gpt-oss-120b and gpt-oss-20b
3. THE System SHALL include medical safety guardrails in the system prompt
4. THE System SHALL instruct LLM to never diagnose medical conditions
5. THE System SHALL instruct LLM to never suggest stopping medications
6. THE System SHALL instruct LLM to advise consulting doctor for medical symptoms
7. THE System SHALL include user's current medicines and health metrics in LLM context
8. THE System SHALL request responses in user's preferred language (English or Telugu)

### Requirement 26: Text-to-Speech Audio Output

**User Story:** As a user, I want voice assistant responses to be spoken aloud, so that I can hear answers without reading the screen.

#### Acceptance Criteria

1. THE System SHALL convert text responses to speech using gTTS or pyttsx3 engine
2. WHEN elderly mode is enabled, THE System SHALL use slower speech rate for better comprehension
3. THE System SHALL support voice gender selection (male or female voice)
4. THE System SHALL generate audio in user's selected language (English or Telugu)
5. THE System SHALL display audio player controls for playing, pausing, and stopping speech
6. WHEN TTS generation fails, THE System SHALL display text response as fallback
7. THE System SHALL cache generated audio to improve performance for repeated phrases

### Requirement 27: Prescription Image Storage and Management

**User Story:** As a user, I want to store my prescription images, so that I can reference the original documents later.

#### Acceptance Criteria

1. WHEN a user uploads a prescription, THE System SHALL save the image file to a secure storage location
2. THE System SHALL generate a unique filename using user_id and timestamp
3. THE System SHALL associate the stored file path with the user's account
4. THE System SHALL allow users to view previously uploaded prescription images
5. THE System SHALL display prescription images in a gallery view on Prescriptions page
6. THE System SHALL allow users to delete prescription images from storage
7. THE System SHALL validate file types (JPG, PNG, PDF) and file size (max 10MB) before upload

### Requirement 28: Session State Persistence

**User Story:** As a user, I want my session to persist as I navigate the app, so that I don't need to re-authenticate frequently.

#### Acceptance Criteria

1. THE System SHALL store authenticated user information in session state
2. THE System SHALL maintain language preference in session state
3. THE System SHALL maintain elderly mode setting in session state
4. THE System SHALL maintain current page navigation in session state
5. THE System SHALL persist session state throughout application usage
6. WHEN a user closes the browser, THE System SHALL require re-authentication on next visit
7. THE System SHALL clear session state on explicit logout action

### Requirement 29: Medicine Timeline Visualization

**User Story:** As a user, I want to see my daily medicines in a timeline view, so that I can understand when to take each dose throughout the day.

#### Acceptance Criteria

1. WHEN a user views the medicine timeline, THE System SHALL display medicines sorted by time slot
2. THE System SHALL group medicines by time periods (Morning, Afternoon, Evening, Night)
3. THE System SHALL display medicine name, dosage, and status for each timeline entry
4. THE System SHALL show time-specific indicators for medicines with exact scheduled times
5. THE System SHALL visually differentiate between Pending, Taken, and Skipped medicines using color coding
6. THE System SHALL display tablet/pill image icons for each medicine
7. THE System SHALL allow quick status updates directly from timeline view

### Requirement 30: Voice Command Intent Classification

**User Story:** As a user, I want my voice commands to be understood correctly, so that the system performs the actions I request.

#### Acceptance Criteria

1. WHEN voice input contains "show my medicines" or "మందులు", THE System SHALL navigate to Medicines page
2. WHEN voice input contains "show my reports" or "రిపోర్టులు", THE System SHALL navigate to Reports page
3. WHEN voice input contains "open diet" or "ఆహార", THE System SHALL navigate to Diet page
4. WHEN voice input contains "go to dashboard" or "డాష్‌బోర్డ్", THE System SHALL navigate to Dashboard
5. WHEN voice input contains "my blood pressure is X over Y", THE System SHALL extract values and record to database
6. WHEN voice input contains health questions, THE System SHALL generate LLM response with medical disclaimers
7. THE System SHALL handle voice recognition errors gracefully and allow retry
