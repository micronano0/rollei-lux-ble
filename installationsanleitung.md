# Installationsanleitung – Rollei LUX BLE

## 1. Voraussetzungen

- Raspberry Pi mit Bluetooth Low Energy
- Debian 13 (trixie)
- Benutzer pi mit Home-Verzeichnis /home/pi
- Bluetooth-Adapter hci0
- Internetverbindung während der Paketinstallation
- Python 3

Der Installer muss mit Root-Rechten gestartet werden.
Andere Debian-Versionen werden vom Installer abgewiesen.

## 2. Repository herunterladen

Terminal öffnen und ausführen:

    cd /home/pi
    git clone https://github.com/micronano0/rollei-lux-ble.git
    cd rollei-lux-ble

Bei bereits vorhandenem Repository zunächst dessen lokale
Änderungen prüfen, bevor Aktualisierungen übernommen werden.

## 3. Installation starten

    sudo bash install_rollei.sh

Der Installer:

1. Prüft Betriebssystem, Benutzer und Projektdateien.
2. Prüft die Python-Syntax.
3. Installiert benötigte Debian-Pakete.
4. Sichert vorhandene Rollei-Dateien.
5. Stoppt die Rollei-Dienste für die Aktualisierung.
6. Installiert beziehungsweise aktualisiert die Programme.
7. Übernimmt die Effektkonfiguration nur bei Erstinstallation.
8. Installiert die systemd-Dienste.
9. Richtet Bluetooth-Berechtigungen ein.
10. Initialisiert bei Bedarf die Statusdatei.
11. Startet die Dienste und führt weitere Prüfungen durch.

## 4. Programme und Dateien

Die Programme werden unter /home/pi installiert.

Wichtige Dateien:

- rollei_effekte_auto.py – zentrale Steuerung
- rollei_monitor.py – BLE-Überwachung
- rollei_auto_init.py – automatische Initialisierung
- rollei_effekte.json – gespeicherte Einstellungen
- rollei_status.json – dynamischer Lampenstatus
- rollei_effekt_01 bis 13 – einzelne Effekte

Die Statusdatei wird nicht aus GitHub übernommen.

## 5. Systemdienste prüfen

    systemctl status rollei-monitor.service
    systemctl status rollei-auto-init.service

Aktuelle Protokolle anzeigen:

    journalctl -u rollei-monitor.service -n 50 --no-pager
    journalctl -u rollei-auto-init.service -n 50 --no-pager

## 6. Lampe steuern

Einschalten:

    python3 ~/rollei_effekte_auto.py on

Einschalten mit Farbtemperatur und Helligkeit:

    python3 ~/rollei_effekte_auto.py on 5600 50

Ausschalten:

    python3 ~/rollei_effekte_auto.py off

Effekt mit gespeicherten Einstellungen:

    python3 ~/rollei_effekte_auto.py 8

Effekt mit Variante und Helligkeit:

    python3 ~/rollei_effekte_auto.py 8 2 50

Parameter:

- Effekt: 1 bis 13
- Variante: 1, 2 oder 3
- Helligkeit: 1 bis 100 Prozent

## 7. Gespeicherte Einstellungen

Die Datei /home/pi/rollei_effekte.json enthält die Einstellungen
der einzelnen Effekte und die CCT-Konfiguration.

Bei erneuter Installation bleibt eine vorhandene Datei erhalten.

Der Monitor verwaltet /home/pi/rollei_status.json.
Fehlt diese Datei, legt der Installer eine Ausgangsdatei an.

## 8. Sicherungen

Vor einer Aktualisierung erstellt der Installer ein Verzeichnis:

    /home/pi/rollei_sicherungen/vor_installation_DATUM_UHRZEIT/

Dort werden vorhandene Programmdateien, Konfigurationen,
Statusdatei und systemd-Dienste gesichert.

Die Sicherung wird nicht automatisch zurückgespielt.

## 9. Bluetooth prüfen

Adapter anzeigen:

    bluetoothctl list

Bluetooth-Dienst prüfen:

    systemctl status bluetooth.service

Blockierung prüfen:

    rfkill list

Die Steuerung benötigt den BLE-fähigen Adapter hci0.

## 10. Fehlerdiagnose

Wenn die Lampe nicht reagiert:

1. Prüfen, ob die Lampe eingeschaltet und erreichbar ist.
2. Prüfen, ob Bluetooth auf dem Raspberry Pi funktioniert.
3. Prüfen, ob ein Smartphone die Steuerung beeinflusst.
4. Systemdienste und Journalmeldungen kontrollieren.
5. Statusdatei und Effektkonfiguration überprüfen.

Statusdatei anzeigen:

    cat /home/pi/rollei_status.json

Effektkonfiguration anzeigen:

    cat /home/pi/rollei_effekte.json

## 11. Aktualisierung

Eine erneute Ausführung des Installers aktualisiert die
Programmdateien und systemd-Dienste.

Vorhandene Effekteinstellungen und die Statusdatei bleiben
erhalten. Der Installer erstellt zuvor eine Sicherung.

Hinweis: Der überarbeitete Installer wurde noch nicht durch
eine vollständige Neuinstallation separat getestet.
