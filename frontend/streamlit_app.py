import os
import streamlit as st
import requests
import pandas as pd
from datetime import date

st.set_page_config(page_title="Tool Subscription Dashboard", layout="wide")

API_BASE_URL = "http://localhost:8000"

if "user_email" not in st.session_state:
    query_params = st.query_params
    if "user_email" in query_params:
        st.session_state.user_email = query_params["user_email"]
        st.query_params.clear()
    else:
        st.session_state.user_email = None

headers = {"X-User-Email": st.session_state.user_email} if st.session_state.user_email else {}

with st.sidebar:
    st.title("Setup & Nav")
    if st.session_state.user_email:
        st.success(f"Logged in as: {st.session_state.user_email}")
        if st.button("Logout"):
            st.session_state.user_email = None
            st.rerun()
            
        st.subheader("Navigation")
        ADMIN_MAIL = os.getenv("ADMIN_MAIL", "keerthikiruthiga2002@gmail.com")
        nav_options = ["Dashboard", "Subscriptions"]
        if st.session_state.user_email == ADMIN_MAIL:
            nav_options.append("Admin Panel")
        page = st.radio("Go to:", nav_options)
    else:
        st.warning("Please log in to manage your tools.")
        login_url = f"{API_BASE_URL}/auth/login"
        st.markdown(f'<a href="{login_url}" target="_self"><button style="background-color:#4285F4;color:white;padding:10px;border:none;border-radius:5px;cursor:pointer;">Login with Google</button></a>', unsafe_allow_html=True)
        page = "Login"

col_main, col_ai = st.columns([3, 1])

with col_ai:
    st.markdown("### Assistant")
    st.write("Ask me anything about your tools!")
    
    # Quick access prompts
    st.markdown("**Quick Prompts:**")
    quick_prompts = [
        "What are my upcoming renewals?",
        "What is my monthly spending?",
        "Most expensive tools?"
    ]
    
    # Use columns for compact buttons
    selected_prompt = None
    for i, qp in enumerate(quick_prompts):
        if st.button(qp, key=f"qp_{i}", use_container_width=True):
            selected_prompt = qp
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        
    for msg in st.session_state.chat_history:
        st.chat_message(msg["role"]).write(msg["content"])
        
    prompt = st.chat_input("Type your message...")
    if selected_prompt:
        prompt = selected_prompt

    if prompt:
        if not st.session_state.user_email:
            st.error("Please log in first.")
        else:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            
            with st.spinner("Thinking..."):
                try:
                    resp = requests.post(f"{API_BASE_URL}/chat/", headers=headers, json={"message": prompt, "history": st.session_state.chat_history[:-1]})
                    if resp.status_code == 200:
                        bot_reply = resp.json().get("reply", "No reply")
                    else:
                        bot_reply = f"Error: {resp.text}"
                except Exception as e:
                    bot_reply = f"Connection error: {e}"

            st.session_state.chat_history.append({"role": "assistant", "content": bot_reply})
            st.chat_message("assistant").write(bot_reply)

with col_main:
    if not st.session_state.user_email:
        if page == "Login":
            st.title("Tool Subscription Management Dashboard")
            st.info("👈 Please use the sidebar to log in and get started.")
    else:
        if page == "Dashboard":
            st.title("Dashboard")
            try:
                resp = requests.get(f"{API_BASE_URL}/dashboard/", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    
                    view_mode = st.radio("View Setting", ["Monthly View", "Yearly View"], horizontal=True)
                    st.divider()
                    
                    c1, c2 = st.columns(2)
                    if view_mode == "Yearly View":
                        c1.metric("Yearly Spending", f"₹{data['total_spending']:.2f}")
                        c2.metric("Monthly Equivalent", f"₹{data['monthly_spending']:.2f}")
                    else:
                        c1.metric("Monthly Spending", f"₹{data['monthly_spending']:.2f}")
                        c2.metric("Yearly Equivalent", f"₹{data['total_spending']:.2f}")
                    
                    st.subheader("Spending Distribution")
                    tools_stats = data.get('all_tools_stats', [])
                    if tools_stats:
                        df_tools = pd.DataFrame(tools_stats)
                        if view_mode == "Monthly View":
                            df_tools = df_tools.sort_values("monthly_equivalent", ascending=False)
                            st.bar_chart(df_tools, x="tool_name", y="monthly_equivalent")
                        else:
                            df_tools = df_tools.sort_values("yearly_equivalent", ascending=False)
                            st.bar_chart(df_tools, x="tool_name", y="yearly_equivalent")
                    else:
                        st.info("No tools found.")
                        
                    st.divider()
                    st.subheader("Upcoming Renewals (7 Days)")
                    if data['upcoming_renewals']:
                        st.dataframe(data['upcoming_renewals'])
                    else:
                        st.info("No upcoming renewals in 7 days.")
                    
                else:
                    st.error("Failed to load dashboard data.")
            except Exception as e:
                st.error(f"Error fetching dashboard: {e}")
        
        elif page == "Subscriptions":
            st.title("Tool Subscriptions")
            st.write("Manage your tools here.")
            
            with st.expander("Add New Subscription"):
                with st.form("add_sub_form"):
                    t_name = st.text_input("Tool Name")
                    t_cost = st.number_input("Cost (₹)", min_value=0.0, step=1.0)
                    t_cycle = st.selectbox("Billing Cycle", ["monthly", "yearly"])
                    t_pdate = st.date_input("Purchase Date", date.today())
                    t_rdate = st.date_input("Renewal Date", date.today())
                    submit = st.form_submit_button("Save Subscription")
                    
                    if submit:
                        payload = {
                            "tool_name": t_name,
                            "cost": t_cost,
                            "billing_cycle": t_cycle,
                            "purchase_date": t_pdate.isoformat(),
                            "renewal_date": t_rdate.isoformat()
                        }
                        res = requests.post(f"{API_BASE_URL}/subscriptions/", headers=headers, json=payload)
                        if res.status_code == 200:
                            st.success("Added successfully!")
                            st.rerun()
                        else:
                            st.error(f"Failed to add: {res.text}")

            st.divider()
            
            st.subheader("My Subscriptions")
            try:
                resp = requests.get(f"{API_BASE_URL}/subscriptions/", headers=headers)
                if resp.status_code == 200:
                    subs = resp.json()
                    if subs:
                        df = pd.DataFrame(subs)
                        st.dataframe(df.drop(columns=['user_id'], errors='ignore'))
                        
                        st.divider()
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("Update Subscription")
                            upd_id = st.selectbox("Select ID to update", [s['id'] for s in subs], format_func=lambda x: next((f"{s['tool_name']} (ID: {s['id']})" for s in subs if s['id'] == x), x))
                            selected_sub = next((s for s in subs if s['id'] == upd_id), None)
                            if selected_sub:
                                with st.form("update_sub_form"):
                                    u_name = st.text_input("Tool Name", value=selected_sub['tool_name'])
                                    u_cost = st.number_input("Cost (₹)", min_value=0.0, step=1.0, value=float(selected_sub['cost']))
                                    cycle_index = 0 if selected_sub['billing_cycle'] == 'monthly' else 1
                                    u_cycle = st.selectbox("Billing Cycle", ["monthly", "yearly"], index=cycle_index)
                                    
                                    u_pdate = st.date_input("Purchase Date", pd.to_datetime(selected_sub['purchase_date']).date())
                                    u_rdate = st.date_input("Renewal Date", pd.to_datetime(selected_sub['renewal_date']).date())
                                    
                                    update_submit = st.form_submit_button("Update Subscription")
                                    
                                    if update_submit:
                                        u_payload = {
                                            "tool_name": u_name,
                                            "cost": u_cost,
                                            "billing_cycle": u_cycle,
                                            "purchase_date": u_pdate.isoformat(),
                                            "renewal_date": u_rdate.isoformat()
                                        }
                                        u_res = requests.put(f"{API_BASE_URL}/subscriptions/{upd_id}", headers=headers, json=u_payload)
                                        if u_res.status_code == 200:
                                            st.success("Updated successfully!")
                                            st.rerun()
                                        else:
                                            st.error(f"Failed to update: {u_res.text}")

                        with col2:
                            st.subheader("Delete Subscription")
                            del_id = st.selectbox("Select ID to delete", [s['id'] for s in subs], format_func=lambda x: next((f"{s['tool_name']} (ID: {s['id']})" for s in subs if s['id'] == x), x))
                            if st.button("Delete"):
                                d_res = requests.delete(f"{API_BASE_URL}/subscriptions/{del_id}", headers=headers)
                                if d_res.status_code == 200:
                                    st.success("Deleted successfully!")
                                    st.rerun()
                                else:
                                    st.error("Failed to delete.")
                    else:
                        st.info("No subscriptions found. Add some above!")
                else:
                    st.error("Failed to load subscriptions.")
            except Exception as e:
                st.error(f"Error: {e}")
            
        elif page == "Admin Panel":
            st.title("Admin Panel")
            
            st.subheader("Manual Actions")
            if st.button("Trigger Daily Renewals Email"):
                with st.spinner("Executing check..."):
                    treq = requests.post(f"{API_BASE_URL}/admin/trigger-reminders", headers=headers)
                    if treq.status_code == 200:
                        st.success("Emails triggered and sent successfully (if any tools are renewing tomorrow)!")
                    else:
                        st.error(f"Failed to trigger: {treq.text}")
            st.divider()
            
            try:
                resp = requests.get(f"{API_BASE_URL}/admin/users", headers=headers)
                if resp.status_code == 200:
                    st.subheader("All Users")
                    st.dataframe(resp.json())
                    
                    st.subheader("All Subscriptions (System-wide)")
                    s_resp = requests.get(f"{API_BASE_URL}/admin/subscriptions", headers=headers)
                    st.dataframe(s_resp.json() if s_resp.status_code == 200 else [])
                else:
                    st.error(f"Access Denied or Error: {resp.text}")
            except Exception as e:
                st.error(f"Error: {e}")