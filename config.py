"""
Plik konfiguracyjny dla przeglądarki.

Zawiera wszystkie stałe konfiguracyjne używane w aplikacji, takie jak:
- Ścieżki do plików NRRD i JSON
- Mapowanie nazw tkanek na identyfikatory w plikach VTK
- Pozycje suwaków w interfejsie użytkownika
"""

# =============================================================================
# ŚCIEŻKI DO PLIKÓW DANYCH
# =============================================================================

# Ścieżka do głównego pliku NRRD z danymi CT/MRI
# To jest plik z obrazem medycznym w skali szarości
NRRD_FILE_PATH = "IM-0001-0015.dcm.nrrd"

# Ścieżka do pliku NRRD z etykietami segmentacji
# Każdy piksel ma wartość odpowiadającą ID struktury anatomicznej
NRRD_LABELS_PATH = "combined.nrrd"

# Ścieżka do pliku JSON z konfiguracją atlasu wątroby
# Zawiera informacje o plikach VTK, kolorach i właściwościach tkanek
JSON_PATH = "Liver_vtk.json"


# =============================================================================
# MAPOWANIE NAZW TKANEK
# =============================================================================

# Słownik mapujący przyjazne nazwy tkanek (lowercase) na ich oficjalne nazwy
# używane w nazwach plików VTK. Dzięki temu można używać prostszych nazw
# w kodzie i CLI, a aplikacja automatycznie znajdzie odpowiednie pliki.
#
# Struktura: "nazwa_uzywana_w_kodzie": "NazwaWStemPliku"
TISSUE_TO_STEM = {
    # Żyły główne
    "ivc": "IVC",                                   # Żyła główna dolna (Inferior Vena Cava)
    "caudate_veins": "CaudateVeins",                # Żyły płata ogoniastego
    
    # Żyła wrotna i jej gałęzie
    "main_portal_vein": "MainPortalVein",           # Główna żyła wrotna
    "left_portal_vein": "LeftPortalVein",           # Lewa gałąź żyły wrotnej
    "right_portal_vein": "RightPortalVein",         # Prawa gałąź żyły wrotnej
    
    # Żyły wątrobowe (hepatic veins)
    "left_hepatic_vein": "LeftHepaticVein",         # Lewa żyła wątrobowa
    "middle_hepatic_vein": "MiddleHepaticVein",     # Środkowa żyła wątrobowa
    "right_hepatic_vein": "RightHepaticVein",       # Prawa żyła wątrobowa
    
    # Segmenty wątroby (według klasyfikacji Couinaud)
    # Wątroba dzieli się na 8 segmentów oznaczonych cyframi rzymskimi
    "liver_segment_i": "LiverSegment_I",            # Segment I (płat ogoniasty)
    "liver_segment_ii": "LiverSegment_II",          # Segment II (lewy górny boczny)
    "liver_segment_iii": "LiverSegment_III",        # Segment III (lewy dolny boczny)
    "liver_segment_iva": "LiverSegment_IVa",        # Segment IVa (lewy przyśrodkowy górny)
    "liver_segment_ivb": "LiverSegment_IVb",        # Segment IVb (lewy przyśrodkowy dolny)
    "liver_segment_v": "LiverSegment_V",            # Segment V (prawy dolny przedni)
    "liver_segment_vi": "LiverSegment_VI",          # Segment VI (prawy dolny tylny)
    "liver_segment_vii": "LiverSegment_VII",        # Segment VII (prawy górny tylny)
    "liver_segment_viii": "LiverSegment_VIII",      # Segment VIII (prawy górny przedni)
    
    # Inne narządy jamy brzusznej
    "gallbladder": "Gallbladder",                   # Pęcherzyk żółciowy
    "stomach": "Stomach",                           # Żołądek
    "right_kidney": "RightKidney",                  # Prawa nerka
    "left_kidney": "LeftKidney",                    # Lewa nerka
    "spleen": "Spleen",                             # Śledziona
    "aorta": "Aorta"                                # Aorta brzuszna
}


# =============================================================================
# POZYCJE SUWAKÓW W INTERFEJSIE
# =============================================================================

# Interfejs ma dwie kolumny suwaków po prawej stronie okna.
# Współrzędne są w układzie znormalizowanym (0.0 - 1.0), gdzie:
# - (0, 0) to lewy dolny róg okna
# - (1, 1) to prawy górny róg okna

# KOLUMNA 1 (najbardziej na prawo)
right_x0_col1 = 0.82    # Początek suwaka (lewa krawędź)
right_x1_col1 = 0.97    # Koniec suwaka (prawa krawędź)

# KOLUMNA 2 (środkowa kolumna po prawej)
right_x0_col2 = 0.62    # Początek suwaka (lewa krawędź)
right_x1_col2 = 0.77    # Koniec suwaka (prawa krawędź)

# POZYCJE WERTYKALNE
# Suwaki są rozmieszczone wertykalnie od góry do dołu
top_y = 0.80            # Pozycja Y pierwszego (najwyższego) suwaka
step_y = 0.045          # Odstęp między kolejnymi suwakami w pionie