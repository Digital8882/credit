from flask import Flask, request, jsonify
import asyncio
import httpx
import os
import logging
from SL_agents import researcher, product_manager, marketing_director, sales_director
from SL_tasks import icp_task, get_channels_task_template, pains_task, gains_task, jtbd_task, propdesign_task, customerj_task
from langchain_openai import ChatOpenAI
from langsmith import traceable
from crewai import Crew, Process, Task

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment variables for Langsmith
os.environ["LANGSMITH_TRACING_V2"] = "true"
os.environ["LANGSMITH_PROJECT"] = "king ek"
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

# Email configuration
SMTP_SERVER = "mail.privateemail.com"
SMTP_PORT = 587
SENDER_EMAIL = "yourorder@swiftlaunch.biz"
SENDER_PASSWORD = "Lovelife1#"

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
            response.raise_for_status()
            records = response.json().get('records', [])
            if records:
                fields = records[0].get('fields', {})
                credits = fields.get('Credits', 0)
                if credits is not None:
                    credits = int(credits)
                else:
                    credits = 0
                record_id = records[0]['id']
                return credits, record_id
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
        return record['id']

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
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
        except Exception as e:
            logging.error(f"An error occurred during the crew process: {e}")
            raise

@app.route('/check_credits', methods=['POST'])
def check_credits_route():
    data = request.json
    email = data.get('email')
    credits, record_id = asyncio.run(check_credits(email))
    return jsonify({'credits': credits, 'record_id': record_id})

@app.route('/start_process', methods=['POST'])
def start_process_route():
    data = request.json
    email = data.get('email')
    product_service = data.get('product_service')
    price = data.get('price')
    currency = data.get('currency')
    payment_frequency = data.get('payment_frequency')
    selling_scope = data.get('selling_scope')
    location = data.get('location')
    marketing_channels = data.get('marketing_channels')
    features = data.get('features')
    benefits = data.get('benefits')
    icp_output, = asyncio.run(start_crew_process(email, product_service, price, currency, payment_frequency, selling_scope, location, marketing_channels, features, benefits))
    return jsonify({'icp_output': icp_output})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
