# ------------------------------------------------------------
# Free Fire Account Info API — Improved Version
# Based on: @vaibhavff570 & @SENKU_CODEX
# JOIN : @vaibhavapix, @vaibhavapisx
# Purpose : Fetch Free Fire profile details using UID (JWT + AES)
# Endpoint: /info?uid=<PLAYER_UID>&region=<REGION>
# ------------------------------------------------------------

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
import asyncio
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
from proto import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2
from google.protobuf import json_format
from google.protobuf.json_format import MessageToDict
import threading
import time
from collections import defaultdict
from functools import wraps

app = Flask(__name__)
CORS(app)

# Global JWT token storage
jwt_tokens = defaultdict(dict)
jwt_lock = threading.Lock()

# AES Keys
G = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
F = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# Supported regions with their JWT endpoints
REGIONS = {
    "IND": {
        "jwt_url": "https://papajwt.vercel.app/kirito?uid=4797885396&password=M4X_BY_SEMY_km11H3EV",
        "api_endpoint": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    },
    "BD": {
        "jwt_url": "https://raihan-access-to-jwt.vercel.app/token?uid=4363457346&password=SENKU_692491",
        "api_endpoint": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
    },
    "PK": {
        "jwt_url": "https://raihan-access-to-jwt.vercel.app/token?uid=4363456802&password=SENKU_692458",
        "api_endpoint": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
    },
    "US": {
        "jwt_url": "https://raihan-access-to-jwt.vercel.app/token?uid=4363456802&password=SENKU_692458",
        "api_endpoint": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
    },
    "BR": {
        "jwt_url": "https://raihan-access-to-jwt.vercel.app/token?uid=4363456802&password=SENKU_692458",
        "api_endpoint": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
    }
}

def extract_token_from_response(data):
    """Extract JWT token from API response."""
    if not isinstance(data, dict):
        return None
    
    if data.get("success") is True:
        if "jwt" in data:
            return data["jwt"]
        if "token" in data:
            return data["token"]
    
    if data.get('status') in ['success', 'live']:
        return data.get('token') or data.get('jwt')
    
    if 'token' in data:
        return data['token']
    if 'jwt' in data:
        return data['jwt']
    
    return None

def get_jwt_token_sync(region):
    """Fetch JWT token synchronously for a region."""
    global jwt_tokens
    
    if region not in REGIONS:
        region = "IND"
    
    with jwt_lock:
        try:
            url = REGIONS[region]["jwt_url"]
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            token = extract_token_from_response(data)
            
            if token:
                jwt_tokens[region] = {
                    'token': f"Bearer {token}",
                    'expires': time.time() + 25200  # 7 hours
                }
                print(f"[JWT] Token for {region} updated successfully")
                return jwt_tokens[region]['token']
            else:
                print(f"[JWT] Failed to extract token for {region}")
                return None
        except Exception as e:
            print(f"[JWT] Error fetching token for {region}: {e}")
            return None

def ensure_jwt_token_sync(region):
    """Ensure JWT token is available and valid."""
    global jwt_tokens
    
    if region not in REGIONS:
        region = "IND"
    
    token_info = jwt_tokens.get(region)
    
    # Check if token exists and is not expired
    if token_info and time.time() < token_info.get('expires', 0):
        return token_info['token']
    
    # Fetch new token
    return get_jwt_token_sync(region)

def jwt_token_updater(region):
    """Background thread to refresh JWT tokens."""
    while True:
        get_jwt_token_sync(region)
        time.sleep(300)  # Refresh every 5 minutes

def encrypt_aes(hex_data):
    """Encrypt data using AES-CBC."""
    key = G
    iv = F
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

def call_api(encrypted_hex, region):
    """Make API call to Free Fire servers."""
    token = ensure_jwt_token_sync(region)
    if not token:
        raise Exception(f"Failed to get JWT token for region {region}")
    
    endpoint = REGIONS.get(region, REGIONS["IND"])["api_endpoint"]
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': token,
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB54',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    try:
        data = bytes.fromhex(encrypted_hex)
        response = requests.post(endpoint, headers=headers, data=data, timeout=15)
        response.raise_for_status()
        return response.content.hex()
    except requests.exceptions.RequestException as e:
        print(f"[API] Request to {endpoint} failed: {e}")
        raise

@app.route('/info', methods=['GET'])
def get_player_info():
    """Main endpoint to get player info."""
    try:
        uid = request.args.get('uid')
        region = request.args.get('region', 'IND').upper()
        
        if not uid:
            return jsonify({"error": "UID parameter is required"}), 400
        
        # Validate UID
        if not uid.isdigit() or len(uid) < 8:
            return jsonify({"error": "Invalid UID format. Must be numeric and at least 8 digits."}), 400
        
        # Check if region is supported
        if region not in REGIONS:
            return jsonify({
                "error": f"Region '{region}' not supported. Supported regions: {', '.join(REGIONS.keys())}"
            }), 400
        
        # Start background JWT updater for this region
        threading.Thread(target=jwt_token_updater, args=(region,), daemon=True).start()
        
        # Generate protobuf request
        message = main_pb2.GetPlayerPersonalShow()
        message.a = int(uid)  # UID
        message.b = 7  # Unknown parameter
        protobuf_data = message.SerializeToString()
        hex_data = binascii.hexlify(protobuf_data).decode()
        
        # Encrypt
        encrypted_hex = encrypt_aes(hex_data)
        
        # Call API
        api_response = call_api(encrypted_hex, region)
        if not api_response:
            return jsonify({"error": "Empty response from API"}), 400
        
        # Parse response
        response_msg = AccountPersonalShow_pb2.AccountPersonalShowInfo()
        response_msg.ParseFromString(bytes.fromhex(api_response))
        result = MessageToDict(response_msg)
        
        # Add metadata
        result['region'] = region
        result['supported_regions'] = list(REGIONS.keys())
        result['credits'] = "Powered by @vaibhavff570 & @SENKU_CODEX"
        
        return jsonify(result)
    
    except ValueError as e:
        return jsonify({"error": f"Invalid data format: {str(e)}"}), 400
    except Exception as e:
        print(f"[ERROR] Processing request: {e}")
        return jsonify({"error": f"Failed to process request: {str(e)}"}), 500

@app.route('/batch', methods=['POST'])
def batch_player_info():
    """Get info for multiple UIDs at once."""
    try:
        data = request.get_json()
        if not data or 'uids' not in data:
            return jsonify({"error": "Please provide 'uids' array in request body"}), 400
        
        uids = data.get('uids', [])
        region = data.get('region', 'IND').upper()
        
        if not isinstance(uids, list):
            return jsonify({"error": "'uids' must be an array"}), 400
        
        if len(uids) > 50:
            return jsonify({"error": "Maximum 50 UIDs per batch request"}), 400
        
        results = []
        for uid in uids:
            try:
                # Reuse the single UID logic
                message = main_pb2.GetPlayerPersonalShow()
                message.a = int(uid)
                message.b = 7
                protobuf_data = message.SerializeToString()
                hex_data = binascii.hexlify(protobuf_data).decode()
                encrypted_hex = encrypt_aes(hex_data)
                api_response = call_api(encrypted_hex, region)
                
                if api_response:
                    response_msg = AccountPersonalShow_pb2.AccountPersonalShowInfo()
                    response_msg.ParseFromString(bytes.fromhex(api_response))
                    result = MessageToDict(response_msg)
                    result['uid'] = uid
                    results.append(result)
                else:
                    results.append({"uid": uid, "error": "Empty response"})
            except Exception as e:
                results.append({"uid": uid, "error": str(e)})
        
        return jsonify({
            "total": len(results),
            "region": region,
            "results": results
        })
    
    except Exception as e:
        return jsonify({"error": f"Batch request failed: {str(e)}"}), 500

@app.route('/refresh_tokens', methods=['POST'])
def refresh_tokens():
    """Manually refresh JWT tokens for all regions."""
    try:
        results = {}
        for region in REGIONS:
            token = get_jwt_token_sync(region)
            results[region] = "Success" if token else "Failed"
        
        return jsonify({
            "message": "Token refresh completed",
            "results": results
        }), 200
    except Exception as e:
        return jsonify({"error": f"Token refresh failed: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "regions": list(REGIONS.keys()),
        "jwt_status": {region: "valid" if jwt_tokens.get(region) else "invalid" for region in REGIONS}
    }), 200

@app.route('/')
def index():
    """API documentation."""
    return jsonify({
        "name": "Free Fire Account Info API",
        "version": "2.0",
        "description": "Fetch Free Fire player profile information",
        "endpoints": {
            "/info": {
                "method": "GET",
                "params": {
                    "uid": "Player UID (required)",
                    "region": "Region (optional, default: IND)"
                },
                "example": "/info?uid=12345678&region=IND"
            },
            "/batch": {
                "method": "POST",
                "body": {
                    "uids": ["Array of UIDs"],
                    "region": "Region (optional)"
                },
                "example": '{"uids": ["12345678", "87654321"], "region": "IND"}'
            },
            "/refresh_tokens": {
                "method": "POST",
                "description": "Manually refresh JWT tokens"
            },
            "/health": {
                "method": "GET",
                "description": "Health check endpoint"
            }
        },
        "supported_regions": list(REGIONS.keys()),
        "credits": "Powered by @vaibhavff570 & @SENKU_CODEX"
    })

if __name__ == "__main__":
    # Initialize tokens for all regions on startup
    print("Initializing JWT tokens...")
    for region in REGIONS:
        get_jwt_token_sync(region)
    
    print(f"Starting server on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)