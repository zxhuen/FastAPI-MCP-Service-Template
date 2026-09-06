# FastAPI MCP Service Template

FastAPI MCP Service Template is a Python starter project that exposes product data through two interfaces:

- A REST API built with FastAPI.
- An MCP server built with FastMCP, so MCP-compatible clients and an AI assistant can manage products through structured tools.

The application stores products in PostgreSQL with SQLAlchemy and Alembic. The optional chat endpoint connects Gemini to the MCP tools and provides a natural-language inventory assistant.

## Features

- Create, list, update, delete, and search products.
- UUID product identifiers and unique product names.
- Decimal-backed prices with a database precision of `NUMERIC(10, 2)`.
- PostgreSQL persistence through SQLAlchemy.
- Database migrations with Alembic.
- MCP tools for programmatic and AI-assisted inventory operations.
- Gemini-powered conversational access through the REST API.
- Rate limiting of 10 requests per minute on each REST endpoint.

## Technology

- Python
- FastAPI and Uvicorn
- SQLAlchemy and psycopg2
- PostgreSQL
- Alembic
- FastMCP (`mcp<2`)
- Google Gemini (`google-genai`)
- Pydantic Settings
- SlowAPI

## Project Layout

```text
fastapi-mcp-service-template/
|-- app/
|   |-- main.py                         # FastAPI application
|   |-- api/
|   |   |-- Product.py                   # Product REST routes
|   |   `-- chat.py                      # Gemini chat route
|   |-- ai/providers/gemini.py           # Gemini client setup
|   |-- core/
|   |   |-- config.py                    # Environment-backed settings
|   |   |-- database.py                  # SQLAlchemy engine and sessions
|   |   `-- limiter.py                   # Rate limiter
|   |-- mcp_server/
|   |   |-- server.py                    # MCP server entry point
|   |   |-- mcp_client.py                # Gemini-to-MCP bridge
|   |   |-- tools/product_tools.py       # Product MCP tools
|   |   `-- prompts/inventory_assistant.md
|   |-- models/Products.py               # SQLAlchemy product model
|   |-- schemas/Products.py              # Pydantic request schema
|   |-- Repository/Product_Repo.py       # Database queries
|   `-- services/Products_Services.py    # Business logic
|-- alembic/                             # Database migrations
|-- docker-compose.yml                   # Local PostgreSQL service
|-- requirements.txt
`-- README.md
```

## Requirements

- Python 3.10 or newer is recommended.
- Docker Desktop, or an accessible PostgreSQL  database.
- A Gemini API key if you want to use the chat endpoint or import the application normally.

## Installation

From the repository root:

```bash
python -m venv venv
```

Activate the virtual environment.

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the repository root. The application expects all of these values:

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/test_db
GEMINI_API_KEY=your-gemini-api-key
```

`DATABASE_URL` is the value used by SQLAlchemy and Alembic. `SUPABASE_URL` and `SUPABASE_KEY` are loaded by the settings object but are not currently used by the product service. `GEMINI_API_KEY` is required because the Gemini client is initialized when the application imports.

Do not commit `.env` or API keys to source control.

## Start PostgreSQL Locally

The included Compose file starts PostgreSQL 17 with these development credentials:

```bash
docker compose up -d postgres
```

The default connection string is:

```text
postgresql+psycopg2://postgres:postgres@localhost:5432/test_db
```

Stop the database with:

```bash
docker compose down
```

To also remove the persisted development volume, use `docker compose down -v`.

## Database Migrations

Apply all checked-in migrations before starting the API:

```bash
alembic upgrade head
```

Create a new migration after changing the SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

The current product table contains:

| Column | Type | Rules |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `name` | `VARCHAR(255)` | Required and unique |
| `description` | `TEXT` | Nullable in the database; required by the request schema |
| `price` | `NUMERIC(10, 2)` | Required |
| `stock` | `INTEGER` | Required; defaults to `0` at the model level |
| `created_at` | Timestamp | Set by the database |

## Run the REST API

Run from the repository root so the `app` package can be imported:

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

Interactive documentation is available at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

## REST API

All product routes use the `/Product` prefix. JSON request bodies use this shape:

```json
{
	"name": "Mechanical Keyboard",
	"description": "75 percent wireless keyboard",
	"price": 89.99,
	"stock": 12
}
```

### Add a product

```http
POST /Product/add-product
Content-Type: application/json
```

```bash
curl -X POST http://127.0.0.1:8000/Product/add-product \
	-H "Content-Type: application/json" \
	-d '{"name":"Mechanical Keyboard","description":"75 percent wireless keyboard","price":89.99,"stock":12}'
```

The response is the created product, including its generated UUID and `created_at` timestamp.

### List products

```http
GET /Product/list-product
```

```bash
curl http://127.0.0.1:8000/Product/list-product
```

Returns an array of products. An empty inventory returns an empty array.

### Edit a product

```http
PUT /Product/edit-product?product_id=<uuid>
Content-Type: application/json
```

```bash
curl -X PUT "http://127.0.0.1:8000/Product/edit-product?product_id=PRODUCT_UUID" \
	-H "Content-Type: application/json" \
	-d '{"name":"Mechanical Keyboard","description":"Updated description","price":94.99,"stock":8}'
```

Updates all four editable fields. The product UUID is a query parameter, not part of the JSON body.

### Delete a product

```http
DELETE /Product/delete-product?product_id=<uuid>
```

```bash
curl -X DELETE "http://127.0.0.1:8000/Product/delete-product?product_id=PRODUCT_UUID"
```

The response is the deleted product. A missing product returns HTTP 404 with `{"detail":"no product found"}`.

### Search by product name

```http
GET /Product/search-product?name=<name>
```

```bash
curl "http://127.0.0.1:8000/Product/search-product?name=Mechanical%20Keyboard"
```

The current repository query uses an exact name comparison and returns one product object or `null` when no row matches. Although the MCP tool description allows partial-name wording, the current database query is exact and should be treated that way by REST clients.

### Chat assistant

```http
POST /Chat/assistant?message=<natural-language-request>
```

```bash
curl -X POST "http://127.0.0.1:8000/Chat/assistant?message=How%20many%20keyboards%20are%20in%20stock%3F"
```

The endpoint sends the message to Gemini. Gemini can call the product MCP tools, and the final assistant response is returned as text. The bridge allows at most five Gemini/MCP tool rounds for one request.

## MCP Server

The MCP server uses stdio transport. Start it from the repository root:

```bash
python -m app.mcp_server.server
```

An MCP client should launch that command with the repository root as its working directory. Because stdio is used for transport, the process communicates through stdin/stdout rather than exposing a separate HTTP port.

### Available MCP tools

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `hello` | None | Returns `Hello MCP`. Useful as a basic server check. |
| `add_product` | `name: string`, `description: string`, `price: number`, `stock: integer` | Creates a product. |
| `list_products` | None | Returns every product. |
| `edit_product` | `product_id: string`, `name: string`, `description: string`, `price: number`, `stock: integer` | Replaces all editable fields for a product. |
| `delete_product` | `product_id: string` | Deletes a product and returns a success wrapper. |
| `lookup_product_by_name` | `name: string` | Finds a product by name. The current query is exact despite the tool description mentioning partial names. |

MCP tools return prices as strings, for example `"89.99"`, to preserve decimal values when data crosses the tool boundary. Product IDs are returned as UUID strings.

### MCP client configuration example

The exact configuration format depends on the MCP client. A client that supports the common `mcpServers` format can use:

```json
{
	"mcpServers": {
		"product-service": {
			"command": "C:\\path\\to\\fastapi-mcp-service-template\\venv\\Scripts\\python.exe",
			"args": ["-m", "app.mcp_server.server"],
			"cwd": "C:\\path\\to\\fastapi-mcp-service-template"
		}
	}
}
```

On macOS/Linux, replace the Python executable and working directory with their platform-specific paths. The environment must contain the same `.env` configuration and installed dependencies as the REST API.

## Architecture

The application separates transport, business logic, and persistence:

1. FastAPI routes in `app/api` validate incoming HTTP parameters and request bodies.
2. Services in `app/services` implement create, read, update, delete, and search behavior.
3. Repository functions in `app/Repository` issue SQLAlchemy queries.
4. The SQLAlchemy model in `app/models` maps products to PostgreSQL.
5. MCP functions in `app/mcp_server/tools` call the same service layer as the REST API.
6. The chat bridge starts the MCP server over stdio, exposes its tools to Gemini, executes requested tools, and returns Gemini's final text.

This shared service layer keeps REST and MCP operations consistent and prevents each interface from implementing its own database logic.

## Rate Limits and Errors

Each REST endpoint is limited to 10 requests per minute per client according to SlowAPI. Exceeding the limit produces a rate-limit error response.

Common errors include:

- `422 Unprocessable Entity`: a required query parameter or body field is missing or has the wrong type.
- `404 Not Found`: an update or delete request references no product. Search may return `null` when there is no exact match.
- Database constraint errors: product names must be unique.
- MCP tool errors: invalid UUID strings or database failures are reported by the MCP call and should be surfaced by the client.

## Development Checks

Run the test suite with:

```bash
pytest
```

There is currently only a small test scaffold in `app/tests`, so use the interactive OpenAPI documentation and direct API calls to verify new endpoint behavior while adding coverage.

## Troubleshooting

### `ModuleNotFoundError: No module named 'app'`

Run commands from the repository root, the directory that contains `app/`, or set `PYTHONPATH` to that directory.

### Database connection failures

Confirm that PostgreSQL is running, that `DATABASE_URL` matches the active credentials and port, and that migrations have been applied with `alembic upgrade head`.

### Gemini or chat startup failures

Confirm that `GEMINI_API_KEY` exists in `.env`. The Gemini client is initialized during import, so the key is required even when only running the REST application.

### MCP client cannot start the server

Check the command, `cwd`, Python interpreter, virtual environment, and `.env` file. The MCP process must be launched with `python -m app.mcp_server.server` from the repository root.

## Security Notes

This project is configured for local development. Before exposing it publicly, add authentication and authorization, configure trusted origins and deployment settings, keep secrets outside the repository, and review rate-limit storage and database permissions.