from flask import Flask, request, jsonify
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
import markdown
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.enums import TA_JUSTIFY

# Import your custom modules
from SL_agents import researcher, product_manager, marketing_director, sales_director
from SL_tasks import icp_task, get_channels_task_template, pains_task, gains_task, jtbd_task, propdesign_task, customerj_task
from langchain_openai import ChatOpenAI
from langsmith import traceable
from crewai import Crew, Process, Task

app = Flask(__name__)

@app.route('/')
def index():
    return "Welcome to Swift Launch Backend API"

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Email configuration
SMTP_SERVER = 'mail.privateemail.com'
SMTP_PORT = 587
SENDER_EMAIL = 'yourorder@swiftlaunch.biz'
SENDER_PASSWORD = 'Lovelife1#'
RECEIVER_EMAIL = 'yourorder@swiftlaunch.biz'

# Environment variables for Langsmith
os.environ["LANGSMITH_TRACING_V2"] = "true"
os.environ["LANGSMITH_PROJECT"] = "King E"
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

# Add fields for chunks
for key in ['icp', 'channels', 'pains', 'gains', 'jtbd', 'propdesign', 'customerj']:
    for i in range(1, 11):  # Assuming a maximum of 10 chunks per field, adjust as needed
        AIRTABLE_FIELDS[f"{key}_{i}"] = f"fld{key.capitalize()}{i:02}"

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

def chunk_text(text, chunk_size):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

@traceable
def send_to_airtable(email, icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output):
    chunks = {
        'icp': chunk_text(icp_output, CHUNK_SIZE),
        'channels': chunk_text(channels_output, CHUNK_SIZE),
        'pains': chunk_text(pains_output, CHUNK_SIZE),
        'gains': chunk_text(gains_output, CHUNK_SIZE),
        'jtbd': chunk_text(jtbd_output, CHUNK_SIZE),
        'propdesign': chunk_text(propdesign_output, CHUNK_SIZE),
        'customerj': chunk_text(customerj_output, CHUNK_SIZE),
    }

    data = {
        "fields": {
            "Email": email
        }
    }

    for key, chunks_list in chunks.items():
        for i, chunk in enumerate(chunks_list):
            field_name = f"{key}_{i+1}"
            if field_name in AIRTABLE_FIELDS:
                data["fields"][AIRTABLE_FIELDS[field_name]] = chunk

    store_chunk_in_airtable(data)

def store_chunk_in_airtable(data):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    with httpx.Client() as client:
        response = client.post(url, headers=headers, json=data)
        response.raise_for_status()
        record = response.json()
        logging.info(f"Airtable chunk response: {record}")
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

    with httpx.Client() as client:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        records = response.json().get('records', [])

        chunks = {
            'icp': [],
            'channels': [],
            'pains': [],
            'gains': [],
            'jtbd': [],
            'propdesign': [],
            'customerj': [],
        }

        for record in records:
            fields = record.get('fields', {})
            for key in chunks.keys():
                for i in range(1, 11):  # assuming no more than 10 chunks per output
                    field_name = f"{AIRTABLE_FIELDS[key]}_{i}"
                    chunk = fields.get(field_name, '')
                    if chunk:
                        chunks[key].append(chunk)
                    else:
                        break

        assembled_outputs = {key: ''.join(value) for key, value in chunks.items()}
        logging.info("Data retrieved and reassembled from Airtable successfully")
        return (
            assembled_outputs['icp'],
            assembled_outputs['channels'],
            assembled_outputs['pains'],
            assembled_outputs['gains'],
            assembled_outputs['jtbd'],
            assembled_outputs['propdesign'],
            assembled_outputs['customerj'],
        )

@traceable
def check_credits(email):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    params = {
        "filterByFormula": f"{{{AIRTABLE_FIELDS['email']}}}='{email}'"
    }

    with httpx.Client() as client:
        try:
            logging.info(f"Sending GET request to {url} with params {params}")
            response = client.get(url, headers=headers, params=params)
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
    with httpx.Client() as client:
        response = client.patch(url, headers=headers, json=data)
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
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, spaceAfter=3.6))  # Reduce spacing by 50%
    styles.add(ParagraphStyle(name='Bold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13.2))  # Increase font size by 10%
    styles['Normal'].fontSize = 13.2  # Increase font size by 10%

    elements = []

    # Add header
    header = Paragraph("<para align=right><font color='orange' size=12>Swift Launch Report</font></para>", styles['Normal'])
    elements.append(header)
    elements.append(Spacer(1, 18))  # Small spacer after the header

    # Split content into lines
    lines = content.split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith('## '):
            elements.append(Spacer(1, 13.5))  # Increase space above headers by 50%
            elements.append(Paragraph(line[3:], styles['Bold']))  # Bold and underline headers
            elements.append(Spacer(1, 3.6))  # Space after headers
        elif line.startswith('-'):
            # Handle bullet points
            items = line.split('- ')[1:]
            list_items = []
            for item in items:
                list_items.append(ListItem(Paragraph(item, styles['Justify']), leftIndent=20))
            elements.append(ListFlowable(list_items, bulletType='bullet'))
        elif line.startswith('**') and line.endswith('**'):
            # Handle bold lines
            elements.append(Paragraph(line.strip('*'), styles['Bold']))
            # Add specific check for the section needing more space
            if line.strip('*') == "Unique Selling Points and Positioning:":
                elements.append(Spacer(1, 14.4))  # Increase space after specific bold lines by 100%
            else:
                elements.append(Spacer(1, 3.6))  # Default space after bold lines
        else:
            # Handle normal paragraphs
            elements.append(Paragraph(line, styles['Justify']))
            elements.append(Spacer(1, 1.8))  # Reduce spacing by 50% below headers and content

    doc.build(elements)

    buffer.seek(0)
    with open(filename, 'wb') as f:
        f.write(buffer.getvalue())
    buffer.seek(0)
    return buffer

@traceable
def generate_pdf(icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output):
    # Combine all task outputs into a single markdown string
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
    
    # Convert the combined content to HTML
    html_content = markdown.markdown(combined_content)

    # Create the PDF file
    output_filename = "Swift_Launch_Report.pdf"
    create_pdf(html_content, output_filename)
    logging.info(f"PDF generated: {output_filename}")

    # Check file size
    file_size = os.path.getsize(output_filename)
    logging.info(f"PDF file size: {file_size} bytes")
    if file_size > 20 * 1024 * 1024:  # Check if file size is greater than 20MB
        logging.error("PDF file size exceeds the 20MB limit")
        return None

    return output_filename

@traceable
def send_email_with_pdf(pdf_filename):
    try:
        if not pdf_filename or not os.path.exists(pdf_filename):
            logging.error(f"File not found or exceeds size limit: {pdf_filename}")
            return False

        logging.info(f"Preparing to send email to {RECEIVER_EMAIL} with attachment {pdf_filename}")

        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
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
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, text)
        server.quit()
        logging.info(f"Email sent to {RECEIVER_EMAIL} with attachment {pdf_filename}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")
        logging.debug(traceback.format_exc())
        return False


@profile
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

@app.route('/generate_report', methods=['POST'])
def generate_report():
    data = request.json
    email = data.get("email")
    product_service = data.get("product_service")
    price = data.get("price")
    currency = data.get("currency")
    payment_frequency = data.get("payment_frequency")
    selling_scope = data.get("selling_scope")
    location = data.get("location")
    marketing_channels = data.get("marketing_channels")
    features = data.get("features")
    benefits = data.get("benefits")

    try:
        credits, record_id = check_credits(email)
        if credits > 0:
            icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output = start_crew_process(
                email, product_service, price, currency, payment_frequency, selling_scope, location, marketing_channels, features, benefits)
            
            send_to_airtable(email, icp_output, channels_output, pains_output, gains_output, jtbd_output, propdesign_output, customerj_output)
            retrieved_outputs = retrieve_from_airtable(email)
            pdf_filename = generate_pdf(*retrieved_outputs)
            if pdf_filename:
                if send_email_with_pdf(pdf_filename):
                    new_credits = credits - 1
                    update_credits(record_id, new_credits)
                    return jsonify({"status": "success", "message": "Report generated and email sent successfully"}), 200
                else:
                    return jsonify({"status": "error", "message": "Failed to send email"}), 500
            else:
                return jsonify({"status": "error", "message": "PDF generation failed or exceeds size limit"}), 500
        else:
            return jsonify({"status": "error", "message": "No credits available"}), 400
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        logging.debug(traceback.format_exc())
        return jsonify({"status": "error", "message": "An internal error occurred"}), 500

if __name__ == '__main__':
    app.run(debug=True)
