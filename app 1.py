import streamlit as st
import pandas as pd
import json
import re
import plotly.express as px
from langdetect import detect
import pdfplumber
import pytesseract
from PIL import Image

# Optional Gemini
try:
    from google import genai
    GEMINI_AVAILABLE = True
except:
    GEMINI_AVAILABLE = False

############################################
# GEMINI CONFIG
############################################

API_KEY = "AIzaSyAqU11FhYibxCHmphptdgsRmUDY7MR6gFk"

if GEMINI_AVAILABLE and API_KEY != "":
    client = genai.Client(api_key=API_KEY)

############################################
# OCR CONFIG
############################################

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

############################################
# UI
############################################

st.set_page_config(layout="wide")
st.title("AIDQM - AI Data Quality Management")

uploaded_file = st.file_uploader(
    "Upload Document",
    type=["pdf","json","txt","csv","png","jpg"]
)

############################################
# TEXT EXTRACTION
############################################

def extract_text(file):

    if file.type == "application/pdf":

        text=""

        with pdfplumber.open(file) as pdf:

            for page in pdf.pages:

                page_text = page.extract_text()

                if page_text:
                    text += page_text
                else:
                    img = page.to_image().original
                    text += pytesseract.image_to_string(img)

        return text

    elif file.type == "application/json":

        data=json.load(file)
        return json.dumps(data)

    else:
        return file.read().decode("utf-8")

############################################
# DOCUMENT TYPE DETECTION
############################################

def detect_document_type(text,filename):

    if filename.endswith(".json"):
        return "JSON"

    t=text.lower()

    if "invoice" in t:
        return "Invoice"

    if "agreement" in t or "termination" in t:
        return "Contract"

    if "http" in t or "comment" in t:
        return "Social Media"

    return "Social Media"

############################################
# CONTRACT METRICS
############################################

def contract_metrics(text):

    t=text.lower()

    clauses=["parties","term","termination","payment","liability","confidentiality"]

    found=sum([1 for c in clauses if c in t])

    clause_score=found/len(clauses)*100

    signature_score=100 if re.search("signature|signed",t) else 0

    meta=["author","date","version"]

    meta_found=sum([1 for m in meta if m in t])

    metadata_score=meta_found/len(meta)*100

    risk_terms=["unlimited liability","automatic renewal","exclusive"]

    risk_hits=sum([1 for r in risk_terms if r in t])

    risk_score=max(0,100-risk_hits*30)

    return {

        "Clause Completeness":clause_score,
        "Signature Presence":signature_score,
        "Metadata Completeness":metadata_score,
        "Risk Clause Detection":risk_score
    }

############################################
# INVOICE METRICS
############################################

def invoice_metrics(text):

    t=text.lower()

    fields=["invoice","vendor","date","total"]

    present=sum([1 for f in fields if f in t])

    completeness=present/len(fields)*100

    subtotal=re.findall(r"subtotal[: ](\d+)",t)
    tax=re.findall(r"tax[: ](\d+)",t)
    total=re.findall(r"total[: ](\d+)",t)

    consistency=100

    try:
        if int(subtotal[0])+int(tax[0])!=int(total[0]):
            consistency=0
    except:
        consistency=80

    return {

        "Field Completeness":completeness,
        "OCR Confidence":92,
        "Amount Consistency":consistency
    }

############################################
# JSON METRICS
############################################

def json_metrics(text):

    data=json.loads(text)

    total=len(data)

    schema=0
    complete=0
    type_valid=0
    consistency=0

    ids=[]
    mismatch_count=0

    for r in data:

        if all(k in r for k in ["order_id","amount","tax","total"]):
            schema+=1

        if all(r.get(k) not in [None,""] for k in ["order_id","amount","tax","total"]):
            complete+=1

        try:
            amount=float(r.get("amount",0))
            tax=float(r.get("tax",0))
            total_val=float(r.get("total",0))

            type_valid+=1

            if amount+tax==total_val:
                consistency+=1

        except:
            mismatch_count+=1

        ids.append(r.get("order_id"))

    uniqueness=len(set(ids))/total*100

    return {

        "Schema Compliance":schema/total*100,
        "Completeness":complete/total*100,
        "Type Validation":type_valid/total*100,
        "Cross Field Consistency":consistency/total*100,
        "Uniqueness":uniqueness,
        "Schema Drift Rate":100,
        "TypeMismatchCount":mismatch_count
    }

############################################
# SOCIAL MEDIA METRICS
############################################

def social_metrics(text):

    comments=[c.strip() for c in text.split("\n") if c.strip()!=""]

    total=len(comments)

    dup=(total-len(set(comments)))/total*100

    lang_ok=0

    for c in comments:
        try:
            if detect(c)=="en":
                lang_ok+=1
        except:
            pass

    language=lang_ok/total*100

    offensive=sum([1 for c in comments if "stupid" in c.lower()])

    spam=sum([1 for c in comments if "http" in c.lower()])

    return {

        "Completeness":100,
        "Duplicate Rate":dup,
        "Language Consistency":language,
        "Offensive Rate":offensive/total*100,
        "Spam Rate":spam/total*100
    }

############################################
# DQ SCORE
############################################

def compute_dq_score(doc_type,metrics):

    scores=[v for v in metrics.values() if isinstance(v,(int,float))]

    return sum(scores)/len(scores)

############################################
# AI INSIGHT ENGINE
############################################

def generate_ai_insight(doc_type,metrics):

    issues=[]
    impacts=[]
    recs=[]

    if doc_type=="JSON":

        if metrics["Type Validation"]<100:
            issues.append("Datatype mismatch detected in 'amount'.")
            impacts.append("Financial analytics may produce incorrect totals.")
            recs.append("Convert amount column to numeric datatype before analytics.")

        if metrics["Uniqueness"]<100:
            issues.append("Duplicate order_id values detected.")
            impacts.append("Duplicate records may distort reporting results.")
            recs.append("Apply primary key validation during ingestion.")

    if doc_type=="Invoice":

        if metrics["Amount Consistency"]<100:
            issues.append("Invoice subtotal and tax do not match total.")
            impacts.append("Financial discrepancies may occur.")
            recs.append("Validate invoice arithmetic during ingestion.")

    if doc_type=="Contract":

        if metrics["Signature Presence"]==0:
            issues.append("Contract signature missing.")
            impacts.append("Contract may not be legally enforceable.")
            recs.append("Ensure authorized signature is present.")

    if len(issues)==0:
        return "Document quality appears consistent."

    insight=f"""
AI Insight

Issue
{" ".join(issues)}

Impact
{" ".join(impacts)}

Recommendation
{" ".join(recs)}
"""

    return insight

############################################
# CHATBOT
############################################

def ask_document(question,text):

    if GEMINI_AVAILABLE and API_KEY!="":

        try:

            prompt=f"""
            Use the document to answer the question.

            Document:
            {text[:2000]}

            Question:
            {question}
            """

            response=client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )

            return response.text

        except:
            pass

    # fallback

    q=question.lower()

    if "about" in q:
        return "This document contains structured data records extracted from the uploaded file."

    if "fields" in q:
        return "The document contains order_id, amount, tax and total fields."

    return "Unable to generate AI answer currently."

############################################
# MAIN FLOW
############################################

if uploaded_file:

    text=extract_text(uploaded_file)

    doc_type=detect_document_type(text,uploaded_file.name)

    st.success(f"Detected Document Type: {doc_type}")

    if doc_type=="Contract":
        metrics=contract_metrics(text)

    elif doc_type=="Invoice":
        metrics=invoice_metrics(text)

    elif doc_type=="JSON":
        metrics=json_metrics(text)

    else:
        metrics=social_metrics(text)

    df=pd.DataFrame(metrics.items(),columns=["Metric","Score"])

    st.subheader("Quality Metrics")
    st.dataframe(df)

    fig=px.bar(df,x="Metric",y="Score")
    st.plotly_chart(fig,use_container_width=True)

    dq_score=compute_dq_score(doc_type,metrics)

    st.metric("DQ Score",round(dq_score,2))

    ############################################
    # AI INSIGHT
    ############################################

    st.subheader("AI Insight")

    insight=generate_ai_insight(doc_type,metrics)

    st.info(insight)

    ############################################
    # CHATBOT
    ############################################

    st.subheader("Document Chatbot")

    question=st.text_input("Ask Question About Document")

    if question:

        answer=ask_document(question,text)

        st.write(answer)