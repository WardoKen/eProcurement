import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()

textract = boto3.client(
    "textract",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

with open("sample.jpg", "rb") as f:
    image = f.read()

response = textract.analyze_document(
    Document={"Bytes": image},
    FeatureTypes=["TABLES", "FORMS"]
)

with open("textract_output.json", "w") as outfile:
    json.dump(response, outfile, indent=2)

print("Done!")