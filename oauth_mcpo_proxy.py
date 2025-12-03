#!/usr/bin/env python3
"""
OAuth 2.0 Proxy for Friday Memory MCP Server

This proxy sits between Claude Desktop (which requires OAuth 2.0) and the existing
MCPO server (which uses bearer token authentication). It provides:

1. OAuth 2.0 Authorization Code flow
2. Token generation and validation
3. Request proxying to MCPO with bearer token authentication

Architecture:
    Claude Desktop → OAuth 2.0 → This Proxy → Bearer Token → MCPO → MCP Server
"""

import asyncio
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlencode, parse_qs

import aiohttp
import aiosqlite
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Form, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =========================================================================
# Configuration
# =========================================================================

# Load configuration from file
CONFIG_PATH = Path("/media/nate/Friday/Friday/oauth_config.json")
TOKEN_DB_PATH = Path("/media/nate/Friday/Friday/memory_data/oauth_tokens.db")

try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    logger.info(f"Loaded configuration from {CONFIG_PATH}")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise

# Load MCPO bearer token
try:
    with open(config['mcpo_bearer_token_file'], 'r') as f:
        MCPO_BEARER_TOKEN = f.read().strip()
    logger.info(f"Loaded MCPO bearer token from {config['mcpo_bearer_token_file']}")
except Exception as e:
    logger.error(f"Failed to load MCPO bearer token: {e}")
    raise

# OAuth configuration
CLIENTS = config.get('clients', {})
AUTHORIZATION_ENDPOINT = config['authorization_endpoint']
TOKEN_ENDPOINT = config['token_endpoint']
MCPO_BACKEND = config['mcpo_backend']
TOKEN_EXPIRY_SECONDS = config['token_expiry_seconds']
REFRESH_TOKEN_EXPIRY_SECONDS = config['refresh_token_expiry_seconds']

logger.info(f"Loaded {len(CLIENTS)} OAuth clients: {', '.join(CLIENTS.keys())}")

# JWT configuration - Automatic key rotation for security
SECRET_KEY_FILE = Path("/media/nate/Friday/Friday/keys/oauth_jwt_secret.txt")

# ALWAYS generate new key on restart for security
SECRET_KEY = secrets.token_urlsafe(32)
SECRET_KEY_FILE.write_text(SECRET_KEY)
SECRET_KEY_FILE.chmod(0o600)  # Secure permissions
logger.info(f"Generated NEW JWT SECRET_KEY for this session (saved to {SECRET_KEY_FILE})")
logger.info("Claude.ai will auto-reconnect with new tokens if needed")

ALGORITHM = "HS256"

# Initialize FastAPI app
app = FastAPI(
    title="Friday Memory OAuth Proxy",
    description="OAuth 2.0 proxy for Friday Memory MCP Server",
    version="1.0.0"
)

# Password/token hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token validation
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/oauth/token")

# ==========================================================================
# SQLite Database Functions
# ==========================================================================

async def init_token_database():
    """Initialize SQLite database for token storage"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        # Authorization codes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS authorization_codes (
                code TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                redirect_uri TEXT,
                state TEXT,
                scope TEXT,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)

        # Access tokens table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS access_tokens (
                token TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)

        # Refresh tokens table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)

        await db.commit()
    logger.info(f"Initialized token database at {TOKEN_DB_PATH}")


async def store_authorization_code(code: str, data: dict):
    """Store authorization code in database"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        await db.execute(
            """INSERT INTO authorization_codes
               (code, client_id, redirect_uri, state, scope, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, data['client_id'], data.get('redirect_uri'),
             data.get('state'), data.get('scope'),
             data['created_at'], data['expires_at'])
        )
        await db.commit()


async def get_authorization_code(code: str) -> Optional[dict]:
    """Retrieve authorization code from database"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM authorization_codes WHERE code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def delete_authorization_code(code: str):
    """Delete authorization code from database"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        await db.execute("DELETE FROM authorization_codes WHERE code = ?", (code,))
        await db.commit()


async def store_access_token(token: str, data: dict):
    """Store access token in database"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        # Extract expiry from JWT if not provided
        expires_at = data.get('expires_at', time.time() + TOKEN_EXPIRY_SECONDS)
        await db.execute(
            """INSERT INTO access_tokens (token, client_id, created_at, expires_at)
               VALUES (?, ?, ?, ?)""",
            (token, data['client_id'], data['created_at'], expires_at)
        )
        await db.commit()


async def get_access_token(token: str) -> Optional[dict]:
    """Retrieve access token from database"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM access_tokens WHERE token = ?", (token,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def store_refresh_token(token: str, data: dict):
    """Store refresh token in database"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        await db.execute(
            """INSERT INTO refresh_tokens (token, client_id, created_at, expires_at)
               VALUES (?, ?, ?, ?)""",
            (token, data['client_id'], data['created_at'], data['expires_at'])
        )
        await db.commit()


async def get_refresh_token(token: str) -> Optional[dict]:
    """Retrieve refresh token from database"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM refresh_tokens WHERE token = ?", (token,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def delete_refresh_token(token: str):
    """Delete refresh token from database"""
    async with aiosqlite.connect(TOKEN_DB_PATH) as db:
        await db.execute("DELETE FROM refresh_tokens WHERE token = ?", (token,))
        await db.commit()


# ==========================================================================
# Helper Functions
# ==========================================================================

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(seconds=TOKEN_EXPIRY_SECONDS)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token() -> str:
    """Create a random refresh token"""
    return secrets.token_urlsafe(32)


def verify_access_token(token: str) -> Optional[dict]:
    """Verify and decode an access token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None


# ==========================================================================
# OAuth 2.0 Endpoints
# ==========================================================================

@app.get("/oauth/authorize", response_class=HTMLResponse)
async def authorize(
    client_id: str,
    redirect_uri: Optional[str] = None,
    response_type: str = "code",
    state: Optional[str] = None,
    scope: Optional[str] = None
):
    """
    OAuth 2.0 Authorization Endpoint

    Displays a consent page and generates an authorization code.
    In a real implementation, this would authenticate the user first.
    """
    # Validate client_id
    client_key = None
    for key, client in CLIENTS.items():
        if client['client_id'] == client_id:
            client_key = key
            break
    
    if not client_key:
        raise HTTPException(status_code=400, detail=f"Invalid client_id")

    # Validate response_type
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Unsupported response_type")

    # Generate authorization code
    auth_code = secrets.token_urlsafe(32)

    # Store authorization code with metadata
    await store_authorization_code(auth_code, {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": scope,
        "created_at": time.time(),
        "expires_at": time.time() + 600  # 10 minute expiry
    })

    logger.info(f"Generated authorization code for client {client_id}")

    # Auto-approve for simplicity (in production, show a consent form)
    # Build redirect URI with code
    if redirect_uri:
        params = {"code": auth_code}
        if state:
            params["state"] = state
        redirect_url = f"{redirect_uri}?{urlencode(params)}"
        return RedirectResponse(url=redirect_url)
    else:
        # If no redirect_uri, show the code directly
        return HTMLResponse(f"""
        <html>
            <head><title>Authorization Code</title></head>
            <body>
                <h1>Authorization Successful</h1>
                <p>Your authorization code:</p>
                <code>{auth_code}</code>
                <p>This code expires in 10 minutes.</p>
            </body>
        </html>
        """)


@app.post("/oauth/token")
async def token(
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None)
):
    """
    OAuth 2.0 Token Endpoint

    Exchanges authorization code for access token,
    or exchanges refresh token for new access token.
    """

    # Validate client credentials
    client_key = None
    client_config = None
    for key, client in CLIENTS.items():
        if client['client_id'] == client_id:
            client_key = key
            client_config = client
            break
    
    if not client_config or client_secret != client_config['client_secret']:
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    if grant_type == "authorization_code":
        # Exchange authorization code for tokens
        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")

        # Validate authorization code
        auth_data = await get_authorization_code(code)
        if not auth_data:
            raise HTTPException(status_code=400, detail="Invalid authorization code")

        # Check if code is expired
        if time.time() > auth_data['expires_at']:
            await delete_authorization_code(code)
            raise HTTPException(status_code=400, detail="Authorization code expired")

        # Delete code after use (single-use)
        await delete_authorization_code(code)

        # Generate access token
        access_token_data = {
            "sub": "friday-memory-user",
            "client_id": client_id,
            "scope": auth_data.get("scope", "")
        }
        access_token = create_access_token(access_token_data)

        # Generate refresh token
        refresh_token_value = create_refresh_token()
        await store_refresh_token(refresh_token_value, {
            "client_id": client_id,
            "created_at": time.time(),
            "expires_at": time.time() + REFRESH_TOKEN_EXPIRY_SECONDS
        })

        # Store access token metadata
        await store_access_token(access_token, {
            "client_id": client_id,
            "created_at": time.time()
        })

        logger.info(f"Issued access token for client {client_id}")

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": TOKEN_EXPIRY_SECONDS,
            "refresh_token": refresh_token_value
        })

    elif grant_type == "refresh_token":
        # Exchange refresh token for new access token
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Missing refresh token")

        # Validate refresh token
        refresh_data = await get_refresh_token(refresh_token)
        if not refresh_data:
            raise HTTPException(status_code=400, detail="Invalid refresh token")

        # Check if refresh token is expired
        if time.time() > refresh_data['expires_at']:
            await delete_refresh_token(refresh_token)
            raise HTTPException(status_code=400, detail="Refresh token expired")

        # Generate new access token
        access_token_data = {
            "sub": "friday-memory-user",
            "client_id": client_id,
            "scope": ""
        }
        access_token = create_access_token(access_token_data)

        # Store access token metadata
        await store_access_token(access_token, {
            "client_id": client_id,
            "created_at": time.time()
        })

        logger.info(f"Issued new access token via refresh token for client {client_id}")

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": TOKEN_EXPIRY_SECONDS
        })

    else:
        raise HTTPException(status_code=400, detail="Unsupported grant_type")


@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)"""
    return JSONResponse({
        "issuer": "https://fridayonline.bounceme.net",
        "authorization_endpoint": AUTHORIZATION_ENDPOINT,
        "token_endpoint": TOKEN_ENDPOINT,
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "code_challenge_methods_supported": ["S256"]  # PKCE support
    })


# ==========================================================================
# MCP Proxy Endpoints
# ==========================================================================

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency to validate access token"""
    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ==========================================================================
# OpenID Configuration Endpoint (for MCP protocol discovery)
# ==========================================================================

@app.get("/.well-known/openid-configuration")
async def openid_configuration():
    """
    OpenID Connect Discovery Endpoint
    
    Claude.ai looks for this endpoint to discover OAuth endpoints.
    This follows the OpenID Connect Discovery standard.
    """
    return {
        "issuer": "https://fridayonline.bounceme.net",
        "authorization_endpoint": "https://fridayonline.bounceme.net/oauth/authorize",
        "token_endpoint": "https://fridayonline.bounceme.net/oauth/token",
        "userinfo_endpoint": "https://fridayonline.bounceme.net/oauth/userinfo",
        "jwks_uri": "https://fridayonline.bounceme.net/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "response_modes_supported": ["query"],
        "scopes_supported": ["openid", "profile", "email"],
        "claims_supported": ["sub", "aud", "exp", "iat"],
        "request_object_signing_alg_values_supported": ["none"]
    }


@app.get("/.well-known/jwks.json")
async def jwks():
    """
    JSON Web Key Set Endpoint
    
    Provides public keys for JWT validation.
    In this implementation, we use HS256 (symmetric) so this is minimal.
    """
    return {
        "keys": [
            {
                "kty": "oct",
                "kid": "friday-oauth-key",
                "use": "sig",
                "alg": "HS256"
            }
        ]
    }


@app.get("/oauth/userinfo")
async def userinfo(current_user: dict = Depends(get_current_user)):
    """
    OAuth 2.0 UserInfo Endpoint
    
    Returns information about the authenticated user.
    Requires a valid access token.
    """
    return {
        "sub": current_user.get("sub", "friday-memory-user"),
        "client_id": current_user.get("client_id", "unknown"),
        "scope": current_user.get("scope", ""),
        "aud": "friday-memory"
    }


@app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_root(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Proxy root path requests to MCPO backend

    Claude.ai strips the path from the server URL and hits the root path.
    This handler catches those requests and proxies them to MCPO.
    """
    target_url = MCPO_BACKEND
    body = await request.body()

    headers = dict(request.headers)
    headers.pop('authorization', None)
    headers.pop('Authorization', None)
    headers['Authorization'] = f'Bearer {MCPO_BEARER_TOKEN}'
    headers.pop('host', None)
    headers.pop('Host', None)

    logger.info(f"Proxying {request.method} to {target_url} (root path)")
    if body:
        try:
            body_preview = body[:200].decode('utf-8') if isinstance(body, bytes) else str(body)[:200]
            logger.debug(f"Request body preview: {body_preview}")
        except:
            logger.debug(f"Request body (binary): {len(body)} bytes")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body,
                params=request.query_params
            ) as resp:
                content = await resp.read()
                response_headers = dict(resp.headers)
                response_headers.pop('transfer-encoding', None)
                response_headers.pop('Transfer-Encoding', None)
                
                logger.info(f"MCPO responded with {resp.status} to {request.method} /")
                if resp.status != 200 and content:
                    try:
                        error_preview = content[:200].decode('utf-8') if isinstance(content, bytes) else str(content)[:200]
                        logger.debug(f"MCPO response: {error_preview}")
                    except:
                        pass
                
                return Response(
                    content=content,
                    status_code=resp.status,
                    headers=response_headers
                )
    except Exception as e:
        logger.error(f"Error proxying to MCPO: {e}")
        raise HTTPException(status_code=502, detail=f"Error: {str(e)}")


@app.api_route("/*", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_wildcard(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Proxy wildcard path requests to MCPO backend

    Claude.ai also hits the wildcard path /* (URL-encoded as /%2A).
    This handler catches those requests and proxies them to MCPO.
    """
    target_url = MCPO_BACKEND
    body = await request.body()

    headers = dict(request.headers)
    headers.pop('authorization', None)
    headers.pop('Authorization', None)
    headers['Authorization'] = f'Bearer {MCPO_BEARER_TOKEN}'
    headers.pop('host', None)
    headers.pop('Host', None)

    logger.info(f"Proxying {request.method} to {target_url} (wildcard path)")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body,
                params=request.query_params
            ) as resp:
                content = await resp.read()
                response_headers = dict(resp.headers)
                response_headers.pop('transfer-encoding', None)
                response_headers.pop('Transfer-Encoding', None)
                return Response(
                    content=content,
                    status_code=resp.status,
                    headers=response_headers
                )
    except Exception as e:
        logger.error(f"Error proxying to MCPO: {e}")
        raise HTTPException(status_code=502, detail=f"Error: {str(e)}")


@app.api_route("/mcp", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_mcp_root(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Proxy MCP root endpoint to MCPO backend

    This handles requests to /mcp (without additional path)
    which is the base endpoint for MCP protocol initialization.
    """
    target_url = MCPO_BACKEND

    # Get request body
    body = await request.body()

    # Prepare headers
    headers = dict(request.headers)
    headers.pop('authorization', None)
    headers.pop('Authorization', None)
    headers['Authorization'] = f'Bearer {MCPO_BEARER_TOKEN}'
    headers.pop('host', None)
    headers.pop('Host', None)

    logger.info(f"Proxying {request.method} request to {target_url} (MCP root)")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body,
                params=request.query_params
            ) as resp:
                content = await resp.read()
                response_headers = dict(resp.headers)
                response_headers.pop('transfer-encoding', None)
                response_headers.pop('Transfer-Encoding', None)

                return Response(
                    content=content,
                    status_code=resp.status,
                    headers=response_headers
                )
    except Exception as e:
        logger.error(f"Error proxying request to MCPO: {e}")
        raise HTTPException(status_code=502, detail=f"Error communicating with backend: {str(e)}")


@app.api_route("/mcp/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_mcpo(
    request: Request,
    path: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Proxy authenticated requests to MCPO backend

    Validates OAuth access token, then forwards the request to MCPO
    with the bearer token added.
    """
    # Build target URL - handle empty path
    if path:
        target_url = f"{MCPO_BACKEND}/{path}"
    else:
        target_url = MCPO_BACKEND

    # Get request body
    body = await request.body()

    # Prepare headers for MCPO request
    headers = dict(request.headers)

    # Remove the OAuth Authorization header
    headers.pop('authorization', None)
    headers.pop('Authorization', None)

    # Add MCPO bearer token
    headers['Authorization'] = f'Bearer {MCPO_BEARER_TOKEN}'

    # Remove host header (will be set by aiohttp)
    headers.pop('host', None)
    headers.pop('Host', None)

    logger.info(f"Proxying {request.method} request to {target_url}")

    try:
        # Forward request to MCPO
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body,
                params=request.query_params
            ) as resp:
                # Get response content
                content = await resp.read()

                # Build response headers
                response_headers = dict(resp.headers)

                # Remove headers that shouldn't be forwarded
                response_headers.pop('transfer-encoding', None)
                response_headers.pop('Transfer-Encoding', None)

                # Return proxied response
                return Response(
                    content=content,
                    status_code=resp.status,
                    headers=response_headers
                )

    except Exception as e:
        logger.error(f"Error proxying request to MCPO: {e}")
        raise HTTPException(status_code=502, detail=f"Error communicating with backend: {str(e)}")


# ==========================================================================
# Health Check Endpoint
# ==========================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "oauth-mcpo-proxy",
        "timestamp": datetime.utcnow().isoformat()
    })


# ==========================================================================
# Cleanup Task
# ==========================================================================

async def cleanup_expired_tokens():
    """Background task to clean up expired tokens and codes from database"""
    while True:
        try:
            current_time = time.time()

            async with aiosqlite.connect(TOKEN_DB_PATH) as db:
                # Clean up expired authorization codes
                await db.execute(
                    "DELETE FROM authorization_codes WHERE expires_at < ?",
                    (current_time,)
                )

                # Clean up expired access tokens
                await db.execute(
                    "DELETE FROM access_tokens WHERE expires_at < ?",
                    (current_time,)
                )

                # Clean up expired refresh tokens
                await db.execute(
                    "DELETE FROM refresh_tokens WHERE expires_at < ?",
                    (current_time,)
                )

                await db.commit()

            logger.info("Cleaned up expired tokens from database")

        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")

        # Run cleanup every 5 minutes
        await asyncio.sleep(300)


@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    await init_token_database()
    asyncio.create_task(cleanup_expired_tokens())
    logger.info("OAuth MCPO Proxy started successfully")


# ==========================================================================
# Main Entry Point
# ==========================================================================

if __name__ == "__main__":
    logger.info("Starting OAuth MCPO Proxy server on port 8888")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        log_level="info"
    )
