# Pipeline de recetas — TheMealDB → SQLite

Pipeline en Python que lee nombres de recetas de un fichero de texto, consulta la API pública de [TheMealDB](https://www.themealdb.com/api.php) y guarda cada resultado en una base de datos SQLite: la lista de ingredientes de forma estructurada y la receta completa transformada a markdown, pensado para su consumo posterior por LLM/RAG.

Todo el código vive en un único archivo: [`pipeline.py`](pipeline.py).

## Requisitos

- Python 3.10+ (usa sintaxis de tipos `X | None` y `list[str]`)
- Dependencias (en [`requirements.txt`](requirements.txt)):
  - `httpx` — cliente HTTP
  - `sqlalchemy` — ORM (estilo declarativo 2.x)

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Uso

1. Edita `recipes.txt` con un nombre de receta por línea (las líneas vacías se ignoran):

   ```
   Arrabiata
   Pad Thai
   Paella
   ```

2. Ejecuta el pipeline:

   ```powershell
   .\.venv\Scripts\python.exe pipeline.py
   ```

3. Los resultados quedan en `recipes.db` (se crea automáticamente junto a `pipeline.py`). Salida típica:

   ```
   Pipeline iniciado: 6 recetas a buscar
   'Paella': 2 resultado(s)
     - 'Paella' insertado
     - 'Roast fennel and aubergine paella' insertado
   ...
   Pipeline terminado: 6 buscadas | 6 insertadas | 1 saltadas | 0 sin resultados | 0 errores
   ```

## Cómo funciona

Flujo de `run_pipeline()`:

```
recipes.txt ──> load_recipe_names() ──> search_recipe() ──> extract_meals()
                                          (API TheMealDB)        │
                                                                 ▼  por cada meal
recipes.db <── Session.add/commit <── Recipe(name, ingredients, llm_info)
                                        │            │
                                        │            └── meal_to_markdown()
                                        └── extract_ingredients()
```

Funciones principales:

| Función | Responsabilidad |
|---|---|
| `load_recipe_names(filepath)` | Lee el fichero de nombres (uno por línea, con strip, ignora vacías). `FileNotFoundError` si no existe. |
| `search_recipe(name)` | GET a `search.php?s=<name>` con timeout de 10 s. Hasta 3 intentos con espera fija de 2 s ante errores de red o HTTP ≠ 200. Devuelve el JSON parseado, o `None` si no hay resultados (`{"meals": null}`) o si agota los reintentos. |
| `extract_meals(response)` | Convierte la respuesta en una lista segura de iterar (vacía si no hubo datos). Una búsqueda puede devolver **varios** meals; se inserta un registro por cada uno. |
| `extract_ingredients(meal)` | Recorre `strIngredient1..20` y devuelve **solo los nombres** de ingrediente (sin cantidades), ignorando entradas null, vacías o en blanco. Es lo que se guarda en el campo `ingredients`. |
| `meal_to_markdown(meal)` | Genera el markdown del campo `llm_info`: título, cabecera (Categoría / Origen / País / Tags), ingredientes **con cantidades**, instrucciones completas y enlaces (YouTube, fuente, imagen). Los campos sin contenido se omiten. |
| `run_pipeline()` | Orquestación: crea las tablas, busca cada nombre y persiste cada meal con commit por receta buscada y rollback ante errores, sin romper el bucle. |

## Modelo de datos

Tabla `Recipes` (SQLAlchemy 2.x declarativo, modelo `Recipe`):

| Campo | Tipo | Notas |
|---|---|---|
| `id` | Integer, PK | Autoincremental |
| `name` | String, not null | `strMeal` del meal |
| `ingredients` | JSON | Lista de nombres de ingrediente (`list[str]`), sin cantidades. SQLite no soporta arrays nativos, por eso JSON. |
| `llm_info` | Text, nullable | La receta completa en markdown, con cantidades incluidas. |

## Comportamiento ante errores e idempotencia

- **Reintentos**: cada petición a la API se intenta hasta 3 veces (espera fija de 2 s). Si falla definitivamente, se registra y se continúa con la siguiente receta.
- **Sin resultados**: las búsquedas que no devuelven meals se contabilizan y no interrumpen el proceso.
- **Idempotencia**: antes de insertar se comprueba si ya existe un `Recipe` con el mismo `name`; los duplicados se saltan (tanto entre ejecuciones como dentro de una misma ejecución). Re-ejecutar el pipeline no duplica filas.
- **Transacciones**: commit por receta buscada; si algo falla al guardar, rollback de esa receta y se sigue con la siguiente.

## Futuras mejoras

- **Logging en lugar de `print`**: niveles (INFO/ERROR), timestamps, redirección a fichero y posibilidad de silenciar la salida.
- **Corte temprano en el bucle de ingredientes**: en `extract_ingredients` (y el bucle equivalente de `meal_to_markdown`), cortar en el primer `strIngredientN` vacío en vez de recorrer siempre los 20 — **solo** si se puede garantizar que la API devuelve los ingredientes seguidos y sin huecos; con huecos, un `break` perdería los ingredientes posteriores.
- **Volcado "catch-all" en `meal_to_markdown`**: registrar en un set las claves del meal ya consumidas por cada sección y volcar al final cualquier otro campo con valor, para no perder información si la API añade campos nuevos y sin duplicar los ya escritos.

## Contexto y proceso de desarrollo

En [explicacion.md](explicacion.md) se documenta el flujo de trabajo seguido para construir este pipeline: el planteamiento inicial, el prompt enviado a Claude Opus para generar los prompts secuenciales, los 5 prompts paso a paso enviados a Claude Code y los ajustes que fue necesario precisar durante el proceso.
