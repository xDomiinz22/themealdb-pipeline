# Flujo de trabajo con IA

## Planteamiento inicial

Hola! Este es el flujo de trabajo que he ideado para resolver el problema con IA, en mi caso he utilizado Claude Opus 4.8 (medio) para que me desarrolle el prompt y Sonnet 4.6 (alto) para lo demás.

En primer lugar, escribí en papel el flujo que quería que siguiera el pipeline y es el siguiente:

1. Como input tenemos recipes.txt con varias recetas (una por línea).
2. Búsqueda por API para obtener la información de las recetas.
3. Transformar dichos resultados a un buen formato apto para LLMs o RAG para el algoritmo de recomendación (Json, Markdown, ...). En este caso elegí Markdown porque es el tipo de archivo que se suele utilizar para entrenar LLMs, por ende estos tienden a comprender mejor este tipo de archivos, además de ser más legible por el ser humano que un JSON.
4. Guardarlo todo en una base de datos.

## Prompt inicial enviado a Claude Opus

Con esto en mente escribí un prompt que me tomó un tiempo, con el fin de que la IA realizase un prompt más elaborado sobre estos pasos, esto fue lo que escribí:

```
Z:\prueba_room714 En este directorio hay un archivo "recipes.txt" el cual almacena línea a línea una serie de recetas (solamente el nombre) y hay que hacer lo siguiente:

1.- Recolectar todos los nombres de las recetas en una estructura de datos (una lista, por ejemplo).

2.- Buscar por API a la dirección "themealdb.com/api/json/v1/1/search.php?s=${nombre}" siendo la variable "${nombre}" el nombre de la receta en cuestión.

3.- Por cada una obtendrás varios resultados, se deben guardar en una base de datos, el esquema de esta base de datos contiene una tabla "Recipes" con un total de 4 campos (id, name (varchar), ingredients (lista varchar) y llm_info (contendrá el contenido de la respuesta en formato markdown apto para modelos de IA, para ello debe transformarse la respuesta de la api a markdown). Quiero que para la inserción utilices sql-alchemy de forma que sea model-safe y en este caso utilizaremos sqlite como base de datos.

Necesito que generes un prompt con toda esta información para enviarlo a Claude Code de forma que lo entienda a la perfección, quiero que estos pasos vayan divididos, es decir, deben hacerse uno a uno y no todos de golpe, si para ello necesitas generar más prompts adelante con ello. Quizás el paso 3 pueda dividirse en dos o tres pasos, eres libre de hacerlo si lo crees necesario.
```

## Prompts secuenciales para Claude Code — Pipeline de recetas (TheMealDB → SQLite)

Con ello obtuve varios prompts más elaborados listos para enviar:

> **Instrucciones de uso:** Envía cada prompt a Claude Code **uno a uno**, esperando a que termine y verifique cada fase antes de enviar el siguiente. Todo el código vive en un único archivo: `pipeline.py`. Cada prompt AÑADE funcionalidad a ese mismo archivo.

---

### PROMPT 1 — Setup del proyecto y lectura de recetas

```
Estamos trabajando en el directorio Z:\prueba_room714 (Windows). Este es el PASO 1 de un pipeline de 5 pasos; haz SOLO lo que se describe aquí, no te adelantes a fases futuras.

CONTEXTO GENERAL DEL PROYECTO (solo para que entiendas hacia dónde vamos, NO lo implementes aún):
Vamos a construir un pipeline en Python que: (1) lee nombres de recetas de un fichero, (2) consulta la API de TheMealDB por cada nombre, (3) transforma las respuestas a markdown y las guarda en una base de datos SQLite usando SQLAlchemy.

REGLA IMPORTANTE DE ARQUITECTURA: TODO el código del proyecto irá en UN ÚNICO archivo llamado pipeline.py en la raíz de Z:\prueba_room714. No crees paquetes, módulos separados ni carpetas app/. En los pasos siguientes iremos AÑADIENDO funciones a este mismo archivo.

TAREA DE ESTE PASO:
1. Crea en Z:\prueba_room714:
   - Un entorno virtual (.venv) y un requirements.txt con: httpx, sqlalchemy
   - El archivo pipeline.py
2. En pipeline.py implementa una función `load_recipe_names(filepath: str) -> list[str]` que:
   - Lea el archivo "recipes.txt" que YA EXISTE en Z:\prueba_room714 (una receta por línea, solo el nombre).
   - Devuelva una lista de strings con los nombres.
   - Ignore líneas vacías y elimine espacios sobrantes (strip).
   - Lance FileNotFoundError con un mensaje claro si el archivo no existe.
3. Añade un bloque if __name__ == "__main__" que cargue recipes.txt e imprima la lista y el número de recetas encontradas. (Este bloque irá evolucionando en cada paso hasta convertirse en la orquestación final.)

VERIFICACIÓN: Ejecuta pipeline.py y muéstrame la salida con la lista de recetas leídas. No continúes con nada más.
```

---

### PROMPT 2 — Cliente de la API de TheMealDB (con retries simples)

```
PASO 2 del pipeline (el PASO 1 ya está hecho: pipeline.py existe con load_recipe_names). Trabajamos en Z:\prueba_room714 y TODO va en el mismo archivo pipeline.py. Haz SOLO este paso.

TAREA — añade a pipeline.py:
1. Una función `search_recipe(name: str) -> dict | None` que:
   - Use la librería httpx (cliente síncrono, no async) para hacer una petición GET a: https://www.themealdb.com/api/json/v1/1/search.php?s=${name}
     (sustituyendo ${name} por el nombre de la receta, correctamente URL-encoded pasándolo en el parámetro params de httpx, no concatenación manual).
   - Devuelva el JSON parseado (dict) de la respuesta.
   - La API devuelve {"meals": null} cuando no hay resultados: en ese caso devuelve None.
   - Incluya un timeout de 10 segundos por petición.
   - RETRIES SIMPLES: si la petición falla (httpx.RequestError, timeout o HTTP != 200), reintenta hasta un máximo de 3 intentos en total, con una espera FIJA de 2 segundos entre intentos (time.sleep(2)). Nada de backoff exponencial ni librerías externas de retry: un bucle simple. Si tras los 3 intentos sigue fallando, registra el error con logging (no print) y devuelve None sin romper el flujo.
2. Ten en cuenta que cada búsqueda puede devolver VARIOS resultados (la clave "meals" es una lista de comidas). La función devuelve el dict completo; el procesado de cada meal individual se hará en pasos posteriores.
3. Una función auxiliar `extract_meals(response: dict | None) -> list[dict]` que devuelva la lista de meals (lista vacía si response es None o meals es null).
4. Actualiza el bloque if __name__ == "__main__" para que, de forma temporal, busque "Arrabiata" e imprima cuántos resultados devuelve y el nombre (strMeal) de cada uno.

VERIFICACIÓN: Ejecuta pipeline.py y muéstrame la salida. No implementes nada de base de datos todavía.
```

---

### PROMPT 3 — Modelo SQLAlchemy y base de datos SQLite

```
PASO 3 del pipeline (pasos 1 y 2 completados en pipeline.py: load_recipe_names, search_recipe con retries y extract_meals). Trabajamos en Z:\prueba_room714 y TODO va en el mismo archivo pipeline.py. Haz SOLO este paso.

TAREA — añade a pipeline.py:
1. El modelado con SQLAlchemy 2.x en estilo declarativo moderno (DeclarativeBase, Mapped, mapped_column) para que todo sea model-safe y con tipado.
2. Define el modelo `Recipe` mapeado a la tabla "Recipes" con EXACTAMENTE estos 4 campos:
   - id: Integer, primary key, autoincremental.
   - name: String (varchar), not null.
   - ingredients: lista de strings. Como SQLite no soporta arrays nativos, usa el tipo JSON de SQLAlchemy (sqlalchemy.JSON) para almacenar la lista de varchar de forma estructurada y recuperable como list[str]. Documenta esta decisión con un comentario en el código.
   - llm_info: Text, nullable. Contendrá la respuesta de la API transformada a markdown apto para modelos de IA (se generará en el paso 4; aquí solo defines la columna).
3. Crea el engine apuntando a un fichero SQLite local "recipes.db" en la raíz del proyecto (construye la ruta con pathlib relativa al propio pipeline.py, no hardcodees la unidad Z:).
4. Implementa:
   - `init_db()`: crea las tablas si no existen (Base.metadata.create_all).
   - `get_session()`: devuelve una Session de SQLAlchemy.
5. Actualiza temporalmente el bloque if __name__ == "__main__": llama a init_db(), inserta un registro dummy (name="TEST", ingredients=["a","b"], llm_info="# test"), haz commit, léelo de vuelta, imprímelo y bórralo después para no dejar basura.

VERIFICACIÓN: Ejecuta pipeline.py, muéstrame la salida y confirma que recipes.db se ha creado. No implementes la transformación a markdown ni la ingesta masiva todavía.
```

---

### PROMPT 4 — Transformación de la respuesta de la API a markdown (llm_info)

```
PASO 4 del pipeline (pasos 1-3 completados en pipeline.py: lectura, cliente API con retries, y modelo Recipe en SQLite con SQLAlchemy). Trabajamos en Z:\prueba_room714 y TODO va en el mismo archivo pipeline.py. Haz SOLO este paso.

CONTEXTO: Cada "meal" del JSON de TheMealDB tiene esta estructura relevante:
- strMeal: nombre
- strCategory, strArea: categoría y origen
- strInstructions: instrucciones de preparación (texto largo)
- strIngredient1..strIngredient20 y strMeasure1..strMeasure20: ingredientes y sus cantidades (muchos vienen vacíos o null)
- strTags, strYoutube, strSource y otros metadatos opcionales

IMPORTANTE — distinción clave entre los dos destinos de los datos:
- El campo `ingredients` de la BD: SOLO nombres de ingredientes, sin cantidades.
- El campo `llm_info` (markdown): debe contener TODA la información de la respuesta de la API, incluyendo las cantidades (strMeasureN) junto a cada ingrediente. Este markdown se usará en el futuro para procesado por LLM/RAG, así que NO debe perderse información.

TAREA — añade a pipeline.py:
1. `extract_ingredients(meal: dict) -> list[str]`:
   - Recorre strIngredient1..strIngredient20.
   - Ignora entradas null, vacías o solo espacios.
   - Devuelve una lista de strings con SOLAMENTE el nombre del ingrediente, sin cantidades (los strMeasureN no se incluyen AQUÍ; sí se usarán en el markdown).
   - Esta lista es la que se guardará en el campo `ingredients` del modelo.

2. `meal_to_markdown(meal: dict) -> str`:
   - Transforma el meal COMPLETO a un markdown limpio y estructurado, apto para ser consumido por modelos de IA / RAG (campo llm_info). Debe ser EXHAUSTIVO: vuelca toda la información útil de la respuesta, no resumas ni descartes campos con datos. Estructura sugerida:
     # {strMeal}
     **Categoría:** ... | **Origen:** ... | **Tags:** ...
     ## Ingredientes
     - lista con viñetas: ingrediente — cantidad (usando los pares strIngredientN / strMeasureN; si un ingrediente no tiene medida, solo el nombre)
     ## Instrucciones
     texto completo de strInstructions
     ## Enlaces y metadatos
     YouTube, fuente (strSource), imagen (strMealThumb) y cualquier otro campo strXxx con valor que no encaje en las secciones anteriores
   - Omite únicamente los campos que vengan null, vacíos o solo espacios (no dejes "None" ni viñetas vacías en el markdown), pero todo campo con contenido debe acabar reflejado.

3. Actualiza temporalmente el bloque if __name__ == "__main__": busca "Arrabiata", coge el primer meal, e imprime la lista de ingredientes extraída y el markdown generado.

VERIFICACIÓN: Ejecuta pipeline.py y muéstrame la salida completa del markdown. No hagas la ingesta masiva todavía.
```

---

### PROMPT 5 — Orquestación e ingesta completa

```
PASO 5 y FINAL del pipeline (pasos 1-4 completados en pipeline.py: load_recipe_names, search_recipe + extract_meals, modelo Recipe + init_db/get_session, y extract_ingredients + meal_to_markdown). Trabajamos en Z:\prueba_room714 y TODO sigue en pipeline.py.

TAREA:
1. Implementa una función `run_pipeline()` y deja el bloque if __name__ == "__main__" definitivo llamándola. El flujo:
   a) init_db().
   b) Cargar la lista de nombres con load_recipe_names("recipes.txt").
   c) Por cada nombre:
      - Consultar la API con search_recipe(name) y extraer los meals con extract_meals().
      - RECUERDA: cada búsqueda puede devolver VARIOS meals; hay que insertar un registro por CADA meal devuelto, no solo el primero.
      - Por cada meal: extraer ingredients con extract_ingredients() (solo nombres), generar llm_info con meal_to_markdown(), y crear una instancia del modelo Recipe (name = strMeal del meal).
   d) Insertar usando la Session de SQLAlchemy (model-safe: siempre a través de instancias del modelo, nunca SQL crudo). Commit por receta buscada y rollback ante errores.
2. Idempotencia básica: antes de insertar un meal, comprueba si ya existe un Recipe con el mismo name en la BD y sáltalo si es así, registrándolo con logging.
3. Logging informativo durante todo el proceso: receta buscada, nº de resultados, insertados, saltados, errores. Resumen final con totales.
4. Si una búsqueda devuelve None o lista vacía (incluyendo fallos tras los 3 retries), regístralo como "sin resultados" y continúa con la siguiente sin romper el proceso.

VERIFICACIÓN FINAL:
- Ejecuta pipeline.py con el recipes.txt real.
- Muéstrame el resumen final del log.
- Haz una consulta de comprobación con SQLAlchemy que imprima: total de filas en Recipes, y para 2 registros de ejemplo: id, name, ingredients (la lista deserializada) y los primeros ~300 caracteres de llm_info, para verificar que el markdown se ha guardado correctamente.
```

---

## Notas

- **Archivo único:** todo vive en `pipeline.py`. Cada prompt recuerda explícitamente esta regla para que Claude Code no se vaya a crear módulos por su cuenta, y el bloque `__main__` se va reutilizando como zona de pruebas hasta convertirse en la orquestación final en el paso 5.
- **Ingredientes vs. markdown:** el campo `ingredients` de la BD lleva solo nombres (sin cantidades), pero el markdown de `llm_info` es exhaustivo: incluye cantidades, instrucciones completas, enlaces y todos los metadatos con valor, pensado para procesado futuro por LLM/RAG sin pérdida de información.
- **Retries:** 3 intentos máximo con espera fija de 2 segundos (`time.sleep(2)`), implementado con un bucle simple, sin backoff ni librerías de retry. Si quieres otros valores, cámbialos en el Prompt 2.
- **HTTP con httpx:** se especifica el cliente síncrono de `httpx` (no async) para mantener el pipeline simple. Si en el futuro quisieras paralelizar las búsquedas, ya tendrías la librería adecuada para pasar a `httpx.AsyncClient`.
- **Campo `ingredients`:** SQLite no tiene tipo array nativo, así que se usa el tipo `JSON` de SQLAlchemy: cumple "lista de varchar" y se deserializa automáticamente a `list[str]` al leer.
- Cada prompt termina con una verificación ejecutable: no envíes el siguiente hasta ver esa salida correcta.

## Ajustes y refinamientos

Aunque posteriormente tras revisarlo tuve que especificar algunas cosas como por ejemplo:

1. Que todo se realizase dentro de un archivo, pipeline.py en este caso.
2. Que al extraer los nombres de los ingredientes, no se le añada su cantidad, cosa que hizo automáticamente pero solamente nos interesa el nombre del ingrediente y por ello tuve que especificarlo.
3. A causa del punto anterior, dejó de guardar la cantidad en el markdown, también tuve que especificar que era necesario guardarlo.
4. Que utilizase las librerías sqlalchemy y httpx, ya que son con las que más familiarizado estoy y son aptas para este problema.

