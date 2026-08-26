# CodeoMentis

### The Mind of Your Codebase.

CodeoMentis is an AI-powered repository intelligence platform designed to help developers understand and navigate unfamiliar codebases.

It analyzes repository structure, source code, dependencies, and code relationships to provide contextual tools for exploring architecture, tracing code impact, identifying technical-debt hotspots, generating guided walkthroughs, and asking questions about a codebase.

## Overview

Understanding an unfamiliar repository often requires navigating large numbers of files, tracing dependencies manually, and building a mental model of the system from scattered information.

CodeoMentis provides a centralized interface for repository analysis and exploration.

A repository can be connected through GitHub and ingested into CodeoMentis, after which the platform provides several analysis and exploration capabilities.

## Features

### Repository Ingestion

CodeoMentis can ingest GitHub repositories and process their source code and repository structure for subsequent analysis.

The ingestion process builds the information required by the platform's analysis and retrieval features.

### Architecture Analyzer

The Architecture Analyzer provides an overview of a repository's technical and structural organization.

It can surface information including:

- Technology stack
- Project structure
- Configuration
- Dependencies
- Architectural organization

### Impact Analysis

Impact Analysis helps trace relationships between code elements and identify potential areas affected by a change.

It can be used to investigate questions such as:

> If this function or component changes, what parts of the codebase may be affected?

The analyzer can trace callers and related code relationships to a configurable depth.

### Technical Debt Heatmap

The Technical Debt Heatmap highlights potential maintenance hotspots within a repository.

It uses signals such as:

- Code complexity
- Coupling
- TODOs
- Structural characteristics
- Repository-level maintenance indicators

### Codebase Walkthrough

CodeoMentis can generate guided walkthroughs for unfamiliar repositories.

The walkthrough provides a structured path through important parts of a codebase rather than requiring developers to discover the structure manually.

### Codebase Chat

CodeoMentis provides a conversational interface for asking questions about an ingested repository.

Questions are answered using repository context and retrieval rather than relying exclusively on the language model's general knowledge.

Example questions:

```text
How does authentication work?

Where is repository ingestion implemented?

What happens after a repository is connected?

Which components depend on this function?

Where is the database connection configured?
Repository Management

Users can manage their connected repositories from the application, including removing repositories and their associated analysis data.

The application also provides ingestion progress information while repositories are being processed.

How It Works

At a high level, CodeoMentis follows this workflow:

GitHub Repository
       |
       v
Repository Ingestion
       |
       v
Source Code Processing
       |
       v
Codebase Representation
       |
       +-------------------+
       |                   |
       v                   v
Code Analysis        Context Retrieval
       |                   |
       +---------+---------+
                 |
                 v
          CodeoMentis
          Intelligence
                 |
       +---------+---------+---------+
       |         |         |         |
       v         v         v         v
   Architecture Impact  Technical  Codebase
    Analysis   Analysis    Debt       Chat
                         Analysis
Architecture

CodeoMentis consists of a React-based frontend and a Python-based backend.

CodeoMentis
|
+-- frontend/
|   +-- components/
|   +-- pages/
|   +-- hooks/
|   +-- lib/
|   +-- types/
|   +-- assets/
|
+-- backend/
|   +-- API layer
|   +-- Repository ingestion
|   +-- Code analysis
|   +-- Retrieval
|   +-- LLM integration
|   +-- Data processing
|
+-- README.md

The frontend provides the user interface for repository exploration and analysis.

The backend handles repository processing, analysis, retrieval, and integration with the language model.

Technology Stack
Frontend
React
TypeScript
Vite
Tailwind CSS
React Router
Lucide React
Backend
Python
FastAPI
Repository ingestion and analysis
Retrieval pipeline
LLM integration
AI

CodeoMentis currently uses:

Provider: Groq
Model: openai/gpt-oss-20b

The language model is used for AI-powered repository understanding and contextual responses.

Code Analysis

The platform processes source code and repository structure to build the context required by its analysis and retrieval features.

Authentication

CodeoMentis uses GitHub authentication for repository-related workflows.

Users can authenticate through GitHub and connect repositories through the application.

Getting Started
Prerequisites
Git
Node.js
npm
Python 3.10 or later
Clone the Repository
git clone https://github.com/Udayveer2103/codeomentis.git
cd codeomentis
Backend Setup

Navigate to the backend directory:

cd backend

Create a virtual environment:

python -m venv .venv

Activate the virtual environment on Windows:

.venv\Scripts\Activate.ps1

Install the backend dependencies:

pip install -r requirements.txt

Configure the required environment variables in a .env file.

These include the credentials and configuration required for:

GitHub authentication
Database access
Groq
LLM configuration
Application secrets
Frontend Setup

Open a separate terminal and navigate to the frontend:

cd frontend

Install dependencies:

npm install

Start the development server:

npm run dev
Environment Configuration

An example LLM configuration is:

LLM_MODEL=openai/gpt-oss-20b

The application uses Groq as the provider for the configured language model.

API keys, OAuth credentials, database credentials, and other secrets should never be committed to the repository.

Development

Start the frontend development server:

npm run dev

Build the frontend:

npm run build

For backend development, activate the virtual environment and start the FastAPI application using the project's configured application entry point.

Typical Workflow
1. Authenticate with GitHub
2. Connect a repository
3. Ingest the repository
4. Analyze the codebase
5. Explore the repository
6. Analyze architecture and dependencies
7. Investigate potential change impact
8. Review technical-debt indicators
9. Generate a codebase walkthrough
10. Ask questions using Codebase Chat
Project Goals

CodeoMentis is designed around a simple objective:

Make complex codebases easier to understand before making changes.

Traditional repository navigation primarily answers questions such as:

Where is this code?

CodeoMentis aims to provide additional context around questions such as:

How does this code relate to the rest of the system?

What could be affected if this changes?

How is this repository structured?

Where should I start when learning this codebase?
Current Scope

CodeoMentis currently focuses on:

GitHub repository workflows
Repository ingestion
Repository structure and code analysis
Architecture analysis
Impact analysis
Technical-debt analysis
Guided codebase walkthroughs
Context-aware codebase chat
Repository management
Future Work

Potential areas for future development include:

Improved support for private repositories
Additional programming-language analysis
More scalable visualization for very large repositories
Deeper dependency and architectural analysis
Pull-request impact analysis
Repository comparison
Change-risk analysis
Improved retrieval and code-context ranking
Additional developer workflows built around repository intelligence
Contributing

Contributions and suggestions are welcome.

To contribute, fork the repository and create a feature branch:

git checkout -b feature/your-feature

Make your changes, test them locally, and submit a pull request.

License

This project is currently maintained as a personal project.

A formal open-source license can be added if the repository is released under an open-source license.

Author

Uday Veer Singh

CodeoMentis

The Mind of Your Codebase.
