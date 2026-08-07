# data/

Lokal generierte Laufzeit-Daten. **Kein Inhalt wird ins Repository committed** –
nur die `.gitkeep`-Dateien, damit die Verzeichnisstruktur erhalten bleibt.

---

## Verzeichnisse

### `cache/`
OHLCV-Kursdaten im Parquet-Format (snappy-komprimiert), gecacht für
`CACHE_TTL_HOURS` Stunden (Standard: 24 h).

- Dateiname: `{SYMBOL}_{PERIOD}_{INTERVAL}.parquet`
- Automatisch ungültig nach TTL, wird beim nächsten Abruf erneuert.
- Kann jederzeit gelöscht werden – StockMind lädt die Daten neu.

### `training_state/`
Persistierter Trainings-Zustand je Aktie im JSON-Format.

- Dateiname: `{SYMBOL}.json`
- Enthält: Trainingszyklen, Accuracy-Verlauf, Methoden-Scores (UCB1),
  beste Methode, KI-Erkenntnisse, sklearn-Feature-Importance.
- **Empfehlung:** Diese Dateien sichern, wenn viele Trainingszyklen gelaufen sind.

### `portfolio/`
Paper-Trading-Portfolio-Daten im JSON-Format.

- Dateiname: `{NAME}_trades.json`
- Enthält: Startkapital, offene Positionen, Trade-Historie, Snapshot-Verlauf.
- ⚠️ **Backup-Empfehlung:** Portfolio-Daten regelmäßig sichern!
  Ein versehentliches `rm -rf data/portfolio/` löscht alle Trade-Historie.

  ```bash
  # Beispiel-Backup
  cp -r data/portfolio/ ~/stockmind-portfolio-backup-$(date +%Y%m%d)/
  ```

### `logs/`
Anwendungs-Logs (reserviert für zukünftige Verwendung).

- Aktuell noch leer; LOG_LEVEL ist via `.env` konfigurierbar.

---

## Wiederherstellung

Alle Verzeichnisse werden beim App-Start automatisch angelegt (`_ensure_data_dirs()`).
Nach einem versehentlichen Löschen reicht:

```bash
streamlit run app.py   # legt data/ neu an
```

Cache und Training-States werden durch normale Nutzung neu befüllt.
Nur Portfolio-Daten sind unwiederbringlich verloren – daher sichern.
