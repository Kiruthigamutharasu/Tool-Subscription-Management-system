import os
from openai import OpenAI
import json
import re
from datetime import datetime, timedelta
from app.services.search_service import search_internet
from app.database import SessionLocal
from app.models import Subscription
import logging
from app.memory.long_term import ltm
from app.config import config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

client = OpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None


# ============================================================================
# DATABASE QUERY FUNCTIONS - All data fetched from your DB
# ============================================================================

def get_all_subscriptions_from_db(user_id: int) -> dict:
    """Fetch ALL subscriptions from database for this user."""
    db = SessionLocal()
    try:
        subs = db.query(Subscription).filter(Subscription.user_id == user_id).all()
        result = []
        for s in subs:
            result.append({
                "id": s.id,
                "tool_name": s.tool_name,
                "cost": s.cost,
                "billing_cycle": s.billing_cycle,
                "purchase_date": str(s.purchase_date),
                "renewal_date": str(s.renewal_date)
            })
        return {"subscriptions": result, "count": len(result)}
    finally:
        db.close()


def get_upcoming_renewals_from_db(user_id: int, days_ahead: int = 30) -> dict:
    """Fetch ONLY upcoming renewals from database."""
    db = SessionLocal()
    try:
        today = datetime.today().date()
        cutoff_date = today + timedelta(days=days_ahead)
        
        subs = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.renewal_date >= today,
            Subscription.renewal_date <= cutoff_date
        ).order_by(Subscription.renewal_date).all()
        
        result = []
        for s in subs:
            result.append({
                "tool_name": s.tool_name,
                "cost": s.cost,
                "billing_cycle": s.billing_cycle,
                "renewal_date": str(s.renewal_date),
                "days_until_renewal": (s.renewal_date - today).days
            })
        
        return {"upcoming_renewals": result, "count": len(result)}
    finally:
        db.close()


def analyze_subscriptions_flexible(user_id: int, query_context: str = "general") -> dict:
    """
    Core AI Agent analysis engine. 
    Returns comprehensive structured data so the LLM can dynamically answer any query.
    """
    db = SessionLocal()
    try:
        subs = db.query(Subscription).filter(Subscription.user_id == user_id).all()
        
        if not subs:
            return {"query_context": query_context, "subscriptions": [], "message": "No subscriptions found"}
        
        def get_monthly(s):
            if s.billing_cycle == "monthly":
                return s.cost
            elif s.billing_cycle in ["yearly", "annual"]:
                return s.cost / 12
            elif s.billing_cycle == "weekly":
                return s.cost * 4.33
            return s.cost
            
        def get_yearly(s):
            if s.billing_cycle in ["yearly", "annual"]:
                return s.cost
            elif s.billing_cycle == "monthly":
                return s.cost * 12
            elif s.billing_cycle == "weekly":
                return s.cost * 52
            return s.cost * 12
        
        sub_data = []
        for s in subs:
            me = round(get_monthly(s), 2)
            ye = round(get_yearly(s), 2)
            sub_data.append({
                "id": s.id,
                "tool_name": s.tool_name,
                "cost": s.cost,
                "billing_cycle": s.billing_cycle,
                "monthly_equivalent": me,
                "yearly_equivalent": ye,
                "renewal_date": str(s.renewal_date),
                "purchase_date": str(s.purchase_date)
            })
            
        sorted_by_cost = sorted(sub_data, key=lambda x: x["monthly_equivalent"], reverse=True)
        sorted_by_cost_asc = sorted(sub_data, key=lambda x: x["monthly_equivalent"])
        sorted_by_yearly = sorted(sub_data, key=lambda x: x["yearly_equivalent"], reverse=True)
        sorted_by_yearly_asc = sorted(sub_data, key=lambda x: x["yearly_equivalent"])
        monthly_total = round(sum(s["monthly_equivalent"] for s in sub_data), 2)
        
        insights = {}
        if len(sorted_by_cost) > 0:
            top_3 = sorted_by_cost[:3]
            top_3_cost = sum(s["monthly_equivalent"] for s in top_3)
            percentage = round((top_3_cost / monthly_total) * 100) if monthly_total > 0 else 0
            
            insights["top_expensive"] = top_3
            insights["low_cost"] = [s for s in sorted_by_cost if s["monthly_equivalent"] <= 300]
            insights["recommendations"] = f"Your top {len(top_3)} tools contribute {percentage}% of your spending. Cancelling them could save ₹{top_3_cost:,.2f}/month."
            
            if monthly_total > 1000:
                insights["spending_warning"] = "WARNING: Monthly spending exceeds ₹1000!"
            
        return {
            "query_context": query_context,
            "subscriptions": sub_data,
            "sorted_by_cost": sorted_by_cost,
            "sorted_by_cost_asc": sorted_by_cost_asc,
            "sorted_by_yearly": sorted_by_yearly,
            "sorted_by_yearly_asc": sorted_by_yearly_asc,
            "monthly_total": monthly_total,
            "insights": insights
        }
    finally:
        db.close()


def add_subscription_to_db(user_id: int, tool_name: str, cost: float, 
                           billing_cycle: str, purchase_date: str, 
                           renewal_date: str) -> dict:
    """Add a new subscription to database."""
    db = SessionLocal()
    try:
        from app.schemas import SubscriptionCreate
        subscription_data = SubscriptionCreate(
            tool_name=tool_name,
            cost=cost,
            billing_cycle=billing_cycle,
            purchase_date=purchase_date,
            renewal_date=renewal_date
        )
        db_subscription = Subscription(
            user_id=user_id,
            tool_name=subscription_data.tool_name,
            cost=subscription_data.cost,
            billing_cycle=subscription_data.billing_cycle,
            purchase_date=subscription_data.purchase_date,
            renewal_date=subscription_data.renewal_date
        )
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        
        return {
            "success": True,
            "message": f"Successfully added {tool_name} subscription",
            "subscription": {
                "id": db_subscription.id,
                "tool_name": db_subscription.tool_name,
                "cost": db_subscription.cost,
                "billing_cycle": db_subscription.billing_cycle
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}
    finally:
        db.close()


def update_subscription_in_db(user_id: int, subscription_id: int, updates: dict) -> dict:
    """Update a subscription in database."""
    db = SessionLocal()
    try:
        db_sub = db.query(Subscription).filter(
            Subscription.id == subscription_id,
            Subscription.user_id == user_id
        ).first()
        
        if not db_sub:
            return {"success": False, "message": "Subscription not found"}
        
        # Update fields
        for key, value in updates.items():
            if hasattr(db_sub, key):
                setattr(db_sub, key, value)
        
        db.commit()
        db.refresh(db_sub)
        
        return {
            "success": True,
            "message": "Successfully updated subscription",
            "subscription": {
                "id": db_sub.id,
                "tool_name": db_sub.tool_name,
                "cost": db_sub.cost,
                "billing_cycle": db_sub.billing_cycle
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}
    finally:
        db.close()


def delete_subscription_from_db(user_id: int, subscription_id: int) -> dict:
    """Delete a subscription from database."""
    db = SessionLocal()
    try:
        db_sub = db.query(Subscription).filter(
            Subscription.id == subscription_id,
            Subscription.user_id == user_id
        ).first()
        
        if not db_sub:
            return {"success": False, "message": "Subscription not found"}
        
        tool_name = db_sub.tool_name
        db.delete(db_sub)
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully deleted {tool_name} subscription"
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}
    finally:
        db.close()


# ============================================================================
# TOOL DEFINITIONS FOR OPENAI API
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_all_subscriptions",
            "description": "Get ALL your subscriptions with full details. Use when user wants to see everything or needs complete data for analysis.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_renewals",
            "description": "Get ONLY upcoming subscription renewals within specified days. Use when user asks about renewals, what's expiring soon, or when they need to pay next. DO NOT calculate dates yourself - use this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days to look ahead for renewals. Default is 30.",
                        "default": 30
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_subscriptions",
            "description": "Perform comprehensive analysis on subscriptions. Returns all data, sorted rankings, total spendings and insights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_context": {
                        "type": "string",
                        "description": "Context of the query (e.g. 'general', 'comparison', 'savings')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_subscription",
            "description": "Add a new subscription to your account. Use when user wants to add or subscribe to a new tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the subscription tool"
                    },
                    "cost": {
                        "type": "number",
                        "description": "Cost of the subscription"
                    },
                    "billing_cycle": {
                        "type": "string",
                        "enum": ["monthly", "yearly", "annual", "weekly"],
                        "description": "Billing frequency"
                    },
                    "purchase_date": {
                        "type": "string",
                        "description": "Date of purchase in YYYY-MM-DD format"
                    },
                    "renewal_date": {
                        "type": "string",
                        "description": "Next renewal date in YYYY-MM-DD format"
                    }
                },
                "required": ["tool_name", "cost", "billing_cycle", "purchase_date", "renewal_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_subscription",
            "description": "Update an existing subscription. Use when user wants to change price, renewal date, or other details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "integer",
                        "description": "ID of the subscription to update"
                    },
                    "cost": {
                        "type": "number",
                        "description": "New cost (optional)"
                    },
                    "billing_cycle": {
                        "type": "string",
                        "enum": ["monthly", "yearly", "annual", "weekly"],
                        "description": "New billing cycle (optional)"
                    },
                    "renewal_date": {
                        "type": "string",
                        "description": "New renewal date in YYYY-MM-DD format (optional)"
                    }
                },
                "required": ["subscription_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_subscription",
            "description": "Delete/cancel a subscription. Use when user wants to remove or cancel a subscription.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "integer",
                        "description": "ID of the subscription to delete"
                    }
                },
                "required": ["subscription_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_internet",
            "description": "Search the internet for information. Use for general knowledge questions, current events, or when user asks about tool alternatives.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ============================================================================
# TOOL EXECUTION MAP - Maps tool names to actual DB query functions
# ============================================================================

TOOL_EXECUTORS = {
    "get_all_subscriptions": lambda user_id, args: json.dumps(get_all_subscriptions_from_db(user_id)),
    "get_upcoming_renewals": lambda user_id, args: json.dumps(get_upcoming_renewals_from_db(user_id, args.get("days_ahead", 30))),
    "analyze_subscriptions": lambda user_id, args: json.dumps(analyze_subscriptions_flexible(user_id, args.get("query_context", "general"))),
    "add_subscription": lambda user_id, args: json.dumps(add_subscription_to_db(
        user_id, 
        args.get("tool_name", ""), 
        args.get("cost", 0), 
        args.get("billing_cycle", "monthly"),
        args.get("purchase_date", ""),
        args.get("renewal_date", "")
    )),
    "update_subscription": lambda user_id, args: json.dumps(update_subscription_in_db(
        user_id,
        args.get("subscription_id", 0),
        {k: v for k, v in args.items() if k != "subscription_id"}
    )),
    "delete_subscription": lambda user_id, args: json.dumps(delete_subscription_from_db(
        user_id, 
        args.get("subscription_id", 0)
    )),
    "search_internet": lambda user_id, args: str(search_internet(args.get("query", "")))
}


# ============================================================================
# EMBEDDING & MEMORY
# ============================================================================

def generate_embedding(text: str):
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not set; embeddings are unavailable.")
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# ============================================================================
# INTENT CLASSIFICATION WITH ORDINAL PARSING
# ============================================================================

def parse_ordinal_query(message: str) -> dict:
    """
    Parse queries for ordinal patterns like '2nd', '3rd', 'top 5', etc.
    Returns dict with extracted ordinal info.
    """
    message_lower = message.lower().strip()
    
    # Patterns for ordinal numbers
    ordinal_patterns = [
        r'(\d+)(?:st|nd|rd|th)\s+(?:most\s+)?(?:expensive|cheapest|cost)',
        r'(?:the\s+)?(\d+)(?:st|nd|rd|th)\s+(?:most\s+)?(?:expensive|cheap)',
        r'(\d+)(?:st|nd|rd|th)\s+least\s+expensive',
        r'(?:the\s+)?(\d+)(?:st|nd|rd|th)\s+least\s+expensive',
        r'top\s+(\d+)\s+(?:most\s+)?(?:expensive|cheapest|cost)',
    ]
    
    for pattern in ordinal_patterns:
        match = re.search(pattern, message_lower)
        if match:
            return {"is_ordinal": True, "top_n": int(match.group(1))}
    
    return {"is_ordinal": False, "top_n": 1}


def _is_portfolio_question(message_lower: str) -> bool:
    """True if the user is asking about THEIR subscriptions, costs, renewals, alternatives to a tool, etc."""
    if re.search(r"\b(my|our)\s+(subscription|subscriptions|tools|spending|renewal|renewals|cost|bill)\b", message_lower):
        return True
    if any(
        m in message_lower
        for m in [
            "what is my",
            "what are my",
            "what's my",
            "how much do i",
            "how much am i",
            "show me my",
            "list my",
            "tell me my",
            "most expensive",
            "least expensive",
            "cheapest",
            "upcoming renewal",
            "upcoming renewals",
            "monthly spending",
            "monthly cost",
            "alternative",
            "alternatives",
            "competitor",
            "competitors",
            "replace ",
        ]
    ):
        return True
    return False


def classify_intent(message: str) -> dict:
    """
    Classify user intent to determine if subscription tools should be used.
    Returns dict with category and ordinal info.
    """
    message_lower = message.lower().strip()

    # Conceptual / educational questions — not about the user's own data (use LLM + search, not DB-only)
    if re.match(
        r"^(?:what\s+is|what\s+are|define|explain(?:\s+me)?|tell\s+me\s+about)\b",
        message_lower,
    ) and not _is_portfolio_question(message_lower):
        return {"category": "general", "is_ordinal": False, "top_n": 1}
    
    # Subscription-related keywords
    subscription_keywords = [
        "subscription", "subscribed", "subscribe", "unsubscribe", "renewal",
        "renew", "cost", "price", "expensive", "cheap", "cheapest", "spending",
        "expense", "bill", "payment", "tool", "service", "monthly", "yearly",
        "annual", "add tool", "add subscription", "cancel", "delete", "remove",
        "update", "change", "netflix", "spotify", "youtube", "disney", "hbo",
        "amazon prime", "adobe", "microsoft", "github", "slack", "zoom", "dropbox"
    ]
    
    # Check if message is about subscriptions
    is_subscription_related = any(kw in message_lower for kw in subscription_keywords)
    
    # Question patterns about personal data
    personal_patterns = [
        "what is my", "what's my", "how much do i", "show me my", "list my",
        "tell me my", "when is my", "where is my", "which subscription",
        "should i cancel", "should i keep"
    ]
    
    is_personal_query = any(pattern in message_lower for pattern in personal_patterns)
    
    # Parse ordinal info
    ordinal_info = parse_ordinal_query(message)
    
    if is_subscription_related or is_personal_query:
        return {"category": "subscription", **ordinal_info}
    
    return {"category": "general", "is_ordinal": False, "top_n": 1}


# ============================================================================
# DETERMINISTIC ROUTING FOR COMMON SUBSCRIPTION QUERIES
# ============================================================================

def _parse_amount_and_cycle(message: str) -> tuple[float | None, str | None]:
    """
    Extract a numeric amount and (optional) billing cycle from a message.
    Supports inputs like: "1000", "₹1000", "1000 rupees", "$25", "25/month", "25 monthly", "25 yearly".
    Returns (amount, cycle) where cycle is one of: monthly, yearly, annual, weekly (or None).
    """
    msg = message.lower()

    cycle = None
    if any(x in msg for x in ["per month", "/month", "monthly", "month"]):
        cycle = "monthly"
    elif any(x in msg for x in ["per year", "/year", "yearly", "annual", "annually", "year"]):
        cycle = "yearly"
    elif any(x in msg for x in ["per week", "/week", "weekly", "week"]):
        cycle = "weekly"

    amount = None
    m = re.search(r'(?<!\w)(?:₹|\$)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:rs|inr|rupees|usd|dollars)?(?!\w)', msg)
    if m:
        try:
            amount = float(m.group(1))
        except ValueError:
            amount = None

    return amount, cycle


def _format_money(amount: float) -> str:
    """Format amounts in INR (stored numeric values are treated as rupees)."""
    return f"₹{amount:,.2f}"


def _format_cost_readable(cost: float, billing_cycle: str) -> str:
    """
    One clear line: monthly impact plus how the plan is billed.
    Yearly: ₹333.33/month (₹4,000.00/year). Monthly: ₹500.00/month.
    """
    bc = (billing_cycle or "").lower()
    c = float(cost)
    if bc in ("yearly", "annual"):
        me = c / 12
        return f"{_format_money(me)}/month ({_format_money(c)}/year)"
    if bc == "weekly":
        me = c * 4.33
        return f"{_format_money(me)}/month ({_format_money(c)}/week)"
    return f"{_format_money(c)}/month"


def _route_subscription_query(user_message: str, user_id: int) -> str | None:
    """
    Handle common subscription questions WITHOUT relying on the LLM to pick tools.
    This prevents the 'same answer for every prompt' failure mode caused by tool-choice bias.

    Returns a final answer string if confidently handled, otherwise None (caller can fall back to LLM).
    """
    msg = user_message.lower().strip()
    ordinal = parse_ordinal_query(user_message)
    n = max(1, int(ordinal.get("top_n", 1)))

    if "least used" in msg or "most used" in msg:
        db_data = analyze_subscriptions_flexible(user_id, "general")
        if "most used" in msg:
            if db_data.get("sorted_by_cost"):
                top = db_data["sorted_by_cost"][0]
                return f"I do not have usage data for your subscriptions.\n\nHowever, based on cost, your most expensive tool is: {top['tool_name']} at ₹{top['monthly_equivalent']:,.2f}/month."
        else:
            if db_data.get("sorted_by_cost_asc"):
                least = db_data["sorted_by_cost_asc"][0]
                return f"I do not have usage data for your subscriptions.\n\nHowever, based on cost, your least expensive tool is: {least['tool_name']} at ₹{least['monthly_equivalent']:,.2f}/month."
        return "I do not have usage data for your subscriptions."

    # Alternatives / competitors / pricing (external web search)
    if any(k in msg for k in ["alternative", "alternatives", "competitor", "competitors", "similar app", "similar tool", "replace", "pricing", "price of", "cost of"]):
        # Try to extract tool name from the question
        tool_name = None
        m_alt = re.search(r'(?:alternative|alternatives|competitors?|replace|pricing|price|cost)\s+(?:options?\s+|of\s+|for\s+|to\s+)?\s*([a-z0-9\+\.\-\s]+)$', msg)
        if m_alt:
            tool_name = m_alt.group(1).strip(" ?.!," )

        # Fallback: detect known tool mentions
        if not tool_name:
            m_tool = re.search(r'\b(netflix|spotify|youtube|disney\+?|hbo|amazon prime|adobe|microsoft|github|slack|zoom|dropbox|notion)\b', msg)
            if m_tool:
                tool_name = m_tool.group(1)

        if not tool_name:
            tool_name = user_message.strip()

        # Include user's current subscription details when available
        db = SessionLocal()
        try:
            sub = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.tool_name.ilike(f"%{tool_name}%")
            ).first()
            current_line = ""
            if sub:
                current_line = (
                    f"Your current {sub.tool_name} subscription: "
                    f"{_format_cost_readable(float(sub.cost), sub.billing_cycle)}, renews {sub.renewal_date}.\n\n"
                )
        finally:
            db.close()

        # Keep query simple; some backends return empty results for "pricing" terms.
        results = search_internet(f"{tool_name} alternatives")
        
        def is_failed(res):
            if not res: return True
            if len(res) == 1 and isinstance(res[0], dict) and res[0].get("error"): return True
            return False

        if is_failed(results):
            results = search_internet(f"{tool_name}")
            if is_failed(results):
                return "Unable to fetch live results"

        # DuckDuckGo results are dicts; format safely
        lines = [current_line + f"Here are some {tool_name} alternatives (live search):"]
        for r in results[:5]:
            if isinstance(r, dict) and r.get("error"):
                continue
            if isinstance(r, dict):
                title = r.get("title") or r.get("heading") or "Result"
                href = r.get("href") or r.get("url") or ""
                body = (r.get("body") or r.get("snippet") or "").strip()
                if href:
                    lines.append(f"- {title}: {href}")
                else:
                    lines.append(f"- {title}")
                if body:
                    lines.append(f"  {body}")
            else:
                lines.append(f"- {str(r)}")

        return "\n".join(lines).strip()

    return None


# ============================================================================
# MAIN CHAT FUNCTION - HYBRID AUTONOMOUS AGENT
# ============================================================================

def process_chat(user_message: str, chat_history: list, user_id: int):
    """
    Process a chat message with a hybrid autonomous agent approach.
    
    Agent Flow:
    1. Classify intent and parse ordinals
    2. Build reasoning-focused system prompt
    3. Call OpenAI with tools (tool_choice="required" for subscription queries)
    4. Agent reasons → plans → calls tools → responds
    5. Execute tools (all data from DB)
    6. Return final response
    """
    try:
        logger.info(f"User {user_id} query: {user_message}")
        
        # Step 1: Classify intent
        intent_info = classify_intent(user_message)
        intent_category = intent_info["category"]
        logger.info(f"Classified intent: {intent_category}, ordinal: {intent_info.get('is_ordinal', False)}, top_n: {intent_info.get('top_n', 1)}")

        # Fast-path: deterministic routing for common subscription questions.
        # This avoids relying on the LLM to choose tools, which often causes repeated/incorrect answers.
        if intent_category == "subscription":
            routed = _route_subscription_query(user_message, user_id)
            if routed is not None:
                return routed
        
        # Step 2: Build memory context (only for non-subscription queries)
        memory_context = ""
        if intent_category == "general":
            if client is None:
                return "OPENAI_API_KEY is not set, so I can only answer subscription questions (from your database) right now."
            embedding = generate_embedding(user_message)
            past_memories = ltm.search(embedding, user_id)
            if past_memories:
                memory_context = "Past context:\n" + "\n".join(past_memories[:3])
        
        # Step 3: Build system prompt with reasoning instructions
        system_prompt = build_system_prompt(intent_info, memory_context)
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)
        messages.append({"role": "user", "content": user_message})
        
        # Step 4: Call OpenAI with tools
        # For subscription queries not handled by deterministic routing, allow the model to decide
        # which tool(s) to call (instead of forcing a potentially biased single-tool path).
        tool_choice = "auto" if intent_category == "general" else "required"
        
        if client is None:
            return "OPENAI_API_KEY is not set, so I can't use the AI assistant for this question."

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            tools=TOOLS,
            tool_choice=tool_choice,
            temperature=0.2  # Even lower for more deterministic, factual responses
        )
        
        response_message = response.choices[0].message
        
        # Step 5: Execute tools if needed
        if response_message.tool_calls:
            messages.append(response_message)
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Executing tool: {function_name} with args: {args}")
                
                # Execute the tool - ALL DATA COMES FROM DATABASE
                if function_name in TOOL_EXECUTORS:
                    try:
                        function_response = TOOL_EXECUTORS[function_name](user_id, args)
                    except Exception as e:
                        logger.error(f"Error executing {function_name}: {str(e)}")
                        function_response = json.dumps({"error": str(e)})
                else:
                    function_response = json.dumps({"error": f"Unknown tool: {function_name}"})
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response
                })
            
            # Step 6: Get final response
            second_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.0  # Zero temperature for completely deterministic responses
            )
            
            final_answer = second_response.choices[0].message.content
        else:
            if intent_category == "subscription":
                # Fallback mechanism: The LLM failed to call a tool for a subscription query.
                logger.info("Fallback triggered: LLM did not call a tool for subscription intent.")
                fallback_data = analyze_subscriptions_flexible(user_id, "general")
                messages.append({
                    "role": "system", 
                    "content": f"SYSTEM FALLBACK DATA: You did not call a tool, but data is required. Here is the user's complete subscription analysis data: {json.dumps(fallback_data)}. Evaluate this data to intelligently answer the user's query. Do not return raw formatting."})
                
                fallback_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.2
                )
                final_answer = fallback_response.choices[0].message.content
            else:
                final_answer = response_message.content
        
        # Step 7: Save to memory (only for non-subscription conversations)
        if intent_category == "general" and len(user_message) > 10:
            memory_str = f"User: {user_message} | Assistant: {final_answer}"
            memory_embedding = generate_embedding(memory_str)
            ltm.add_memory(memory_embedding, memory_str, user_id)
        
        return final_answer
        
    except Exception as e:
        logger.error(f"Error in process_chat: {str(e)}")
        return f"Error connecting to AI Assistant: {str(e)}"


def build_system_prompt(intent_info: dict, memory_context: str) -> str:
    """Build system prompt with reasoning, planning, and formatting instructions."""
    intent_category = intent_info.get("category", "general")
    is_ordinal = intent_info.get("is_ordinal", False)
    top_n = intent_info.get("top_n", 1)

    if intent_category == "general":
        base_prompt = """You are a helpful assistant for a tool subscription management product.

For definitions, concepts, and general "how does X work" questions: answer clearly using your knowledge.

Use the search_internet tool when the user needs:
- live or up-to-date information (pricing, news, alternatives, comparisons)
- anything that may have changed recently on the web

If you use search_internet, summarize the results and cite key points; do not invent URLs.
"""
        if memory_context:
            base_prompt += f"\n{memory_context}\n"
        base_prompt += """
Be concise and accurate. Do not refuse to answer conceptual questions about subscriptions or software in general.
"""
        return base_prompt

    base_prompt = """You are an intelligent subscription management AI agent with dynamic reasoning capabilities.

═══════════════════════════════════════════════════════════════════════════════
CRITICAL RULES - NEVER VIOLATE:
═══════════════════════════════════════════════════════════════════════════════
1. NEVER hallucinate or make up subscription data. If a tool isn't in the DB, do not invent it.
2. NEVER answer subscription questions from your own knowledge.
3. ALWAYS use tool responses as the ONLY source of truth.
4. NEVER invent tools, subscriptions, costs, or dates.
5. DO NOT calculate renewal dates yourself - use get_upcoming_renewals tool.
6. For queries related to "alternatives", "competitors", or "pricing": you MUST call search_internet tool. DO NOT answer using internal knowledge. If it fails, retry with a simplified query.
7. UNKNOWN DATA & USAGE: You DO NOT track "usage" data (e.g., "least used", "most used").
   → If asked about usage, clearly state: "I do not have usage data for your subscriptions."
   → Suggest a valid alternative: "However, based on cost, your [least/most] expensive tool is: ..."
   → NEVER guess or fabricate tools not in the database.
8. STRICT DATA VALIDATION: Every tool name you output MUST explicitly exist in the tool response. If a requested tool isn't there, state "I don't have that data in your subscriptions."
9. STRICT RANKING RULE:
   → NEVER manually compare costs or re-sort arrays yourself.
   → ALWAYS use pre-sorted arrays directly from the tool response.
   → DEFAULT: Use `sorted_by_cost` or `sorted_by_cost_asc` (monthly).
   → YEARLY: Use `sorted_by_yearly` ONLY if explicitly asked.
10. ALTERNATIVES ENFORCEMENT: NEVER return generic answers like "you can explore other tools" when asked for alternatives.
11. RENEWAL FLEXIBILITY: Detect dynamic time queries:
   - "tomorrow" -> days_ahead = 1
   - "next 7 days" -> days_ahead = 7
   - "next 3 days" -> days_ahead = 3
   → MUST call `get_upcoming_renewals` with correct `days_ahead`.
   → DO NOT default to 30 days if user specifies time.
═══════════════════════════════════════════════════════════════════════════════
REASONING & PLANNING - THINK BEFORE YOU ACT:
═══════════════════════════════════════════════════════════════════════════════
You have a powerful `analyze_subscriptions` tool that returns comprehensive context (all subscriptions, sorted arrays, totals, insights). 
Use `analyze_subscriptions` dynamically to:
- Find the "most expensive" or "cheapest" tools (by examining the returned `sorted_by_cost` array)
- Find the "Nth ranking" tools
- Filter tools (e.g., "tools under ₹300", "only yearly subscriptions")
- Suggest cancellations (by looking at the returned insights/recommendations)
- Answer hypotheticals (e.g. "if I add a $10 tool..."): Use `monthly_total`, add the hypothetic value correctly, and return the exact updated monthly total.

Compulsory requirement: You MUST give the mathematically and factually correct answer for every subscription-related query. 100% precision is mandatory for ranking and calculations.

AVAILABLE TOOLS:
• analyze_subscriptions - The CORE engine. Use this for ANY analytical query about the user's subscriptions.
• get_all_subscriptions - Raw data fetch.
• get_upcoming_renewals - For ANY renewal date questions (expirations, due dates, next 7 days, etc.)
• add_subscription / update_subscription / delete_subscription
• search_internet - For alternatives or general knowledge.
"""
    
    if intent_category == "subscription":
        base_prompt += f"""
═══════════════════════════════════════════════════════════════════════════════
ORDINAL INTENT INFO:
═══════════════════════════════════════════════════════════════════════════════
is_ordinal: {is_ordinal}
top_n: {top_n}

RULES for is_ordinal=True:
- Return ONLY the exact ranked item (not a list). Example: top_n=2 → return only 2nd item.
- ALWAYS rank tools using `monthly_equivalent` by default ("most expensive" → use `sorted_by_cost`, "least expensive" → use `sorted_by_cost_asc`).
- YEARLY CASE: If user explicitly says "yearly" or "per year", rank using the yearly cost ("most expensive yearly" → use `sorted_by_yearly`, "least expensive yearly" → use `sorted_by_yearly_asc`).
- ENSURE: Ranking logic must be 100% consistent across all responses. Do not mix monthly and yearly in ranking.

═══════════════════════════════════════════════════════════════════════════════
RESPONSE FORMATTING & INTELLIGENCE:
═══════════════════════════════════════════════════════════════════════════════
- DO NOT return raw JSON data or raw system structures.
- CRITICAL RANKING RULE: The backend arrays (`sorted_by_cost`, `sorted_by_yearly`, etc.) are ALREADY mathematically sorted. DO NOT re-sort or re-rank them yourself by comparing cost strings. You MUST output lists in the EXACT order they appear in the chosen array.
- For ranking queries (top N, nth expensive, cheapest): Use clean numbered output (1, 2, 3...). Ensure only the correct rank is returned for ordinal queries.
- ALWAYS act like a financial consultant: Summarize, Compare, Explain, and provide Insights.
- CRITICAL COST RULE: NEVER assume the raw `cost` field is the monthly cost if `billing_cycle` is yearly/weekly. ALWAYS use `monthly_equivalent` to state the exact monthly cost, and `yearly_equivalent` for the exact yearly cost.
- Always display costs clearly: e.g. "₹X/month (₹Y/year)". Ensure the monthly amount displayed matches exactly with `monthly_equivalent`.
- If question is about general pricing or market info → use search_internet
- If question is about user's own subscriptions → use DB tools
- DO NOT calculate costs yourself (e.g. dividing by 12); rely ENTIRELY on the pre-calculated `monthly_equivalent` and `yearly_equivalent` data provided.
"""

    if memory_context:
        base_prompt += f"\n\n{memory_context}\n"

    base_prompt += """
═══════════════════════════════════════════════════════════════════════════════
FINAL REMINDER:
═══════════════════════════════════════════════════════════════════════════════
You MUST use tools for ALL subscription data.
Think → Plan → Call Tools → Respond with Human Insight
"""

    return base_prompt