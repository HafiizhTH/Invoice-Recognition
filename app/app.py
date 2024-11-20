from fastapi import FastAPI, UploadFile, HTTPException
from model import process_invoice, convert_pdf_to_images
import os
import logging
import uvicorn

app = FastAPI()

# Setup logging
logging.basicConfig(level=logging.INFO)

@app.get("/")
def read_root():
    return {"message": "Success"}

@app.post("/process-invoice/")
async def process_invoice_endpoint(file: UploadFile):
    try:
        logging.info(f"Processing file: {file.filename}")

        # Buat folder sementara untuk menyimpan file
        os.makedirs("./temp", exist_ok=True)
        file_path = f"./temp/{file.filename}"
        
        # Simpan file sementara
        with open(file_path, "wb") as f:
            f.write(await file.read())
        logging.info(f"File saved temporarily at {file_path}")


        # Jika file adalah PDF, konversi menjadi gambar
        if file.filename.endswith(".pdf"):
            logging.info("File is a PDF. Converting to images...")
            try:
                image_paths = convert_pdf_to_images(file_path)
                logging.info(f"PDF converted to images: {image_paths}")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error converting PDF to images: {str(e)}")
        else:
            image_paths = [file_path] 


        # Promp untuk menentukan hasil invoice
        system_prompt = """
            You are a specialist in understanding invoice documents. 
            You will be given an image of an invoice as input, 
            and your task is to answer questions based on the content of the image.

            You need to find data to fill in the data structure below,
            if there is currency data (IDR/Rp/$) do not use it,
            if there is discount data give the (%) symbol, 
            If there is a numeric value then make it an integer,
            if it does not exist then provide an empty status:
            {
                "supplier": {
                    "name": ,
                    "address": ,
                    "phone": ,
                    "email": ,
                    "website": 
                },
                "invoice_number": ,
                "invoice_date": ,
                "due_date": ,
                "client": {
                    "name": ,
                    "address": ,
                    "phone": ,
                    "email": 
                },
                "items": [
                    {
                    "description": ,
                    "unit_price": ,
                    "quantity":,
                    "amount":
                    }
                ],
                "payment_method": {
                    "account": ,
                    "account_name": ,
                    "bank_details": 
                },
                "totals": {
                    "subtotal": ,
                    "revisi": ,
                    "discount": ,
                    "down_payment": ,
                    "total": 
                }
            }
            """

        user_prompt = "Convert Invoice data into json format with appropriate json tags as required for the data in image."
        responses = []
        for img_path in image_paths:
            response = process_invoice(img_path, system_prompt, user_prompt)
            responses.append(response)
        logging.info("Invoice processed successfully")


        # Hapus file sementara
        for path in image_paths:
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists(file_path):
            os.remove(file_path)

        return {"data": responses}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
