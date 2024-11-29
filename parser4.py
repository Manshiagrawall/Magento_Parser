import os
import json
import requests
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Fetch API keys from environment variables or Streamlit secrets
try:
    # Attempt to load from .env file for local development
    PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
except KeyError:
    # Fallback to Streamlit secrets for deployment
    PAGESPEED_API_KEY = st.secrets["api_keys"]["PAGESPEED_API_KEY"]
    GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]

# Check if GROQ_API_KEY is set before initializing Groq client
if not GROQ_API_KEY:
    st.error("GROQ_API_KEY is not set. Please configure it in your environment.")
else:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        st.error(f"Failed to initialize Groq client: {e}")

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

client = Groq(api_key=GROQ_API_KEY)

def generate_questions(query: str, num_questions: int = 1) -> str:
    prompt = f"""
Based on the topic "{query}", generate {num_questions} highly refined and semantically rich questions.
Ensure the questions:
1. Are detailed and specific to the topic.
2. Use terminology that reflects developer concerns or priorities related to the topic.
3. Emphasize actionable insights or solutions that developers can implement.
4. Are designed to cover different facets of the topic to ensure breadth and depth of coverage.
"""
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="mixtral-8x7b-32768",
            temperature=0.7,
            max_tokens=256
        )
        response_text = response.choices[0].message.content.strip()
        question = response_text.split("\n")[0]
        return question
    except Exception as e:
        return f"Error generating question: {e}"

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
            results.append(
                f"{audit_data.get('title')} ({priority} priority)\n"
                f"Potential Savings: {savings:.2f} ms\nSolution:\n{solutions}\n"
            )
        else:
            total_time_saved_manual += savings
            unknown_question = generate_questions(audit_data.get("title"))
            results.append(
                f"{audit_data.get('title')} ({priority} priority)\n"
                f"Potential Savings: {savings:.2f} ms\nGenerated Question:\n- {unknown_question}\n"
            )

    combined_savings = (
        f"Total Admin Panel Savings: {total_time_saved_admin / 1000:.2f} seconds\n"
        f"Total Manual Intervention Savings: {total_time_saved_manual / 1000:.2f} seconds\n"
        f"Total Combined Savings: {(total_time_saved_admin + total_time_saved_manual) / 1000:.2f} seconds"
    )
    return "\n\n".join(results) + "\n\n" + combined_savings

# Streamlit App
st.title("Lighthouse Audit Tool")
site_url = st.text_input("Website URL", placeholder="Enter the URL of the website to audit")

if st.button("Run Audit"):
    if not PAGESPEED_API_KEY:
        st.error("PAGESPEED_API_KEY is not set. Please configure it in your environment.")
    else:
        results = parse_lighthouse_json(site_url, PAGESPEED_API_KEY)
        st.text_area("Audit Results", results, height=300)
