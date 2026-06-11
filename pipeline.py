"""Pipeline de recetas: lee nombres de recipes.txt, consulta TheMealDB y
guarda cada resultado (ingredientes + markdown para LLM/RAG) en SQLite.

Posibles mejoras:
- Usar logging en lugar de print: niveles (INFO/ERROR), timestamps,
  redirección a fichero y posibilidad de silenciar la salida.
- En extract_ingredients (y el bucle de ingredientes de meal_to_markdown):
  cortar en el primer strIngredientN vacío en vez de recorrer siempre los 20,
  SOLO si se puede garantizar que la API devuelve los ingredientes seguidos
  y sin huecos (con huecos, un break perdería los ingredientes posteriores).
- En meal_to_markdown: volcado "catch-all" — registrar en un set las claves
  del meal ya consumidas por cada sección y añadir al final cualquier otro
  campo con valor (p. ej. strCountry), para no perder información si la API
  añade campos nuevos y sin duplicar los ya escritos.
"""

import time
from pathlib import Path

import httpx
from sqlalchemy import JSON, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

MEALDB_SEARCH_URL = "https://www.themealdb.com/api/json/v1/1/search.php"

# Ruta del SQLite relativa a este archivo, sin hardcodear la unidad.
DB_PATH = Path(__file__).resolve().parent / "recipes.db"

engine = create_engine(f"sqlite:///{DB_PATH}")


class Base(DeclarativeBase):
    pass


class Recipe(Base):
    __tablename__ = "Recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # SQLite no soporta arrays nativos: usamos JSON para almacenar la lista
    # de ingredientes (solo el nombre, sin cantidades) de forma estructurada
    # y recuperable como list[str].
    ingredients: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    llm_info: Mapped[str | None] = mapped_column(Text, nullable=True)


def init_db() -> None:
    """Crea las tablas si no existen."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Devuelve una Session de SQLAlchemy ligada al engine del proyecto."""
    return Session(engine)


def load_recipe_names(filepath: str) -> list[str]:
    """Lee un fichero con un nombre de receta por línea.

    Ignora líneas vacías y elimina espacios sobrantes.
    Lanza FileNotFoundError si el fichero no existe.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(
            f"No se encuentra el fichero de recetas: '{filepath}'. "
            "Crea el fichero con un nombre de receta por línea."
        )
    with path.open(encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def search_recipe(name: str) -> dict | None:
    """Busca una receta por nombre en TheMealDB y devuelve el JSON parseado.

    Devuelve None si no hay resultados ({"meals": null}) o si la petición
    sigue fallando tras 3 intentos (espera fija de 2 s entre intentos).
    """
    for attempt in range(1, 4):
        try:
            response = httpx.get(
                MEALDB_SEARCH_URL, params={"s": name}, timeout=10
            )
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
            data = response.json()
            if data.get("meals") is None:
                return None
            return data
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            if attempt < 3:
                time.sleep(2)
            else:
                print(f"Búsqueda de '{name}' falló tras 3 intentos: {exc}")
    return None


def extract_meals(response: dict | None) -> list[dict]:
    """Devuelve la lista de meals de una respuesta (vacía si no hay datos)."""
    if response is None or response.get("meals") is None:
        return []
    return response["meals"]


def _clean(value) -> str | None:
    """Normaliza un valor de la API: devuelve el string sin espacios, o None
    si viene null, vacío o solo espacios."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_ingredients(meal: dict) -> list[str]:
    """Devuelve solo los nombres de ingrediente (sin cantidades) del meal.

    Recorre strIngredient1..20 ignorando entradas null, vacías o en blanco.
    Es la lista destinada al campo `ingredients` del modelo.
    """
    ingredients = []
    for i in range(1, 21):
        name = _clean(meal.get(f"strIngredient{i}"))
        if name:
            ingredients.append(name)
    return ingredients


def meal_to_markdown(meal: dict) -> str:
    """Transforma un meal a markdown estructurado para LLM/RAG (campo llm_info).

    Secciones: título, clasificación, ingredientes con sus cantidades,
    instrucciones completas y enlaces. Los campos null, vacíos o en blanco
    se omiten.
    """
    lines: list[str] = []

    lines.append(f"# {_clean(meal.get('strMeal')) or 'Receta sin nombre'}")

    header_parts = []
    for label, key in (
        ("Categoría", "strCategory"),
        ("Origen", "strArea"),
        # País complementa a Origen (Spain vs Spanish): mejora el matching
        # léxico en RAG cuando se pregunta por el nombre del país.
        ("País", "strCountry"),
        ("Tags", "strTags"),
    ):
        value = _clean(meal.get(key))
        if value:
            header_parts.append(f"**{label}:** {value}")
    if header_parts:
        lines.append("")
        lines.append(" | ".join(header_parts))

    ingredient_lines = []
    for i in range(1, 21):
        name = _clean(meal.get(f"strIngredient{i}"))
        if not name:
            continue
        measure = _clean(meal.get(f"strMeasure{i}"))
        ingredient_lines.append(f"- {name} — {measure}" if measure else f"- {name}")
    if ingredient_lines:
        lines.append("")
        lines.append("## Ingredientes")
        lines.extend(ingredient_lines)

    instructions = _clean(meal.get("strInstructions"))
    if instructions:
        lines.append("")
        lines.append("## Instrucciones")
        lines.append(instructions)

    metadata_lines = []
    for label, key in (
        ("YouTube", "strYoutube"),
        ("Fuente", "strSource"),
        ("Imagen", "strMealThumb"),
    ):
        value = _clean(meal.get(key))
        if value:
            metadata_lines.append(f"- **{label}:** {value}")
    if metadata_lines:
        lines.append("")
        lines.append("## Enlaces y metadatos")
        lines.extend(metadata_lines)

    return "\n".join(lines)


def run_pipeline() -> None:
    """Orquestación completa: lee recipes.txt, consulta TheMealDB e ingesta
    cada meal devuelto en la tabla Recipes (un registro por meal)."""
    init_db()
    names = load_recipe_names("recipes.txt")
    print(f"Pipeline iniciado: {len(names)} recetas a buscar")

    total_inserted = 0
    total_skipped = 0
    total_no_results = 0
    total_errors = 0

    with get_session() as session:
        for name in names:
            meals = extract_meals(search_recipe(name))
            if not meals:
                print(f"'{name}': sin resultados")
                total_no_results += 1
                continue
            print(f"'{name}': {len(meals)} resultado(s)")

            try:
                inserted = 0
                skipped = 0
                for meal in meals:
                    meal_name = _clean(meal.get("strMeal")) or name
                    exists = session.execute(
                        select(Recipe).where(Recipe.name == meal_name)
                    ).scalar_one_or_none()
                    if exists is not None:
                        print(f"  - '{meal_name}' ya existe en la BD (id={exists.id}), saltado")
                        skipped += 1
                        continue
                    session.add(
                        Recipe(
                            name=meal_name,
                            ingredients=extract_ingredients(meal),
                            llm_info=meal_to_markdown(meal),
                        )
                    )
                    print(f"  - '{meal_name}' insertado")
                    inserted += 1
                session.commit()
                total_inserted += inserted
                total_skipped += skipped
            except Exception as exc:
                session.rollback()
                total_errors += 1
                print(f"Error guardando resultados de '{name}', rollback: {exc}")

    print(
        f"Pipeline terminado: {len(names)} buscadas | {total_inserted} insertadas | "
        f"{total_skipped} saltadas | {total_no_results} sin resultados | "
        f"{total_errors} errores"
    )


if __name__ == "__main__":
    run_pipeline()
