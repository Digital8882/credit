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

os.environ["LANGSMITH_TRACING_V2"] = "true"
os.environ["LANGSMITH_PROJECT"] = "SL0llsssu1p0o"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_API_KEY"] = "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"

# Airtable configuration
AIRTABLE_API_KEY = 'patnWOUVJR780iDNN.de9fb8264698287a5b4206fad59a99871d1fc6dddb4a94e7e7770ab3bcef014e'
AIRTABLE_BASE_ID = 'appPcWNUeei7MNMCj'
AIRTABLE_TABLE_NAME = 'tblaMtAcnVa4nwnby'
AIRTABLE_FIELDS = {
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
async def check_credits(email):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    params = {
        "filterByFormula": f"{{Email}}='{email}'"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        records = response.json().get('records', [])
        if records:
            fields = records[0]['fields']
            credits = fields.get(AIRTABLE_FIELDS['credits'], 0)
            record_id = records[0]['id']
            return credits, record_id
        else:
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
        logging.info(f"Airtable response: {record}")
        return record['id']

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
        return fields.get(AIRTABLE_FIELDS['icp'], '')

@traceable
async def start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location, retries=3):
    task_description = f"New task from {email} selling {product_service} at {price} {currency} with payment frequency {payment_frequency}."
    if selling_scope == "Locally":
        task_description += f" Location: {location}."

    new_task = Task(description=task_description, expected_output="...")

    project_crew = Crew(
        tasks=[new_task, icp_task],
        agents=[researcher],
        manager_llm=ChatOpenAI(temperature=0, model="gpt-4o"),
        max_rpm=5,
        process=Process.hierarchical,
        memory=True,
    )

    for attempt in range(retries):
        try:
            logging.info(f"Starting crew process, attempt {attempt + 1}")
            results = project_crew.kickoff()
            # Access task outputs directly
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
    pdf.set_font(font_name, style='')
    add_markdown_text(pdf, icp_output)

    pdf.output("icp_report.pdf")
    logging.info("PDF generated successfully")

def send_email(recipient_email, icp_output, retries=3):
    message = f"""Subject: Your ICP Report

    Dear Customer,

    Please find attached your ICP report generated based on the information provided.

    Best regards,
    Swift Launch Team
    """

    try:
        generate_pdf(icp_output)  # Generate the PDF before sending

        for attempt in range(retries):
            try:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    msg = MIMEMultipart()
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = recipient_email
                    msg['Subject'] = "Your ICP Report"
                    msg.attach(MIMEText(message, 'plain'))

                    with open("icp_report.pdf", "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f"attachment; filename= icp_report.pdf")
                        msg.attach(part)

                    text = msg.as_string()
                    server.sendmail(SENDER_EMAIL, recipient_email, text)
                logging.info("Email sent successfully")
                return True
            except Exception as e:
                logging.error(f"Failed to send email on attempt {attempt + 1}: {e}")
                logging.debug(traceback.format_exc())
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return False
    except Exception as e:
        logging.error(f"Failed to generate PDF or send email: {e}")
        logging.debug(traceback.format_exc())
        return False

def main():
    # Inject custom CSS for dynamic iframe height adjustment and hiding Streamlit branding
    st.markdown(
        """
        <style>
        @import url('style.css');
        .stApp {
            background-color: #000000;
        }
        .title {
            color: #DE6A1D;
            font-size: 3em;
        }
        .subtitle {
            color: #DE6A1D;
            font-size: 1.2em;
        }
        input {
            background-color: #1A1A1A !important;
            color: #FFFFFF !important;
        }
        textarea {
            background-color: #1A1A1A !important;
            color: #FFFFFF !important;
        }
        select {
            background-color: #1A1A1A !important;
            color: #FFFFFF !important;
        }
        footer {visibility: hidden;}
        .css-1v0mbdj {padding-top: 0 !important;}
        .block-container {padding-top: 20px !important;}
        .stApp a:first-child {display: none;}
        .css-15zrgzn {display: none;}
        .css-eczf16 {display: none;}
        .css-jn99sy {display: none;}
        div[data-testid="stToolbar"] { display: none; }
        </style>
        <script>
        function sendHeight() {
            const height = document.documentElement.scrollHeight;
            window.parent.postMessage({ height: height }, '*');
        }

        window.addEventListener('load', sendHeight);
        window.addEventListener('resize', sendHeight);
        </script>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<h1 class="title">Swift Launch Report</h1>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    first_name = col1.text_input("First Name")
    email = col2.text_input("Email")

    if len(email) > 0 and "@" not in email:
        st.error("Please enter a valid email address")

    product_service = st.text_input("Product/Service being sold")
    
    col3, col4 = st.columns(2)
    price = col3.text_input("Price")
    currency = col4.selectbox("Currency", ["USD", "EUR", "GBP", "JPY", "AUD"])
    
    col5, col6 = st.columns(2)
    payment_frequency = col5.selectbox("Payment Frequency", ["One-time", "Monthly", "Yearly"])
    selling_scope = col6.selectbox("Are you selling Locally or Globally?", ["Locally", "Globally"])

    location = ""
    if selling_scope == "Locally":
        location = st.text_input("Location")

    if st.button("Submit"):
        if email and product_service and price:
            try:
                with st.spinner("Generating customer profile..."):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    credits, record_id = loop.run_until_complete(check_credits(email))
                    if credits > 0:
                        icp_output = loop.run_until_complete(
                            start_crew_process(
                                email, product_service, price, currency, payment_frequency, selling_scope, location
                            )
                        )

                        airtable_record_id = loop.run_until_complete(
                            send_to_airtable(email, icp_output)
                        )
                        
                        if airtable_record_id:
                            st.success("Data successfully sent to Airtable!")
                            email_sent = send_email(email, icp_output)
                            if email_sent:
                                st.success("Email sent successfully!")
                                new_credits = credits - 1
                                loop.run_until_complete(update_credits(record_id, new_credits))
                            else:
                                st.error("Failed to send email after multiple attempts.")
                        else:
                            st.error("Failed to send data to Airtable.")
                    else:
                        st.error("Insufficient credits. Please purchase a report from swiftlaunch.biz.")
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.error(traceback.format_exc())
                logging.error(f"An error occurred: {e}")
                logging.debug(traceback.format_exc())
        else:
            st.error("Please fill in all the required fields.")

if __name__ == "__main__":
    main()

# Restore the original print function after execution
builtins.print = original_print
