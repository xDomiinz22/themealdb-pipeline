Hola! Este es el flujo de trabajo que he ideado para resolver el problema con IA, en mi caso he utilizado Claude Opus 4.8 (medio) para que me desarrolle el prompt y Sonnet 4.6 (alto) para lo demás.

En primer lugar, escribí en papel el flujo que quería que siguiera el pipeline y es el siguiente:

1.- Como input tenemos recipes.txt con varias recetas (una por línea).
2.- Búsqueda por API para obtener la información de las recetas.
3.- Transformar dichos resultados a un buen formato apto para LLMs o RAG para el algoritmo de recomendación (Json, Markdown, ...). En este caso elegí Markdown porque es el tipo de archivo que se suele utilizar
para entrenar LLMs, por ende estos tienden a comprender mejor este tipo de archivos, además de ser más legible por el ser humano que un JSON.
4.- Guardarlo todo en una base de datos.

Con esto en mente escribí un prompt que me tomó un tiempo, con el fin de que la IA realizase un prompt más elaborado sobre estos pasos, esto fue lo que escribí:


Z:\prueba_room714 En este directorio hay un archivo "recipes.txt" el cual almacena línea a línea una serie de recetas (solamente el nombre) y hay que hacer lo siguiente:

1.- Recolectar todos los nombres de las recetas en una estructura de datos (una lista, por ejemplo).

2.- Buscar por API a la dirección "themealdb.com/api/json/v1/1/search.php?s=${nombre}" siendo la variable "${nombre}" el nombre de la receta en cuestión.

3.- Por cada una obtendrás varios resultados, se deben guardar en una base de datos, el esquema de esta base de datos contiene una tabla "Recipes" con un total de 4 campos (id, name (varchar), ingredients (lista varchar) y llm_info (contendrá el contenido de la respuesta en formato markdown apto para modelos de IA, para ello debe transformarse la respuesta de la api a markdown). Quiero que para la inserción utilices sql-alchemy de forma que sea model-safe y en este caso utilizaremos sqlite como base de datos.

Necesito que generes un prompt con toda esta información para enviarlo a Claude Code de forma que lo entienda a la perfección, quiero que estos pasos vayan divididos, es decir, deben hacerse uno a uno y no todos de golpe, si para ello necesitas generar más prompts adelante con ello. Quizás el paso 3 pueda dividirse en dos o tres pasos, eres libre de hacerlo si lo crees necesario.


Con ello obtuve varios prompts más elaborados listos para enviar, aunque posteriormente tuve que especificar algunas cosas como por ejemplo:

1.- Que todo se realizase dentro de un archivo, pipeline.py en este caso.
2.- Que al extraer los nombres de los ingredientes, no se le añada su cantidad, cosa que hizo automáticamente pero solamente nos interesa el nombre del ingrediente y por ello tuve que especificarlo.
3.- A causa del punto anterior, dejó de guardar la cantidad en el markdown, también tuve que especificar que era necesario guardarlo.
4.- Que utilizase las librerías sqlalchemy y httpx, ya que son con las que más familiarizado estoy y son aptas para este problema.
