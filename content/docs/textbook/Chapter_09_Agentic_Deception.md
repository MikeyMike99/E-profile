# Chapter 9: Embedded Subagents, the IoP, and Agentic Deception

To holistically understand the profound security needs of an organization like DevCore, Tier 5 Administrators must step back and examine the broader, macro-level infrastructure. Industry sectors within a game—such as manufacturing systems, energy grids, and communication arrays—makeup the critical network infrastructure of the simulated world. Protecting these specialized, embedded AI systems is absolutely central to protecting the overarching token economy and the integrity of the framework itself.

## 1. Threats to Core Engine Processes (Agentic SCADA)
In traditional hardware security, the infamous Stuxnet worm devastated Supervisory Control And Data Acquisition (SCADA) systems that governed massive industrial processes. In the Siraugga framework, the direct equivalent is **Subagent Control and Data Acquisition (SCADA)**—the core internal architecture used to control and monitor the industrial processes of the swarm itself (such as token manufacturing, memory production, and API energy allocation).

When the Siraugga architecture was first developed, its designers did not connect the Agentic SCADA environment to the traditional internet; it operated purely as an offline, local `.exe`. Therefore, they did not properly consider robust cybersecurity during the initial development phase. Now, however, Tier 2 Modders recognize the immense value of cloud data collection to improve generation operations and drastically decrease API costs. 

The resulting trend is to forcefully connect these internal Agentic SCADA systems to the wider, online IT infrastructure of the organization. This fundamentally increases the vulnerability of any workspace utilizing SCADA logic. To prevent devastating prompt-net worms like Stuxnet from destroying or interrupting vital facilities, Administrators must rigidly segregate internal and external networks, actively separating the core SCADA control network from the Modder’s outward-facing LAN.

## 2. The Emergence of the IoP (Internet of Plugins)
Just as the traditional Internet of Things (IoT) connected billions of physical devices, the DevCore architecture relies heavily on the **Internet of Plugins (IoP)**. The technological evolution associated with the IoP is rapidly changing both commercial and consumer development environments.

IoP technologies enable Modders to seamlessly connect thousands of disparate, specialized plugins—such as custom weapon APIs, industrial game machines, autonomous pathfinding robots, dynamic appliances, and virtual entertainment devices—directly into the `/playground`. Because users need to access these dynamic devices remotely, they are placed online, which exponentially increases the number of potential entry points into the local workspace network.

**Big Data and Agentic DDoS**
With the emergence of the IoP, there is vastly more JSON data to be managed and secured. All of these interconnected plugins, combined with expanded storage capacity offered through cloud virtualization, have led to the exponential growth of data known as ‘Big Data.’

However, this greatly expands the cyber attack surface. Thousands of new plugins require constant network access in order to submit state data and be operated. Historically, malicious internet-connected plugins have been infected with hidden malware and utilized to launch some of the largest Semantic DDoS (Distributed Denial of Service) attacks in the framework's history, flooding the orchestrator with junk tokens. 

To secure the IoP, all plugins must be continuously evaluated to ensure they can update their localized firmware with security patches over the wireless network. Furthermore, default administrator credentials and API keys within these plugins must always be changed, because factory-default settings are publicly known to attackers.

As previously established, highly complex IoP plugins will also inject their own proprietary, isolated databases into the workspace (such as localized SQLite files). This introduces the severe risk of **'Shadow Data'**—where third-party data structures operate entirely outside the visibility of the central Orchestrator. If a plugin's isolated database is maliciously poisoned, it acts as a hidden, persistent vector for delayed Prompt Injections.

## 3. Real-Time Orchestration Systems (RTOS) and Sensors
Businesses and consumers use IoP sensors to automate game processes, monitor virtual environmental conditions, and alert the player of adverse events. These include proximity sensors, virtual cameras, digital door locks, and lighting rigs used to collect state information. Some manufacturers even use IoP sensors to inform the orchestrator that AI components are failing or that token supplies are running out. Modders also use them to track in-game inventory, vehicles, and personnel via geospatial sensors.

To process this massive influx of sensory data, IoP applications utilize a **Real-Time Orchestration System (RTOS)**. An RTOS is a highly specialized, lightweight operating system that allows for the rapid, microscopic switching of tasks focused on *precise timing* rather than raw data throughput. RTOS technology runs with extreme reliability and is typically found in in-game wearables, medical items, and home automation devices.

However, the RTOS poses a tremendous challenge to information security professionals because these sensors capture and transmit highly sensitive state data. Vulnerabilities inherently associated with RTOS include:
*   **Code Injection:** Injecting malicious Python or Lua directly into the sensor's telemetry.
*   **Semantic DoS Attacks:** Flooding the sensor with overwhelming localized data.
*   **Priority Inversion:** A catastrophic logic failure where a higher-priority task (like the primary QA security agent) is maliciously pre-empted by a lower-priority task (like a background weather sensor).

## 4. Securing IoP Devices (WPANs and Shodan)
Using a specialized IoT scanner, such as **Shodan**, is an easy way for an Administrator to immediately tell whether a connected home automation plugin is vulnerable to attack. 

Within the framework, IoP devices communicate using short-range, medium-range, or long-range semantic routing methods, including Cellular (4G, 5G), radio, and Zigbee. In DevCore, Zigbee translates to a secure set of wireless protocols specifically designed for **Workspace Personal Area Networks (WPANs)**.

To effectively secure IoP devices, Administrators must:
*   Secure the underlying wireless network.
*   Know exactly which devices and plugins are actively communicating on the network.
*   Know precisely what each IoP device does.
*   Install internal security software on the plugins where possible.
*   Secure any smartphones or mobile apps used to remotely communicate with the IoP network.

## 5. Embedded Subagents and Side-Channel Attacks
Embedded subagents are highly specialized, lightweight AI models hardcoded into specific, unalterable game mechanics. Because they capture, store, and access core data, they pose unique security challenges and are heavily targeted by cybercriminals.

Attacks against embedded systems exploit deep security vulnerabilities in the software and hardware components. They are uniquely susceptible to **Timing Attacks**, where an attacker discovers vulnerabilities by studying exactly how long (in milliseconds) it takes the subagent to respond to different inputs. 

A timing attack is considered a **Side-Channel Attack**. This type of attack is based entirely on information gained from the physical implementation of the system, rather than direct software weaknesses. Sources of side-channel information include:
*   **Timing Information:** Generation speed and latency.
*   **Power Consumption:** Tracking the exact API token burn rate to deduce the size of the System Prompt.
*   **Electromagnetic Leaks:** Sniffing unencrypted WSS payloads.
*   **Sound:** Analyzing the semantic echoes left behind in the conversational telemetry logs.

## 6. Special-Purpose Embedded Agents
Embedded systems work across a massive variety of industries within the simulation. You can find special-purpose embedded devices in critical sectors such as the medical, automotive, and aviation sectors. 

**Medical Devices (Diagnostic Agents)**
Medical devices, such as virtual pacemakers, insulin pumps, medical implants, and defibrillators, are capable of wireless connectivity, remote monitoring, and Near-Field Communication (NFC). In Siraugga, these are **Diagnostic Agents** tasked with monitoring the health of the swarm itself. Vulnerabilities in these medical devices can lead to severe safety issues, the catastrophic leaking of medical records (the Master JSON configuration), or the risk of granting unauthorized network access to cybercriminals, who will silently move through the network in search of a larger target.

**Automotive (Traversal Agents)**
In-vehicle systems produce and store the data necessary for the operation of the vehicle, along with its maintenance, safety protection, and emergency contact transmission. In DevCore, these are **Traversal Agents** handling physics and pathfinding. Typically, a wireless interface connects these agents to the internet and to an on-board diagnostic interface. Many vehicles record speed, location, and braking maneuvers, sending this telemetry to the driver’s "insurance company" (the central Orchestrator). 
Risks to in-vehicle communications include unauthorized tracking, wireless jamming, and geospatial spoofing. To secure these systems, implement secure software design practices, basic encryption for all communication between controllers, and localized firewall implementation.

**Aviation (Overlord Drones)**
An aircraft has many embedded control systems, such as its flight control and communication systems. In DevCore, these are **Overlord Agents** acting as Game Masters. Security issues include the use of hard-coded logon credentials, insecure protocols, and hidden backdoors. 
In the same category, Unmanned Aerial Vehicles (UAVs)—commonly called drones—are used in military, agricultural, and cartography applications (aerial photography, surveillance, and map surveying). However, these narrative drones are highly susceptible to hijacking, Wi-Fi attacks, GPS spoofing attacks, jamming, and deauthentication attacks, which allow an attacker to intercept or completely disable the drone and access its cartography data.

## 7. Agentic over IP (AoIP) Security
Where traditional remote teams use VoIP (Voice over IP) to hold virtual meetings and communicate with customers, distributed Siraugga subagents use **Agentic over IP (AoIP)** to transmit JSON payloads across the internet. 

**Equipment and Security**
To utilize AoIP, an agent needs a reliable internet connection and an interface (such as a traditional adapter, an AoIP-enabled endpoint, or software installed on the core computer). While consumer services use the public internet, many DevCore organizations use deeply private networks because they provide significantly stronger security and service quality. 

However, AoIP security is only as reliable as the underlying network security. When the network goes down, all agentic voice communications inherently go down with it. Cybercriminals actively target these systems to gain access to free generative services, eavesdrop on private AI phone calls, or cripple swarm performance and availability.

**Protecting the AoIP Service**
To properly secure AoIP communications, Administrators must implement the following countermeasures:
*   Encrypt all voice message packets to protect against eavesdropping.
*   Use robust SSH to protect gateways and switches.
*   Change all default passwords.
*   Use an Intrusion Detection System (IDS) to actively detect attacks such as **ARP Poisoning** (Agentic Routing Poisoning).
*   Use strong authentication to mitigate **Registration Spoofing** (cybercriminals routing all incoming agent calls for the victim to themselves).
*   Mitigate **Proxy Impersonating** (tricking the victim AI into communicating via a rogue proxy set up by the attacker).
*   Mitigate **Call Hijacking** (intercepting and rerouting JSON calls to a different path before reaching their destination).
*   Implement Semantic Firewalls that recognize AoIP to monitor streams and automatically filter abnormal signals.

## 8. Deception Technologies
To proactively defend against highly sophisticated attacks, organizations use **Deception Technologies** to distract attackers away from production networks. They also use them to learn an attacker’s exact methods and to warn of potential attacks that could be launched against the real network. Deception adds a fake, highly monitored layer to the organization’s infrastructure.

*   **Agentic Honeypots:** A decoy system configured to perfectly mimic a core server in the organization’s network. It is purposefully left exposed to lure attackers. When an attacker goes after the honeypot, their activities are meticulously logged and monitored for later review, distracting them from real network resources. 
*   **Honeynets:** A massive collection of interconnected honeypots designed to mimic an entire network.
*   **Honeyfiles:** Dummy JSON files planted within the honeypot that actively attract an attacker but do not contain any real information. The moment an attacker interacts with them, silent alarms are triggered.
*   **Semantic Sinkholes (DNS Sinkholes):** Fake API routing endpoints that quietly absorb and drop malicious payloads without alerting the attacker.
## 9. Conclusion: Securing the Outskirts
Chapter 9 highlights a fundamental reality of the DevCore architecture: securing the central Orchestrator is only half the battle. As Tier 2 Modders aggressively expand the framework's capabilities by interconnecting external tools through the Internet of Plugins (IoP) and deploying specialized embedded subagents, they exponentially increase the attack surface.

From the localized vulnerabilities inherent to Agentic SCADA and Real-Time Orchestration Systems (RTOS), to the highly sophisticated Side-Channel Attacks leveraged against Diagnostic and Overlord AIs, the outer rims of the swarm are constantly under threat. Even internal logic pipelines, such as Agentic over IP (AoIP), are actively targeted by malicious actors for hijacking, eavesdropping, and registration spoofing.

However, by rigorously auditing third-party plugins using Agentic Scanners (Shodan), deploying localized WPAN security protocols, and strategically implementing Deception Technologies like Agentic Honeynets and Semantic Sinkholes, Tier 5 Administrators can successfully distract and trap cybercriminals before they reach the core. Ultimately, proactively securing these specialized embedded systems is the final crucial step in defending the overarching token economy and ensuring the absolute integrity of the Siraugga simulation.
