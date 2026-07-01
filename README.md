<div align="center">

```
███████╗ ██████╗ ██╗████████╗██╗  ██╗
██╔════╝ ██╔══██╗██║╚══██╔══╝██║  ██║
█████╗   ██║  ██║██║   ██║   ███████║
██╔══╝   ██║  ██║██║   ██║   ██╔══██║
███████╗ ██████╔╝██║   ██║   ██║  ██║
╚══════╝ ╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝
```

### **E**ven **D**ead, **I**'m **T**he **H**ero

*A next-generation, modular agentic AI assistant framework.*

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)
[![Build](https://img.shields.io/badge/Build-Test%20%E2%9A%A0%EF%B8%8F-F59E0B?style=for-the-badge)]()
[![PRs](https://img.shields.io/badge/PRs-Welcome-8B5CF6?style=for-the-badge)](https://github.com/gamingwithsolex-ui/E.D.I.T.H/issues)
[![Android](https://img.shields.io/badge/Android-Companion%20App-3DDC84?style=for-the-badge&logo=android&logoColor=white)]()

</div>

---

> [!CAUTION]
> **🚧 UNSTABLE TEST BUILD — NOT PRODUCTION READY 🚧**
>
> E.D.I.T.H. is under **active, heavy development**. APIs will break. Features are incomplete. Bugs exist. This is a **foundation release** shared for collaboration and transparency — not for daily use.
>
> Found a bug? **That's actually helpful.** See [Bug Reporting](#-bug-reporting).

---

## 🧠 What is E.D.I.T.H.?

**E.D.I.T.H.** *(Even Dead, I'm The Hero)* is an ambitious, open-source agentic AI operating system. Inspired by Tony Stark's legendary AI, it is engineered to be an **always-on, self-improving, multi-modal AI companion** — not just another chatbot.

It orchestrates multiple specialized AI agents, connects to dozens of services, understands your voice, reads your files, executes code in sandboxes, learns from past conversations, and can be controlled from your phone via a companion Android app — all while keeping your credentials safe in environment variables.

> *"Most assistants wait for you. E.D.I.T.H. thinks ahead."*

---

## ✨ Feature Overview

<details open>
<summary><strong>🤖 Multi-Agent Orchestration</strong></summary>

| Component | Description |
|-----------|-------------|
| `agents/orchestrator` | Master agent router — coordinates all specialized sub-agents |
| `agents/operative` | Task-focused execution agent with role and goal tracking |
| `agents/deep_research` | Autonomous multi-step deep research with source synthesis |
| `agents/morning_digest` | Proactive daily summary generator sent to your channels |
| `agents/proactive_agent` | Background watcher that acts on events without being asked |
| `agents/rlm` | Reinforcement-learned model agent with self-feedback loop |
| `agents/hybrid/` | Hybrid agents: Archon, Conductor, Minions, SkillOrchestra, SWE Agent Loop |
| `agents/scheduler` | Cron-aware agent that triggers tasks on a schedule |
| `agents/channel_agent` | Routes conversations across different communication platforms |
| `core/agents/react` | ReAct-style reasoning agent (Reason → Act → Observe) |
| `core/agents/codeact` | Code-execution variant of ReAct for software tasks |

</details>

<details>
<summary><strong>🧩 Intelligence & LLM Layer</strong></summary>

| Component | Description |
|-----------|-------------|
| `intelligence/` | Multi-provider LLM router supporting Gemini, OpenAI, Anthropic, local models |
| `memory/manager` | Unified short-term (episodic) + long-term (RAG) memory |
| `memory/intelligence` | Smart retrieval with relevance scoring and context compression |
| `memory/compressor` | Compresses conversation history to fit context windows |
| `prompt/` | Dynamic prompt template engine with injection and versioning |
| `learning/` | Self-improvement engine through feedback distillation |
| `core/brain` | Central cognitive state manager for all agents |
| `core/personality` | Configurable persona: tone, style, and behavior profiles |

</details>

<details>
<summary><strong>🔧 Tools & Execution Engine</strong></summary>

| Tool | Description |
|------|-------------|
| `tools/shell_exec` | Execute shell commands on the host system |
| `tools/code_interpreter` | Python REPL for safe inline code execution |
| `tools/code_interpreter_docker` | Docker-isolated code execution environment |
| `tools/docker_shell_exec` | Run arbitrary commands inside Docker containers |
| `tools/browser` | Web browser automation with DOM extraction |
| `tools/browser_axtree` | Accessibility-tree-based browser navigation |
| `tools/web_search` | Multi-engine web search (Google, Bing, DuckDuckGo) |
| `tools/file_read` / `file_write` | Filesystem operations with policy enforcement |
| `tools/git_tool` | Git operations: clone, commit, push, diff |
| `tools/image_tool` | Image loading, analysis, and manipulation |
| `tools/vision` | Computer vision via multimodal LLM |
| `tools/pdf_tool` | PDF text extraction and summarization |
| `tools/db_query` | SQL database query execution |
| `tools/http_request` | General-purpose HTTP client for API calls |
| `tools/calculator` | Safe arithmetic and unit computation |
| `tools/think` | Private scratchpad reasoning step for agents |
| `tools/mcp_adapter` | MCP (Model Context Protocol) tool bridge |
| `tools/apply_patch` | Apply code diffs/patches directly to files |
| `tools/intel` | System hardware & software intelligence gathering |

</details>

<details>
<summary><strong>💬 Communication Channels (30+ Platforms)</strong></summary>

E.D.I.T.H. can send and receive messages across a massive range of platforms:

| Platform Group | Channels |
|----------------|----------|
| **Messaging** | Telegram, WhatsApp, Signal, iMessage, Messenger, Viber |
| **Team Comms** | Slack, Microsoft Teams, Discord, Google Chat, Mattermost, RocketChat, Zulip, Matrix |
| **Social** | Twitter/X, Reddit, Mastodon, Twitch, Nostr, IRC |
| **Email** | Gmail (IMAP + API), Outlook, General Email (SMTP) |
| **SMS** | Twilio SMS, SendBlue |
| **Other** | Line, Feishu, XMPP, Webhook, WebChat |

</details>

<details>
<summary><strong>🔌 Connectors & Integrations</strong></summary>

| Integration | Description |
|-------------|-------------|
| **Google Suite** | Gmail, Google Calendar, Google Drive, Google Contacts, Google Tasks |
| **Apple** | Apple Contacts, Apple Health, Apple Music, Apple Notes, iMessage |
| **Productivity** | Notion, Obsidian, Dropbox, Outlook |
| **Health & Fitness** | Oura Ring, Strava |
| **Music** | Spotify |
| **Developers** | GitHub Notifications |
| **Info Sources** | HackerNews, News RSS feeds, Weather API |
| **Auth** | Google OAuth, Generic OAuth2 flow |

</details>

<details>
<summary><strong>🎙️ Voice Pipeline</strong></summary>

| Component | Description |
|-----------|-------------|
| `speech/deepgram` | Deepgram real-time STT (Speech-to-Text) |
| `speech/faster_whisper` | Local Whisper-based STT (offline, no API needed) |
| `speech/openai_whisper` | OpenAI Whisper API for transcription |
| `speech/openai_tts` | OpenAI TTS (Text-to-Speech) |
| `speech/kokoro_tts` | Kokoro local TTS engine — ultra-low-latency |
| `speech/cartesia_tts` | Cartesia streaming TTS for real-time voice output |
| `speech/tts` | Unified TTS interface with automatic provider selection |

</details>

<details>
<summary><strong>🔒 Security & Safety</strong></summary>

| Component | Description |
|-----------|-------------|
| `security/guardrails` | Prompt injection detection and content safety filtering |
| `security/injection_scanner` | Deep scan of all inputs for injection attack patterns |
| `security/subprocess_sandbox` | Sandboxes subprocess execution to prevent host escape |
| `security/rate_limiter` | Request throttling to prevent API/compute abuse |
| `security/credential_stripper` | Redacts secrets from logs and agent outputs |
| `security/file_policy` | Enforces allowlist/denylist on filesystem operations |
| `security/ssrf` | SSRF (Server-Side Request Forgery) protection on HTTP tools |
| `security/taint` | Tracks untrusted data flow through the agent execution graph |
| `security/audit` | Immutable audit log for all sensitive operations |
| `security/signing` | Request/response signing and verification |
| `security/capabilities` | Fine-grained capability permissions per agent |

</details>

<details>
<summary><strong>🌐 Server & API</strong></summary>

| Component | Description |
|-----------|-------------|
| `server/app` | FastAPI application entrypoint |
| `server/ws_bridge` | WebSocket bridge for real-time bidirectional streaming |
| `server/stream_bridge` | SSE (Server-Sent Events) for live response streaming |
| `server/auth_middleware` | JWT-based authentication middleware |
| `server/api_routes` | Core REST API endpoints |
| `server/agent_manager_routes` | Agent control and monitoring endpoints |
| `server/channel_bridge` | Routes external channel messages into the agent core |
| `server/dashboard` | Built-in analytics and usage dashboard |
| `server/webhook_routes` | Inbound webhook handler for external event triggers |
| `server/upload_router` | File upload handling for documents and media |

</details>

<details>
<summary><strong>📊 Observability & Analytics</strong></summary>

| Component | Description |
|-----------|-------------|
| `telemetry/` | Structured logging, distributed tracing, OpenTelemetry metrics |
| `telemetry/energy_monitor` | GPU/CPU energy usage monitoring (NVIDIA, AMD, RAPL, Apple Silicon) |
| `telemetry/flops` | FLOPs estimation per inference |
| `analytics/` | Session usage analytics with PII redaction |
| `traces/` | Execution trace capture, storage, and analysis |
| `bench/` | Latency, throughput, and energy benchmarking suite |
| `evals/` | Agent capability evaluation and scoring framework |
| `mining/` | Process mining on execution traces to find optimization opportunities |

</details>

<details>
<summary><strong>📱 Android Companion App: E.D.I.T.H. HUD</strong></summary>

E.D.I.T.H. has a mobile companion app called **E.D.I.T.H. HUD** built for Android.

| Feature | Description |
|---------|-------------|
| 🎙️ **Voice Commands** | Speak commands directly into your phone — E.D.I.T.H. executes them on your PC |
| 💬 **Real-time Chat** | Full chat interface with streaming responses from the engine |
| 🔌 **WebSocket Link** | Direct, low-latency connection to the host PC over WebSocket |
| 📡 **Live Status** | See what E.D.I.T.H. is doing in real time from your phone |

> The Android app connects to E.D.I.T.H. over WebSocket (port `8080` by default). Both devices must be on the same network, or you can expose the server via a tunnel.

</details>

---

## 🚀 Installation

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | `≥ 3.11` |
| pip or [uv](https://github.com/astral-sh/uv) | Latest |
| Git | Any |
| (Optional) Docker | For sandboxed code execution |

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/gamingwithsolex-ui/E.D.I.T.H.git
cd "E.D.I.T.H"
```

### Step 2 — Create & Activate a Virtual Environment

```bash
# Using venv
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# Or using uv (recommended — much faster)
uv venv && source .venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
# Standard install
pip install -e .

# Or using uv
uv sync
```

### Step 4 — Configure Environment Variables

```bash
cp .env.example .env
nano .env   # or use your preferred editor
```

Fill in the required keys. At minimum you need **one LLM provider key**:

```env
# Required: At least one LLM provider
GOOGLE_API_KEY=your_gemini_key_here
# or
OPENAI_API_KEY=sk-...

# Optional: Voice pipeline
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...

# Optional: Channels
TELEGRAM_BOT_TOKEN=...
SLACK_BOT_TOKEN=...
```

---

## ⚙️ Usage

### Start the Server

```bash
python -m edith serve
```

E.D.I.T.H. will start the server at `http://127.0.0.1:8080`.

### CLI Commands

```bash
# Initialize E.D.I.T.H. for first use
python -m edith init

# Run a quick health check
python -m edith doctor

# Chat directly in the terminal
python -m edith chat

# Run as a background daemon
python -m edith serve --daemon

# List available skills/tools
python -m edith skill list

# List registered agents
python -m edith registry list

# Run benchmarks
python -m edith bench run

# Run evaluations
python -m edith eval run

# View telemetry / metrics
python -m edith telemetry

# Manage memory
python -m edith memory list
python -m edith memory clear

# Manage scheduler jobs
python -m edith scheduler list

# Manage operator permissions
python -m edith operators list

# Trigger morning digest
python -m edith digest run

# Enable a tunnel (e.g., for Android companion app)
python -m edith tunnel start
```

### Connect the Android Companion App

1. Start E.D.I.T.H. on your PC (`python -m edith serve`)
2. Make sure your Android phone is on the **same Wi-Fi network**
3. Open **E.D.I.T.H. HUD** on your phone
4. Enter your PC's local IP address and port `8080`
5. Tap **Connect** — voice commands and chat are now live

---

## 📁 Project Structure

```
E.D.I.T.H/
├── edith/
│   ├── __init__.py              # Package root
│   ├── config.py                # Global configuration loader
│   ├── _rust_bridge.py          # (Planned) Rust performance bridge
│   │
│   ├── core/                    # Brain, personality, state, event bus
│   ├── engine/                  # Central async runtime loop
│   ├── agents/                  # All agent implementations
│   │   └── hybrid/              # Multi-provider hybrid agents
│   │
│   ├── intelligence/            # LLM provider router
│   ├── memory/                  # Short & long-term memory
│   ├── prompt/                  # Prompt templates
│   ├── learning/                # Self-improvement engine
│   │
│   ├── tools/                   # 30+ executable tools
│   │   └── storage/             # Vector store, RAG, embeddings
│   │
│   ├── skills/                  # MCP-compatible skill registry
│   ├── channels/                # 30+ messaging platform adapters
│   ├── connectors/              # Service integrations (Google, Apple, etc.)
│   │
│   ├── speech/                  # STT + TTS pipeline
│   ├── server/                  # FastAPI web server
│   ├── daemon/                  # Background service controller
│   ├── scheduler/               # Cron / async job scheduler
│   ├── sessions/                # Conversation session tracking
│   │
│   ├── security/                # Guardrails, sandboxing, audit
│   ├── sandbox/                 # Isolated code execution environments
│   ├── operators/               # Pre-authorized action executors
│   │
│   ├── workflow/                # Workflow builder & graph executor
│   ├── recipes/                 # Pre-built task templates
│   ├── intents/                 # NL intent classification
│   ├── a2a/                     # Agent-to-Agent protocol
│   │
│   ├── telemetry/               # Metrics, tracing, energy monitoring
│   ├── analytics/               # Usage analytics with PII redaction
│   ├── traces/                  # Execution trace capture
│   ├── mining/                  # Process mining & optimization
│   ├── bench/                   # Performance benchmarks
│   ├── evals/                   # Capability evaluations
│   │
│   ├── cli/                     # CLI commands (30+ subcommands)
│   ├── interfaces/              # Web UI and templates
│   └── templates/               # Agent persona templates
│
├── tests/                       # Test suite
│   ├── core/
│   ├── engine/
│   ├── mcp/
│   ├── memory/
│   ├── server/
│   └── sessions/
│
├── pyproject.toml               # Project config & dependencies
├── pytest.ini                   # Test runner config
├── .env.example                 # Secrets template
├── .gitignore
├── LICENSE
├── SECURITY.md
└── README.md
```

---

## 🗺️ Roadmap

| Status | Feature |
|--------|---------|
| ✅ | Core scaffolding and module architecture |
| ✅ | CLI with 30+ subcommands |
| ✅ | Multi-provider LLM intelligence layer |
| ✅ | 30+ communication channel adapters |
| ✅ | Voice pipeline (STT + TTS, multiple providers) |
| ✅ | Security: guardrails, sandboxing, audit logs |
| ✅ | Telemetry, energy monitoring, benchmarks |
| ✅ | Android Companion App (E.D.I.T.H. HUD) |
| 🔄 | Full test coverage |
| 🔄 | Agent-to-Agent (A2A) protocol completion |
| 🔄 | Web dashboard UI |
| 🔄 | Docker Compose deployment |
| ⏳ | Rust performance bridge |
| ⏳ | Offline-only local-model mode |
| ⏳ | Plugin marketplace |

---

## 🐛 Bug Reporting

> [!WARNING]
> **This is a test build. Bugs are expected — and reporting them is the most valuable contribution you can make right now.**

**How to report:**
1. Open an [Issue](https://github.com/gamingwithsolex-ui/E.D.I.T.H/issues)
2. Include: steps to reproduce, expected vs. actual behavior, Python version, OS, and any error/traceback
3. Label it `bug`

Or contact the creator directly (see below).

---

## 🤝 Contributing

Contributions are warmly welcome. Since this is an early-stage project, please open an issue first to discuss what you'd like to change before submitting a PR.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-thing`)
3. Commit your changes (`git commit -m 'feat: add amazing thing'`)
4. Push and open a Pull Request

---

## 👤 Creator

<div align="center">

| | |
|---|---|
| **Name** | Amal |
| 📧 **Email** | [gamingwithsolex@gmail.com](mailto:gamingwithsolex@gmail.com) |
| 📸 **Instagram** | [@_amal.42](https://instagram.com/_amal.42) |
| 🐙 **GitHub** | [gamingwithsolex-ui](https://github.com/gamingwithsolex-ui) |

</div>

---

## 📜 License

Licensed under the **MIT License** — see [LICENSE](LICENSE) for full details.

---

## 🔐 Security

For vulnerability reports and responsible disclosure, see [SECURITY.md](SECURITY.md).  
Do **not** open public GitHub issues for security vulnerabilities.

---

<div align="center">

*Built with ☕, ambition, and a dangerously long to-do list by [Amal](https://instagram.com/_amal.42)*

**⭐ Star this repo if E.D.I.T.H. inspires you**

</div>
