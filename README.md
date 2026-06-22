# MP Incident Manager

Daemon de monitoreo automático de tickets Jira para IX Engineers de Mercado Libre/Pago.

Monitorea los proyectos **IXFS** e **IXF** cada 5 minutos. Cuando detecta un ticket nuevo asignado al usuario, muestra un popup de alerta, envía un saludo automático en el ticket, verifica el estado del SLA y genera un reporte completo de la incidencia.

---

## ¿Qué hace exactamente?

### Flujo por ticket nuevo detectado

```
Nuevo ticket asignado
        │
        ▼
Verifica SLA ──── ¿Vencido? ────► Alerta SLA (notificación + nota interna en Jira)
        │
        ▼
Popup macOS bloqueante
  "IXFS-1234: [resumen]"
  [Ver en Jira] [Aceptar]
        │
        ▼ (usuario confirma)
Publica comentario público con saludo
  "Buenos días/tardes, hemos recibido su caso..."
        │
        ▼
Genera reporte Markdown en /reports/
  - Info completa del ticket
  - Estado SLA
  - Historial de comentarios
  - Análisis IA (si ANTHROPIC_API_KEY configurada)
        │
        ▼
Registra en historial JSON (/data/ticket_history.json)
  - Hora de primera vista
  - Tiempo transcurrido al tomar
  - Si SLA estaba vencido
```

### Verificación SLA

- Usa el campo SLA nativo de Jira Service Management si está disponible (campo `timetoFirstResponse`).
- Si no, calcula el tiempo desde la creación del ticket hasta ahora.
- Umbral configurable en `.env` → `SLA_THRESHOLD_MINUTES=5`.
- Si el SLA está vencido al momento de tomar el ticket:
  - Muestra alerta de sonido y notificación adicional en macOS.
  - Publica una **nota interna** en Jira indicando el tiempo sin respuesta.

### Saludo automático

Detecta la hora local (zona horaria configurable) y envía:

| Hora | Saludo |
|------|--------|
| 00:00 – 11:59 | Buenos días |
| 12:00 – 18:59 | Buenas tardes |
| 19:00 – 23:59 | Buenas noches |

Solo envía el saludo si el usuario no ha comentado antes en el ticket.

### Historial de tickets

Guardado en `data/ticket_history.json`. Contiene por cada ticket:
- Clave, resumen, proyecto, URL
- Hora de primera detección
- Hora de primera respuesta enviada
- Si el SLA estaba vencido al recibirlo
- Minutos transcurridos al momento de tomar el caso

---

## Estructura del proyecto

```
mp-incident-manager/
├── main.py                    # Daemon principal (loop de polling)
├── setup.sh                   # Instalación y configuración inicial
├── start.sh                   # Inicia el daemon en background
├── stop.sh                    # Detiene el daemon
├── requirements.txt
├── .env.example               # Plantilla de configuración
├── .env                       # Tu configuración real (gitignored)
├── src/
│   ├── config.py              # Carga de variables de entorno
│   ├── jira_client.py         # Cliente REST de Jira (IXFS + IXF)
│   ├── notifier.py            # Popups y notificaciones macOS (osascript)
│   ├── sla_checker.py         # Verificación de SLA
│   ├── reporter.py            # Generación de reportes y comentarios
│   └── history.py             # Persistencia de historial
├── data/
│   ├── ticket_history.json    # Historial completo (gitignored)
│   └── seen_tickets.json      # Control de tickets ya procesados (gitignored)
├── reports/                   # Reportes generados por ticket (gitignored)
└── logs/
    └── incident_manager.log   # Log del daemon
```

---

## Instalación

### Requisitos

- macOS (por `osascript` para popups)
- Python 3.10+
- Credenciales de Jira (API token de Atlassian)

### Setup inicial

```bash
cd /Users/framirezadas/Proyectos/mp-incident-manager
chmod +x setup.sh start.sh stop.sh
./setup.sh
```

`setup.sh` crea automáticamente un virtualenv Python en `.venv/` e instala las dependencias ahí.

El script `setup.sh`:
1. Genera `.env` automáticamente desde `~/.jira_config` si existe.
2. Instala las dependencias de Python.

Verifica tu `.env` antes de iniciar:

```bash
cat .env
```

### Iniciar el daemon

```bash
./start.sh
```

El daemon arranca en background. Para ver los logs en tiempo real:

```bash
tail -f logs/incident_manager.log
```

### Detener el daemon

```bash
./stop.sh
```

### Ejecutar un solo ciclo de polling (modo debug)

```bash
python3 main.py --poll-once
```

---

## Configuración (.env)

| Variable | Descripción | Default |
|----------|-------------|---------|
| `JIRA_URL` | URL de la instancia IXFS | `https://mercadolibre-externals.atlassian.net` |
| `JIRA_EMAIL` | Tu email de Jira | — |
| `JIRA_TOKEN` | API token de Atlassian | — |
| `JIRA_INTERNAL_URL` | URL de la instancia IXF | `https://mercadolibre.atlassian.net` |
| `JIRA_INTERNAL_TOKEN` | Token para IXF (si es diferente) | igual que `JIRA_TOKEN` |
| `JIRA_PROJECTS` | Proyectos a monitorear | `IXFS,IXF` |
| `SLA_THRESHOLD_MINUTES` | Minutos sin respuesta para alerta SLA | `5` |
| `POLL_INTERVAL_SECONDS` | Intervalo entre polls | `300` (5 min) |
| `ANTHROPIC_API_KEY` | API key de Anthropic (opcional) | — |
| `TIMEZONE` | Zona horaria para saludos | `America/Santiago` |

---

## Análisis interactivo con Claude Code

No se necesita API key. El sistema usa directamente **Claude Code CLI** (`~/.local/bin/claude`) que ya tienes instalado.

Cuando se detecta un ticket nuevo, después del popup se abre automáticamente una **nueva ventana de Terminal** con:

1. El reporte completo del ticket impreso en pantalla
2. Claude Code iniciado con el contexto del ticket como mensaje inicial
3. Claude ya analiza el ticket y entrega: resumen, contexto histórico, estado SLA y pasos recomendados
4. La sesión queda abierta para que puedas hacer preguntas adicionales

---

## Comandos útiles

```bash
# Ver historial de tickets tomados
python3 -c "from src.history import get_history; import json; print(json.dumps(get_history(), indent=2, ensure_ascii=False))"

# Ver tickets ya marcados como vistos
python3 -c "from src.history import get_seen_tickets; print(sorted(get_seen_tickets()))"

# Resetear el control de tickets vistos (fuerza reprocesar todos)
rm data/seen_tickets.json

# Ver reportes generados
ls -la reports/
```

---

## Troubleshooting

**El popup no aparece:**
- Asegúrate de que la app Terminal (o iTerm) tiene permisos de Accesibilidad en Preferencias del Sistema → Privacidad y Seguridad → Accesibilidad.

**Error de autenticación Jira:**
- Verifica que `JIRA_TOKEN` es un API token válido de https://id.atlassian.com/manage-profile/security/api-tokens.
- Asegúrate de que `JIRA_EMAIL` es exactamente el email registrado en Atlassian.

**No detecta tickets de IXF:**
- El token para `mercadolibre.atlassian.net` puede ser diferente al de IXFS.
- Configura `JIRA_INTERNAL_TOKEN` en tu `.env` con el token correspondiente.

**Nota interna no aparece en Jira:**
- Algunas instancias de Jira no tienen la API de Service Desk habilitada.
- El sistema intenta automáticamente un fallback usando visibilidad de rol.

---

## Próximas funcionalidades planificadas

- [ ] Integración con Gmail para notificaciones adicionales
- [ ] Dashboard HTML con métricas de tiempo de respuesta
- [ ] Autorespuesta configurable por tipo de ticket o cliente
- [ ] Integración con Slack para alertas en canal del equipo
- [ ] Exportación del historial a CSV/Google Sheets
