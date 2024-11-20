import os
import re
from PIL import Image
from pdf2image import convert_from_path
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
import json
import datetime as dt

# Load environment variables
load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=google_api_key)

# Model configuration
MODEL_CONFIG = {
    "temperature": 0.2,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 4096,
}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Initialize the model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=MODEL_CONFIG,
    safety_settings=safety_settings,
)


# Convert PDF to images
def convert_pdf_to_images(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=300)
        image_paths = []
        for i, img in enumerate(images):
            img_path = f"{pdf_path}_{i}.png"
            img.save(img_path, "PNG")
            image_paths.append(img_path)
        return image_paths
    except Exception as e:
        raise RuntimeError(f"Error converting PDF to images: {e}")


# Format image data
def image_format(image_path):
    img = Path(image_path)
    if not img.exists():
        raise FileNotFoundError(f"Could not find image: {img}")
    return [{"mime_type": "image/png", "data": img.read_bytes()}]


# Generate output from Gemini model
def gemini_output(image_path, system_prompt, user_prompt):
    image_info = image_format(image_path)
    input_prompt = [system_prompt, image_info[0], user_prompt]
    response = model.generate_content(input_prompt)
    return response.text


# Extract fields using regex
def extract_field(pattern, response):
    match = re.search(pattern, response)
    return match.group(1) if match else None

# Convert to integer
def int_type(value):
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None

# Convert to datetime
def datetime_type(date_str):
    try:
        return dt.datetime.strptime(date_str, "%d/%m/%Y").strftime("%d/%m/%Y") if date_str else None
    except ValueError:
        return None

# Clean phone data
def clean_phone(phone):
    if not phone:
        return None
    if isinstance(phone, int):
        return phone
    cleaned_phone = re.sub(r"[^\d]", "", phone)
    if cleaned_phone.startswith("0"):
        cleaned_phone = "62" + cleaned_phone[1:]
    return int(cleaned_phone)


# Mapping Data
def mapping_data(response):
    # Invoice data structure
    invoice_data = {
        "supplier": {
            "name": None,
            "address": None,
            "phone": None,
            "email": None,
            "website": None
        },
        "invoice_number": None,
        "invoice_date": None,
        "due_date": None,
        "client": {
            "name": None,
            "address": None,
            "phone": None,
            "email": None
        },
        "items": [],
        "payment_method": {
            "account": None,
            "account_name": None,
            "bank_details": None
        },
        "totals": {
            "subtotal": None,
            "revisi": None,
            "discount": None,
            "down_payment": None,
            "total": None
        }
    }

    try:
        # Supplier Information
        supplier_section = re.search(r'"supplier":\s*{(.*?)}', response, re.DOTALL)
        if supplier_section:
            supplier_data = supplier_section.group(1)
            invoice_data["supplier"]["name"] = extract_field(r'"name":\s*"([^"]+)"', supplier_data)
            invoice_data["supplier"]["address"] = extract_field(r'"address":\s*"([^"]+)"', supplier_data)
            invoice_data["supplier"]["phone"] = extract_field(r'"phone":\s*"([^"]+)"', supplier_data)
            invoice_data["supplier"]["email"] = extract_field(r'"email":\s*"([^"]+)"', supplier_data)
            invoice_data["supplier"]["website"] = extract_field(r'"website":\s*"([^"]+)"', supplier_data)

        # Invoice Information
        invoice_data["invoice_number"] = extract_field(r'"invoice_number":\s*"([^"]+)"', response)
        invoice_data["invoice_date"] = datetime_type(extract_field(r'"invoice_date":\s*"([^"]+)"', response))
        invoice_data["due_date"] = datetime_type(extract_field(r'"due_date":\s*"([^"]+)"', response))

        # Client Information
        client_section = re.search(r'"client":\s*{(.*?)}', response, re.DOTALL)
        if client_section:
            client_data = client_section.group(1)
            invoice_data["client"]["name"] = extract_field(r'"name":\s*"([^"]+)"', client_data)
            invoice_data["client"]["address"] = extract_field(r'"address":\s*"([^"]+)"', client_data)
            invoice_data["client"]["phone"] = extract_field(r'"phone":\s*"([^"]+)"', client_data)
            invoice_data["client"]["email"] = extract_field(r'"email":\s*"([^"]+)"', client_data)

        # Payment Method
        invoice_data["payment_method"]["account"] = extract_field(r'"account":\s*"([^"]+)"', response)
        invoice_data["payment_method"]["account_name"] = extract_field(r'"account_name":\s*"([^"]+)"', response)
        invoice_data["payment_method"]["bank_details"] = extract_field(r'"bank_details":\s*"([^"]+)"', response)

        # Totals Information (Konversi ke integer untuk subtotal, revisi, down_payment, total)
        invoice_data["totals"]["subtotal"] = int_type(extract_field(r'"subtotal":\s*([0-9]+)', response))
        invoice_data["totals"]["revisi"] = int_type(extract_field(r'"revisi":\s*([0-9]+)', response))
        invoice_data["totals"]["discount"] = extract_field(r'"discount":\s*"([^"]+)"', response)
        invoice_data["totals"]["down_payment"] = int_type(extract_field(r'"down_payment":\s*([0-9]+)', response))
        invoice_data["totals"]["total"] = int_type(extract_field(r'"total":\s*([0-9]+)', response))

        # Items Information
        item_pattern = r'"description":\s*"([^"]+)",\s*"unit_price":\s*([0-9]+),\s*"quantity":\s*([0-9]+),\s*"amount":\s*([0-9]+)'
        matches = re.findall(item_pattern, response)
        
        for match in matches:
            item = {
                "description": match[0],
                "unit_price": int_type(match[1]),
                "quantity": int_type(match[2]),
                "amount": int_type(match[3])
            }
            invoice_data["items"].append(item)

    except Exception as e:
        print(f"Error during parsing: {e}")

    return invoice_data


def process_invoice(image_path, system_prompt, user_prompt):
    try:
        response = gemini_output(image_path, system_prompt, user_prompt)

        if not response:
            raise ValueError("Response from the model is empty.")

        invoice_data = mapping_data(response)

        invoice_data["supplier"]["phone"] = clean_phone(invoice_data["supplier"]["phone"])
        invoice_data["client"]["phone"] = clean_phone(invoice_data["client"]["phone"])

        return invoice_data

    except Exception as e:
        raise RuntimeError(f"Error processing invoice: {e}")