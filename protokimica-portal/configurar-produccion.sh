#!/bin/bash
# Arma backend/.env.prod y .env (raíz) preguntando los valores uno por
# uno, sin que tengas que editar archivos a mano con nano/vim.
#
# Uso (parado en ~/PortalEmpresarial/protokimica-portal):
#   bash configurar-produccion.sh

set -e

if [ ! -f "backend/.env.prod.example" ]; then
  echo "❌ No encuentro backend/.env.prod.example."
  echo "   ¿Estás parado en ~/PortalEmpresarial/protokimica-portal?"
  echo "   Corre: cd ~/PortalEmpresarial/protokimica-portal"
  exit 1
fi

echo "=========================================================="
echo " Configuración de producción — Portal Empresarial"
echo "=========================================================="
echo ""

# 1) Password de Postgres
read -s -p "1) Crea una password para la base de datos (no se va a ver mientras escribes): " POSTGRES_PASSWORD
echo ""
if [ -z "$POSTGRES_PASSWORD" ]; then
  echo "❌ No puede quedar vacía. Corre el script de nuevo."
  exit 1
fi

# 2) Usuario de n8n
read -p "2) Usuario para entrar a n8n (ej: admin) [admin]: " N8N_USER
N8N_USER=${N8N_USER:-admin}

# 3) Password de n8n
read -s -p "3) Password para entrar a n8n: " N8N_PASSWORD
echo ""
if [ -z "$N8N_PASSWORD" ]; then
  echo "❌ No puede quedar vacía. Corre el script de nuevo."
  exit 1
fi

# 4) Token del túnel de Cloudflare
read -s -p "4) Pega el token del túnel de Cloudflare (empieza con 'eyJ'): " CLOUDFLARE_TUNNEL_TOKEN
echo ""
if [ -z "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
  echo "❌ No puede quedar vacío. Corre el script de nuevo."
  exit 1
fi

# 5) SECRET_KEY — se genera solo, no hay que inventarla
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo ""
echo "Generando archivos..."

# ── backend/.env.prod ───────────────────────────────────────
cat > backend/.env.prod << EOF
ENVIRONMENT=production

DATABASE_URL=postgresql://protokimica:${POSTGRES_PASSWORD}@db:5432/protokimica_portal
REDIS_URL=redis://redis:6379/0

SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=480

CORS_ORIGINS=https://portal.protokimica.com
FRONTEND_URL=https://portal.protokimica.com

REGISTER_SETUP_KEY=

N8N_WEBHOOK_URL=http://n8n:5678
EOF

# ── .env (raíz) ──────────────────────────────────────────────
cat > .env << EOF
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

N8N_USER=${N8N_USER}
N8N_PASSWORD=${N8N_PASSWORD}

CLOUDFLARE_TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
EOF

chmod 600 backend/.env.prod .env

echo ""
echo "✅ Listo. Se crearon:"
echo "   - backend/.env.prod"
echo "   - .env"
echo ""
echo "Siguiente paso:"
echo "   docker compose -f docker-compose.prod.yml up -d --build"
