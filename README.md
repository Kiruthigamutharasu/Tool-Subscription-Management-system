# Tool Subscription Management System

A full-stack application designed to help individuals and organizations manage software subscriptions, monitor spending, receive automated renewal reminders, and interact with an AI-powered assistant.

---

## Features

* Google OAuth authentication
* Centralized dashboard with spending insights
* Subscription management (create, view, delete)
* AI-powered assistant for natural language queries
* Live web search integration for alternatives and comparisons
* Automated email reminders for upcoming renewals
* Long-term conversational memory using vector embeddings

---

## Technology Stack

**Frontend**

* Streamlit

**Backend**

* FastAPI
* SQLAlchemy
* Pydantic

**AI System**

* OpenAI GPT-3.5 Turbo (function calling)
* FAISS (vector-based memory)

**Additional Components**

* APScheduler (background jobs)
* DuckDuckGo Search (DDGS integration)
* SQLite

---

## AI Agent Overview

The application uses a hybrid tool-based AI agent combining deterministic routing with LLM-driven reasoning.

### Capabilities

* Retrieves user-specific subscription data directly from the database
* Performs accurate financial calculations without hallucination
* Uses live web search for alternatives and competitor analysis
* Maintains long-term conversational context using vector similarity

### Workflow

1. User sends a message to the `/chat` endpoint
2. Intent classification determines whether the query is subscription-related or general
3. Deterministic routing handles common subscription queries
4. The LLM selects appropriate tools when required
5. Tool execution results are used to generate the final response

---

## Example Queries

### Spending Insights

* What is my total monthly spending?
* What is my most expensive tool?
* Show my top 3 subscriptions

### Renewals

* What renews tomorrow?
* Show renewals in the next 7 days

### Web Search

* What is a cheaper alternative to Notion?
* Who are the competitors of AWS?

### General Questions

* What is subscription management?
* What are the pros and cons of annual billing?

---

## Project Structure

```
app/
 ├── routes/        # API endpoints
 ├── services/      # Business logic
 ├── memory/        # FAISS-based AI memory
 ├── models.py      # Database models
 ├── schemas.py     # Request/response validation
 ├── database.py    # Database configuration
 └── main.py        # Application entry point

frontend/
 └── streamlit_app.py   # User interface
```

---

## Setup Instructions

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 2. Configure environment variables

```bash
cp .env.example .env
```

Provide the following values in `.env`:

* OpenAI API key
* Google OAuth credentials
* SMTP credentials for email notifications

---

### 3. Run backend server

```bash
uvicorn app.main:app --reload
```

---

### 4. Run frontend

```bash
streamlit run frontend/streamlit_app.py
```

---

## Authentication and Data Isolation

* Google OAuth is handled through the backend
* User identity is passed securely via request headers
* FastAPI dependency injection ensures strict data isolation per user

---

## Automated Reminder System

* Scheduled daily using APScheduler
* Identifies subscriptions renewing the next day
* Sends structured HTML email notifications
* Supports instant trigger for demonstration purposes

---

## Key Highlights

* Modular and scalable architecture
* Clear separation between API, services, and data layers
* Hybrid AI agent combining deterministic logic and LLM reasoning
* Accurate, database-driven financial insights
* Background task processing for automation

---

## Challenges Addressed

### AI Context and Memory Management

Implemented a combination of short-term chat history and long-term FAISS-based memory to provide contextual and personalized responses without exceeding token limits.

### Authentication Design

Simplified OAuth integration without relying on complex session management or JWT systems, ensuring stable and secure user identification.

---

## Future Improvements

* Payment integration (e.g., Stripe)
* Multi-user organizational support
* Advanced analytics and reporting
* Containerization and cloud deployment

---

## Author

Kiruthigamutharasu

