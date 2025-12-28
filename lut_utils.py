"""
Moduł z narzędziami do tworzenia Lookup Tables (LUT) dla mapowania kolorów.

LUT to tablica, która przypisuje kolory do wartości liczbowych (np. etykiet segmentacji).
W obrazowaniu medycznym używamy LUT do kolorowania różnych struktur anatomicznych.

Przykład:
    - Wartość 0 (tło) -> przezroczysty
    - Wartość 1 (wątroba) -> kolor pomarańczowy
    itd
"""

import colorsys  # Biblioteka do konwersji między modelami kolorów (HSV <-> RGB)
from vtkmodules.vtkCommonCore import vtkLookupTable


def create_visible_all_lut():
    """
    Tworzy lookup table z unikalnymi kolorami dla wszystkich możliwych wartości etykiet.
    
    Ta funkcja generuje LUT, w której KAŻDA wartość od 1 do 255 dostaje swój własny,
    wyraźnie odróżniający się kolor. To jest przydatne podczas debugowania segmentacji,
    bo możemy zobaczyć wszystkie etykiety nawet jeśli nie wiemy ile ich jest.
    
    Wartość 0 (tło) jest zawsze przezroczysta - bez tego tło w widoku segmentacji 2d robi się niebieskie
    
    Returns:
        vtkLookupTable: Gotowa tabela kolorów z 256 wpisami (0-255)
        
    """
    
    # Tworzymy nową pustą lookup table
    lut = vtkLookupTable()
    
    # Ustawiamy maksymalną liczbę etykiet
    # 256 to standardowa maksymalna wartość dla obrazów 8-bitowych
    MAX_LABELS = 256
    
    # Rezerwujemy miejsce na wszystkie kolory
    lut.SetNumberOfTableValues(MAX_LABELS)
    
    # Definiujemy zakres wartości, które będziemy mapować
    # Od 0 (tło) do 255 (maksymalna etykieta)
    lut.SetRange(0, MAX_LABELS - 1)
    
    # SPECJALNY PRZYPADEK: Wartość 0 to zawsze tło
    # Ustawiamy jako całkowicie przezroczyste (RGBA = 0, 0, 0, 0)
    # Parametry SetTableValue: (index, R, G, B, Alpha)
    # gdzie R, G, B, Alpha są w zakresie 0.0 - 1.0
    lut.SetTableValue(0, 0, 0, 0, 0)
    
    # Generujemy kolory dla wartości 1-255
    for i in range(1, MAX_LABELS):
        
        # 1: Oblicz odcień (HUE) 
        # Używamy złotego podziału (0.618...) żeby równomiernie rozłożyć kolory
        # Dzięki temu sąsiednie etykiety mają mocno różne kolory
        # Operator % 1.0 zapewnia że wartość będzie w zakresie [0, 1)
        hue = (i * 0.6180339887) % 1.0
        
        # 2: Oblicz nasycenie (SATURATION) 
        # Lekko variujemy nasycenie (0.7 - 1.0) żeby dodać więcej różnorodności
        # Różne wartości i dają różne nasycenia według wzoru periodycznego
        saturation = 0.7 + 0.3 * ((i * 0.382) % 1.0)
        
        # 3: Oblicz jasność (VALUE/BRIGHTNESS) 
        # Podobnie variujemy jasność (0.8 - 1.0) dla lepszego zróżnicowania
        # Unikamy zbyt ciemnych kolorów (min 0.8) żeby wszystko było widoczne
        value = 0.8 + 0.2 * ((i * 0.236) % 1.0)
        
        # 4: Konwersja HSV -> RGB 
        # Model HSV jest wygodny do generowania kolorów,
        # ale VTK potrzebuje RGB, więc konwertujemy
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        
        # 5: Zapisz kolor do LUT 
        # Parametry: (indeks, czerwony, zielony, niebieski, przezroczystość)
        # Alpha = 0.8 oznacza 80% nieprzezroczystości (lekko przezroczyste)
        # Dzięki temu możemy widzieć nakładające się struktury
        lut.SetTableValue(i, r, g, b, 0.8)
    
    # Finalizujemy tablicę - VTK musi to zrobić przed użyciem
    lut.Build()
    
    # Zwracamy gotową lookup table
    return lut
