#!/bin/bash
# Generate .streamlit/secrets.toml from Railway environment variables at container startup

mkdir -p .streamlit

# Strip leading/trailing whitespace from env vars (guards against copy-paste spaces)
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID// /}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET// /}"
AUTH_REDIRECT_URI="${AUTH_REDIRECT_URI// /}"
AUTH_COOKIE_SECRET="${AUTH_COOKIE_SECRET// /}"

# Debug: confirm vars are set (values hidden)
echo "GOOGLE_CLIENT_ID   set: $([ -n "$GOOGLE_CLIENT_ID" ] && echo YES || echo NO)"
echo "GOOGLE_CLIENT_SECRET set: $([ -n "$GOOGLE_CLIENT_SECRET" ] && echo YES || echo NO)"
echo "AUTH_REDIRECT_URI  set: $([ -n "$AUTH_REDIRECT_URI" ] && echo YES || echo NO)"
echo "AUTH_COOKIE_SECRET set: $([ -n "$AUTH_COOKIE_SECRET" ] && echo YES || echo NO)"

# st.login() (no args) uses the "default" provider — keys must live in [auth] directly
cat > .streamlit/secrets.toml << EOF
[auth]
redirect_uri        = "${AUTH_REDIRECT_URI}"
cookie_secret       = "${AUTH_COOKIE_SECRET}"
client_id           = "${GOOGLE_CLIENT_ID}"
client_secret       = "${GOOGLE_CLIENT_SECRET}"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
EOF

echo "secrets.toml written."

exec python -m streamlit run app.py \
    --server.headless=true \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0
