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
import requests

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Email configuration
SMTP_SERVER = 'smtp-mail.outlook.com'
SMTP_PORT = 587
SENDER_EMAIL = 'info@swiftlaunch.biz'
SENDER_PASSWORD = 'Lovelife1#'

# Environment variables for Langsmith
os.environ["LANGSMITH_TRACING_V2"] = "true"
os.environ["LANGSMITH_PROJECT"] = "SL0llu1ddp0o"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_API_KEY"] = "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"

# Airtable configuration
AIRTABLE_API_KEY = 'patnWOUVJR780iDNN.de9fb8264698287a5b4206fad59a99871d1fc6dddb4a94e7e7770ab3bcef014e'
AIRTABLE_BASE_ID = 'appPcWNUeei7MNMCj'
AIRTABLE_TABLE_NAME = 'tblaMtAcnVa4nwnby'
AIRTABLE_FIELDS = {
    'email': 'fldsx1iIk4FiRaLi8',
    'credits': 'fldxwzSmMmldMGlgI',
    'icp': 'fldL1kkrGflCtOxwa'
}

# Font configuration
FONT_DIR = "fonts"
ARIAL_REGULAR_URL = "https://example.com/path/to/arial.ttf"
ARIAL_BOLD_URL = "https://example.com/path/to/arialbd.ttf"

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

def download_font(url, font_path):
    if not os.path.exists(font_path):
        response = requests.get(url)
        response.raise_for_status()
        with open(font_path, 'wb') as f:
            f.write(response.content)
        logging.info(f"Downloaded font from {url} to {font_path}")

def ensure_fonts():
    if not os.path.exists(FONT_DIR):
        os.makedirs(FONT_DIR)
    download_font(ARIAL_REGULAR_URL, os.path.join(FONT_DIR, "arial.ttf"))
    download_font(ARIAL_BOLD_URL, os.path.join(FONT_DIR, "arialbd.ttf"))

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
            AIRTABLE_FIELDS['icp']: icp_output
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
        return fields.get(AIRTABLE_FIELDS['icp'], '')

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
async def start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location, retries=3):
    task_description = f"New task from {email} selling {product_service} at {price} {currency} with payment frequency {payment_frequency}."
    if selling_scope == "Locally":
        task_description += f" Location: {location}."

    new_task = Task(description=task_description, expected_output="...")

    project_crew = Crew(
        tasks=[new_task, icp_task],
        agents=[researcher],  # Removed report_writer
        manager_llm=ChatOpenAI(temperature=0, model="gpt-4o"),
        max_rpm=5,
        process=Process.hierarchical,
        memory=True,
    )

    for attempt in range(retries):
        try:
            logging.info(f"Starting crew process, attempt {attempt + 1}")
            results = project_crew.kickoff()
            icp_output = icp_task.output.exported_output if hasattr(icp_task.output, 'exported_output') else "No ICP output"
            logging.info("Crew process completed successfully")
            return icp_output
        except BrokenPipeError as e:
            logging.error(f"BrokenPipeError occurred on attempt {attempt + 1}: {e}")
            logging.debug(traceback.format_exc())
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
        except Exception as e:
            logging.error(f"An error occurred during the crew process: {e}")
            logging.debug(traceback.format_exc())
            raise

@traceable
def format_output(output):
    formatted_output = ""
    sections = output.split("\n\n")
    for section in sections:
        lines = section.split("\n")
        if lines:
            header = lines[0].strip()
            content_lines = []
            for line in lines[1:]:
                stripped_line = line.strip()
                if stripped_line.startswith("-"):
                    content_lines.append(stripped_line)
                else:
                    content_lines[-1] += f" {stripped_line}"
            formatted_output += f"{header}\n" + "\n".join(content_lines) + "\n\n"
    return formatted_output

def create_pdf(output, email):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', size=12)

    output = re.sub(r'(?<=\w)-\n(?=\w)', '', output)
    output = re.sub(r'(?<=\w)\n(?=\w)', ' ', output)
    output = re.sub(r'(?<=\w)\n(?=-)', '\n\n', output)
    pdf.multi_cell(0, 10, output)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{email}_output_{timestamp}.pdf"
    pdf_path = os.path.join("outputs", file_name)
    pdf.output(pdf_path)
    logging.info(f"PDF created successfully at {pdf_path}")
    return pdf_path

async def send_email(to_address, attachment_path):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_address
    msg['Subject'] = 'ICP Report'
    body = 'Please find attached your ICP report.'
    msg.attach(MIMEText(body, 'plain'))

    with open(attachment_path, 'rb') as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
        msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            text = msg.as_string()
            server.sendmail(SENDER_EMAIL, to_address, text)
        logging.info(f"Email sent successfully to {to_address}")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def main():
    st.title("ICP Report Generator")

    email = st.text_input("Enter your email")
    product_service = st.text_input("Enter the product/service name")
    price = st.text_input("Enter the price")
    currency = st.selectbox("Select the currency", ["USD", "EUR", "GBP"])
    payment_frequency = st.selectbox("Select the payment frequency", ["One-time", "Monthly", "Annually"])
    selling_scope = st.selectbox("Select the selling scope", ["Locally", "Nationally", "Internationally"])
    location = st.text_input("Enter the location (if selling locally)")

    if st.button("Generate Report"):
        try:
            ensure_fonts()
            credits, record_id = asyncio.run(check_credits(email))
            if credits > 0:
                output = asyncio.run(start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location))
                formatted_output = format_output(output)
                pdf_path = create_pdf(formatted_output, email)
                asyncio.run(send_email(email, pdf_path))
                asyncio.run(send_to_airtable(email, formatted_output))
                new_credits = credits - 1
                asyncio.run(update_credits(record_id, new_credits))
                st.success("Report generated and sent successfully!")
            else:
                st.warning("Insufficient credits to generate the report.")
        except Exception as e:
            st.error(f"An error occurred: {e}")
            logging.error(f"An error occurred: {e}")
            logging.debug(traceback.format_exc())

if __name__ == "__main__":
    main()

