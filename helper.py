# imports 
import os
import base64
import pandas as pd
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# from env 
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SENDER_EMAIL = 'enter email here'
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
MARKUP = 1.16

# gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('models/gemini-flash-lite-latest')


def authenticate():
    """
    handles logging into Gmail.
    """
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES) #Loads Google credentials from credentials.json
        creds = flow.run_local_server(port=0) # Opens the browser ask user to log in with Google and grant permission. 
        # port=0 pick any available port 

        # Saves the login to token.json so next time the script runs it won't open the browser again.
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def download_attachments(service, output_dir='downloads'):
    """
    Downloads attachments from gmail
    """
    os.makedirs(output_dir, exist_ok=True) # Creates the downloads file 
    downloaded_files = [] # collect the paths of all downloaded files

    # Searches for emails only from SENDER_EMAIL, only with xlsx attachments, only unread ones.
    results = service.users().messages().list(
        userId='me', # my email
        q=f'from:{SENDER_EMAIL} has:attachment filename:xlsx is:unread'  
    ).execute()

    # Gets list of matching emails or returns empty list 
    messages = results.get('messages', [])
    if not messages:
        print(f"No new Excel emails found from {SENDER_EMAIL}")
        return downloaded_files

    print(f"Found {len(messages)} new emails with Excel attachments")

    # loop through found eamils
    for msg in messages:
        # Fetches the full email content using its ID 
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        
        # Gets the "parts" of the email (body text, attachments, etc) 
        parts = msg_data['payload'].get('parts', [])

        # Loop through each part of the email to find attachments
        for part in parts:
            if part.get('filename') and part['filename'].endswith('.xlsx'):
                att_id = part['body'].get('attachmentId') # get email ID of xlsx
                
                # download attachment 
                if att_id:
                    att = service.users().messages().attachments().get(
                        userId='me', messageId=msg['id'], id=att_id
                    ).execute()

                    #att['data'] the attachment as that long text string
                    data = base64.urlsafe_b64decode(att['data']) # base64 for Transport data convert back to raw when arrive
                    
                    # Builds the full file path
                    filepath = os.path.join(output_dir, part['filename'])                    
                    with open(filepath, 'wb') as f:
                        f.write(data)
                    print(f"Downloaded: {part['filename']}")
                    downloaded_files.append(filepath) # add to list 

        # Mark as read after downloading
        service.users().messages().modify(
            userId='me',
            id=msg['id'],
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"Marked as read: {msg['id']}")

    return downloaded_files

def gemini_get_price(product_name, description):
    """Ask Gemini to suggest a retail price based on product info"""

    prompt = f"""
    You are a pricing expert. Based on the product name and description below, 
    suggest a realistic retail price in USD. 
    Return ONLY a number with no currency symbol or text. Example: 29.99
    
    Product Name: {product_name}
    Description: {description}
    """
    response = model.generate_content(prompt)
    try:
        return float(response.text.strip())
    except:
        return 9.99  # fallback price


def gemini_map_columns(columns):
    """Ask Gemini to dynamically map supplier columns to eBay columns"""

    prompt = f"""
    You are a data mapping expert. Map these supplier Excel columns to eBay template columns.
    
    Supplier columns: {columns}
    
    eBay columns needed:
    - Product_ID
    - Product Name
    - Brand
    - Description
    - Quantity Available
    - Unit Cost
    - Custom Label
    
    Return ONLY a JSON object mapping eBay column → supplier column.
    If no match found, use null.
    Example: {{"Product_ID": "uniq_id", "Product Name": "product_name", "Brand": null}}
    Return only the JSON, no explanation, no markdown.
    """
    response = model.generate_content(prompt)
    import json
    try:
        # removes extra spaces, markdown code blocks
        # string -> dictionary 
        text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(text)
    except:
        return {}

def convert_to_ebay(filepath, output_dir='ebay_output'):
    """
    Takes the downloaded excel workbook and creates the ebay excel template
    """
   
    # create file ebay_output
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_excel(filepath)
    print(f"Loaded {len(df)} products from {filepath}")

    # Ask Gemini to map columns dynamically
    print("Asking Gemini to map columns...")

    # Sends the column names to Gemini and returns dict
    mapping = gemini_map_columns(list(df.columns))
    print(f"Gemini mapping: {mapping}")

    def get_col(ebay_col):
        supplier_col = mapping.get(ebay_col)
        if supplier_col and supplier_col in df.columns:
            return df[supplier_col]
        return None

    ebay_df = pd.DataFrame()
    ebay_df['Product_ID']         = get_col('Product_ID') if get_col('Product_ID') is not None else range(len(df))
    ebay_df['Product Name']       = get_col('Product Name')
    ebay_df['Brand']              = get_col('Brand')
    ebay_df['Description']        = get_col('Description')
    ebay_df['Quantity Available'] = get_col('Quantity Available') if get_col('Quantity Available') is not None else 1

    # Handle price — use Gemini if missing
    price_col = get_col('Unit Cost')
    if price_col is not None:
        prices = price_col.copy()
    else:
        prices = pd.Series([None] * len(df)) # if price column not available creates cloumn of none 

    print("Checking prices...")
    for i, row in df.iterrows():
        if pd.isna(prices.iloc[i]) or prices.iloc[i] == 0: # check for price if none or 0 
            # if null get product name and description 
            product_name = row.get(mapping.get('Product Name'), 'Unknown')
            description  = row.get(mapping.get('Description'), 'Unknown')

            print(f"  Row {i}: No price found, asking Gemini for '{product_name}'...")
            suggested = gemini_get_price(product_name, description) # Asks Gemini to suggest a price
            prices.iloc[i] = suggested
            print(f"  Gemini suggested: ${suggested}")

    ebay_df['Unit Cost']    = prices * MARKUP
    ebay_df['Custom Label'] = get_col('Custom Label') if get_col('Custom Label') is not None else ebay_df['Product_ID']

    # rename file
    filename = os.path.basename(filepath).replace('.xlsx', '_ebay.xlsx')

    # Builds the full save path and saves in file
    output_path = os.path.join(output_dir, filename)
    ebay_df.to_excel(output_path, index=False)
    print(f"eBay template saved: {output_path}")
