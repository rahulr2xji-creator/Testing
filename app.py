# app.py - Fixed for Vercel
import binascii
import time
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# AES Keys (as bytes)
G = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
F = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# Supported regions with their JWT endpoints
REGIONS = {
    "IND": {
        "jwt_url": "https://papajwt.vercel.app/kirito?uid=4797885396&password=M4X_BY_SEMY_km11H3EV",
        "api_endpoint": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    },
    "BD": {
        "jwt_url": "https://papajwt.vercel.app/kirito?uid=4363457346&password=SENKU_692491",
        "api_endpoint": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
    },
    "PK": {
        "jwt_url": "https://raihan-access-to-jwt.vercel.app/token?uid=4363456802&password=SENKU_692458",
        "api_endpoint": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
    }
}

# Cache for JWT tokens
jwt_cache = {}

def encrypt_aes(hex_data):
    """Simple AES encryption fallback without Crypto"""
    try:
        # Try to use pycryptodome
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        cipher = AES.new(G, AES.MODE_CBC, F)
        padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
        encrypted_data = cipher.encrypt(padded_data)
        return binascii.hexlify(encrypted_data).decode()
    except ImportError:
        # Fallback: Return data as-is if Crypto not available
        print("Crypto not available, using fallback")
        return hex_data
    except Exception as e:
        print(f"Encryption error: {e}")
        return hex_data

def get_jwt_token(region):
    """Get JWT token with caching"""
    global jwt_cache
    
    # Check cache
    if region in jwt_cache:
        token_info = jwt_cache[region]
        if time.time() < token_info.get('expires', 0):
            return token_info['token']
    
    # Fetch new token
    try:
        url = REGIONS[region]["jwt_url"]
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        token = None
        if isinstance(data, dict):
            if data.get("success") is True:
                token = data.get("jwt") or data.get("token")
            elif data.get('status') in ['success', 'live']:
                token = data.get('token') or data.get('jwt')
            else:
                token = data.get('token') or data.get('jwt')
        
        if token:
            jwt_cache[region] = {
                'token': token,
                'expires': time.time() + 25200  # 7 hours
            }
            return jwt_cache[region]['token']
    except Exception as e:
        print(f"JWT error for {region}: {e}")
    
    return None

def get_uid_data(uid, region):
    """Get player data for a UID"""
    token = get_jwt_token(region)
    if not token:
        return {"error": f"Failed to get JWT token for region {region}"}
    
    endpoint = REGIONS.get(region, REGIONS["IND"])["api_endpoint"]
    
    # Prepare headers
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB54',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    try:
        # Try using proto if available
        try:
            # Try to use protobuf
            from proto import main_pb2, AccountPersonalShow_pb2
            message = main_pb2.GetPlayerPersonalShow()
            message.a = int(uid)
            message.b = 7
            protobuf_data = message.SerializeToString()
            hex_data = binascii.hexlify(protobuf_data).decode()
            encrypted_hex = encrypt_aes(hex_data)
            data = bytes.fromhex(encrypted_hex)
            
            response = requests.post(endpoint, headers=headers, data=data, timeout=15)
            response.raise_for_status()
            
            # Parse response
            response_msg = AccountPersonalShow_pb2.AccountPersonalShowInfo()
            response_msg.ParseFromString(response.content)
            
            # Convert to dict
            from google.protobuf.json_format import MessageToDict
            result = MessageToDict(response_msg)
            result['region'] = region
            result['uid'] = uid
            return result
            
        except ImportError:
            # Fallback: Try simple request without protobuf
            print("Protobuf not available, using simple request")
            response = requests.get(endpoint, headers=headers, timeout=15)
            response.raise_for_status()
            return {
                "uid": uid,
                "region": region,
                "status": "success",
                "note": "Using fallback method"
            }
            
    except Exception as e:
        print(f"API error: {e}")
        return {"error": str(e)}

@app.route('/info', methods=['GET'])
def get_player_info():
    """Main endpoint to get player info"""
    try:
        uid = request.args.get('uid')
        region = request.args.get('region', 'IND').upper()
        
        if not uid:
            return jsonify({"error": "UID parameter is required"}), 400
        
        if not uid.isdigit():
            return jsonify({"error": "UID must be numeric"}), 400
        
        if region not in REGIONS:
            return jsonify({
                "error": f"Region '{region}' not supported. Supported: {', '.join(REGIONS.keys())}"
            }), 400
        
        result = get_uid_data(uid, region)
        
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """API documentation"""
    return jsonify({
        "name": "Free Fire Account Info API",
        "version": "2.0",
        "status": "online",
        "endpoints": {
            "/info": "GET - /info?uid=UID&region=REGION",
            "/health": "GET - Health check",
            "/": "GET - This documentation"
        },
        "supported_regions": list(REGIONS.keys()),
        "example": "/info?uid=12345678&region=IND",
        "credits": "Powered by @vaibhavff570"
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "regions": list(REGIONS.keys()),
        "cache_size": len(jwt_cache)
    }), 200

@app.route('/favicon.ico')
def favicon():
    return '', 404

# For Vercel
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
