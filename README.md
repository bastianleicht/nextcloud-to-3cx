# nextcloud-to-3cx
Script to import Nextcloud Contacts in 3CX

## Setup

Diese Skripte sind so ausgelegt, das sie unter `/home/scripts/` liegen und von dort per Crontab ausgeführt werden.

### Auto Increment ID anpassen

Auto Increment ID anpassen, um persönliche Kontakte nicht zu überschreiben.

Die Kontakte aus der Nextcloud werden mit der Nextcloud ID importiert. Hierbei wird ausgegangen das diese ID nicht größer als 400000 ist.

```sql
ALTER SEQUENCE sqphonebook RESTART WITH 400000;
```

3CX legt hiernach die neu erstellten Kontakte mit der ID 400000 und höher an.

## Importscript

`/home/scripts/nc_contacts_import.py`

In diesem Skript müssen folgende Variablen angepasst werden:

- `WEBDAV_URL` - URL zu Nextcloud WebDAV (z.B. `https://cloud.example.com/remote.php/dav/addressbooks/users/username/contacts/`)
- `username` - Nextcloud Benutzername
- `password` - Nextcloud Passwort (Besser ein App-Passwort verwenden)

## Import der CSV

`/home/scripts/contact_import.sh`

Dieses Skript zieht sich automatisch die Postgres Datenbank Zugangsdaten aus der 3CX Konfiguration, löscht alle Firmenkontakte (`fkidtenant = 1`) und importiert die neue CSV.

Hierbei muss Postgres einmal neu gestartet werden. Dies bricht alle aktiven Anrufe etc. ab. Demnach wird das Skript nur Nachts ausgeführt.

## Crontab

```bash
# Kontakte um 00:10 Uhr exportieren
10 0 * * * /usr/bin/python3 /home/scripts/nc_contacts_import.py
# CSV um 00:20 Uhr importieren
20 0 * * * /home/scripts/contact_import.sh
```

## Contributing

I use the following commit message convention: [Semantic Commit Messages](https://gist.github.com/bastianleicht/2a43faa85eb6bce79f2afa110cd764fc)