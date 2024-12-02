import os
import json
import requests
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
import boto3

# Load environment variables from a .env file
load_dotenv()

# Fetch API keys from environment variables
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# AWS credentials and region
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def get_bedrock_client():
    """Create and return a boto3 client for Amazon Bedrock"""
    try:
        session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        
        return session.client(
            service_name='bedrock-runtime',
            region_name=AWS_REGION,
        )
    except Exception as e:
        print(f"Error creating Bedrock client: {str(e)}")
        return None

def initialize_bedrock_llm():
    """Initialize and return the Bedrock LLM model"""
    try:
        return ChatBedrock(
            model_id="meta.llama3-8b-instruct-v1:0",
            client=get_bedrock_client(),
            model_kwargs={
                "temperature": 0.7,
                "max_tokens": 256
            }
        )
    except Exception as e:
        print(f"Error initializing Bedrock LLM: {str(e)}")
        return None

PRIORITY_MAPPING = {
    "FCP": "High",
    "LCP": "Medium",
    "CLS": "Medium",
    "TBT": "Low"
}

ADDRESSABLE_ISSUES = {
    "modern-image-formats": [
        "Convert the images: Use an image conversion tool to parse the image URLs and convert the images to the WebP format.",
        "Update the Codebase: Replace the original image URLs with the WebP image URLs for improved performance."
    ],
    "unminified-javascript": [
        "1. Go to Stores > Configuration > Advanced > Developer > JavaScript Settings.",
        "2. Set Minify JavaScript Files to 'Yes'."
    ],
    "render-blocking-resources": [
        "Optimize loading order:",
        "1. Go to Stores > Configuration > Advanced > Developer > JavaScript Settings.",
        "2. Enable 'Deferred JavaScript Loading' if available."
    ]
}

def fetch_json_from_api(site_url, api_key):
    api_url = f'https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={site_url}&key={api_key}'
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as err:
        return f"Error fetching data: {err}"
    except json.JSONDecodeError:
        return "Failed to decode JSON. Please check the API response."

# client = Groq(api_key=GROQ_API_KEY)

llm = initialize_bedrock_llm()

# Add the provider stop sequence key name map to handle the error
llm.provider_stop_sequence_key_name_map = {
    'meta': ''
}

def generate_questions(query: str, num_questions: int = 1) -> list[dict]:
    prompt = f"""
    You are an AI assistant specializing in optimization and issue resolution for web performance metrics. 
    Given the following issue or optimization metric from a PageSpeed Insights report:  
    "{query}"
    Generate a simple, concise question that a developer could use to understand and address the issue. 
    Avoid using database query syntax, code-like formatting, or complex logical structures. Focus on clarity and relevance.
    The question should:
    1. Clearly explain the context of the issue in plain language.
    2. Be actionable and useful for a developer to resolve the issue effectively.
    3. Avoid technical jargon or unnecessary complexity.
    Return the question as plain text.
    """

    try:
        # Simulated LLM call for generating the response
        response = llm.invoke(prompt).content  # Replace with your actual LLM call
        questions = []

        # print(response)

        # Parse the response for questions
        for line in response.splitlines():
            if line.strip():  # Skip empty lines
                questions.append({line.strip()})

        # Limit results to `num_questions`
        que=questions[1]
        return que

    except Exception as e:
        return [{"error": f"Error generating questions: {e}"}]


def parse_lighthouse_json(site_url, api_key):
    data = fetch_json_from_api(site_url, api_key)
    if not data:
        return "No data fetched from API."

    audits = data.get("lighthouseResult", {}).get("audits", {})
    results = []
    total_time_saved_admin = 0
    total_time_saved_manual = 0

    for audit_id, audit_data in audits.items():
        metric_savings = audit_data.get("metricSavings", {})
        if not any(metric_savings.values()):
            continue

        savings = sum(metric_savings.values())
        priority = PRIORITY_MAPPING.get(audit_id, "Unknown")

        if audit_id in ADDRESSABLE_ISSUES:
            total_time_saved_admin += savings
            solutions = '\n'.join(f"- {line}" for line in ADDRESSABLE_ISSUES[audit_id])
            result=(
                f"{audit_data.get('title')} ({priority} priority)\n"
                f"Potential Savings: {savings:.2f} ms\nSolution:\n{solutions}\n"
            )
            st.text_area("Audit Results", value=result, height=200)

    for audit_id, audit_data in audits.items():
        metric_savings = audit_data.get("metricSavings", {})
        if not any(metric_savings.values()):
            continue

        savings = sum(metric_savings.values())
        priority = PRIORITY_MAPPING.get(audit_id, "Unknown")

        if audit_id in ADDRESSABLE_ISSUES:
            continue
        else:
            total_time_saved_manual += savings
            unknown_question = generate_questions(audit_data.get("title"))
            result=(
                f"{audit_data.get('title')} ({priority} priority)\n"
                f"Potential Savings: {savings:.2f} ms\nGenerated Question:\n- {unknown_question}\n"
            )
            st.text_area("Audit Results", value=result, height=200)

    combined_savings = (
        f"Total Admin Panel Savings: {total_time_saved_admin / 1000:.2f} seconds\n"
        f"Total Manual Intervention Savings: {total_time_saved_manual / 1000:.2f} seconds\n"
        f"Total Combined Savings: {(total_time_saved_admin + total_time_saved_manual) / 1000:.2f} seconds"
    )
    st.text_area("Audit Results", value=combined_savings, height=200)

# Streamlit App
st.title("Web Analyser")
site_url = st.text_input("Website URL", placeholder="Enter the URL of the website to audit")

if st.button("Run Audit"):
    if not PAGESPEED_API_KEY:
        st.error("PAGESPEED_API_KEY is not set. Please configure it in your environment.")
    else:
        # with st.spinner("Analyzing website... this might take up to 50 seconds."):
            parse_lighthouse_json(site_url, PAGESPEED_API_KEY)
        
