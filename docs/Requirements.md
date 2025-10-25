# Capstone: Design and Implementation of a Secure On-Demand

# Wireless Thumb Drive

## Constantinos Kolias

## August 6, 2025

## 1 Project Overview

The proliferation of personal data across devices, applications, and networked services has created a
heightened need for secure, user-controlled, and infrastructure-independent storage solutions. This
capstone project proposes the development of a portable and secure Wi-Fi-enabled Network-Attached
Storage (NAS) system, designed to operate in on-demand mode and rely exclusively on open and
standardized protocols. Built on a Raspberry Pi or equivalent single-board computing platform, this
device will pair with a USB storage drive to serve as an ephemeral file-sharing node that advertises itself
over a local network, securely authenticates clients, and allows authenticated file access. The project
responds to contemporary demands for privacy-aware, self-hosted systems, especially in environments
where commercial cloud-based services are infeasible or untrusted.
What distinguishes this system is its emphasis on user control, decentralized ownership, and trans-
parent implementation. The device remains silent and undiscoverable until manually activated. Upon
user input—such as a button press—it becomes discoverable on the local wireless network through
multicast DNS (mDNS), offering secure file-sharing services via the Network File System (NFS). All
communications and data transfers are confined to the Wi-Fi interface and restricted to authenticated
client machines, which must present valid X.509 certificates. These certificates, issued by a local or
pre-established Certificate Authority (CA), ensure mutual trust between the storage device and its
users. The goal is to allow a data owner to retain full custody and control of shared information, while
preserving security, usability, and portability.

## 2 Project Objectives

The primary objective of this capstone is to implement a fully functional, standards-compliant secure
NAS solution that can be deployed without external dependencies. From a pedagogical perspective,
the project aims to guide students through the complete design process of a cybersecurity-centric
system—from threat modeling and protocol selection to low-level implementation and system test-
ing. The learning emphasis lies in building practical skills in embedded system configuration, secure
networking, open-source protocol integration, and cryptographic infrastructure deployment. The sys-
tem should support mutual TLS authentication, certificate revocation, encrypted storage, time-based
access control, encrypted backups, and a secure update mechanism. All of these features must be
implemented using transparent and reproducible tools with accompanying technical documentation.
Secondarily, the proposed system should be capable to offer a set of advanced features including
operation in peer-to-peer (P2P) mode. In this extended design, multiple portable NAS devices—each
running a variant of the system developed in the core project—can discover one another on a local
network and engage in mutual file synchronization. Such a distributed storage model enables con-
tent to be shared or mirrored across trusted peers without a central server. This scenario becomes
particularly compelling in decentralized, infrastructure-less contexts such as field deployments or com-
munity networks. Enabling such P2P functionality introduces questions of version control, consensus
on shared file state, conflict resolution, and selective synchronization. Moreover, this architecture ne-
cessitates secure mutual authentication between nodes, necessitating advanced PKI management or
shared trust anchors. Students interested in distributed systems and cryptographic protocols could
explore implementations inspired by distributed hash tables, Merkle trees, or quorum consensus.


Additionally, students must also investigate attribute-based access control schemes to enhance file-
level confidentiality. Rather than relying solely on binary certificate validity, access to data could
be governed by embedded attributes in client certificates, enforced using Attribute-Based Encryption
(ABE). With Ciphertext-Policy ABE, for example, content owners could encrypt files such that only
devices satisfying particular role or policy requirements (e.g., “staff,” “device region:west”) would be
able to decrypt them. This would introduce students to modern cryptographic primitives and increase
the granularity of trust enforcement.
Finally, device behavior could also be enhanced through anomaly detection mechanisms that mon-
itor for unusual client access patterns or environmental deviations. Machine learning-based baselining
of activity logs—e.g., unexpected frequency of accesses, failed authentication attempts, or abnormal
file modification sequences—could support early warning of misuse or compromise.

## 3 Technical Approach

The implementation of the proposed portable and secure Wi-Fi NAS device begins with the configura-
tion of a single-board computing platform such as a Raspberry Pi. The operating system environment
will be based on a lightweight Linux distribution, with Raspberry Pi OS Lite or OpenWrt selected
for their minimal resource footprint and extensive support for embedded hardware and network inter-
faces. Wireless functionality is central to the project, and students will configure the Wi-Fi interface
to operate either in access point mode or client mode, depending on whether the device is to serve as
a standalone hotspot or integrate into an existing network.
Upon manual activation—triggered, for example, via a physical button—the device initializes its
services and becomes discoverable on the local network using multicast DNS (mDNS). The Avahi
daemon will be responsible for service discovery and hostname advertisement. The advertised service
is a secured Network File System (NFS) share, which is configured to accept connections only from
clients that present valid X.509 certificates. The mutual TLS handshake forms the basis of the trust
model, ensuring that only authenticated and authorized machines can access the shared storage.
To ensure data-at-rest protection, the attached USB storage will be formatted with a LUKS-
encrypted volume. The unlocking of this volume is conditioned on the success of the mutual TLS
authentication process. In effect, the device will not mount the storage drive unless it verifies the
client’s certificate against a local Certificate Authority (CA) and confirms its validity through certificate
revocation checking. This mechanism provides a high level of assurance regarding the integrity and
authenticity of both the device and the client accessing it.
Secured communication between the NAS and its clients will be established using OpenSSL or
stunnel, which encapsulate NFS traffic within an encrypted tunnel. The device will log all client
interactions, including authentication outcomes, failed connection attempts, and file access activities.
These logs are essential for supporting both usage auditing and post-event forensics. An inactivity
monitor will observe system usage patterns and, in the absence of sustained activity over a configurable
period, will automatically return the device to a dormant state. This behavior minimizes its exposure
on the network and conserves power.
Backup functionality will be implemented via secure automation routines using tools such as rsync
over SSH. These routines will encrypt and transmit selected data sets to a predefined remote end-
point for redundancy. The backup process will be designed to be efficient and resilient to network
interruptions, and the security of the remote target will be managed using SSH key-based access and
encrypted channels. In parallel, a secure software update pipeline will be developed. This will involve
cryptographically signed update manifests and scripts. Students will be responsible for designing
a mechanism to verify the authenticity and integrity of these updates prior to application, thereby
mitigating the risks associated with unauthorized or tampered software components.
To support decentralized synchronization, students will implement a peer-to-peer (P2P) file sharing
mode. This will be achieved through the use of Zeroconf-based discovery via Avahi, paired with mTLS
authentication to verify peer legitimacy. File synchronization will be orchestrated using Syncthing,
which provides encrypted, versioned, and cross-platform file sync capabilities. The project will con-
figure Syncthing to operate in a mutually authenticated mode, and the software stack must handle
network partitions, selective synchronization, and timestamp-based conflict resolution.
For fine-grained access control, students will implement Ciphertext-Policy Attribute-Based En-
cryption (CP-ABE) using open-source libraries such as Charm-Crypto. Files will be encrypted with


embedded policies, and only client devices presenting certificates with the required attributes will be
able to decrypt and access the data. This ensures flexible and secure role-based access management.
Anomaly detection capabilities will be developed using Python-based log parsers and lightweight
machine learning models such as isolation forests or statistical profiling techniques. These models will
monitor access patterns and flag anomalous activity such as repeated access attempts, high-frequency
reads, or deviation from established user behaviors. Notifications will be sent to the device owner, and
suspicious activity logs will be retained for audit.

## 4 Evaluation and Deliverables

Assessment of student work will be conducted across several axes, including the completeness of the
functional implementation, the effectiveness of the security controls, the transparency and reproducibil-
ity of the system setup, and the clarity of documentation. Each team is expected to deliver a fully
operational prototype of the NAS device, complete with the configured operating system, encryption
schemes, networking setup, certificate infrastructure, and access control mechanisms. The prototype
must demonstrate secure activation, authenticated discovery, and reliable data sharing behavior under
typical operational conditions.
The final deliverables will include all source code, system configurations, service scripts, and sup-
porting documentation detailing system architecture, design decisions, and testing procedures. The
system’s behavior will be validated in a demonstration session, where students will be required to show
real-time mutual authentication, certificate revocation enforcement, file access authorization, auto-lock
activation, and encrypted backup operations. Additionally, the secure update workflow must be tested
using a digitally signed software update. Students will also present their work formally, explaining
their threat models, cryptographic design, network configuration, and implementation challenges.
Where project extensions such as peer-to-peer synchronization or attribute-based access control
have been pursued, these will be evaluated for correctness, performance, and security adherence.
The incorporation of anomaly detection will be assessed through simulation of abnormal behaviors
and validation of detection responses. Grading will emphasize not only functionality but also the
modularity, extensibility, and documentation quality of the system, thereby preparing students to
communicate complex security designs clearly and effectively.

## 5 Learning Outcomes

Upon completion of the project, students will have demonstrated a mastery of secure system design
and implementation in resource-constrained environments. They will gain hands-on experience in
configuring embedded Linux platforms and integrating network services into a portable NAS device.
By working with open protocols and cryptographic tools, they will learn to engineer trustworthy
communication and storage workflows in the absence of commercial infrastructure.
Specifically, students will:

- Configure and harden embedded Linux environments for secure device operation
- Deploy and secure mDNS and NFS services using mutual TLS and X.509 certificates
- Implement certificate management, revocation checking, and access logging mechanisms
- Encrypt storage using LUKS and enforce unlocking only after client authentication
- Script backup operations using rsync over SSH with encrypted transport
- Explore optional peer-to-peer file synchronization across trusted NAS devices
- Experiment with Attribute-Based Encryption (ABE) for fine-grained access control

These outcomes prepare students for careers in cybersecurity, embedded systems, and privacy-
aware network services by blending theoretical understanding with rigorous, hands-on practice in
system security engineering.
