# <img src="https://img.shields.io/badge/E.D.I.T.H.-AI%20Assistant-blueviolet?style=for-the-badge&logo=robot&logoColor=white" alt="E.D.I.T.H." />

<div align="center">

```
███████╗ ██████╗  ██╗ ████████╗ ██╗  ██╗
██╔════╝ ██╔══██╗ ██║ ╚══██╔══╝ ██║  ██║
█████╗   ██║  ██║ ██║    ██║    ███████║
██╔══╝   ██║  ██║ ██║    ██║    ██╔══██║
███████╗ ██████╔╝ ██║    ██║    ██║  ██║
╚══════╝ ╚═════╝  ╚═╝    ╚═╝    ╚═╝  ╚═╝
```

### **Even Dead, I'm The Hero**

*An advanced, modular, agentic AI assistant framework built in Python.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Test%20Build-orange?style=flat-square)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](https://github.com)

---

</div>

> [!CAUTION]
> **🚧 THIS IS A TEST BUILD — NOT STABLE 🚧**
>
> E.D.I.T.H. is currently under **heavy active development**. Expect breaking changes, incomplete features, and bugs. This project is **NOT production-ready**. Use at your own risk.
>
> If you encounter any issues, **please report them** — every bug report helps make E.D.I.T.H. smarter. See the [Bug Reporting](#-bug-reporting) section below.

---

## 🧠 What is E.D.I.T.H.?

**E.D.I.T.H.** *(Even Dead, I'm The Hero)* is an ambitious, modular AI assistant framework designed to push the boundaries of what a personal AI can do. Inspired by Tony Stark's legendary AI systems, E.D.I.T.H. is built to be extensible, intelligent, and dangerously capable.

It is designed as a **multi-agent orchestration platform** — not just a chatbot, but a full-fledged AI operating system that can reason, remember, execute code, talk, learn, and coordinate with other agents.

---

## ⚡ Features

### 🏗️ Core Architecture
| Module | Description |
|--------|-------------|
| **Core Engine** | Pydantic-powered configuration and base agent abstractions |
| **Execution Engine** | Central runtime loop with async support and daemon mode |
| **CLI Interface** | Typer-powered command-line interface for starting and managing E.D.I.T.H. |

### 🤖 Agent Systems
| Module | Description |
|--------|-------------|
| **Agent Registry** | Manage multiple specialized agent personas |
| **A2A Protocol** | Agent-to-Agent communication for multi-agent collaboration |
| **Hybrid Agents** | Combine different AI models and strategies |
| **Intent Parser** | Natural language intent recognition and routing |

### 🧩 Intelligence & Memory
| Module | Description |
|--------|-------------|
| **Intelligence Orchestrator** | Route tasks to optimal LLM providers (Gemini, OpenAI, etc.) |
| **Memory Manager** | Short-term episodic + long-term semantic RAG memory |
| **Learning Engine** | Self-improvement through feedback loops and context distillation |
| **Prompt Engine** | Dynamic prompt template management and injection |

### 🔧 Tools & Execution
| Module | Description |
|--------|-------------|
| **Skill Registry** | Extensible MCP-compatible tools and plugins |
| **Code Sandbox** | Secure isolated environments for untrusted code execution |
| **Operators** | Pre-authorized action execution modules |
| **Workflow Orchestrator** | Convert complex tasks into actionable execution plans |

### 🌐 Interfaces & Communication
| Module | Description |
|--------|-------------|
| **Server** | SSE/HTTP web server for real-time communication |
| **Channels** | Multi-platform support (CLI, WebSocket, API) |
| **Connectors** | External integrations (databases, APIs, services) |
| **Speech Pipeline** | STT and TTS for voice-enabled interaction |
| **Web Interface** | Browser-based UI with templates and static assets |

### 🔒 Security & Observability
| Module | Description |
|--------|-------------|
| **Safety Guardrails** | Prompt injection detection and output safety monitoring |
| **Session Manager** | Conversation history and user context tracking |
| **Telemetry** | Structured logging, metrics, and distributed traces |
| **Process Mining** | Analyze execution traces to optimize agent behavior |
| **Benchmarks** | Performance, latency, and accuracy benchmarking suite |
| **Evaluations** | Systematic scoring of agent capabilities |

---

## 🚀 Quick Start

### Prerequisites

- **Python ≥ 3.11**
- **pip** or [**uv**](https://github.com/astral-sh/uv) package manager

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/edith.git
cd edith
```

### 2. Set Up Environment

```bash
# Copy the environment template
cp .env.example .env

# Open .env and fill in your API keys
nano .env
```

### 3. Install Dependencies

```bash
# Using pip
pip install -e .

# Or using uv (recommended)
uv sync
```

### 4. Launch E.D.I.T.H.

```bash
# Start the server
python main.py start

# Start in daemon mode
python main.py start --daemon

# Verify project structure
python main.py verify
```

---

## 📁 Project Structure

```
project-- edith/
├── main.py                  # CLI entrypoint (Typer-powered)
├── pyproject.toml           # Project configuration & dependencies
├── .env.example             # Environment variable template
├── .gitignore               # Git exclusion rules
├── LICENSE                  # MIT License
├── SECURITY.md              # Security policy
│
├── edith/                   # Main application package
│   ├── core/                # Configuration, base agent classes
│   ├── engine/              # Central execution loop
│   ├── a2a/                 # Agent-to-Agent protocols
│   ├── agents/              # Specialized agent runners
│   ├── analytics/           # Usage & performance analytics
│   ├── bench/               # Benchmarking suite
│   ├── channels/            # Communication channels
│   ├── cli/                 # CLI commands & utilities
│   ├── connectors/          # External system integrations
│   ├── daemon/              # Background process controller
│   ├── evals/               # Agent evaluation & scoring
│   ├── intelligence/        # LLM orchestration layer
│   ├── intents/             # Intent recognition
│   ├── interfaces/          # Web UI (templates, static)
│   ├── learning/            # Self-improvement engine
│   ├── memory/              # Short & long-term memory
│   ├── mining/              # Process mining & optimization
│   ├── operators/           # Action execution modules
│   ├── prompt/              # Prompt template engine
│   ├── recipes/             # Pre-defined workflow recipes
│   ├── sandbox/             # Sandboxed code execution
│   ├── scheduler/           # Task scheduling (cron, async)
│   ├── security/            # Access control & guardrails
│   ├── server/              # SSE/HTTP web server
│   ├── sessions/            # Session & context management
│   ├── skills/              # Tool & plugin registry
│   ├── speech/              # STT/TTS pipeline
│   ├── system/              # OS & filesystem interactions
│   ├── telemetry/           # Logging, metrics, traces
│   ├── templates/           # Scaffolding templates
│   ├── tools/               # Utility functions
│   ├── traces/              # Execution trace logger
│   └── workflow/            # Workflow orchestrator
│
└── tests/                   # Test suite
    ├── core/
    ├── engine/
    ├── mcp/
    ├── memory/
    ├── server/
    └── sessions/
```

---

## 🐛 Bug Reporting

> [!WARNING]
> **This is a test build with known and unknown bugs.**
>
> Found a bug? **Please report it!** Your reports are critical to improving E.D.I.T.H.

**How to report:**

1. **Open an Issue** on the [GitHub Issues](https://github.com) page
2. **Include** the following details:
   - Steps to reproduce the bug
   - Expected behavior vs. actual behavior
   - Python version and OS
   - Any error logs or stack traces
3. **Label** your issue with `bug` tag

Or reach out directly to the creator (see below).

---

## 🗺️ Roadmap

- [x] Core scaffolding & module structure
- [x] CLI entrypoint with Typer
- [x] Pydantic configuration models
- [x] Engine execution loop
- [ ] LLM provider integration (Gemini, OpenAI)
- [ ] MCP server with tool registry
- [ ] Voice pipeline (STT/TTS)
- [ ] Agent-to-Agent (A2A) protocol
- [ ] Web interface
- [ ] Memory & RAG pipeline
- [ ] Sandbox code execution
- [ ] Full test coverage

---

## 👤 Creator

<div align="center">

| | |
|---|---|
| **Name** | **Amal** |
| 📧 **Email** | [gamingwithsolex@gmail.com](mailto:gamingwithsolex@gmail.com) |
| 📸 **Instagram** | [@_amal.42](https://instagram.com/_amal.42) |

</div>

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🔐 Security

For security concerns, vulnerability reports, and responsible disclosure guidelines, see [SECURITY.md](SECURITY.md).

---

<div align="center">

*Built with ☕ and ambition by [Amal](https://instagram.com/_amal.42)*

**If E.D.I.T.H. helped you or inspired you, consider giving it a ⭐**

</div>
