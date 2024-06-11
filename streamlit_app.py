import streamlit as st
from SL_agents import researcher
from SL_tasks import icp_task
from langchain_openai import ChatOpenAI
from langsmith import traceable
from crewai import Crew, Process, Task
from fpdf import FPDF
import os
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import time
import traceback
import builtins
import re
import asyncio
import httpx

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Email configuration
SMTP_SERVER = 'smtp-mail.outlook.com'
SMTP_PORT = 587
SENDER_EMAIL = 'info@swiftlaunch.biz'
SENDER_PASSWORD = 'Lovelife1#'

# Environment variables for Langsmith
os.environ["LANGSMITH_TRACING_V2"] = "true"
os.environ["LANGSMITH_PROJECT"] = "king nip"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_API_KEY"] = "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"

# Airtable configuration
AIRTABLE_API_KEY = 'patnWOUVJR780iDNN.de9fb8264698287a5b4206fad59a99871d1fc6dddb4a94e7e7770ab3bcef014e'
AIRTABLE_BASE_ID = 'appPcWNUeei7MNMCj'
AIRTABLE_TABLE_NAME = 'tblaMtAcnVa4nwnby'
AIRTABLE_FIELDS = {
    'email': 'fldsx1iIk4FiRaLi8',
    'credits': 'fldxwzSmMmldMGlgI',
    'icp': 'fldL1kkrGflCtOxwa',
    'channels': 'flduJ5ubWm0Bs2Ile',
    'jtbd': 'fldFFAnoI7to8ZXgu',
    'pains': 'fldyazmtByhtLBEds',
    'gains': 'fldudHL1MwHsIHrNO',
    'propdesign': 'fldXZ4CLKu2p85gPa',
    'customerj': 'fld9XtbBFTEEiq70F'
}

# Save the original print function
original_print = builtins.print

# Define a patched print function that logs instead of printing
def patched_print(*args, **kwargs):
    try:
        original_print(*args, **kwargs)
    except BrokenPipeError:
        logging.error(f"BrokenPipeError: {args}")
        logging.debug(traceback.format_exc())

# Patch the print function
builtins.print = patched_print

@traceable
async def send_to_airtable(email, icp_output):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "fields": {
            "Email": email,
            AIRTABLE_FIELDS['icp']: icp_output,
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        response.raise_for_status()
        record = response.json()
        logging.info(f"Airtable response: {record}")
        return record['id']

@traceable
async def retrieve_from_airtable(record_id):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        record = response.json()
        fields = record.get('fields', {})
        logging.info("Data retrieved from Airtable successfully")
        return (
            fields.get(AIRTABLE_FIELDS['icp'], ''),
        )

@traceable
async def check_credits(email):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    params = {
        "filterByFormula": f"{{{AIRTABLE_FIELDS['email']}}}='{email}'"
    }

    async with httpx.AsyncClient() as client:
        try:
            logging.info(f"Sending GET request to {url} with params {params}")
            response = await client.get(url, headers=headers, params=params)
            logging.info(f"HTTP Request: GET {response.url} {response.status_code} {response.reason_phrase}")
            response.raise_for_status()
            logging.debug(f"Response JSON: {response.json()}")
            records = response.json().get('records', [])
            if records:
                fields = records[0].get('fields', {})
                logging.debug(f"Fields returned for the record: {fields}")
                credits = fields.get('Credits', 0)
                if credits is not None:
                    credits = int(credits)  # Ensure credits is treated as an integer
                else:
                    credits = 0
                record_id = records[0]['id']
                logging.info(f"Email {email} found. Credits: {credits}")
                return credits, record_id
            else:
                logging.info(f"Email {email} not found.")
            return 0, None
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")

@traceable
async def update_credits(record_id, new_credits):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "fields": {
            AIRTABLE_FIELDS['credits']: new_credits
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.patch(url, headers=headers, json=data)
        response.raise_for_status()
        record = response.json()
        logging.info(f"Airtable update response: {record}")
        return record['id']

@traceable
def format_output(output):
    return output.strip()

@traceable
def generate_pdf(result):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(200, 10, txt="CrewAI Task Result", align='C')
    pdf.multi_cell(0, 10, txt=str(result))
    return pdf.output(dest='S').encode('latin1')

@traceable
def send_email(receiver_email, result):
    try:
        logging.info("Generating PDF content")
        pdf_content = generate_pdf(result)
        
        # Email details
        subject = 'CrewAI Task Result'
        body = 'Please find attached the result of your CrewAI task.'
        
        # Create a multipart message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = subject
        
        # Attach the body with the msg instance
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach the PDF file
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(pdf_content)
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f'attachment; filename=crewAI_result.pdf')
        msg.attach(attachment)
        
        logging.info("Connecting to SMTP server")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            logging.info("Sending email")
            server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        logging.info(f"Email sent to {receiver_email} with attachment crewAI_result.pdf")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")
        logging.debug(traceback.format_exc())
        return False

@traceable
async def start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location, marketing_channels, features, benefits, retries=3):
    task_description = f"New task from {email} selling {product_service} at {price} {currency} with payment frequency {payment_frequency}."
    if selling_scope == "Locally":
        task_description += f" Location: {location}."
    task_description += f" Focus on the following marketing channels: {', '.join(marketing_channels)}."

    new_task = Task(description=task_description, expected_output="...")

    project_crew = Crew(
        tasks=[new_task, icp_task],
        agents=[researcher],
        manager_llm=ChatOpenAI(temperature=0, model="gpt-4o"),
        max_rpm=4,
        process=Process.hierarchical,
    )

    for attempt in range(retries):
        try:
            logging.info(f"Starting crew process, attempt {attempt + 1}")
            results = project_crew.kickoff()
            icp_output = icp_task.output.exported_output if hasattr(icp_task.output, 'exported_output') else "No ICP output"
            logging.info("Crew process completed successfully")
            return icp_output,
        except BrokenPipeError as e:
            logging.error(f"BrokenPipeError occurred on attempt {attempt + 1}: {e}")
            logging.debug(traceback.format_exc())
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
        except Exception as e:
            logging.error(f"An error occurred during the crew process: {e}")
            logging.debug(traceback.format_exc())
            raise

def main():
    st.title("ICP Report Generator")

    with st.form("input_form"):
        email = st.text_input("Email")
        product_service = st.text_input("Product/Service")
        price = st.number_input("Price", min_value=0.0, format="%f")
        currency = st.selectbox("Currency", ["USD", "EUR", "GBP"])
        payment_frequency = st.selectbox("Payment Frequency", ["One-time", "Monthly", "Yearly"])
        selling_scope = st.selectbox("Selling Scope", ["Locally", "Globally"])
        location = st.text_input("Location", disabled=(selling_scope == "Globally"))

        # Add multi-select for marketing channels
        marketing_channels = st.multiselect("Marketing Channels", ["Facebook", "Twitter (x)", "Instagram", "Reddit", "TikTok", "SEO", "Blog", "PPC", "LinkedIn"])

        # Add new input fields for Features and Benefits
        features = st.text_area("Features", help="Enter the features of your product/service")
        benefits = st.text_area("Benefits", help="Enter the benefits of your product/service")

        submit_button = st.form_submit_button(label="Generate Swift Launch Report")

    if submit_button:
        with st.spinner("Checking your credits..."):
            credits, record_id = asyncio.run(check_credits(email))
        
        if credits > 0:
            with st.spinner("Generating Swift Launch Report..."):
                icp_output, = asyncio.run(
                    start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location, marketing_channels, features, benefits)
                )
            
            st.write("Swift Launch Report Generated")

            result = {
                'ICP Output': icp_output,
            }

            with st.spinner("Sending email with the report..."):
                if send_email(email, result):
                    st.success("Email sent successfully")
                    new_credits = credits - 1
                    asyncio.run(update_credits(record_id, new_credits))
                else:
                    st.error("Failed to send email. Please try again later.")
        else:
            st.error("No credits available. Please purchase more credits to generate the Swift Launch Report.")

if __name__ == "__main__":
    main()
