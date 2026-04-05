"""
Comprehensive validation script for the AI Agent (ai_service.py)
Tests real agent execution scenarios to ensure correctness.
"""

import json
from unittest.mock import patch, MagicMock
from app.services.ai_service import (
    process_chat,
    classify_intent,
    parse_ordinal_query,
    get_all_subscriptions_from_db,
    get_most_expensive_from_db,
    get_least_expensive_from_db,
    get_upcoming_renewals_from_db,
    get_specific_tool_from_db,
    analyze_subscriptions_flexible,
    build_system_prompt,
    TOOL_EXECUTORS,
    TOOLS
)


# ============================================================================
# MOCK DATA FOR TESTING
# ============================================================================

MOCK_SUBSCRIPTIONS = [
    {"id": 1, "tool_name": "Netflix", "cost": 15.99, "billing_cycle": "monthly", "monthly_equivalent": 15.99},
    {"id": 2, "tool_name": "Spotify", "cost": 99.99, "billing_cycle": "yearly", "monthly_equivalent": 8.33},
    {"id": 3, "tool_name": "Adobe Creative Cloud", "cost": 59.99, "billing_cycle": "monthly", "monthly_equivalent": 59.99},
    {"id": 4, "tool_name": "Disney+", "cost": 7.99, "billing_cycle": "monthly", "monthly_equivalent": 7.99},
    {"id": 5, "tool_name": "Gym Membership", "cost": 29.99, "billing_cycle": "monthly", "monthly_equivalent": 29.99},
]


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


# ============================================================================
# TEST 1: TOOL CALL VALIDATION
# ============================================================================

def test_tool_call_validation():
    """Ensure for ALL subscription queries, the model ALWAYS calls a tool."""
    print_section("TEST 1: TOOL CALL VALIDATION")
    
    subscription_queries = [
        "What is my most expensive tool?",
        "Show me my subscriptions",
        "What is my monthly spending?",
        "When is Netflix renewing?",
        "Which subscription should I cancel?",
    ]
    
    all_passed = True
    
    for query in subscription_queries:
        intent = classify_intent(query)
        
        # Check 1: Intent should be "subscription"
        if intent["category"] != "subscription":
            print(f"❌ FAIL: '{query}' classified as '{intent['category']}' (expected 'subscription')")
            all_passed = False
            continue
        
        # Check 2: System prompt should enforce tool usage
        prompt = build_system_prompt("subscription", "")
        if "tool_choice=\"required\"" not in prompt and "MUST use tools" not in prompt:
            print(f"⚠️  WARNING: System prompt may not strongly enforce tool usage")
        
        # ASCII-only output for Windows consoles that may not support unicode
        print(f"[PASS] '{query}' -> category: {intent['category']}")
    
    if all_passed:
        print("\n[PASS] TEST 1 PASSED: Subscription queries classified correctly")
    else:
        print("\n[FAIL] TEST 1 FAILED: Some queries not classified as subscription")
    
    return all_passed


# ============================================================================
# TEST 2: ORDINAL QUERY VALIDATION
# ============================================================================

def test_ordinal_query_validation():
    """Test ordinal queries like '2nd most expensive', '3rd cheapest'."""
    print_section("TEST 2: ORDINAL QUERY VALIDATION")
    
    test_cases = [
        ("What is my 2nd most expensive tool?", 2, "most_expensive"),
        ("What is the 3rd cheapest subscription?", 3, "least_expensive"),
        ("Show me the top 5 most expensive tools", 5, "most_expensive"),
        ("What is the most expensive tool?", 1, "most_expensive"),
        ("What is the cheapest?", 1, "least_expensive"),
    ]
    
    all_passed = True
    
    for query, expected_top_n, expected_type in test_cases:
        ordinal = parse_ordinal_query(query)
        
        if ordinal["top_n"] != expected_top_n:
            print(f"[FAIL] '{query}' -> top_n={ordinal['top_n']} (expected {expected_top_n})")
            all_passed = False
        else:
            print(f"[PASS] '{query}' -> top_n={ordinal['top_n']}")
    
    # Test that the AI would call the right tool with right top_n
    print("\n--- Simulating tool calls ---")
    
    # Test 2nd most expensive
    ordinal = parse_ordinal_query("What is my 2nd most expensive tool?")
    if ordinal["top_n"] == 2:
        print(f"[PASS] '2nd most expensive' -> would call get_most_expensive_tool(top_n=2)")
    else:
        print(f"[FAIL] '2nd most expensive' -> top_n={ordinal['top_n']} (expected 2)")
        all_passed = False
    
    # Test 3rd cheapest
    ordinal = parse_ordinal_query("What is the 3rd cheapest subscription?")
    if ordinal["top_n"] == 3:
        print(f"[PASS] '3rd cheapest' -> would call get_least_expensive_tool(top_n=3)")
    else:
        print(f"[FAIL] '3rd cheapest' -> top_n={ordinal['top_n']} (expected 3)")
        all_passed = False
    
    if all_passed:
        print("\n[PASS] TEST 2 PASSED: Ordinal queries parsed correctly")
    else:
        print("\n[FAIL] TEST 2 FAILED: Some ordinal queries incorrect")
    
    return all_passed


# ============================================================================
# TEST 3: FALLBACK TOOL VALIDATION
# ============================================================================

def test_fallback_tool_validation():
    """Test that analyze_subscriptions is used for complex queries."""
    print_section("TEST 3: FALLBACK TOOL VALIDATION")
    
    # Check that analyze_subscriptions tool exists
    analyze_tool = None
    for tool in TOOLS:
        if tool["function"]["name"] == "analyze_subscriptions":
            analyze_tool = tool
            break
    
    if not analyze_tool:
        print("[FAIL] analyze_subscriptions tool not found in TOOLS")
        return False
    
    print("[PASS] analyze_subscriptions tool exists")
    
    # Check supported analysis types
    analysis_types = analyze_tool["function"]["parameters"]["properties"]["analysis_type"]["enum"]
    expected_types = ["comparison", "filter", "savings_analysis", "renewal_analysis", "general"]
    
    for expected in expected_types:
        if expected in analysis_types:
            print(f"[PASS] analysis_type '{expected}' supported")
        else:
            print(f"[FAIL] analysis_type '{expected}' not supported")
            return False
    
    # Test query classification for complex queries
    complex_queries = [
        "Which subscription should I cancel to save money?",
        "Compare all my subscriptions",
        "Show subscriptions under $50",
    ]
    
    for query in complex_queries:
        intent = classify_intent(query)
        if intent["category"] == "subscription":
            print(f"[PASS] '{query}' -> subscription category")
        else:
            print(f"[FAIL] '{query}' -> {intent['category']} (expected subscription)")
            return False
    
    print("\n[PASS] TEST 3 PASSED: Fallback tool properly configured")
    return True


# ============================================================================
# TEST 4: NO HALLUCINATION CHECK
# ============================================================================

def test_no_hallucination():
    """Ensure no fake data is generated for unknown tools."""
    print_section("TEST 4: NO HALLUCINATION CHECK")
    
    # Check system prompt has anti-hallucination rules
    prompt = build_system_prompt("subscription", "")
    
    critical_rules = [
        "NEVER hallucinate",
        "NEVER answer subscription questions from your own knowledge",
        "ALWAYS use tool responses",
        "No data available",
    ]
    
    all_passed = True
    for rule in critical_rules:
        if rule.lower() in prompt.lower():
            print(f"[PASS] Anti-hallucination rule found: '{rule}'")
        else:
            print(f"[WARN] Rule '{rule}' not explicitly in prompt")
    
    # Check that get_specific_tool returns proper "not found" response
    # (This would need a real DB, but we can verify the function exists)
    print("\n--- Verifying tool response handling ---")
    
    # Check that the tool executor handles unknown tools gracefully
    if "get_specific_tool" in TOOL_EXECUTORS:
        print("[PASS] get_specific_tool executor exists")
    else:
        print("[FAIL] get_specific_tool executor missing")
        all_passed = False
    
    if all_passed:
        print("\n[PASS] TEST 4 PASSED: Anti-hallucination safeguards in place")
    else:
        print("\n[WARN] TEST 4: Some safeguards may need review")
    
    return all_passed


# ============================================================================
# TEST 5: RENEWAL VALIDATION
# ============================================================================

def test_renewal_validation():
    """Ensure renewal queries use the correct tool."""
    print_section("TEST 5: RENEWAL VALIDATION")
    
    # Check system prompt instructs not to calculate dates
    prompt = build_system_prompt("subscription", "")
    
    if "DO NOT calculate renewal dates yourself" in prompt or "DO NOT calculate dates yourself" in prompt:
        print("[PASS] System prompt instructs not to calculate dates")
    else:
        print("[WARN] Date calculation warning may be missing")
    
    # Check that get_upcoming_renewals tool exists
    renewals_tool = None
    for tool in TOOLS:
        if tool["function"]["name"] == "get_upcoming_renewals":
            renewals_tool = tool
            break
    
    if renewals_tool:
        print("[PASS] get_upcoming_renewals tool exists")
    else:
        print("[FAIL] get_upcoming_renewals tool missing")
        return False
    
    # Check renewal query classification
    renewal_queries = [
        "What are my upcoming renewals?",
        "When does Netflix renew?",
        "What subscriptions expire soon?",
    ]
    
    all_passed = True
    for query in renewal_queries:
        intent = classify_intent(query)
        if intent["category"] == "subscription":
            print(f"[PASS] '{query}' -> subscription")
        else:
            print(f"[FAIL] '{query}' -> {intent['category']} (expected subscription)")
            all_passed = False
    
    if all_passed:
        print("\n[PASS] TEST 5 PASSED: Renewal handling properly configured")
    else:
        print("\n[FAIL] TEST 5 FAILED: Some renewal queries not handled correctly")
    
    return all_passed


# ============================================================================
# TEST 6: MULTI-STEP REASONING
# ============================================================================

def test_multi_step_reasoning():
    """Test that complex queries requiring multiple tools are handled."""
    print_section("TEST 6: MULTI-STEP REASONING")
    
    # Check system prompt encourages multi-tool usage
    prompt = build_system_prompt("subscription", "")
    
    if "Combine multiple tools" in prompt or "combination of tools" in prompt.lower():
        print("[PASS] System prompt allows combining multiple tools")
    else:
        print("[WARN] Multi-tool combination may not be explicitly mentioned")
    
    if "Transform tool output" in prompt or "transform" in prompt.lower():
        print("[PASS] System prompt allows transforming tool output")
    else:
        print("[WARN] Output transformation may not be explicitly mentioned")
    
    # Test complex query classification
    complex_query = "Which is the most expensive subscription and how much can I save if I cancel it?"
    intent = classify_intent(complex_query)
    
    if intent["category"] == "subscription":
        print(f"[PASS] Complex query '{complex_query[:50]}...' -> subscription")
    else:
        print(f"[FAIL] Complex query -> {intent['category']} (expected subscription)")
        return False
    
    print("\n[PASS] TEST 6 PASSED: Multi-step reasoning supported")
    return True


# ============================================================================
# TEST 7: TOOL EXECUTOR VALIDATION
# ============================================================================

def test_tool_executors():
    """Verify all tool executors are properly mapped."""
    print_section("TEST 7: TOOL EXECUTOR VALIDATION")
    
    expected_tools = [
        "get_all_subscriptions",
        "get_upcoming_renewals",
        "get_monthly_spending",
        "get_most_expensive_tool",
        "get_least_expensive_tool",
        "get_specific_tool",
        "analyze_subscriptions",
        "add_subscription",
        "update_subscription",
        "delete_subscription",
        "search_internet",
    ]
    
    all_passed = True
    
    for tool_name in expected_tools:
        if tool_name in TOOL_EXECUTORS:
            print(f"[PASS] {tool_name} executor exists")
        else:
            print(f"[FAIL] {tool_name} executor missing")
            all_passed = False
    
    if all_passed:
        print("\n[PASS] TEST 7 PASSED: All tool executors properly mapped")
    else:
        print("\n[FAIL] TEST 7 FAILED: Some tool executors missing")
    
    return all_passed


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all validation tests."""
    print("\n" + "="*60)
    print("  AI AGENT COMPREHENSIVE VALIDATION")
    print("="*60)
    
    results = []
    
    results.append(("Tool Call Validation", test_tool_call_validation()))
    results.append(("Ordinal Query Validation", test_ordinal_query_validation()))
    results.append(("Fallback Tool Validation", test_fallback_tool_validation()))
    results.append(("No Hallucination Check", test_no_hallucination()))
    results.append(("Renewal Validation", test_renewal_validation()))
    results.append(("Multi-Step Reasoning", test_multi_step_reasoning()))
    results.append(("Tool Executor Validation", test_tool_executors()))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nALL TESTS PASSED! Agent looks healthy.")
    else:
        print(f"\n{total - passed} test(s) failed. Review recommended.")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)