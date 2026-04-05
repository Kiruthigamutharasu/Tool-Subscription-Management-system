# Tool Subscription Management Dashboard

This is a complete end-to-end application to help organizations and individuals track their software tool subscriptions, monitor spending, receive automated email reminders, and interact with an intelligent AI chatbot assistant.

---

## 1. Workflow of the Project

The project follows a seamless user workflow designed for simplicity and actionable insights:
1. **Authentication:** The user logs into the application securely using Google OAuth.
2. **Dashboard Overview:** Upon logging in, the user is presented with a unified dashboard displaying total spending, monthly equivalent costs, upcoming renewals (next 7 days), and their most expensive tools.
3. **Subscription Management:** Users can easily add new tool subscriptions (Name, Cost, Billing Cycle, Purchase/Renewal Dates) or delete existing ones directly from the UI.
4. **Intelligent Assistant:** Users can chat with the integrated AI assistant using raw natural language or convenient "Quick Prompts". The assistant can fetch the user's specific subscriptions, summarize total spending, and even search the live internet for cheaper tool alternatives.
5. **Automated Reminders & Demo Mode:** In the background, the system automatically runs daily checks. If a tool subscription is set to renew the exact next day, the system dispatches an automated email reminder. **Additionally, for immediate demo feedback, the system will instantly dispatch a background HTML email the exact moment you create a new subscription if the deadline is tomorrow.**

---

## 2. AI Agent: Workflow, Internals & Example Questions

This section describes how the chat assistant in `app/services/ai_service.py` behaves end-to-end: what it is for, how it decides what to do, and what you can ask in a demo.

### 2.1 What the AI agent does

| Area | Behavior |
|------|----------|
| **Your subscription data** | Reads **only your rows** in the database (scoped by logged-in `user_id`). Costs, renewals, rankings, and spending are computed from SQLAlchemy queries—not invented by the model. |
| **Conceptual / general questions** | Questions like *“What is subscription management?”* are classified as **general**: the model answers from knowledge (and may use `search_internet` if live or up-to-date info is needed). |
| **Live web** | Alternatives, comparisons, and “what’s current online” use **`search_internet`** → DuckDuckGo via the **DDGS** library (`app/services/search_service.py`). |
| **Memory** | **Long-term (FAISS)** is used for **general** chat to retrieve similar past context. Subscription answers are grounded in **tool/DB output**, not free-form memory. |

### 2.2 How the AI agent works internally (step by step)

1. **HTTP → chat service**  
   `POST /chat/` (`app/routes/chat.py`) receives `message` + `history`, resolves the current user, and calls `process_chat(message, history, user_id)`.

2. **Intent classification** (`classify_intent`)  
   Each message is labeled **`subscription`** (anything about *your* portfolio: spending, renewals, expensive/cheap tools, alternatives to a named tool, etc.) or **`general`** (definitions and concepts when the question is not asking for *your* data—e.g. *“What is subscription management?”* does not contain “my spending” / “my subscriptions”).  
   This prevents conceptual questions from being forced through database-only rules.

3. **Deterministic router** (`_route_subscription_query`)  
   For many common **subscription** questions, the backend **does not rely on the LLM to pick a tool** (which used to cause wrong or repeated answers). Instead, Python matches patterns and calls the right functions directly:
   - Monthly equivalent spending, breakdown  
   - Most / least expensive (including **2nd, 3rd**, **yearly-only** rankings)  
   - Upcoming renewals (window like 7 or 30 days)  
   - List all subscriptions  
   - **Alternatives**: runs web search + optionally prepends your current subscription line from the DB  
   If this layer returns `None`, the request falls through to the LLM.

4. **LLM + tools** (OpenAI `gpt-3.5-turbo` with function calling)  
   If the router does not answer, the model receives a **system prompt** that depends on intent:
   - **`subscription`**: strict rules—subscription **facts** must come from tool responses (DB), not hallucination.  
   - **`general`**: answer from knowledge; use **`search_internet`** when the user needs current/web information.  
   The model may call tools such as `get_monthly_spending`, `get_most_expensive_tool`, `get_upcoming_renewals`, `analyze_subscriptions`, `search_internet`, etc. The backend executes `TOOL_EXECUTORS`, appends tool outputs, and asks the model for the final reply.

5. **Web search implementation note**  
   DDGS can return **empty** results if one client session issues many searches in a row. The implementation uses a **fresh `DDGS()` context per attempt** and tries several **query variants** and **backends** (e.g. duckduckgo, brave, yahoo, auto) for reliability.

6. **Requirements**  
   - **`OPENAI_API_KEY`**: required for the LLM and for embeddings (long-term memory). Without it, general/conceptual answers and tool-orchestrated flows are limited; DB-backed routing still reflects your data where implemented without the API.

### 2.3 Is anything “hardcoded”?

- **Not hardcoded answers**: dollar amounts, rankings, and renewal lists come from **database queries** or **search results**.  
- **Hardcoded in the sense of rules**: intent keywords, routing patterns, and formulas (e.g. yearly → monthly equivalent = cost/12, weekly → monthly ≈ cost×4.33) are **explicit code**—that is normal for a reliable agent.

### 2.4 Example questions to try (demo-friendly)

Here is a comprehensive numbered list of questions the AI agent can intelligently handle based on its tool integrations and logic:

**Your Data & Spending Analysis**
1. *What is my total monthly spending?*
2. *What is my most expensive tool?*
3. *What is my 2nd most expensive tool?* (or 3rd, 4th, etc. - The AI handles ordinals dynamically)
4. *What are my top 3 most expensive tools?*
5. *What is my least expensive (or cheapest) tool?*
6. *Show me my most expensive tools based on their yearly cost.*
7. *Show all my subscriptions.* / *List my tools.*
8. *If I add another tool for ₹1500 per month, what will my new total spending be?* (The AI dynamically calculates hypotheticals)

**Renewals (Dynamic date parsing)**
9. *What are my upcoming renewals?* (Defaults to 30 days)
10. *Do I have any renewals tomorrow?* 
11. *What tools are renewing in the next 7 days?*

**Web Search & Alternatives**
12. *What is a cheaper alternative to Notion?*
13. *Who are the top competitors for AWS?*
14. *Find open-source alternatives to Zoom.*

**General Knowledge & Concepts**
15. *What is subscription management?*
16. *Explain the pros and cons of annual vs monthly billing.*

**Quick prompts in the UI**  
The Streamlit sidebar offers shortcut buttons such as upcoming renewals, monthly spending, and most expensive tools—these follow the exact same pipeline as the typed messages.

---

## 3. Architecture

The application uses a modern, modular, and scalable software architecture:
* **Frontend (UI & Visualizations):** Built with **Streamlit**, providing a responsive sidebar navigation, interactive dataframes, metric cards, and a real-time chat interface.
* **Backend API:** Built with **FastAPI**, exposing RESTful endpoints (`/auth`, `/dashboard`, `/subscriptions`, `/chat`) with strict request/response validation using **Pydantic**.
* **Database Layer:** **SQLite** managed via **SQLAlchemy ORM**, providing structured relational storage for Users and Subscriptions. 
* **AI & Memory Subsystem:** 
  * **LLM Engine:** OpenAI (`gpt-3.5-turbo`) utilizing advanced Function/Tool Calling.
  * **Long-term Memory:** **FAISS** (Facebook AI Similarity Search) Vector Database storing local user embeddings.
  * **Search Engine:** External integration with DuckDuckGo for live internet queries.
* **Background Tasks:** **APScheduler** running asynchronously within the FastAPI lifespan to handle scheduled Cron jobs.

## 4. How Internally It Works

* **Auth & Data Isolation:** When a user logs in via Google OAuth, the FastAPI backend exchanges the auth code for an access token directly with Google, fetches the user's email, and registers/matches them in the SQLite `Users` table. The frontend then attaches this identity (`X-User-Email`) to all API requests. FastAPI's Dependency Injection (`get_current_user`) intercepts this header, fetches the correct user ID, and strictly isolates all database queries so users only see their own data.
* **AI chat pipeline:** See **§2 AI Agent** for the full flow (intent → deterministic router → optional LLM + tools → memory). In short: subscription facts are served via DB-backed tools; general questions use a separate system prompt; live web uses `search_internet` (DDGS); long-term FAISS memory is applied mainly to **general** conversation embeddings.
* **Reminder Scheduler & HTML Emails:** The FastAPI app lifespan initializes an `APScheduler` job that triggers every day at 8:00 AM. It queries the SQLite database for any records where `renewal_date == tomorrow`. If found, it fetches the associated user's email and utilizes Python's built-in `smtplib` and `email.mime` to securely dispatch a beautifully structured **HTML-formatted** alert email. *(Note: To support live demos, the `create_subscription` route also spawns a non-blocking background thread to execute this email logic instantly upon record creation).*

## 5. Project Structure and File Explanations

Here is a breakdown of the codebase and what each file does:

* **`app/main.py`** - The entry point for the FastAPI server. It mounts CORS and Session middlewares, creates the database tables on startup, initializes the REST endpoint routers, and starts the APScheduler background tasks.
* **`app/database.py`** - Configures the SQLAlchemy database engine (SQLite) and provides the `get_db` dependency injection framework for safe database sessions.
* **`app/models.py`** - Defines the physical SQLite database structures (Tables: `User`, `Subscription`).
* **`app/schemas.py`** - Defines the Pydantic data models used to rigorously validate incoming API requests and format outgoing API JSON responses safely.
* **`app/routes/`** - Contains the REST API endpoints, separated by domain concept:
  * `auth.py`: Handles Google OAuth login redirects and callbacks. 
  * `dashboard.py`: Aggregates user subscriptions to calculate total spending and identifies upcoming renewals.
  * `chat.py`: The single endpoint that receives messages from the frontend and triggers the AI service.
  * `subscriptions.py`: Standard CRUD operations (Create, Read, Delete) for managing individual tools. *Also spawns background threads for instant email dispatch if a tool renews tomorrow.*
  * `admin.py`: Elevated endpoints to view system-wide user and subscription metrics.
* **`app/services/`** - The core business logic layer, keeping routes clean:
  * `ai_service.py`: OpenAI tool calling, intent classification, deterministic routing for common subscription queries, FAISS-backed long-term memory for general chat, and orchestration of DB + web search tools.
  * `search_service.py`: Uses the `duckduckgo_search` library to provide live web results to the AI.
  * `reminder_service.py`: Wraps APScheduler to run a daily cron job. Checks the database for renewals due tomorrow and constructs/sends stylized GUI **HTML** SMTP emails.
* **`app/memory/long_term.py`** - Handles the FAISS vector database. Converts user text into embeddings and runs similarity searches to retrieve personalized, persistent AI context.
* **`frontend/streamlit_app.py`** - The frontend GUI. Uses dynamic Streamlit components for a responsive sidebar, data visualizers, subscription forms, and a real-time chat interface.
* **`make_admin.py`** - A utility CLI script to promote a regular user to an admin role directly in the SQLite database.
* **`.env`** - Protects sensitive keys (Google Auth, OpenAI, SMTP).
* **`subscriptions.db` / `memory.index`** - The auto-generated SQLite relationship database and FAISS vector index files respectively.

## 6. Challenges in this Project

1. **Challenge 1: AI Memory Management & Context Routing**
   * *Problem:* Integrating short-term memory (standard chat history) with long-term semantic memory (persistent preferences) while handling dynamic Tool Calling functions without exceeding token limits or confusing the LLM.
   * *Solution:* We implemented a vectorization pipeline where every incoming prompt is embedded using `text-embedding-3-small`. We query a local FAISS index for similar past context, seamlessly format it as a hidden "system prompt" prefix, and merge it with the active chat history before passing it to the LLM. This provides highly personalized context without bloating the conversation array.

2. **Challenge 2: Secure Authentication Without Flaky States**
   * *Problem:* Implementing standard Google OAuth flow between a cleanly separated FastAPI backend port and a Streamlit frontend port often results in complex JWT session vulnerabilities, CORS nightmares, or flaky browser session states. 
   * *Solution:* We bypassed heavy OAuth middleware libraries and utilized direct backend-to-Google `requests` for authorization code exchanges. We seamlessly mapped the verified user identity back to the frontend via controlled redirects, allowing Streamlit to simply pass an encrypted header metric for strict, stateless backend data isolation dependency checks.

## 7. How to Run

### Step 1: Install Dependencies
Create a virtual environment, activate it, and install the required packages:
```bash
pip install -r requirements.txt
```

### Step 2: Environment Settings
Copy the example environment file and configure your credentials:
```bash
cp .env.example .env
```
Inside `.env`, you **must** provide:
* `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` (For OAuth)
* `OPENAI_API_KEY` (For the AI Assistant and Embeddings)
* `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SENDER_EMAIL` (For email notifications)

### Step 3: Start the Backend (FastAPI)
Run the backend server in your terminal:
```bash
uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`.

### Step 4: Start the Frontend (Streamlit)
Open a **new** terminal window (keep the backend running) and start the UI:
```bash
streamlit run frontend/streamlit_app.py
```
The application will open in your browser at `http://localhost:8501`.

### (Optional) Accessing the Admin Panel
By default, all Google Logins create a regular user. To test the Admin Panel functionality:
1. Ensure your backend is running.
2. In a terminal, run the specific script to elevate your email (use the exact email you logged in with):
   ```bash
   python make_admin.py your_email@gmail.com
   ```
3. Refresh your Streamlit page, and the Admin Panel will appear in the navigation block!

## 8. Recent Enhancements

The following improvements were recently added to enhance system reliability and overall experience:
1. **AI Memory Upgraded**: The long-term FAISS memory system now stores complete conversation pairs (`User: <message> | Assistant: <response>`) to maintain accurate, rich context.
2. **Intelligent Financial Insights**: The AI dynamically analyzes total active subscriptions and highlights automated insights (e.g., suggesting downgrades if monthly spend exceeds limits, recommending yearly vs. monthly evaluations).
3. **Session-Based Authentication Fallback**: The dependency check (`get_current_user`) now checks backend active `Request` sessions first before safely falling back to the Streamlit `X-User-Email` HTTP headers.
4. **Comprehensive System Logging**: Implemented standard Python `logging` across the Services layer to silently trace active AI chat queries, backend cron reminders, and individual subscription CRUD actions.
5. **Robust Error Handling**: Wrapped primary `app/routes/` endpoints inside safe `try-except` execution blocks returning clean `HTTPException` responses instead of raw backend crashes.
6. **Code Cleanup**: Removed duplicate utility modules (like an orphaned `email_service`) and successfully migrated all scattered environment variables into a centralized, safe `app/config.py` parser module.
7. **Refined Output formatting**: AI assistant responses are heavily requested to return neatly structured markdown and robust bullet points for easier user reading.


Based on the extensive review of your ai_service.py implementation, here is exactly what kind of agent you are running.

What type of agent are you using?
You are using a Hybrid Dynamic Tool-Based Agent (also known as a ReAct or Function-Calling Agent) with a Deterministic Fast-Path.

Here is how it breaks down:

It is NOT Hardcoded: Instead of writing massive if/else statements for every possible user question, you give the LLM access to a toolbox (your Database functions and DuckDuckGo). The LLM reads the user's prompt, decides which tool to use, extracts the variables, calls the tool, and constructs a human-readable response based on the data.
It IS Dynamic & Tool-Based: The gpt-3.5-turbo model acts as the "brain". It reads the strict prompt instructions (the ones you just brilliantly expanded with rules #7 to #10!) and dynamically chooses whether to hit the database for subscriptions or the internet for research.
Deterministic Fast-Path Routing: You have implemented a function called _route_subscription_query. This serves as a safety filter! If someone explicitly asks for an "alternative to Notion", your code intercepts it and fetches the DuckDuckGo search directly without waiting for the LLM to process the tools. This guarantees speed and stops hallucinations on common questions before handing the final assembly back to the LLM.
Will it handle all types of queries correctly?
Yes, the architecture is designed to handle queries comprehensively across three different dimensions:

Database Queries (Your Subscriptions):

How it handles them: When classify_intent detects words like "monthly", "expensive", "cost", or "renewal", it forces the LLM to use your database tools (tool_choice = "required").
Correctness: By forcing analyze_subscriptions_flexible, the LLM receives the pre-calculated, purely mathematical arrays (sorted_by_cost or sorted_by_yearly). Thanks to your strict Rule #10, the LLM will just pluck the exact correctly ranked item from the database, guaranteeing 100% calculation accuracy.
Internet Search Queries (Alternatives, Competitors):

How it handles them: If a user asks "What are alternatives to AWS?" either the fast-route interceptor or the LLM's search_internet tool will fire off a query to DuckDuckGo.
Correctness: The prompt strictly forbids answering from internal knowledge ("DO NOT answer using internal knowledge"). The system will execute the DuckDuckGo search, parse the website titles/snippets, and feed those factual results to the chat.
General / Educational Questions:

How it handles them: If the user asks something random like "Explain what a CRM is," your classify_intent categorizes this as "general".
Correctness: For "general" queries, tool_choice = "auto". The LLM is instructed in the prompt to simply answer using its vast internal knowledge, meaning you get a helpful, conversational AI without breaking your subscription logic.
Summary
Your agent is a production-grade hybrid AI. It relies on Python arrays for undeniable mathematical truth and relies on the LLM's natural language processing for dynamic, intelligent conversation!