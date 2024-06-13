import streamlit as st
import requests
import asyncio

API_URL = "https://credit-t9kr.onrender.com"

st.title("Swift Launch Generator")

with st.form("input_form"):
    email = st.text_input("Email")
    product_service = st.text_input("Product/Service")
    price = st.number_input("Price", min_value=0.0, format="%f")
    currency = st.selectbox("Currency", ["USD", "EUR", "GBP"])
    payment_frequency = st.selectbox("Payment Frequency", ["One-time", "Monthly", "Yearly"])
    selling_scope = st.selectbox("Selling Scope", ["Locally", "Globally"])
    location = st.text_input("Location", disabled=(selling_scope == "Globally"))
    marketing_channels = st.multiselect("Marketing Channels", ["Facebook", "Twitter (X)", "Instagram", "Reddit", "TikTok", "SEO", "Blog", "PPC", "LinkedIn"])
    features = st.text_area("Features", help="Enter the features of your product/service")
    benefits = st.text_area("Benefits", help="Enter the benefits of your product/service")
    submit_button = st.form_submit_button(label="Generate Swift Launch Report")

if submit_button:
    with st.spinner("Checking your credits..."):
        response = requests.post(f"{API_URL}/check_credits", json={'email': email})
        credits_info = response.json()
    
    if credits_info['credits'] > 0:
        with st.spinner("Generating Swift Launch Report..."):
            response = requests.post(f"{API_URL}/start_process", json={
                'email': email,
                'product_service': product_service,
                'price': price,
                'currency': currency,
                'payment_frequency': payment_frequency,
                'selling_scope': selling_scope,
                'location': location,
                'marketing_channels': marketing_channels,
                'features': features,
                'benefits': benefits
            })
            result = response.json()
        
        st.write("Swift Launch Report Generated")
        st.json(result)

        new_credits = credits_info['credits'] - 1
        with st.spinner("Updating your credits..."):
            response = requests.post(f"{API_URL}/update_credits", json={
                'record_id': credits_info['record_id'],
                'new_credits': new_credits
            })
            if response.status_code == 200:
                st.success("Credits updated successfully")
            else:
                st.error("Failed to update credits")
    else:
        st.error("No credits available. Please purchase more credits to generate the Swift Launch Report.")
