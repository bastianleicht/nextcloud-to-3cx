#!/usr/bin/env python3
"""
Nextcloud zu 3CX Kontakt-Import Skript
Ruft Kontakte aus Nextcloud per WebDAV ab und bereitet sie für 3CX Import vor
"""

import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET
import csv
import re
import sys
from urllib.parse import urljoin, quote
import logging

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NextcloudContactImporter:
    def __init__(self, webdav_url, username, password):
        """
        Initialisiert den Kontakt-Importer

        Args:
            webdav_url (str): WebDAV URL der Nextcloud Adressbuch-Collection
            username (str): Nextcloud Benutzername
            password (str): Nextcloud Passwort oder App-Passwort
        """
        self.webdav_url = webdav_url.rstrip('/')
        self.username = username
        self.password = password
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth

    def get_contact_hrefs(self):
        """
        Ruft alle Kontakt-HREFs aus dem Adressbuch ab

        Returns:
            list: Liste der Kontakt-URLs
        """
        propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
            <d:prop>
                <d:getetag/>
                <card:address-data/>
            </d:prop>
        </d:propfind>'''

        headers = {
            'Content-Type': 'application/xml; charset=utf-8',
            'Depth': '1'
        }

        try:
            response = self.session.request(
                'PROPFIND',
                self.webdav_url,
                data=propfind_body,
                headers=headers
            )
            response.raise_for_status()

            # XML parsen
            root = ET.fromstring(response.text)

            # Namespaces definieren
            namespaces = {
                'd': 'DAV:',
                'card': 'urn:ietf:params:xml:ns:carddav'
            }

            contacts = []
            for response_elem in root.findall('.//d:response', namespaces):
                href = response_elem.find('d:href', namespaces)
                address_data = response_elem.find('.//card:address-data', namespaces)

                if href is not None and address_data is not None:
                    if address_data.text and address_data.text.strip():
                        contacts.append({
                            'href': href.text,
                            'vcard_data': address_data.text
                        })

            logger.info(f"Gefunden: {len(contacts)} Kontakte")
            return contacts

        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen der Kontakte: {e}")
            return []

    def parse_vcard(self, vcard_data):
        """
        Parst vCard-Daten und extrahiert relevante Informationen

        Args:
            vcard_data (str): vCard-Datenstring

        Returns:
            dict: Extrahierte Kontaktdaten
        """
        contact = {
            'first_name': '',
            'last_name': '',
            'display_name': '',
            'email': '',
            'phone_work': '',
            'phone_mobile': '',
            'phone_home': '',
            'company': '',
            'title': '',
            'department': '',
            'notes': ''
        }

        lines = vcard_data.strip().split('\n')

        for line in lines:
            line = line.strip()
            if ':' not in line:
                continue

            # Zeile in Property und Wert aufteilen
            prop_part, value = line.split(':', 1)
            prop_parts = prop_part.split(';')
            prop_name = prop_parts[0].upper()

            # Verschiedene vCard-Properties verarbeiten
            if prop_name == 'FN':
                contact['display_name'] = value
            elif prop_name == 'N':
                # Format: Nachname;Vorname;Weitere Namen;Präfix;Suffix
                name_parts = value.split(';')
                if len(name_parts) >= 2:
                    contact['last_name'] = name_parts[0]
                    contact['first_name'] = name_parts[1]
            elif prop_name == 'EMAIL':
                if not contact['email']:  # Erste E-Mail-Adresse nehmen
                    contact['email'] = value
            elif prop_name == 'TEL':
                # Telefonnummer-Typ bestimmen
                tel_type = self._get_tel_type(prop_parts)
                if tel_type == 'work' and not contact['phone_work']:
                    contact['phone_work'] = self._clean_phone_number(value)
                elif tel_type == 'mobile' and not contact['phone_mobile']:
                    contact['phone_mobile'] = self._clean_phone_number(value)
                elif tel_type == 'home' and not contact['phone_home']:
                    contact['phone_home'] = self._clean_phone_number(value)
                elif not contact['phone_work']:  # Fallback für erste Nummer
                    contact['phone_work'] = self._clean_phone_number(value)
            elif prop_name == 'ORG':
                contact['company'] = value
            elif prop_name == 'TITLE':
                contact['title'] = value
            elif prop_name == 'NOTE':
                contact['notes'] = value

        return contact

    def _get_tel_type(self, prop_parts):
        """
        Bestimmt den Telefonnummer-Typ aus den vCard-Properties

        Args:
            prop_parts (list): Liste der Property-Teile

        Returns:
            str: Telefonnummer-Typ (work, mobile, home)
        """
        prop_str = ';'.join(prop_parts).upper()

        if 'WORK' in prop_str:
            return 'work'
        elif 'CELL' in prop_str or 'MOBILE' in prop_str:
            return 'mobile'
        elif 'HOME' in prop_str:
            return 'home'
        else:
            return 'work'  # Default

    def _clean_phone_number(self, phone):
        """
        Bereinigt Telefonnummern

        Args:
            phone (str): Rohe Telefonnummer

        Returns:
            str: Bereinigte Telefonnummer
        """
        # Entfernt alle Zeichen außer Zahlen, +, -, (, ), und Leerzeichen
        cleaned = re.sub(r'[^\d\+\-\(\)\s]', '', phone)
        return cleaned.strip()

    def export_to_csv(self, contacts, filename='addresses.csv'):
        """
        Exportiert Kontakte in CSV-Format für direkten 3CX PostgreSQL Import

        Args:
            contacts (list): Liste der Kontaktdaten
            filename (str): Ausgabe-Dateiname
        """
        # 3CX PostgreSQL phonebook table structure
        fieldnames = [
            'idphonebook',
            'firstname',
            'lastname',
            'phonenumber',
            'fkidtenant',
            'fkiddn',
            'company',
            'tag',
            'pv_an5',  # Email
            'pv_an0',  # Mobile Phone
            'pv_an1',  # Home Phone
            'pv_an2',  # Work Phone 2
            'pv_an3',  # Fax
            'pv_an4',  # Title
            'pv_an6',  # Department
            'pv_an7',  # Notes
            'pv_an8',  # Additional field
            'pv_an9'   # Additional field
        ]

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for i, contact in enumerate(contacts, 1):
                    # Haupttelefonnummer bestimmen (Priorität: Work > Mobile > Home)
                    main_phone = contact['phone_work'] or contact['phone_mobile'] or contact['phone_home']

                    writer.writerow({
                        'idphonebook': i,  # Eindeutige ID
                        'firstname': contact['first_name'][:50] if contact['first_name'] else '',
                        'lastname': contact['last_name'][:50] if contact['last_name'] else '',
                        'phonenumber': main_phone[:20] if main_phone else '',
                        'fkidtenant': 1,  # Tenant ID (Standard: 1)
                        'fkiddn': '',     # DN ID (leer für Kontakte)
                        'company': contact['company'][:100] if contact['company'] else '',
                        'tag': '',        # Tag (leer)
                        'pv_an5': contact['email'][:100] if contact['email'] else '',  # Email
                        'pv_an0': contact['phone_mobile'][:20] if contact['phone_mobile'] else '',  # Mobile
                        'pv_an1': contact['phone_home'][:20] if contact['phone_home'] else '',    # Home
                        'pv_an2': contact['phone_work'][:20] if contact['phone_work'] else '',    # Work
                        'pv_an3': '',     # Fax (leer)
                        'pv_an4': contact['title'][:50] if contact['title'] else '',              # Title
                        'pv_an6': contact['department'][:50] if contact['department'] else '',    # Department
                        'pv_an7': contact['notes'][:200] if contact['notes'] else '',            # Notes
                        'pv_an8': '',     # Additional field (leer)
                        'pv_an9': ''      # Additional field (leer)
                    })

            logger.info(f"Kontakte erfolgreich nach {filename} exportiert")
            logger.info(f"Format: 3CX PostgreSQL phonebook kompatibel")
            return True

        except Exception as e:
            logger.error(f"Fehler beim CSV-Export: {e}")
            return False

    def run_import(self, output_file='addresses.csv'):
        """
        Führt den kompletten Import-Prozess aus

        Args:
            output_file (str): Ausgabe-Datei für CSV
        """
        logger.info("Starte Kontakt-Import aus Nextcloud...")

        # Kontakte abrufen
        raw_contacts = self.get_contact_hrefs()

        if not raw_contacts:
            logger.error("Keine Kontakte gefunden oder Fehler beim Abrufen")
            return False

        # vCard-Daten parsen
        parsed_contacts = []
        for raw_contact in raw_contacts:
            try:
                contact = self.parse_vcard(raw_contact['vcard_data'])
                if contact['display_name'] or contact['first_name'] or contact['last_name']:
                    parsed_contacts.append(contact)
            except Exception as e:
                logger.warning(f"Fehler beim Parsen eines Kontakts: {e}")
                continue

        logger.info(f"Erfolgreich geparst: {len(parsed_contacts)} Kontakte")

        # CSV exportieren
        if parsed_contacts:
            success = self.export_to_csv(parsed_contacts, output_file)
            if success:
                logger.info(f"Import abgeschlossen! CSV-Datei: {output_file}")
                logger.info("Sie können diese Datei nun in 3CX importieren.")
                return True

        return False

def main():
    """
    Hauptfunktion - Konfiguration und Ausführung
    """
    # Konfiguration
    WEBDAV_URL = "https://nextcloud.domain.de/remote.php/dav/addressbooks/users/your_username/your_shared_contacts/"

    # Benutzereingaben
    print("=== Nextcloud zu 3CX Kontakt-Import ===")
    print()

    username = 'your_username'
    password = 'your_custom_app_password'
    output_file = '3cx_contacts.csv'

    # Import ausführen
    importer = NextcloudContactImporter(WEBDAV_URL, username, password)
    success = importer.run_import(output_file)

    if success:
        print(f"\n Export erfolgreich abgeschlossen!")
        print(f"📄 CSV-Datei erstellt: {output_file}")
    else:
        print("\n❌ Import fehlgeschlagen. Bitte prüfen Sie die Logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()
