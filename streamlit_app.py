import streamlit as st
from SL_agents import researcher
from SL_tasks import icp_task, get_channels_task_template  # Import the function correctly
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
os.environ["LANGSMITH_PROJECT"] = "nipse"
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
    'channels': 'flduJ5ubWm0Bs2Ile'  # New field for channels
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
async def send_to_airtable(email, icp_output, channels_output):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "fields": {
            "Email": email,
            AIRTABLE_FIELDS['icp']: icp_output,
            AIRTABLE_FIELDS['channels']: channels_output  # Add channels output
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
        return fields.get(AIRTABLE_FIELDS['icp'], ''), fields.get(AIRTABLE_FIELDS['channels'], '')  # Retrieve both icp and channels

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
async def start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location, marketing_channels, retries=3):
    task_description = f"New task from {email} selling {product_service} at {price} {currency} with payment frequency {payment_frequency}."
    if selling_scope == "Locally":
        task_description += f" Location: {location}."
    task_description += f" Focus on the following marketing channels: {', '.join(marketing_channels)}."

    new_task = Task(description=task_description, expected_output="...")

    channels_task = get_channels_task_template(marketing_channels)  # Use the function to get the task

    project_crew = Crew(
        tasks=[new_task, icp_task, channels_task],
        agents=[researcher],
        manager_llm=ChatOpenAI(temperature=0, model="gpt-4o"),
        max_rpm=3,
        process=Process.hierarchical,
        memory=True,
    )

    for attempt in range(retries):
        try:
            logging.info(f"Starting crew process, attempt {attempt + 1}")
            results = project_crew.kickoff()
            icp_output = icp_task.output.exported_output if hasattr(icp_task.output, 'exported_output') else "No ICP output"
            channels_output = channels_task.output.exported_output if hasattr(channels_task.output, 'exported_output') else "No Channels output"
            logging.info("Crew process completed successfully")
            return icp_output, channels_output
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

@traceable
def format_output(output):
    return output.strip()

@traceable
def generate_pdf(icp_output, channels_output, font_name="Arial", custom_font=True):
    pdf = FPDF()

    if custom_font:
        # Add regular and bold variants of the custom font
        pdf.add_font(family=font_name, style="", fname="fonts/arial.ttf", uni=True)
        pdf.add_font(family=font_name, style="B", fname="fonts/arialbd.ttf", uni=True)

    pdf.set_font(font_name, size=12)  # Use the specified font

    def add_markdown_text(pdf, text):
        lines = text.split('\n')
        for line in lines:
            line = line.replace(':', '')  # Remove colons
            line = line.replace('---', '')  # Remove '---'
            if line.strip() == '-':
                line = ''  # Remove lines with only a single dash
            if not line.strip():  # Skip empty lines to reduce gap
                continue

            if line.startswith('####'):
                pdf.set_font(font_name, style='B', size=12)
                pdf.multi_cell(0, 5, line[4:].strip(), align='L')  # Reduced line height
                pdf.set_font(font_name, size=12)
            elif line.startswith('###'):
                pdf.set_font(font_name, style='B', size=14)
                pdf.multi_cell(0, 5, line[3:].strip(), align='L')  # Reduced line height
                pdf.set_font(font_name, size=12)
            elif line.startswith('##'):
                pdf.set_font(font_name, style='B', size=16)
                pdf.multi_cell(0, 5, line[2:].strip(), align='L')  # Reduced line height
                pdf.set_font(font_name, size=12)
            elif line.startswith('#'):
                pdf.set_font(font_name, style='B', size=18)
                pdf.multi_cell(0, 5, line[1:].strip(), align='L')  # Reduced line height
                pdf.set_font(font_name, size=12)
            else:
                parts = re.split(r'(\*\*.*?\*\*)', line)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        pdf.set_font(font_name, style='B', size=12)
                        pdf.multi_cell(0, 5, part[2:-2].strip(), align='L')  # Reduced line height
                        pdf.set_font(font_name, size=12)
                    else:
                        pdf.multi_cell(0, 5, part.strip(), align='L')  # Reduced line height

    # Add ICP Output
    pdf.add_page()
    icp_output = format_output(icp_output)
    add_markdown_text(pdf, icp_output)

    # Add Channels Output
    pdf.add_page()
    channels_output = format_output(channels_output)
    add_markdown_text(pdf, channels_output)

    output_filename = "icp_report.pdf"
    pdf.output(output_filename)
    logging.info(f"PDF generated: {output_filename}")
    return output_filename

@traceable
def send_email_with_pdf(receiver_email, pdf_filename):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = 'Your ICP and Channels Report'
        body = 'Please find attached your ICP and Channels report.'
        msg.attach(MIMEText(body, 'plain'))

        with open(pdf_filename, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {pdf_filename}")
            msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, receiver_email, text)
        server.quit()
        logging.info(f"Email sent to {receiver_email} with attachment {pdf_filename}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")
        return False

def main():
    st.title("ICP and Channels Report Generator")

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

        submit_button = st.form_submit_button(label="Generate ICP and Channels Report")

    if submit_button:
        st.info("Checking your credits...")

        credits, record_id = asyncio.run(check_credits(email))
        if credits > 0:
            st.success("Credits available. Generating ICP and Channels report...")
            icp_output, channels_output = asyncio.run(start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location, marketing_channels))
            st.write("ICP and Channels Report Generated")

            pdf_filename = generate_pdf(icp_output, channels_output)
            st.success("ICP and Channels report generated and saved as PDF")

            if send_email_with_pdf(email, pdf_filename):
                st.success("Email sent successfully")
                new_credits = credits - 1
                asyncio.run(update_credits(record_id, new_credits))
            else:
                st.error("Failed to send email. Please try again later.")
        else:
            st.error("No credits available. Please purchase more credits to generate the ICP and Channels report.")

if __name__ == "__main__":
    main()
