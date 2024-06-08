import streamlit as st
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
os.environ["LANGSMITH_PROJECT"] = "SL0llu1p0o"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_API_KEY"] = "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"

# Airtable configuration
AIRTABLE_API_KEY = 'patnWOUVJR780iDNN.de9fb8264698287a5b4206fad59a99871d1fc6dddb4a94e7e7770ab3bcef014e'
AIRTABLE_BASE_ID = 'appPcWNUeei7MNMCj'
AIRTABLE_TABLE_NAME = 'tblaMtAcnVa4nwnby'
AIRTABLE_FIELDS = {
    'email': 'fldsx1iIk4FiRaLi8',
    'icp': 'fldL1kkrGflCtOxwa',
    'credits': 'fldxwzSmMmldMGlgI'
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
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        records = response.json().get('records', [])
        if records:
            fields = records[0].get('fields', {})
            credits = fields.get(AIRTABLE_FIELDS['credits'], 0)
            record_id = records[0]['id']
            logging.info(f"Email {email} found. Credits: {credits}")
            return credits, record_id
        else:
            logging.info(f"Email {email} not found.")
        return 0, None

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
                    if content_lines:
                        content_lines[-1] += " " + stripped_line
                    else:
                        content_lines.append(stripped_line)
            content = "\n".join(content_lines)
            formatted_output += f"{header}\n{content}\n\n"
    return formatted_output.strip()

@traceable
def generate_pdf(icp_output, font_name="Courier", custom_font=False):
    pdf = FPDF()
    pdf.add_page()

    if custom_font:
        # Add regular and bold variants of the custom font
        pdf.add_font(font_name, style="", fname=f"{font_name}.ttf")
        pdf.add_font(font_name, style="B", fname=f"{font_name}-Bold.ttf")

    pdf.set_font(font_name, size=12)  # Use the specified font

    icp_output = format_output(icp_output)

    def add_markdown_text(pdf, text):
        lines = text.split('\n')
        for line in lines:
            if line.startswith('###'):
                pdf.set_font(font_name, style='B', size=16)
                pdf.multi_cell(0, 10, line[3:].strip())
            elif line.startswith('##'):
                pdf.set_font(font_name, style='B', size=14)
                pdf.multi_cell(0, 10, line[2:].strip())
            elif line.startswith('#'):
                pdf.set_font(font_name, style='B', size=12)
                pdf.multi_cell(0, 10, line[1:].strip())
            elif line.startswith('-'):
                pdf.set_font(font_name, style='')
                pdf.cell(0, 10, line.strip(), ln=1)
            else:
                bold_parts = re.split(r'(\*\*.*?\*\*)', line)
                for part in bold_parts:
                    if part.startswith('**') and part.endswith('**'):
                        pdf.set_font(font_name, style='B')
                        pdf.multi_cell(0, 5, part[2:-2])
                    else:
                        pdf.set_font(font_name, style='')
                        pdf.multi_cell(0, 5, part)
            pdf.ln(2.5)  # Reduce space between lines to 50%

    # Add ICP output
    pdf.multi_cell(0, 10, "ICP Output:")
    add_markdown_text(pdf, icp_output)

    # Create output directory if it doesn't exist
    output_directory = "output"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"{output_directory}/icp_report_{timestamp}.pdf"
    pdf.output(pdf_filename)

    logging.info(f"PDF generated and saved as {pdf_filename}")
    return pdf_filename

@traceable
def send_email_with_pdf(recipient_email, pdf_filename, sender_email=SENDER_EMAIL, sender_password=SENDER_PASSWORD):
    try:
        logging.info(f"Preparing to send email to {recipient_email}")
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = 'ICP Report'

        body = 'Please find attached the ICP Report.'
        msg.attach(MIMEText(body, 'plain'))

        with open(pdf_filename, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(pdf_filename)}")
            msg.attach(part)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, recipient_email, text)

        logging.info(f"Email sent to {recipient_email}")
    except Exception as e:
        logging.error(f"Failed to send email to {recipient_email}: {e}")
        logging.debug(traceback.format_exc())
        raise

def main():
    st.title("ICP Report Generator")

    email = st.text_input("Enter your email")
    product_service = st.text_input("Enter the product/service you are selling")
    price = st.text_input("Enter the price")
    currency = st.text_input("Enter the currency")
    payment_frequency = st.selectbox("Select the payment frequency", ["One-time", "Monthly", "Annually"])
    selling_scope = st.selectbox("Select the selling scope", ["Locally", "Globally"])
    location = st.text_input("Enter the location (if selling locally)")

    if st.button("Generate ICP Report"):
        try:
            st.info("Checking credits...")
            credits, record_id = asyncio.run(check_credits(email))
            if credits > 0:
                st.info("Generating ICP Report...")
                icp_output = asyncio.run(start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location))
                pdf_filename = generate_pdf(icp_output)
                send_email_with_pdf(email, pdf_filename)
                asyncio.run(update_credits(record_id, credits - 1))
                st.success("ICP Report generated and sent successfully.")
            else:
                st.error("Insufficient credits. Please purchase more credits at swiftlaunch.biz")
        except Exception as e:
            logging.error(f"Failed to generate ICP Report: {e}")
            logging.debug(traceback.format_exc())
            st.error(f"Failed to generate ICP Report: {e}")

if __name__ == "__main__":
    main()
