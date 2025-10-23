# Secure NAS System Architecture Diagrams

## State Machine Diagram

```mermaid
stateDiagram-v2
    [*] --> DORMANT
    
    state DORMANT {
        [*] --> Idle
        Idle: ❌ No mDNS broadcast
        Idle: ❌ No services listening
        Idle: 🔒 Storage locked (LUKS)
    }
    
    DORMANT --> ADVERTISING: Button Press / Manual Activation
    
    state ADVERTISING {
        [*] --> Waiting
        Waiting: 📡 Avahi broadcasts mDNS
        Waiting: 🔓 mTLS service listening (port 8443)
        Waiting: 🔒 Storage still locked
        Waiting: ⏳ Waiting for authenticated client
    }
    
    ADVERTISING --> ACTIVE: Client connects + mTLS succeeds
    ADVERTISING --> DORMANT: Timeout / No connections
    
    state ACTIVE {
        [*] --> Serving
        Serving: 🔓 LUKS storage unlocked
        Serving: 📂 NFS mounted (client-specific rules)
        Serving: 🛡️ Firewall rules per client IP
        Serving: 📝 Logging all access
        Serving: 👁️ Monitoring activity
        
        state Serving {
            [*] --> SingleClient
            SingleClient --> MultipleClients: Additional client connects
            MultipleClients --> SingleClient: Client disconnects
            SingleClient --> [*]: Last client disconnects
        }
    }
    
    ACTIVE --> ACTIVE: Additional clients connect/disconnect
    ACTIVE --> DORMANT: All clients disconnect + inactivity timeout
    
    state DORMANT {
        Cleanup: 📂 Unmount NFS
        Cleanup: 🔒 Lock storage (LUKS)
        Cleanup: 🛡️ Remove firewall rules
        Cleanup: ❌ Stop mDNS broadcast
    }
    
    DORMANT --> [*]: Device powered off
```

## Sequence Diagram - Full System Interaction

```mermaid
sequenceDiagram
    participant User
    participant Device
    participant Avahi
    participant mTLS
    participant Storage
    participant NFS
    participant Firewall
    participant Client
    
    Note over Device: STATE: DORMANT
    Device->>Device: Services stopped
    Device->>Storage: LUKS volume locked
    
    User->>Device: Press activation button
    
    Note over Device: STATE: ADVERTISING
    Device->>Avahi: Start mDNS broadcast
    Avahi-->>Client: Service discoverable (_thumbsup._tcp)
    Device->>mTLS: Listen on port 8443
    
    Client->>Device: Discover service via mDNS
    Client->>mTLS: Initiate connection
    
    mTLS->>mTLS: Mutual certificate validation
    alt mTLS Success
        mTLS-->>Device: Client authenticated (IP, CN)
        
        Note over Device: STATE: ACTIVE (First Client)
        Device->>Storage: Unlock LUKS volume
        Storage-->>Device: Volume unlocked
        Device->>Storage: Mount encrypted storage
        
        Device->>Firewall: Add rule: ALLOW client_ip → NFS
        Device->>NFS: Export /mnt/storage to client_ip
        NFS-->>Client: Mount point available
        
        Device->>Device: Log: Client connected
        Device->>Device: Start activity monitoring
        
        Client->>NFS: Read/Write files
        NFS->>Device: Log access
        
        opt Additional Client
            Client->>mTLS: Client 2 connects
            mTLS->>mTLS: Validate certificate
            Device->>Firewall: Add rule for client_2_ip
            Device->>NFS: Export to client_2_ip
        end
        
        Client->>Device: Disconnect
        Device->>Firewall: Remove client_ip rule
        Device->>NFS: Unexport from client_ip
        Device->>Device: Log: Client disconnected
        
        alt Last Client Disconnected
            Device->>Device: Start inactivity timer (60s)
            
            alt Timeout Expires
                Note over Device: STATE: DORMANT
                Device->>NFS: Unmount all exports
                Device->>Storage: Unmount filesystem
                Device->>Storage: Lock LUKS volume
                Device->>Firewall: Remove all client rules
                Device->>Avahi: Stop mDNS broadcast
                Device->>mTLS: Stop listening
                Device->>Device: Return to dormant state
            end
            
            alt New Client Before Timeout
                Device->>Device: Cancel timer
                Note over Device: Remain ACTIVE
            end
        end
        
    else mTLS Failure
        mTLS-->>Client: Connection rejected
        Device->>Device: Log: Failed authentication
    end
```

## Component Interaction Diagram

```mermaid
graph TB
    subgraph "Secure NAS Device"
        Button[Physical Button/Trigger]
        StateMachine[State Machine Controller]
        
        subgraph "State: DORMANT"
            D1[All services stopped]
            D2[Storage locked]
        end
        
        subgraph "State: ADVERTISING"
            A1[Avahi Daemon]
            A2[mTLS Listener:8443]
            A3[Storage locked]
        end
        
        subgraph "State: ACTIVE"
            AC1[mTLS Auth Handler]
            AC2[LUKS Manager]
            AC3[NFS Server]
            AC4[Firewall Manager]
            AC5[Activity Monitor]
            AC6[Access Logger]
        end
        
        Storage[(Encrypted Storage<br/>LUKS Volume)]
    end
    
    subgraph "Network"
        mDNS[mDNS/Avahi<br/>Service Discovery]
        
        Client1[Client 1<br/>Valid Cert]
        Client2[Client 2<br/>Valid Cert]
        Client3[Attacker<br/>No Valid Cert]
    end
    
    Button -->|Activate| StateMachine
    StateMachine -->|Transition| D1
    StateMachine -->|Transition| A1
    StateMachine -->|Transition| AC1
    
    A1 -->|Broadcast| mDNS
    mDNS -.->|Discover| Client1
    mDNS -.->|Discover| Client2
    mDNS -.->|Discover| Client3
    
    Client1 -->|Connect| A2
    Client2 -->|Connect| A2
    Client3 -->|Connect| A2
    
    A2 -->|Auth Success| AC1
    A2 -.->|Auth Fail| Client3
    
    AC1 -->|First Client| AC2
    AC2 -->|Unlock| Storage
    Storage -->|Mount| AC3
    
    AC1 -->|Client IP| AC4
    AC4 -->|iptables rule| AC3
    AC3 -->|NFS export| Client1
    AC3 -->|NFS export| Client2
    
    AC3 -->|Access events| AC6
    AC1 -->|Auth events| AC6
    AC5 -->|Monitor| AC3
    AC5 -->|Timeout| StateMachine
    
    style Client3 fill:#ffcccc
    style D2 fill:#ffcccc
    style A3 fill:#ffcccc
    style Storage fill:#ffffcc
    style AC6 fill:#ccffcc
```

## Authentication Flow Diagram

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant CA as Certificate Authority
    participant FW as Firewall
    participant ST as Storage
    
    Note over C,S: mTLS Handshake
    C->>S: ClientHello + Client Certificate
    S->>CA: Validate Client Certificate
    CA-->>S: Certificate Valid ✓
    S->>C: ServerHello + Server Certificate
    C->>CA: Validate Server Certificate
    CA-->>C: Certificate Valid ✓
    
    Note over C,S: Mutual Authentication Success
    
    S->>S: Extract Client IP & CN
    S->>FW: iptables -A INPUT -s client_ip -p tcp --dport 2049 -j ACCEPT
    S->>ST: Check if mounted
    
    alt First Client
        S->>ST: cryptsetup luksOpen
        S->>ST: mount /dev/mapper/secure_storage /mnt/storage
    end
    
    S->>S: Update /etc/exports with client_ip
    S->>S: exportfs -ra
    
    S-->>C: Connection Established + NFS Mount Info
    
    C->>S: NFS Mount Request
    S-->>C: NFS Mount Success
    
    Note over C,S: File Operations
    C->>S: Read/Write Files
    S->>S: Log Access
    
    C->>S: Disconnect
    S->>FW: iptables -D INPUT -s client_ip -p tcp --dport 2049 -j ACCEPT
    S->>S: Remove client_ip from /etc/exports
    S->>S: exportfs -ra
    
    alt Last Client Disconnected
        S->>S: Start 60s inactivity timer
        Note over S: Wait for timeout...
        S->>ST: umount /mnt/storage
        S->>ST: cryptsetup luksClose
        S->>S: Stop mDNS, return to DORMANT
    end
```

## Network Security Architecture

```mermaid
graph LR
    subgraph "Local Network"
        Internet[Internet/External Network]
        Router[WiFi Router]
        
        subgraph "NAS Device"
            WiFi[WiFi Interface]
            mDNS[mDNS/Avahi<br/>Port 5353]
            mTLSPort[mTLS Service<br/>Port 8443]
            NFSPort[NFS Server<br/>Port 2049]
            
            FW[iptables Firewall]
            Auth[Certificate Auth]
            
            subgraph "Storage Layer"
                LUKS[LUKS Encryption]
                FS[Filesystem]
                USB[USB Storage]
            end
        end
        
        ValidClient1[✓ Client 1<br/>Valid Cert<br/>192.168.1.100]
        ValidClient2[✓ Client 2<br/>Valid Cert<br/>192.168.1.101]
        InvalidClient[✗ Attacker<br/>No Valid Cert<br/>192.168.1.150]
    end
    
    Router --> WiFi
    
    WiFi --> mDNS
    mDNS -.->|Discover| ValidClient1
    mDNS -.->|Discover| ValidClient2
    mDNS -.->|Discover| InvalidClient
    
    ValidClient1 -->|1. mTLS Handshake| mTLSPort
    ValidClient2 -->|1. mTLS Handshake| mTLSPort
    InvalidClient -.->|1. mTLS Attempt| mTLSPort
    
    mTLSPort --> Auth
    Auth -->|✓ Valid| FW
    Auth -.->|✗ Invalid| InvalidClient
    
    FW -->|Allow 192.168.1.100| NFSPort
    FW -->|Allow 192.168.1.101| NFSPort
    FW -.->|Block 192.168.1.150| InvalidClient
    
    NFSPort --> LUKS
    LUKS --> FS
    FS --> USB
    
    NFSPort -->|2. NFS Mount| ValidClient1
    NFSPort -->|2. NFS Mount| ValidClient2
    
    style ValidClient1 fill:#ccffcc
    style ValidClient2 fill:#ccffcc
    style InvalidClient fill:#ffcccc
    style FW fill:#ffffcc
    style Auth fill:#ffffcc
    style LUKS fill:#ffcccc
```
