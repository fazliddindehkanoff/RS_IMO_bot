#!/bin/bash
# First-time SSL setup for rs.nomean.uz using Let's Encrypt.
# Usage: CERTBOT_EMAIL=your@email.com ./scripts/init-letsencrypt.sh
# Or: ./scripts/init-letsencrypt.sh your@email.com

set -e

DOMAIN="${CERTBOT_DOMAIN:-rs.nomean.uz}"
EMAIL="${CERTBOT_EMAIL:-$1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERTBOT_CONF="$PROJECT_DIR/certbot/conf"
CERTBOT_WWW="$PROJECT_DIR/certbot/www"
LIVE_DIR="$CERTBOT_CONF/live/$DOMAIN"

if [ -z "$EMAIL" ]; then
  echo "Error: Certbot requires an email for Let's Encrypt."
  echo "Usage: CERTBOT_EMAIL=your@email.com $0"
  echo "   Or: $0 your@email.com"
  exit 1
fi

cd "$PROJECT_DIR"

# Create dummy certs so nginx can start with SSL block
if [ ! -f "$LIVE_DIR/fullchain.pem" ]; then
  echo "Creating dummy certificates for $DOMAIN so nginx can start..."
  mkdir -p "$LIVE_DIR" "$CERTBOT_WWW/.well-known/acme-challenge"
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$LIVE_DIR/privkey.pem" \
    -out "$LIVE_DIR/fullchain.pem" \
    -subj "/CN=localhost"
fi

# Create DH params for nginx (used for SSL)
if [ ! -f "$CERTBOT_CONF/ssl-dhparams.pem" ]; then
  echo "Creating DH params..."
  openssl dhparam -out "$CERTBOT_CONF/ssl-dhparams.pem" 2048
fi

echo "Starting db, web, and nginx with dummy certs (certbot service not started yet)..."
docker compose up -d db web nginx

echo "Waiting for nginx to be ready..."
sleep 5

echo "Requesting real certificate from Let's Encrypt for $DOMAIN..."
docker compose run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  --email "$EMAIL" \
  -d "$DOMAIN" \
  --agree-tos \
  --non-interactive \
  --force-renewal

echo "Reloading nginx to use the new certificate..."
docker compose exec nginx nginx -s reload

echo "Starting certbot service for automatic renewal..."
docker compose up -d certbot

echo "Done. HTTPS is available at https://$DOMAIN"
echo "Certbot runs in the background and will renew certificates automatically."
