# Pipedrive Migration Tool - Deployment Guide

## Security Configuration

### Environment Variables

Before deploying, set these environment variables:

**For CLI Mode** (optional - only if using `--id` flag):
```bash
export MAKE_API_TOKEN="your-make-api-token"
```

**For Default Connection** (optional):
```bash
export PIPEDRIVE_OAUTH_CONN_ID="4683394"
export PIPEDRIVE_OAUTH_CONN_LABEL="My Pipedrive OAuth Connection"
```

### Local Development

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your credentials in `.env`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run locally:
   ```bash
   python app.py
   ```

---

## Deployment Options

### Google Cloud Run (Recommended)

1. **Set environment variables** in Google Cloud:
   ```bash
   gcloud run deploy pipedrive-migrator \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 512Mi \
     --timeout 60 \
     --set-env-vars PIPEDRIVE_OAUTH_CONN_ID=4683394
   ```

2. **Or set via Console**:
   - Go to Cloud Run → Your Service → Edit & Deploy New Revision
   - Add environment variables under "Variables & Secrets"

### Authentication Options

**Option 1: Keep Public** (current setup)
- Anyone with the URL can use it
- Good for internal tools with obscure URLs

**Option 2: Add Cloud Run Authentication**
```bash
# Remove --allow-unauthenticated and require Google account login
gcloud run deploy pipedrive-migrator \
  --source . \
  --platform managed \
  --region us-central1
```

**Option 3: Add Basic Auth** (simple password):

Add to `app.py`:
```python
from functools import wraps
from flask import request, Response

def check_auth(username, password):
    return username == os.getenv('AUTH_USER') and password == os.getenv('AUTH_PASSWORD')

def authenticate():
    return Response('Authentication required', 401, 
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# Add @requires_auth to your routes
@app.route('/')
@requires_auth
def index():
    ...
```

Then set environment variables:
```bash
export AUTH_USER="admin"
export AUTH_PASSWORD="secure-password-here"
```

---

## Production Checklist

- [ ] Remove all hardcoded credentials from code
- [ ] Set environment variables in deployment platform
- [ ] Add `.env` to `.gitignore`
- [ ] Decide on authentication strategy
- [ ] Test with production connection IDs
- [ ] Set up monitoring/logging
- [ ] Configure custom domain (optional)
- [ ] Set up HTTPS (automatic on Cloud Run)

---

## Monitoring

### Cloud Run Logs
```bash
gcloud run services logs read pipedrive-migrator --limit 50
```

### Health Check
Access `/api/health` to verify service is running.

---

## Updating Deployment

```bash
# Google Cloud Run auto-detects changes
gcloud run deploy pipedrive-migrator --source .
```
