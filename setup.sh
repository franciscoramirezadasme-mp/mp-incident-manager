#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo "  MP Incident Manager — Setup"
echo "======================================"

# Create .env from existing Jira config if not exists
if [ ! -f ".env" ]; then
    if [ -f "$HOME/.jira_config" ]; then
        echo "📋 Generating .env from ~/.jira_config..."
        source "$HOME/.jira_config"
        cat > .env << EOF
# Jira - instancia principal (IXFS)
JIRA_URL=${JIRA_URL:-https://mercadolibre-externals.atlassian.net}
JIRA_EMAIL=${JIRA_EMAIL:-francisco.ramirezadasme@mercadolibre.cl}
JIRA_TOKEN=${JIRA_TOKEN:-}

# Jira - instancia interna (IXF) — usa el mismo token si no tienes uno separado
JIRA_INTERNAL_URL=https://mercadolibre.atlassian.net
JIRA_INTERNAL_TOKEN=${JIRA_TOKEN:-}

# Proyectos a monitorear
JIRA_PROJECTS=IXFS,IXF

# SLA threshold en minutos
SLA_THRESHOLD_MINUTES=5

# Intervalo de polling en segundos (300 = 5 min)
POLL_INTERVAL_SECONDS=300

# Anthropic API (opcional — para reportes con análisis IA)
ANTHROPIC_API_KEY=

# Zona horaria
TIMEZONE=America/Santiago
EOF
        echo "✅ .env created from ~/.jira_config"
    else
        cp .env.example .env
        echo "⚠️  .env created from .env.example — please fill in your credentials"
    fi
else
    echo "✅ .env already exists"
fi

# Create virtual environment if not exists
if [ ! -d ".venv" ]; then
    echo ""
    echo "🐍 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install dependencies
echo ""
echo "📦 Installing Python dependencies..."
source .venv/bin/activate
pip install --index-url https://pypi.org/simple -r requirements.txt --quiet

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Review and verify .env has correct values"
echo "  2. Run:  ./start.sh"
echo "  3. View logs:  tail -f logs/incident_manager.log"
