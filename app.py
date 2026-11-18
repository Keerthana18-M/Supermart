import re # Move import to top for performance
from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

# --- MOCK DATABASE ---
# Keys are the GTIN-14 (Global Trade Item Number)
PRODUCT_DB = {
    "08901063158351": {"name": "Britannia Good Day Chunkies", "price": 2.50},
    "08901234567890": {"name": "Amul Butter 500g", "price": 5.00},
    "08906065450175": {"name": "Gone Mad Choco", "price": 10.00}
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_scan', methods=['POST'])
def process_scan():
    data = request.json
    raw_text = data.get('code', '')
    
    print(f"Scanned: {raw_text}") # Debugging

    # 1. Parse GS1 Data
    parsed = parse_gs1(raw_text)
    
    if not parsed['gtin']:
        return jsonify({"status": "error", "message": "Could not find GTIN (01) in barcode"})
    
    # 2. Lookup Product
    product = PRODUCT_DB.get(parsed['gtin'])
    if not product:
        return jsonify({"status": "error", "message": f"Unknown Product (GTIN: {parsed['gtin']})"})
    
    # 3. Check Expiry
    if parsed['expiry'] and is_expired(parsed['expiry']):
        formatted_date = format_date(parsed['expiry'])
        return jsonify({
            "status": "error", 
            "message": f"STOP! Product Expired on {formatted_date}"
        })
    
    # 4. Success Response
    return jsonify({
        "status": "success",
        "product": {
            "name": product['name'],
            "price": product['price'],
            "batch": parsed['batch'],
            "expiry": format_date(parsed['expiry']),
            "gtin": parsed['gtin']
        }
    })

# --- HELPER FUNCTIONS ---

def parse_gs1(text):
    """
    Parses a GS1-128 string. 
    Supported AIs: 01 (GTIN), 17 (Expiry), 10 (Batch).
    """
    # Remove brackets if the scanner adds them: (01)1234 -> 011234
    clean_text = text.replace('(', '').replace(')', '')
    
    result = {'gtin': None, 'expiry': None, 'batch': 'N/A'}
    
    # 1. GTIN (AI: 01) - Fixed 14 digits
    gtin_match = re.search(r'01(\d{14})', clean_text)
    if gtin_match: 
        result['gtin'] = gtin_match.group(1)
        
    # 2. Expiry (AI: 17) - Fixed 6 digits (YYMMDD)
    exp_match = re.search(r'17(\d{6})', clean_text)
    if exp_match: 
        result['expiry'] = exp_match.group(1)
        
    # 3. Batch (AI: 10) - Variable Length (Max 20 chars)
    # WARNING: In raw GS1, variable fields are ended by a special character (FNC1).
    # Since simple QR scanners don't send FNC1, we assume Batch is 
    # either at the END of the string or followed by a known AI like 17.
    
    # This regex looks for '10' followed by alphanumerics
    batch_match = re.search(r'10([A-Za-z0-9]+)', clean_text)
    
    if batch_match:
        # If the batch match accidentally swallowed the Expiry (e.g. Batch17250101)
        # we need to be careful. For this prototype, we assume
        # you will generate QR codes with Batch at the END.
        result['batch'] = batch_match.group(1)
        
    return result

def is_expired(yymmdd):
    if not yymmdd: return False
    try:
        # 251231 -> 2025-12-31
        exp_date = datetime.strptime(yymmdd, "%y%m%d")
        return datetime.now() > exp_date
    except ValueError:
        return False

def format_date(yymmdd):
    if not yymmdd: return "N/A"
    try:
        dt = datetime.strptime(yymmdd, "%y%m%d")
        return dt.strftime("%Y-%m-%d")
    except:
        return yymmdd

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)