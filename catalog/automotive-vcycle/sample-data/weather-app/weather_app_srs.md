# Software Requirements Specification (SRS) Document: Weather Application

## VERSION HISTORY

| VERSION | APPROVED BY     | REVISION DATE | DESCRIPTION OF CHANGE               | AUTHOR          |
|---------|-----------------|---------------|-------------------------------------|-----------------|
| 1.0.0   | Brunilda Caushi | 10.29.2025    | Initial authoring of the software requirements | Brunilda Caushi |
| 1.0.1   | Brunilda Caushi | 10.31.2025    | Updated requirements after reviews | Brunilda Caushi |

---

## Table of Contents

1. [Introduction](#introduction)
2. [Overall Description](#overall-description)
3. [Specific Requirements](#specific-requirements)

---

# 1. Introduction

This section provides an overview of the entire Software Requirements Specification (SRS) document, introducing the software product to be developed. It defines the purpose and scope of the project, lists definitions and references, and provides an overview of the document structure.

## 1.1. Purpose

The purpose of this SRS is to define the requirements for the Weather Application, outlining the objectives and aims of the software project. This document will be used to ensure clarity, alignment, and accountability among all stakeholders before development begins. It acts as a guide for the development team and a reference throughout the project's lifecycle.

## 1.2. Scope

The scope of the project defines what the software will and will not do, establishing its boundaries. It provides a high-level overview of the product's features, capabilities, and limitations, aligning them with overall business goals.

## 1.3. Definitions, Acronyms, Abbreviations

This subsection will list and define all technical terms, acronyms, and abbreviations used throughout the document. This ensures that all parties, including both technical and non-technical stakeholders, have a clear and unambiguous understanding of the terminology.

## 1.4. References

This section will list all documents, standards, or guidelines referenced in the SRS. This may include existing system documentation, industry standards (e.g., IEEE 830), or previous project deliverables.

## 1.5. Overview

This subsection provides an overview of the SRS document's structure. It explains how the remaining sections are organized to ensure readers can easily navigate and understand the content.

---

# 2. Overall Description

This section describes the general factors that affect the weather application. It does not state specific requirements but provides context to make them easier to understand.

## 2.1. Product Perspective

The weather application is not an independent system but a component that integrates with a larger vehicle ecosystem to provide a seamless user experience. The application is a new element of the vehicle's infotainment system, specifically designed to be compatible with Android Auto. It relies on several existing in-vehicle services and external APIs to function.

*[Block diagram illustrating the application interfaces would be included here]*

## 2.2. Product Functions

The weather application is designed to be a core feature of the vehicle's infotainment system, providing drivers with real-time, context-aware weather information in an intuitive and non-distracting manner. The primary functions are centered around providing on-demand and proactive weather data to the driver, with a focus on enhancing safety, convenience, and overall vehicle performance.

### User-Facing Capabilities

- **Ambient Weather Display:** Upon entering the vehicle, the user will see the current local temperature and weather conditions displayed persistently in the infotainment system's status bar. This display remains active even when using phone projection services like Apple CarPlay or Android Auto.
  - **Privacy-Controlled Display:** If the customer has enabled the privacy setting within the vehicle's radio, the weather display will be suppressed and will not appear in the status bar.

- **On-Demand Weather Forecasts:** Users can request detailed weather information, such as multi-day or hourly forecasts for their current location or a saved favorite city.

- **Hands-Free Voice Interaction:** The application can be controlled using voice commands, allowing drivers to safely request weather forecasts for their current location or their navigation destination without taking their hands off the wheel.

- **Proactive Severe Weather Alerts:** A premium feature provides automatic, unmissable alerts for severe weather events (e.g., tornado warnings, flash floods) that are approaching the vehicle's location or planned route. These alerts are designed to notify the driver in time to react and take appropriate action.

### Vehicle System Capabilities

- **Integrated Data Source:** The application integrates seamlessly with the vehicle's onboard GPS and connectivity services to fetch accurate, location-specific data.

- **Data-Driven Performance Enhancements:** The app silently streams real-time weather data to other vehicle systems, such as the Advanced Driver Assistance Systems (ADAS) and battery management systems. This allows the vehicle to proactively adjust its behavior based on weather conditions, improving safety and efficiency without direct user input.

## 2.3. User Characteristics

This section describes the users who will interact with the weather application and their characteristics. The system is designed to accommodate a wide range of user technical expertise and prioritize safety and ease of use for the primary user, the vehicle driver.

### Primary User: The Vehicle Driver

- **Role and Responsibilities:** The driver's primary responsibility is to safely operate the vehicle. They are the main consumer of the weather application's information and features.

- **Technical Expertise:** Varies widely, from tech-savvy to non-technical. The application interface and voice command features must be intuitive and easy to use for all drivers, regardless of their comfort with technology.

- **Interaction Context:**
  - **In Motion:** The driver is typically in motion, so their interaction with the system must be hands-free or require minimal visual attention. Voice commands are a critical interaction method.
  - **Parked:** When the vehicle is stationary, the driver may have more time to explore detailed weather forecasts, manage favorite locations, and adjust privacy settings.

- **Goals:**
  - To get quick, at-a-glance weather information for their current location.
  - To receive timely, non-distracting alerts about severe weather on their route.
  - To check forecasts for a destination to plan accordingly.

### Secondary User: Vehicle Passengers

- **Role and Responsibilities:** Passengers are not in control of the vehicle but may interact with the infotainment system for convenience or to assist the driver.

- **Technical Expertise:** Varies. They may have more time to interact with the system's screen than the driver.

- **Interaction Context:** Passengers will primarily use the touchscreen interface to browse forecasts for different locations, view weather maps, and manage settings. They will not typically use voice commands intended for the driver.

- **Goals:**
  - To check weather for a destination or a specific location.
  - To view more detailed weather information than what is displayed in the status bar.

### Support and Maintenance Staff

- **Role and Responsibilities:** This includes vehicle service technicians, operations teams, and engineers responsible for maintaining the application and the larger vehicle system.

- **Technical Expertise:** High-level technical expertise in automotive software, diagnostics, and connectivity.

- **Interaction Context:** These users will not interact with the application from a consumer perspective. Instead, they will use diagnostic logging, error reports, and other maintenance tools to monitor the application's performance, troubleshoot issues, and deploy software updates.

- **Goals:**
  - To ensure the application's stability and reliability.
  - To diagnose and resolve any issues related to API connectivity, data accuracy, or system integration.
  - To securely deploy over-the-air (OTA) updates and monitor their success.

## 2.4. Constraints

This subsection outlines any limitations or restrictions that may impact the software's design or development.

### Hardware and Software Constraints

- **Platform:** The software must be developed for a specific platform (e.g., Android Auto) and adhere to its templates and guidelines.

- **Hardware Limitations:** The application must function within the hardware specifications of the target device, such as CPU, memory, and storage limits.

- **Third-Party Interfaces:** The software's design is restricted by the APIs of other systems it must interface with, such as in-vehicle location services or external weather APIs.

### Technical and Operational Constraints

- **Development Language/Tools:** The project may be mandated to use a specific programming language (e.g., Kotlin) or a specific set of development tools.

- **Regulatory Requirements:** The application must comply with relevant regulations, such as those concerning driver distraction or data privacy (e.g., GDPR, CCPA).

- **Performance Requirements:** The software must meet specific performance metrics, such as a minimum response time for API calls or a maximum memory usage.

- **Security:** The system must adhere to security standards, including data encryption, access control, and logging of security events.

- **Integration Limitations:** The project scope may be constrained to prevent deep integration with other systems, such as the vehicle's climate control or navigation systems.

### Resource and Timeline Constraints

- **Budget:** The project has a fixed budget that cannot be exceeded.

- **Timeline:** The software must be completed and delivered by a specific deadline.

- **Personnel:** The project is limited to a specific number of developers or a particular set of skills.

- **Testing Environment:** The availability of testing resources, such as a limited number of vehicle test units, can constrain the testing process.

### Design and Quality Constraints

- **Usability and Accessibility:** The user interface must be designed to be highly readable, intuitive, and compliant with accessibility standards.

- **Reliability:** The software must include mechanisms to handle network outages and service interruptions gracefully, such as displaying cached data or a fallback message.

- **Modifiability:** The system design should be modular, allowing for future changes to be made without affecting other components.

- **Extensibility:** The system's architecture may need to be designed to accommodate future features, such as new monetization models or data sources.

- **Maintainability:** The software must be designed for easy maintenance, with detailed logging and documentation.

## 2.5. Assumptions and Dependencies

### Assumptions

This section outlines the key assumptions upon which the project's success is based. Any changes to these assumptions could significantly impact the project's scope, timeline, and cost.

- **Screen Layout:** The application will be designed and developed to support only a single screen layout, which is a landscape orientation.

- **In-vehicle Services:** In-vehicle location and connectivity middleware services are assumed to be available, stable, and will maintain backward compatibility throughout the project timeline.

- **External API Reliability:** The external weather API provider is assumed to maintain a high level of uptime (e.g., 99.5%) and provide stable, documented API endpoints throughout the project and post-launch.

- **System Resources:** The vehicle infotainment systems are assumed to have sufficient processing power and storage to support the application, with a minimum of 1 CPU core, 10GB RAM, and 100MB of available storage.

- **Connectivity:** All target vehicles are assumed to have active cellular or Wi-Fi connectivity for the continuous retrieval of weather data.

- **Development Platform Stability:** It is assumed that no major changes to the Android Auto platform requirements or restrictions will occur during the development cycle.

- **Test Environment Availability:** The project assumes it will have continuous access to the one vehicle test unit and one test environment for integration and performance testing as defined by the project constraints.

### Dependencies

This section lists the dependencies, which are external factors or components the project relies on to be completed successfully.

- **API Integration:** The application is dependent on the external weather API for all weather data, including current conditions, forecasts, and severe weather alerts.

- **In-Vehicle Middleware:** The application is dependent on the availability and correct functioning of the in-vehicle location and connectivity middleware services to determine the vehicle's position and access the internet.

- **Vehicle Hardware:** The application is dependent on the existence of a compatible infotainment system and the necessary sensors (e.g., GPS, outside temperature sensors) to provide the necessary data streams for the application to function.

- **Voice Assistant:** The voice-activated features of the application are dependent on the integration and the proper functioning of Voice Assistant.

- **Third-Party Libraries:** The project is dependent on the Android for Cars App Library, which dictates the user interface design and interaction patterns.

---

# 3. Specific Requirements

This section details all functional and non-functional requirements for the software. Each requirement must be clear, testable, and traceable.

## 3.1. External Interface Requirements

This subsection describes how the software will interact with people, hardware, other software, and communications.

### 3.1.1. User Interfaces

This section describes the screen layouts, navigation, and user interface design for the weather application.

| Requirement ID | Requirement Description |
|---|---|
| UI 100 | The application shall display an ambient temperature always reading in the top-level status bar of the infotainment system, including during active phone projection sessions (e.g., Apple CarPlay, Android Auto). |
| UI 101 | The application shall use a high-contrast, easily readable font for all text and icons, compliant with automotive safety and accessibility standards. |
| UI 102 | The application shall automatically adapt its color scheme to light or dark mode based on the vehicle's display settings. |
| UI 103 | The application shall display severe weather alerts as a high-visibility, non-dismissible pop-up notification that overlays any active screen. |
| UI 105 | The application shall provide a user interface for viewing detailed weather forecasts (e.g., multi-day, hourly) and managing a list of favorite locations when the vehicle is stationary. |
| UI 106 | The application shall use clear and intuitive icons to represent various weather conditions (e.g., sunny, rain, snow). |
| UI 107 | The application shall launch the main weather forecast screen when the user taps on the ambient temperature and weather icon in the infotainment system's status bar. |
| UI 108 | The application shall provide a user interface for viewing a radar map of local weather, and allow the user to zoom in and out of the map using standard gestures (e.g., pinch-to-zoom) when the vehicle is stationary. |
| UI 109 | The application shall provide a clear and intuitive way (e.g., a "close" or "back" button) for the user to dismiss any full-screen or pop-up interface and return to the previous screen or the home screen. |

### 3.1.2. Hardware Interfaces

This section specifies the hardware components the system must interact with.

| Requirement ID | Requirement Description |
|---|---|
| HI100 | The application shall interface with the vehicle's GPS hardware to receive real-time location coordinates. |
| HI101 | The application shall interface with the vehicle's speakers to provide audible feedback for voice commands and severe weather alerts. |
| HI102 | The application shall interface with the vehicle's microphone to receive and process voice commands. |
| HI103 | The application shall interface with the vehicle's display screen to present all visual information. |

### 3.1.3. Software Interfaces

This section outlines how the software will interact with other software systems and APIs.

| Requirement ID | Requirement Description |
|---|---|
| SI100 | The application shall integrate with an external weather API to retrieve current weather conditions, multi-day forecasts, hourly forecasts, and severe weather alerts. |
| SI101 | The application shall utilize the in-vehicle middleware services for location and network connectivity data. |
| SI102 | The application's voice command functionality shall interface with Voice Assistant or a similar in-vehicle voice recognition engine to parse user intent. |
| SI103 | The application shall provide a data stream interface for other vehicle core systems (e.g., ADAS, battery management) to receive real-time weather information. |
| SI105 | The application shall integrate with the Android for Cars App Library and adhere to its API for all user interface components. |
| SI 106 | The application shall integrate with a real-time weather radar data provider API to display radar maps. |

### 3.1.4. Communications Interfaces

This section describes the communication protocols the software will use.

| Requirement ID | Requirement Description |
|---|---|
| CI100 | All communication between the in-vehicle system and the cloud backend/external APIs shall be over secure, encrypted protocols (e.g., TLS 1.2 or higher). |
| CI101 | The system shall use the vehicle's built-in cellular or Wi-Fi connectivity to communicate with external services. |
| CI102 | The system shall use push notification services to receive severe weather alerts for favorite locations, even when the application is not actively running in the foreground. |

## 3.2. Functional Requirements

Functional requirements detail what the software system should do. They describe specific features and behaviors organized by subsystems.

### 3.2.1. Weather Data Acquisition and Display

#### 3.2.1.1. Requirements Statement: Retrieve and Display Current Weather

**SR 1000** The application shall automatically retrieve and display the current weather conditions for the vehicle's location, including temperature, "feels like" temperature, and an icon representing the conditions.

- **Test Case:** Verify that upon the infotainment system powering on, the application displays the current temperature in the status bar within 10 seconds.

- **Test Case:** Verify that the displayed temperature and icon accurately reflect the conditions at the vehicle's GPS location.

#### 3.2.1.2. Requirements Statement: Retrieve and Display Forecasts

**SR 1001** The application shall retrieve and display hourly and multi-day weather forecasts for the vehicle's current location or a user-selected favorite location.

- **Test Case:** With the vehicle stationary, verify that selecting a favorite city displays its 7-day forecast.

- **Test Case:** Verify that a user can view a 24-hour hourly forecast for the current location.

#### 3.2.1.3 Requirements Statement: Display Additional Weather Metrics

**SR 1010** The application shall display additional weather metrics such as wind speed and direction, humidity, UV index, and sunrise/sunset times, both for the current location and for a selected favorite location.

- **Test Case:** Verify that when viewing the detailed forecast for a location, the application displays wind speed, wind direction, humidity, UV index, sunrise time, and sunset time.

#### 3.2.1.4 Requirements Statement: Display Last Known Data

**SR 1015** The application shall display the last known weather data with a timestamp indicating when the data was last updated, in case of a network connectivity loss. This provides the user with some information instead of a blank screen.

### 3.2.2. User Interaction

#### 3.2.2.1. Requirements Statement: Voice-Activated Weather Queries

**SR 1002** The application shall respond to a voice command from the user by providing an audible summary of the weather.

- **Test Case:** Verify that in response to the voice command "Hey car, what is the weather in a few hours?", the system provides an audible forecast for the next 3-4 hours for the vehicle's current location.

- **Test Case:** With a destination set in navigation, verify that in response to the command "Hey car, what is the weather at our destination?", the system provides an audible forecast for the destination.

#### 3.2.2.2. Requirements Statement: Privacy Settings

**SR 1003** The application shall not display any weather information if the customer has enabled the privacy setting in the radio.

- **Test Case:** Verify that when the privacy setting is enabled, no temperature or weather icon is displayed in the status bar.

- **Test Case:** Verify that when a user attempts a voice query with privacy enabled, the system responds with a message indicating that the feature is disabled due to privacy settings.

#### 3.2.2.3. Requirements Statement: Open Application from Status Bar

**SR 1006** The application shall launch and display the main forecast screen when the user taps on the ambient temperature and weather icon in the infotainment system's status bar.

- **Test Case:** Verify that tapping the weather icon in the status bar opens the full weather application, displaying detailed information.

#### 3.2.2.4. Requirements Statement: Radar Map Display and Interaction

**SR 1007** The application shall include a visual radar map that the user can access to view real-time weather patterns and storm movements.

- **Test Case:** Verify that when the vehicle is stationary, the user can navigate to and view a dynamic radar map.

#### 3.2.2.5. Requirements Statement: Radar Zoom

**SR 1008** When the vehicle is stationary, the user shall be able to zoom in and out of the radar map using standard touch gestures.

- **Test Case:** While the vehicle is stationary, verify that pinch-to-zoom gestures on the radar map successfully magnify and de-magnify the view.

#### 3.2.2.6. Requirements Statement: Dismissal of Application View

**SR 1009** The application shall have a persistent and easily accessible control (e.g., a "Back" button) to close the full application view or any pop-up and return the user to the previous screen or the vehicle's home screen.

- **Test Case:** Verify that pressing the "Back" button while in the full application view returns the user to the home screen or the screen they were on before launching the app.

#### 3.2.2.7 Requirements Statement: Managing Favorite Locations

**SR 1011** The application shall allow the user to add, edit, and remove favorite locations for which they can view weather forecasts.

- **Test Case:** Verify that a user can successfully add a new city as a favorite, and later delete it from their list of saved locations.

#### 3.2.2.8 Requirements Statement: User-Configurable Settings

**SR 1012** The application shall provide a settings menu where users can change the temperature units (e.g., Celsius or Fahrenheit).

- **Test Case:** Verify that changing the temperature unit in the settings menu updates all temperature displays throughout the application.

#### 3.2.2.9 Requirements Statement: Contextual Weather Data on Route

**SR 1013** The application shall display the weather forecast for the vehicle's navigation destination and along the planned route, updating as the vehicle moves.

- **Test Case:** With an active navigation route, verify that the application displays a weather forecast for the destination and provides updates for conditions along the route.

#### 3.2.2.10 Requirements Statement: Application Language Compliance

**SR 1017** The application's language shall automatically change to match the language selected in the infotainment system's radio settings upon startup.

- **Test Case:** Verify that when the vehicle's radio language is changed, the application restarts and all text and labels are displayed in the newly selected language.

#### 3.2.2.11 Requirements Statement: Application Setting

**SR 2000** The application shall provide a dedicated section in the settings menu where users can enable or disable severe weather alerts for their current location, navigation route, and favorite locations.

### 3.2.3. Safety and Proactive Alerts

#### 3.2.3.1. Requirements Statement: Severe Weather Alerts

**SR 1004** The application shall issue an immediate, high-priority audio and visual alert for government-issued severe weather warnings that intersect the vehicle's current location or navigation route.

- **Test Case:** Simulate a severe weather alert for the vehicle's location and verify that a non-dismissible pop-up alert and an audible chime are triggered within 60 seconds of the alert's issuance.

- **Test Case:** Verify that the alert remains on screen until the user acknowledges it or the alert condition passes.

#### 3.2.3.2 Requirements Statement: User Control Over Alerts

**SR 1015** The application shall provide an option in the settings menu to disable all severe weather alerts.

- **Test Case:** Verify that when the severe weather alerts are disabled in the settings, no audio or visual alerts are triggered, even when a severe weather event is simulated for the vehicle's location.

#### 3.2.3.3 Requirements Statement: Alert Volume Control

**SR 1016** The application shall allow the user to control the volume of audible severe weather alerts independently of other audio sources (e.g., radio, media playback).

- **Test Case:** Verify that adjusting the alert volume slider in the settings menu changes the loudness of the audible alert without affecting the volume of other system audio.

### 3.2.4. Integration with Vehicle Core Systems

#### 3.2.4.1. Requirements Statement: Provide Weather Data for Performance Optimization

**SR 1005** The application shall silently and continuously stream a defined set of weather data (e.g., temperature, precipitation, wind speed) to the vehicle's core systems (e.g., ADAS, battery management).

- **Test Case:** Verify that the weather data stream is active and provides updated information at a regular interval to a designated internal logging tool or diagnostic interface.

- **Test Case:** Verify that the data stream is a continuous background process that does not require explicit user interaction after initial opt-in.

### 3.2.5. Push Notifications

#### 3.2.5.1 Requirements Statement: Weather Alerts for Favorite Locations

**SR 1014** The application shall provide proactive audio and visual alerts for severe weather events for a user's favorite locations, in addition to the vehicle's current location and navigation route.

- **Test Case:** Verify that when a severe weather alert is issued for a favorite city, a notification is displayed and an audible alert is triggered for the driver.

## 3.3. Performance Requirements

This subsection specifies the software's performance, including speed, availability, and response time.

### 3.3.1. Standards

*[Standards information to be added]*

### 3.3.2. Hardware Limitations

*[Hardware limitations information to be added]*

## 3.4. Design Constraints

### 3.4.1. Availability

This section addresses the performance and availability requirements for the Android Auto application, focusing on the fast display of the app icon and a quick application load time. These factors are critical for a driver-centric experience, where speed and minimal distraction are paramount.

#### 3.4.1.1 Fast App Icon Display

**SR 1020** The app icon must appear on the radio screen immediately upon the screen being turned on. This ensures the app is discoverable and readily available to the user.

**SR 1100 - Manifest Configuration:** The application's AndroidManifest.xml must be correctly configured to declare a CarAppService and specify the app's name and icon. The icon, defined in the android:icon attribute of the `<service>` tag, is a static resource that the system host can use immediately.

**SR 1110 - Icon Asset Requirements:** The app must provide icon assets that meet the guidelines for readability and contrast in a vehicle environment. White icon sets should be provided, as the system may colorize them for optimal contrast.

**SR 1120 - System Integration:** As a core part of the Android for Cars App Library, the system is designed to display the icon promptly by querying the manifest. There is no need for the app itself to perform any complex logic on startup just to display the icon. The host system handles this based on the manifest entries.

#### 3.4.1.2 App Load Time (within 3 seconds)

The application must load and become interactive within three seconds of the user tapping its icon. This minimizes driver distraction and provides a responsive user experience.

**SR 1150 - Startup Optimization:** The development team must employ several optimizations to meet this performance requirement:

**SR 1152 - Flatten View Hierarchy:** The layout files should be optimized to reduce nested and redundant layouts. A flat view hierarchy inflates much faster.

**SR 1153 - Lazy Resource Initialization:** Any intensive resource initialization (e.g., loading large bitmaps) should be moved off the main thread and performed lazily. The app should load and display a basic UI immediately, then update visual properties as resources become available.

**SR 1154 - Background Tasks:** Heavy-lifting tasks, such as network calls to secure cloud services, must be deferred or initiated on a background thread after the initial screen has loaded.

**SR 1160 - Coroutines for Asynchronous Operations:** In Kotlin, the use of coroutines is highly recommended for managing asynchronous operations. This allows long-running tasks, such as fetching data from the cloud, to execute without blocking the main UI thread, thus preserving the user interface's responsiveness.

**SR 1162 - Performance Monitoring:** The development process must include tools and practices to monitor the app's startup time during testing. This ensures that performance degradation is caught early and that the app consistently meets the three-second load time requirement across different devices.

#### 3.4.1.3 App State Restoration

For a seamless user experience, the app must restore its state as closely as possible when relaunched from the home screen.

**SR 1170 - Session Management:** The app must implement robust session management to preserve the user's progress and state. If a user is listening to a media item, they should be able to resume playback from where they left off.

**SR 1172 - State Persistence:** Utilize shared preferences or a local database to persist the application state. Upon relaunch, this stored state should be used to reconstruct the UI and resume the user's previous task.

#### 3.4.1.4 Responsive Interaction

Beyond initial loading, the app must remain responsive to user input at all times.

**SR 1180 - Non-blocking UI:** All potentially blocking operations, such as data processing or complex calculations, must be handled on background threads to ensure the UI remains smooth and does not freeze or stutter.

**SR 1182 - Driver-centric design:** All interactive elements and flows must be simple and non-distracting, adhering to Android Auto's design principles, which prioritize the driving experience. Touch targets must be sufficiently large (at least 64dp) and spaced appropriately to minimize errors while driving.

### 3.4.2. Security

This section details the security requirements for the Android Auto application developed in Kotlin, covering mandatory app signing, secure cloud communication, and adherence to the secure API framework provided by Android for automotive applications.

#### 3.4.2.1 App Signing

Android requires that all applications be digitally signed with a certificate before they can be installed and updated. This requirement ensures the integrity and authenticity of the app. The following specifications apply to the app-signing process:

**SR 1220 - Hardware Security Module (HSM):** The embedded car radio hardware must contain a tamper-resistant HSM that is used to verify all app and firmware signatures before execution. The HSM's root of trust must be established during the manufacturing or provisioning process.

**SR 1221 - Secure key storage:** All private keys used for signing (both development and production) must be stored securely and never be accessible to developers. An automated and isolated signing service should be used.

**SR 1222 - Development keys:** Development-specific private keys will be used to sign apps intended for development hardware. The public keys for these are provisioned into the HSMs of development units.

**SR 1225 - Production keys:** A highly-protected, separate set of production keys will be used exclusively for signing apps that are ready for deployment on production hardware. The corresponding public keys are permanently burned into the HSMs of production vehicles.

**SR 1227 - Key rotation:** The production keys should be regularly rotated to maintain security over the vehicle's lifespan. A process for secure key updates and certificate lifecycle management must be established.

**SR 1228 - Developer signing API:** The cybersecurity team will provide an API that developers must use to submit their compiled app binaries for signing. This removes direct access to the signing keys from developers and creates a managed, auditable process.

**SR 1229 - Authentication and authorization:** The API will require developers to authenticate and will authorize their signing requests based on their credentials. This ensures only approved developers can request a signature.

**SR 1230 - Automated build integration:** The signing API should be integrated into the continuous integration/continuous deployment (CI/CD) pipeline to automate the signing process.

**SR 1232 - Request metadata:** Signing requests must include metadata to specify the build type (development or production). For production builds, additional approval steps or a more restrictive process should be triggered.

**SR 1235 - No downgrade protection:** The hardware and software must implement an anti-rollback mechanism (also known as "no downgrade") that prevents a device from being updated with an older, potentially vulnerable version of an app. The version number in the signed app must be checked against the currently installed version before an update is allowed.

**SR 1237 - Version tracking:** The signing API will enforce versioning policies to prevent rollbacks. The system must track the latest signed production version and reject requests to sign older versions for production hardware.

**SR 1240 - Integrity verification:** The HSM will perform a cryptographic hash of the app's firmware image and verify it using the public key provisioned in the hardware. If the hashes do not match, the app is rejected.

**SR 1245 - Secure communication:** All communication between the developer tools, the signing API, and the production line must be encrypted using strong, modern protocols like TLS 1.3.

**SR 1247 - Auditable logs:** The signing API and the HSM must generate detailed, tamper-evident logs of all signing requests and verification attempts. These logs should record who made the request, which app was signed, and whether the process was successful.

**SR 1248 - Certificate management:** A system for certificate lifecycle management must be in place to track the validity and expiration of all signing certificates. This system should issue alerts for upcoming renewals and automate the process where possible.

#### 3.4.2.2 Common API with OS

##### Common API framework and layered security

**SR 1300** The Android Auto application must interface with the in-car operating system (OS) via a common, standardized API framework. A layered security approach, leveraging both Android and automotive security features, will protect this interface. The architecture must strictly enforce a separation of concerns, isolating infotainment functions from safety-critical systems.

##### Access control with enhanced SELinux policies

**SR 1350 - Principle of least privilege:** The system must strictly apply the principle of least privilege. The Android app's permissions will be limited to only those necessary to perform its functions, minimizing the potential attack surface.

**SR 1360 - Enforced SELinux policies:** Custom and granular SELinux policies, verified through static and dynamic analysis, must strictly govern access to vehicle subsystems. Non-system apps must only access the Vehicle Hardware Abstraction Layer (VHAL) through the car service, with all permissions explicitly defined and enforced by SELinux.

**SR 1370 - VHAL-level filtering:** The VHAL layer must include its own set of filters to validate messages originating from the Android OS. This prevents a compromised app from flooding the CAN bus or sending unauthorized control messages.

**SR 1380 - Runtime permission decisions:** The system must track and remind users of permissions granted while driving. Recent permission decisions must be visible in a privacy dashboard, allowing users to review and change them at any time.

#####