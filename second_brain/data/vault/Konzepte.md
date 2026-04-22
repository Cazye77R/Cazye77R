---
title: Konzepte & Grundlagen
created: 2026-04-22 09:05
tags: [konzepte, theorie, lernen]
---

# Konzepte & Grundlagen

Eine Sammlung fundamentaler Konzepte rund um Wissensmanagement und KI.

## Zettelkasten-Methode

Der **Zettelkasten** (Niklas Luhmann) ist ein Netzwerk aus atomaren Notizen,
die durch Querverweise miteinander verbunden sind. Kernprinzipien:

- **Atomarität**: Eine Notiz = ein Gedanke.
- **Verlinkung**: Ideen werden durch Links kontextualisiert, nicht durch Ordner.
- **Emergenz**: Neues Wissen entsteht aus unerwarteten Verbindungen.

## Retrieval-Augmented Generation (RAG)

RAG kombiniert **Vektordatenbanken** mit **Sprachmodellen**:

1. Notizen werden in Embeddings umgewandelt (semantische Vektoren).
2. Bei einer Frage werden ähnliche Notizen gesucht (Nearest-Neighbor-Suche).
3. Das LLM erhält die relevanten Textstücke als Kontext.

Dieses System nutzt [[Willkommen|den Einstieg]] als Ausgangspunkt und
speichert Embeddings in ChromaDB.

## Graphentheorie für Wissen

Ein Wissensgraph ist ein gerichteter Graph `G = (V, E)` wobei:

- `V` = Menge der Notizen (Knoten)
- `E` = Menge der Wikilinks (Kanten)

Zentrale Notizen (hoher **Degree**) sind oft Konzepthubs. Notizen ohne
Verbindungen heißen **Orphans** – sie sollten verlinkt werden.

## Weiterführend

- Mehr unstrukturierte Einfälle: [[Ideen]]
- Zurück zur Übersicht: [[Willkommen]]

#konzepte #zettelkasten #rag #graphen
