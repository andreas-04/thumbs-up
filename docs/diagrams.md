# ThumbsUp System Diagrams

This document contains architectural and flow diagrams describing the critical flows of the ThumbsUp secure file sharing system.

---

## 1. System Architecture Overview

High-level view of the containerized deployment showing how Docker containers, networking, and storage interact.

```mermaid
graph TB
    subgraph Clients["Client Layer"]
        Browser["Web Browser"]
        Mobile["Mobile Device"]
    end

    subgraph Docker["Docker Compose Environment"]
        subgraph FrontendContainer["Frontend Container (nginx)"]
            Nginx["Nginx Reverse Proxy<br/>Port 443 (HTTPS)"]
            SPA["React SPA<br/>Static Assets"]
            mTLS["mTLS Termination"]
        end

        subgraph BackendContainer["Backend Container (Flask)"]
            Flask["Flask API Server<br/>Port 8443"]
            Auth["JWT Auth Module<br/>core/auth.py"]
            FileOps["File Operations"]
            UserMgmt["User Management"]
            CertGen["Certificate Generator<br/>utils/generate_certs.py"]
            EmailSvc["Email Service<br/>utils/email_sender.py"]
        end

        subgraph Storage["Persistent Volumes"]
            DB[("SQLite Database<br/>thumbsup-db")]
            Certs["TLS Certificates<br/>thumbsup-certs"]
            subgraph FileStore["File Storage (thumbsup-storage)"]
                Protected["protected/"]
                Unprotected["unprotected/"]
            end
        end
    end

    subgraph External["External Services"]
        SMTP["SMTP Server<br/>(Email Delivery)"]
        mDNS["Avahi / mDNS<br/>Service Discovery"]
    end

    Browser -->|"HTTPS + mTLS"| Nginx
    Mobile -->|"HTTPS + mTLS"| Nginx
    Nginx --> SPA
    Nginx -->|"Proxy /api/*<br/>+ SSL headers"| Flask
    Nginx --- mTLS
    Nginx --- Certs

    Flask --- Auth
    Flask --- FileOps
    Flask --- UserMgmt
    Flask --- CertGen
    Flask --- EmailSvc

    Auth -->|"Query/Update"| DB
    UserMgmt -->|"CRUD"| DB
    FileOps -->|"Read/Write"| FileStore
    CertGen -->|"Store/Load"| Certs
    EmailSvc -->|"SMTP"| SMTP
    Flask -.->|"Advertise"| mDNS
```

---

## 2. Authentication Flow

Sequence diagram showing how users authenticate via email/password, receive JWT tokens, and how tokens are validated on subsequent requests.

```mermaid
sequenceDiagram
    participant U as User/Browser
    participant N as Nginx
    participant F as Flask API
    participant A as Auth Module
    participant DB as SQLite DB

    Note over U,DB: Login Flow
    U->>N: POST /api/v1/auth/login<br/>{email, password}
    N->>F: Forward request
    F->>DB: Query User by email
    DB-->>F: User record
    F->>A: verify_password(input, hash)
    A->>A: bcrypt.checkpw()
    A-->>F: Valid/Invalid

    alt Invalid Credentials
        F-->>N: 401 INVALID_CREDENTIALS
        N-->>U: 401 Unauthorized
    else Valid Credentials
        F->>A: generate_token(user)
        A->>A: jwt.encode(payload, secret, HS256)<br/>payload: {user_id, email, role, exp, jti}
        A-->>F: JWT Token
        F->>DB: Update last_login timestamp
        F-->>N: 200 {token, user}
        N-->>U: Set auth_token in response
        U->>U: Store token in localStorage
    end

    Note over U,DB: Authenticated Request
    U->>N: GET /api/v1/files<br/>Authorization: Bearer <token>
    N->>F: Forward + SSL headers
    F->>A: get_token_from_request()
    A->>A: jwt.decode(token, secret, HS256)
    A->>A: Check expiry (exp claim)

    alt Token Expired
        A-->>F: Token expired
        F-->>N: 401 TOKEN_EXPIRED
        N-->>U: 401 Unauthorized
    else Token Valid
        A->>DB: Query User by user_id
        DB-->>A: User record
        A-->>F: request.user = {user_id, email, role}
        F->>F: Process request
        F-->>N: 200 Response data
        N-->>U: Response
    end

    Note over U,DB: Token Refresh
    U->>N: POST /api/v1/auth/refresh<br/>Authorization: Bearer <token>
    N->>F: Forward request
    F->>A: Validate existing token
    A-->>F: Valid
    F->>A: Generate new token (new jti, fresh exp)
    A-->>F: New JWT Token
    F-->>N: 200 {token}
    N-->>U: New token
```

---

## 3. Role-Based Access Control (RBAC)

Diagram showing the role hierarchy, permissions, and how access control is enforced across the system.

```mermaid
graph TB
    subgraph Roles["User Roles"]
        Admin["🔑 Admin<br/>role = 'admin'<br/>2-hour session"]
        ApprovedUser["👤 Approved User<br/>role = 'user'<br/>is_approved = true<br/>24-hour session"]
        PendingUser["⏳ Pending User<br/>role = 'user'<br/>is_approved = false"]
        Guest["👥 Guest<br/>Legacy token-based<br/>24-hour session"]
    end

    subgraph Permissions["Permission Capabilities"]
        SysMgmt["System Management<br/>• Modify settings<br/>• View dashboard stats"]
        UserAdmin["User Administration<br/>• Create/update/delete users<br/>• Manage folder permissions<br/>• Generate certificates"]
        ProtectedFiles["Protected File Access<br/>• Browse protected/<br/>• Upload files<br/>• Delete files"]
        UnprotectedFiles["Unprotected File Access<br/>• Browse unprotected/<br/>• Read-only or read-write"]
        AuthOnly["Authentication Only<br/>• Login/logout<br/>• Change password"]
    end

    subgraph Enforcement["Enforcement Points"]
        JWTCheck["JWT Token Validation<br/>@auth.require_auth()"]
        AdminCheck["Admin Role Check<br/>@auth.require_admin()"]
        mTLSCheck["mTLS Certificate Check<br/>X-SSL-Client-Verify"]
        ACLCheck["Folder ACL Check<br/>user_has_access()"]
        ApprovalCheck["Approval Check<br/>is_approved flag"]
    end

    Admin -->|"Full Access"| SysMgmt
    Admin -->|"Full Access"| UserAdmin
    Admin -->|"No mTLS needed"| ProtectedFiles
    Admin -->|"Full Access"| UnprotectedFiles

    ApprovedUser -->|"mTLS Required"| ProtectedFiles
    ApprovedUser -->|"ACL Enforced"| UnprotectedFiles

    PendingUser --> AuthOnly

    Guest --> UnprotectedFiles

    SysMgmt -.->|"Requires"| AdminCheck
    UserAdmin -.->|"Requires"| AdminCheck
    ProtectedFiles -.->|"Requires"| JWTCheck
    ProtectedFiles -.->|"Non-admin requires"| mTLSCheck
    ProtectedFiles -.->|"Requires"| ACLCheck
    ProtectedFiles -.->|"Requires"| ApprovalCheck
    UnprotectedFiles -.->|"Optional"| JWTCheck
```

---

## 4. Certificate Lifecycle & mTLS Flow

End-to-end flow of certificate generation, distribution, and mutual TLS authentication.

```mermaid
sequenceDiagram
    participant Admin as Admin User
    participant API as Flask API
    participant CertGen as Certificate Generator
    participant Email as Email Service
    participant SMTP as SMTP Server
    participant NewUser as New User
    participant BrowserCert as User's Browser
    participant NginxTLS as Nginx (mTLS)
    participant Backend as Flask Backend

    Note over Admin,Backend: Phase 1 — Certificate Generation (Admin creates user)
    Admin->>API: POST /api/v1/users<br/>{email, role: "user"}
    API->>CertGen: generate_client_p12(ca_cert, ca_key, email)
    CertGen->>CertGen: Generate RSA 2048-bit client key
    CertGen->>CertGen: Create X.509 certificate<br/>Subject: O=thumbsup, OU=member, CN=email<br/>Extensions: CLIENT_AUTH
    CertGen->>CertGen: Sign with Server CA key (SHA256)
    CertGen->>CertGen: Bundle into PKCS#12 (.p12)<br/>with random password
    CertGen-->>API: Return {p12_bytes, password}
    API->>API: Create User record<br/>password_hash = hash(p12_password)<br/>is_default_pin = true

    Note over Admin,Backend: Phase 2 — Certificate Distribution
    API->>Email: send_invite_email(email, p12_bytes, password)
    Email->>SMTP: Send email with:<br/>• .p12 file attachment<br/>• Import password<br/>• Login instructions
    SMTP-->>NewUser: Email delivered
    NewUser->>NewUser: Import .p12 into<br/>browser/OS cert store

    Note over Admin,Backend: Phase 3 — mTLS Handshake
    NewUser->>BrowserCert: Access https://thumbsup.local
    BrowserCert->>NginxTLS: TLS ClientHello
    NginxTLS->>BrowserCert: ServerHello + CertificateRequest
    BrowserCert->>BrowserCert: Select matching client cert
    BrowserCert->>NginxTLS: Client Certificate (signed by CA)
    NginxTLS->>NginxTLS: Verify cert against<br/>ssl_client_certificate (CA)
    NginxTLS->>NginxTLS: Set headers:<br/>X-SSL-Client-Verify: SUCCESS<br/>X-SSL-Client-S-DN: CN=email

    Note over Admin,Backend: Phase 4 — Backend Certificate Verification
    NginxTLS->>Backend: Forward request + SSL headers
    Backend->>Backend: Extract X-SSL-Client-Verify
    Backend->>Backend: Parse CN from X-SSL-Client-S-DN
    Backend->>Backend: Compare CN with user.email

    alt CN matches user email
        Backend-->>NginxTLS: 200 OK (proceed)
    else CN mismatch or verify != SUCCESS
        Backend-->>NginxTLS: 403 CLIENT_CERT_REQUIRED
    end
```

---

## 5. File Access Control Flow

Decision flow showing how file access requests are evaluated based on user role, approval status, mTLS, and folder ACLs.

```mermaid
flowchart TD
    Start(["Incoming File Request<br/>GET /api/v1/files"])
    ExtractToken["Extract JWT from<br/>Authorization header /<br/>Cookie / URL param"]
    HasToken{Token<br/>present?}
    ValidToken{Token<br/>valid?}
    GetUser["Load User from DB"]
    CheckRole{User role?}

    %% Admin path
    AdminAccess["Full access granted<br/>Protected + Unprotected<br/>No mTLS needed"]

    %% User path
    CheckApproved{is_approved<br/>= true?}
    DenyUnapproved["403 Forbidden<br/>Account not approved"]
    CheckmTLS{mTLS verified?<br/>X-SSL-Client-Verify<br/>== SUCCESS}
    DenyCert["403 Client Certificate<br/>Required"]
    CheckCN{Cert CN ==<br/>User email?}
    DenyMismatch["403 Certificate<br/>Mismatch"]

    %% ACL check
    CheckACL["Load FolderPermissions<br/>for user"]
    HasPerms{Has ACL<br/>entries?}
    FullDefault["Default: Full access<br/>(no restrictions defined)"]
    FindMatch["Find longest matching<br/>folder_path prefix"]
    HasMatch{Match<br/>found?}
    DenyACL["403 Access Denied<br/>No matching permission"]
    CheckReadWrite{Requires<br/>write?}
    CheckWritePerm{can_write<br/>= true?}
    CheckReadPerm{can_read<br/>= true?}
    DenyWrite["403 Write Access<br/>Denied"]
    DenyRead["403 Read Access<br/>Denied"]
    GrantAccess(["✅ Access Granted<br/>Return files"])

    %% Guest path
    GuestAccess["Unprotected files only<br/>No mTLS needed"]

    Start --> ExtractToken --> HasToken
    HasToken -->|No| GuestAccess
    HasToken -->|Yes| ValidToken
    ValidToken -->|No| GuestAccess
    ValidToken -->|Yes| GetUser --> CheckRole

    CheckRole -->|admin| AdminAccess
    CheckRole -->|user| CheckApproved

    CheckApproved -->|No| DenyUnapproved
    CheckApproved -->|Yes| CheckmTLS

    CheckmTLS -->|No| DenyCert
    CheckmTLS -->|Yes| CheckCN

    CheckCN -->|No| DenyMismatch
    CheckCN -->|Yes| CheckACL

    CheckACL --> HasPerms
    HasPerms -->|No| FullDefault
    HasPerms -->|Yes| FindMatch --> HasMatch
    HasMatch -->|No| DenyACL
    HasMatch -->|Yes| CheckReadWrite

    CheckReadWrite -->|Yes| CheckWritePerm
    CheckReadWrite -->|No| CheckReadPerm

    CheckWritePerm -->|Yes| GrantAccess
    CheckWritePerm -->|No| DenyWrite

    CheckReadPerm -->|Yes| GrantAccess
    CheckReadPerm -->|No| DenyRead

    FullDefault --> GrantAccess
    AdminAccess --> GrantAccess
    GuestAccess --> GrantAccess
```

---

## 6. User Onboarding & Approval Workflow

Flow showing the complete user lifecycle from signup through approval to first login.

```mermaid
sequenceDiagram
    participant User as New User
    participant FE as React Frontend
    participant API as Flask API
    participant DB as SQLite DB
    participant CertGen as Cert Generator
    participant Email as Email Service
    participant Admin as Admin User

    Note over User,Admin: Path A — Self-Service Signup
    User->>FE: Navigate to /signup
    FE->>API: GET /api/v1/settings
    API-->>FE: {allowed_domains, ...}
    User->>FE: Enter email + password
    FE->>API: POST /api/v1/auth/signup<br/>{email, password}

    API->>API: Validate email format
    API->>API: Check domain against<br/>allowed_domains list
    API->>DB: Check if email exists

    alt Email exists & is_approved & is_default_pin
        API->>DB: Update password_hash
        API-->>FE: 200 {token, user, requiresPasswordChange: false}
    else Email already claimed
        API-->>FE: 403 EMAIL_EXISTS
    else New email, domain approved
        API->>DB: Create User<br/>is_approved = true<br/>is_default_pin = false
        API-->>FE: 200 {token, user}
    else New email, domain not in allowlist
        API->>DB: Create User<br/>is_approved = false<br/>is_default_pin = false
        API-->>FE: 200 {token, user, requiresApproval: true}
    end

    Note over User,Admin: Path B — Admin-Created User
    Admin->>FE: Navigate to User Management
    Admin->>FE: Click "Add User"
    FE->>API: POST /api/v1/users<br/>{email, password?, role}
    API->>CertGen: generate_client_p12(email)
    CertGen-->>API: {p12_bytes, password}
    API->>DB: Create User<br/>is_approved = true<br/>is_default_pin = true<br/>password = p12_password
    API->>Email: send_invite_email<br/>(email, p12 attachment, password)
    Email-->>User: Email with .p12 cert<br/>+ temporary password
    API-->>FE: 201 {user}

    Note over User,Admin: Admin Approval (for unapproved signups)
    Admin->>FE: View pending users
    Admin->>FE: Approve user
    FE->>API: PUT /api/v1/users/{id}<br/>{is_approved: true}
    API->>CertGen: generate_client_p12(email)
    CertGen-->>API: {p12_bytes, password}
    API->>DB: Update is_approved = true
    API->>Email: Send approval + cert email
    Email-->>User: Approval email with .p12

    Note over User,Admin: First Login (Admin-Created User)
    User->>FE: Login with temp password
    FE->>API: POST /api/v1/auth/login
    API-->>FE: {token, requiresPasswordChange: true}
    FE->>FE: Redirect to password change
    User->>FE: Enter new password
    FE->>API: POST /api/v1/auth/change-password<br/>{new_password} (is_default_pin bypass)
    API->>DB: Update password_hash<br/>Set is_default_pin = false
    API-->>FE: {token} (new session)
    FE->>FE: Redirect to file browser
```

---

## 7. Database Entity Relationship Diagram

Data model showing the relationships between Users, FolderPermissions, and SystemSettings.

```mermaid
erDiagram
    USERS {
        int id PK
        string email UK "Unique, not null"
        string password_hash "bcrypt hashed"
        string role "admin | user"
        boolean is_default_pin "First-time login flag"
        boolean is_approved "Approved for protected files"
        datetime created_at "Default: utcnow"
        datetime last_login "Nullable"
    }

    FOLDER_PERMISSIONS {
        int id PK
        int user_id FK "References users.id"
        string folder_path "Max 1024 chars"
        boolean can_read "Default: true"
        boolean can_write "Default: false"
        datetime created_at "Default: utcnow"
    }

    SYSTEM_SETTINGS {
        int id PK
        string server_name "Display name"
        string allowed_domains "Comma-separated domain list"
        boolean enable_uploads "Default: true"
        boolean enable_delete "Default: false"
        int token_expiry_hours "Default: 24"
        string smtp_server "Email server host"
        int smtp_port "Default: 587"
        string smtp_username "Email account"
        string smtp_password "Email password"
        string smtp_from_email "Sender address"
        boolean smtp_use_tls "Default: true"
    }

    USERS ||--o{ FOLDER_PERMISSIONS : "has"
```

---

*Document Version: 1.0*
*Last Updated: March 2026*
*Format: Mermaid (rendered natively by GitHub)*
