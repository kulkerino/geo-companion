# Project brief

Geo Companion is a private school project for learning visual geographic clues
from sourced lessons and licensed practice material. Its independent learning
loop must run locally and offline; optional model, worker, and GeoGuessr review
adapter work cannot become prerequisites for that loop.

The laptop is authoritative. FastAPI listens only on `127.0.0.1`, SQLite stays
in the user's application-data directory, and Git stores no learner database,
model binary, or downloaded private content pack.
