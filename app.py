import streamlit as st
from SL_agents import researcher, product_manager, marketing_director, sales_director
from SL_tasks import icp_task, get_channels_task_template, pains_task, gains_task, jtbd_task, propdesign_task, customerj_task
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
os.environ["LANGSMITH_PROJECT"] = "King Ell"
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
def send_to_airtable(email, icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output):
    data = {
        "fields": {
            AIRTABLE_FIELDS['email']: email,
            AIRTABLE_FIELDS['icp']: icp_output,
            AIRTABLE_FIELDS['channels']: channels_output,
            AIRTABLE_FIELDS['pains']: pains_output,
            AIRTABLE_FIELDS['gains']: gains_output,
            AIRTABLE_FIELDS['jtbd']: jtbd_output,
            AIRTABLE_FIELDS['propdesign']: propdesign_output,
            AIRTABLE_FIELDS['customerj']: customerj_output
        }
    }

    store_data_in_airtable(data)

def store_data_in_airtable(data):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    response = httpx.post(url, headers=headers, json=data)
    response.raise_for_status()
    record = response.json()
    logging.info(f"Airtable response: {record}")
    return record['id']

@traceable
def retrieve_from_airtable(email):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    params = {
        "filterByFormula": f"{{{AIRTABLE_FIELDS['email']}}}='{email}'"
    }

    response = httpx.get(url, headers=headers, params=params)
    response.raise_for_status()
    records = response.json().get('records', [])

    if records:
        fields = records[0].get('fields', {})
        return (
            fields.get(AIRTABLE_FIELDS['icp'], ''),
            fields.get(AIRTABLE_FIELDS['channels'], ''),
            fields.get(AIRTABLE_FIELDS['pains'], ''),
            fields.get(AIRTABLE_FIELDS['gains'], ''),
            fields.get(AIRTABLE_FIELDS['jtbd'], ''),
            fields.get(AIRTABLE_FIELDS['propdesign'], ''),
            fields.get(AIRTABLE_FIELDS['customerj'], '')
        )
    else:
        logging.info(f"No records found for email: {email}")
        return ('', '', '', '', '', '', '')

@traceable
def check_credits(email):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    params = {
        "filterByFormula": f"{{{AIRTABLE_FIELDS['email']}}}='{email}'"
    }

    response = httpx.get(url, headers=headers, params=params)
    response.raise_for_status()
    records = response.json().get('records', [])
    if records:
        fields = records[0].get('fields', {})
        credits = fields.get(AIRTABLE_FIELDS['credits'], 0)
        return int(credits), records[0]['id']
    else:
        logging.info(f"Email {email} not found.")
    return 0, None

@traceable
def update_credits(record_id, new_credits):
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
    response = httpx.patch(url, headers=headers, json=data)
    response.raise_for_status()
    record = response.json()
    logging.info(f"Airtable update response: {record}")
    return record['id']

@traceable
def format_output(output):
    return output.strip()

@traceable
def create_pdf(content, filename):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, spaceAfter=3.6))
    styles.add(ParagraphStyle(name='Bold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13.2))
    styles['Normal'].fontSize = 13.2

    elements = []

    header = Paragraph("<para align=right><font color='orange' size=12>Swift Launch Report</font></para>", styles['Normal'])
    elements.append(header)
    elements.append(Spacer(1, 18))

    lines = content.split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith('## '):
            elements.append(Spacer(1, 13.5))
            elements.append(Paragraph(line[3:], styles['Bold']))
            elements.append(Spacer(1, 3.6))
        elif line.startswith('-'):
            items = line.split('- ')[1:]
            list_items = []
            for item in items:
                list_items.append(ListItem(Paragraph(item, styles['Justify']), leftIndent=20))
            elements.append(ListFlowable(list_items, bulletType='bullet'))
        elif line.startswith('**') and line.endswith('**'):
            elements.append(Paragraph(line.strip('*'), styles['Bold']))
            if line.strip('*') == "Unique Selling Points and Positioning:":
                elements.append(Spacer(1, 14.4))
            else:
                elements.append(Spacer(1, 3.6))
        else:
            elements.append(Paragraph(line, styles['Justify']))
            elements.append(Spacer(1, 1.8))

    doc.build(elements)

    buffer.seek(0)
    with open(filename, 'wb') as f:
        f.write(buffer.getvalue())
    buffer.seek(0)
    return buffer

@traceable
def generate_pdf(icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output):
    combined_content = f"""
## ICP Output
{icp_output}

## Channels Output
{channels_output}

## Pains Output
{pains_output}

## Gains Output
{gains_output}

## JTBD Output
{jtbd_output}

## Product Design Output
{propdesign_output}

## Customer Journey Output
{customerj_output}
"""
    return create_pdf(combined_content, "Swift_Launch_Report.pdf")

@traceable
def send_email_with_pdf(receiver_email, pdf_filename):
    try:
        if not pdf_filename or not os.path.exists(pdf_filename):
            logging.error(f"File not found or exceeds size limit: {pdf_filename}")
            return False

        logging.info(f"Preparing to send email to {receiver_email} with attachment {pdf_filename}")

        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = 'Your Swift Launch Report'
        body = 'Please find attached your Swift Launch Report.'
        msg.attach(MIMEText(body, 'plain'))

        with open(pdf_filename, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename={pdf_filename}")
            msg.attach(part)

        logging.info("Connecting to SMTP server")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)

        logging.info("Sending email")
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, receiver_email, text)
        server.quit()
        logging.info(f"Email sent to {receiver_email} with attachment {pdf_filename}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")
        logging.debug(traceback.format_exc())
        return False

@traceable
def start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location, marketing_channels, features, benefits, retries=3):
    task_description = f"New task from {email} selling {product_service} at {price} {currency} with payment frequency {payment_frequency}."
    if selling_scope == "Locally":
        task_description += f" Location: {location}."
    task_description += f" Focus on the following marketing channels: {', '.join(marketing_channels)}."

    new_task = Task(description=task_description, expected_output="...")

    channels_task = get_channels_task_template(marketing_channels)

    project_crew = Crew(
        tasks=[new_task, icp_task, channels_task, pains_task, gains_task, jtbd_task, propdesign_task, customerj_task],
        agents=[researcher, product_manager, marketing_director, sales_director],
        manager_llm=ChatOpenAI(temperature=0, model="gpt-4o"),
        max_rpm=6,
        process=Process.hierarchical,
        memory=True,
    )

    for attempt in range(retries):
        try:
            logging.info(f"Starting crew process, attempt {attempt + 1}")
            results = project_crew.kickoff()
            icp_output = icp_task.output.exported_output if hasattr(icp_task.output, 'exported_output') else "No ICP output"
            channels_output = channels_task.output.exported_output if hasattr(channels_task.output, 'exported_output') else "No Channels output"
            pains_output = pains_task.output.exported_output if hasattr(pains_task.output, 'exported_output') else "No Pains output"
            gains_output = gains_task.output.exported_output if hasattr(gains_task.output, 'exported_output') else "No Gains output"
            jtbd_output = jtbd_task.output.exported_output if hasattr(jtbd_task.output, 'exported_output') else "No JTBD output"
            propdesign_output = propdesign_task.output.exported_output if hasattr(propdesign_task.output, 'exported_output') else "No Product Design output"
            customerj_output = customerj_task.output.exported_output if hasattr(customerj_task.output, 'exported_output') else "No Customer Journey output"
            logging.info("Crew process completed successfully")
            return icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output
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
    st.title("ICP and Channels Report Generator")

    with st.form("input_form"):
        email = st.text_input("Email")
        product_service = st.text_input("Product/Service")
        price = st.number_input("Price", min_value=0.0, format="%f")
        currency = st.selectbox("Currency", ["USD", "EUR", "GBP"])
        payment_frequency = st.selectbox("Payment Frequency", ["One-time", "Monthly", "Yearly"])
        selling_scope = st.selectbox("Selling Scope", ["Locally", "Globally"])
        location = st.text_input("Location", disabled=(selling_scope == "Globally"))

        marketing_channels = st.multiselect("Marketing Channels", ["Facebook", "Twitter (x)", "Instagram", "Reddit", "TikTok", "SEO", "Blog", "PPC", "LinkedIn"])

        features = st.text_area("Features", help="Enter the features of your product/service")
        benefits = st.text_area("Benefits", help="Enter the benefits of your product/service")

        submit_button = st.form_submit_button(label="Generate Swift Launch Report")

    if submit_button:
        st.info("Checking your credits...")

        credits, record_id = check_credits(email)
        if credits > 0:
            st.success("Credits available. Generating Swift Launch Report...")
            icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output = start_crew_process(
                email, product_service, price, currency, payment_frequency, selling_scope, location, marketing_channels, features, benefits)
            st.write("Swift Launch Report Generated")

            send_to_airtable(email, icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output)
            retrieved_outputs = retrieve_from_airtable(email)
            pdf_filename = generate_pdf(*retrieved_outputs)
            if pdf_filename:
                st.success("ICP and Channels report generated and saved as PDF")

                if send_email_with_pdf(email, pdf_filename):
                    st.success("Email sent successfully")
                    new_credits = credits - 1
                    update_credits(record_id, new_credits)
                else:
                    st.error("Failed to send email. Please try again later.")
            else:
                st.error("PDF generation failed or exceeds size limit.")
        else:
            st.error("No credits available. Please purchase more credits to generate the Swift Launch Report.")

if __name__ == "__main__":
    main()
