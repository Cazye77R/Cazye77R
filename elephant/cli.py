"""Command-line interface: python -m elephant <command>"""
import argparse
import sys
from pathlib import Path


def _init_collection():
    from elephant.memory.vector_store import init_collection
    return init_collection()


# ── chat ─────────────────────────────────────────────────────────────────────

def cmd_chat(args) -> None:
    from elephant.chat.engine import ChatEngine
    from elephant.utils.retry import OllamaError

    print("🐘 Elephant Chat  (Ctrl-C oder 'exit' zum Beenden)\n")
    try:
        collection = _init_collection()
        engine = ChatEngine(collection=collection)
    except Exception as exc:
        print(f"❌ Initialisierung fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)

    history: list[dict] = []
    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAuf Wiedersehen!")
            break

        if user_input.lower() in ("exit", "quit", "bye"):
            print("Auf Wiedersehen!")
            break
        if not user_input:
            continue

        try:
            response, sources = engine.chat(user_input, conversation_history=history)
        except OllamaError as exc:
            print(f"\n⚠️  Ollama nicht erreichbar: {exc}")
            print("Stelle sicher dass Ollama läuft: ollama serve\n")
            continue
        except Exception as exc:
            print(f"\n❌ Fehler: {exc}\n")
            continue

        print(f"\nElephant: {response}\n")
        if sources:
            print(f"  📎 {len(sources)} Quellen: " +
                  ", ".join(s.get("title", Path(s["source_file"]).stem) for s in sources[:3]))
            print()

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})


# ── sync ─────────────────────────────────────────────────────────────────────

def cmd_sync(args) -> None:
    from elephant.memory.vector_store import sync_all_memories

    print("🔄 Syncing memories with ChromaDB…")
    try:
        collection = _init_collection()
        report = sync_all_memories(collection=collection)
    except Exception as exc:
        print(f"❌ Sync fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ Sync abgeschlossen: {report['synced']} neu eingebettet, "
          f"{report['skipped']} unverändert, {report['total']} gesamt.")


# ── stats ─────────────────────────────────────────────────────────────────────

def cmd_stats(args) -> None:
    import json
    from elephant.config import settings
    from elephant.memory.markdown_store import list_memories

    memories = list_memories()
    by_cat: dict[str, int] = {}
    for m in memories:
        by_cat[m.category or "unknown"] = by_cat.get(m.category or "unknown", 0) + 1

    print("🐘 Elephant Stats")
    print(f"  Memories gesamt:  {len(memories)}")
    for cat, n in sorted(by_cat.items()):
        print(f"    {cat}: {n}")

    # ChromaDB chunk count
    try:
        collection = _init_collection()
        chunks = collection.count()
        print(f"  ChromaDB Chunks:  {chunks}")
    except Exception:
        print("  ChromaDB Chunks:  (nicht erreichbar)")

    # DB size on disk
    chroma_path = settings.chroma_path
    if chroma_path.exists():
        size_bytes = sum(f.stat().st_size for f in chroma_path.rglob("*") if f.is_file())
        size_mb = size_bytes / (1024 * 1024)
        print(f"  ChromaDB Größe:   {size_mb:.1f} MB  ({chroma_path})")

    memory_path = settings.memory_path
    if memory_path.exists():
        md_files = list(memory_path.rglob("*.md"))
        total_chars = sum(f.stat().st_size for f in md_files)
        print(f"  Memory-Dateien:   {len(md_files)} Dateien, {total_chars // 1024} KB  ({memory_path})")


# ── import ────────────────────────────────────────────────────────────────────

def cmd_import(args) -> None:
    from elephant.memory.markdown_store import save_memory
    from elephant.memory.vector_store import embed_memory

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"❌ Datei nicht gefunden: {filepath}", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8")
    title = args.title or filepath.stem
    category = args.category
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    print(f"📥 Importiere «{title}» → {category}/…")
    try:
        path = save_memory(category=category, title=title, content=content,
                           tags=tags, importance=args.importance)
        collection = _init_collection()
        n_chunks = embed_memory(path, collection=collection)
        print(f"✅ Gespeichert: {path.name}  ({n_chunks} Chunks eingebettet)")
    except Exception as exc:
        print(f"❌ Import fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="elephant",
        description="Elephant Memory System — CLI",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    sub.add_parser("chat", help="Interaktives Terminal-Chat mit Gedächtnis")
    sub.add_parser("sync", help="Alle Memories neu in ChromaDB einbetten")
    sub.add_parser("stats", help="Statistiken über Memories und ChromaDB")

    imp = sub.add_parser("import", help="Markdown-Datei als Memory importieren")
    imp.add_argument("file", help="Pfad zur .md Datei")
    imp.add_argument("--title", default=None, help="Titel (Standard: Dateiname)")
    imp.add_argument("--category", default="general",
                     choices=["general", "projects", "conversations"],
                     help="Kategorie (Standard: general)")
    imp.add_argument("--tags", default="", help="Tags kommagetrennt")
    imp.add_argument("--importance", type=float, default=0.5, help="Wichtigkeit 0-1")

    args = parser.parse_args()
    dispatch = {"chat": cmd_chat, "sync": cmd_sync, "stats": cmd_stats, "import": cmd_import}
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
