#!/bin/bash
# Generate .streamlit/secrets.toml from Railway environment variables at container startup

mkdir -p .streamlit

cat > .streamlit/secrets.toml << EOF
[auth]
redirect_uri = "${AUTH_REDIRECT_URI}"
cookie_secret = "${AUTH_COOKIE_SECRET}"

[auth.google]
client_id     = "${GOOGLE_CLIENT_ID}"
client_secret = "${GOOGLE_CLIENT_SECRET}"
EOF

echo "secrets.toml written."

exec python -m streamlit run app.py \
    --server.headless=true \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0
