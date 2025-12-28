"""
Moduł z narzędziami do wczytywania i parsowania plików konfiguracyjnych.

Zamiast hardcodować ścieżki w kodzie,używamy pliku konfiguracyjnego JSON który opisuje:
- Gdzie znajdują się pliki danych
- Jakie tkanki mają być wyświetlone
- Jakie kolory i właściwości mają obiekty
- Jak dane są zorientowane w przestrzeni

Ten moduł dostarcza funkcje do:
1. Parsowania pliku JSON z konfiguracją atlasu anatomicznego
2. Rozwiązywania nazw tkanek na ścieżki do plików VTK
3. Walidacji czy wszystkie wymagane pliki istnieją

STRUKTURA PLIKU JSON: zachęcam porównać z rzeczywistym plikiem!
{
  "files": {
    "root": "/ścieżka/do/danych",
    "vtk_files": ["plik1.vtk", "plik2.vtk", ...]
  },
  "tissues": {
    "names": ["liver", "kidney", ...],
    "opacity": {"liver": 0.9, "kidney": 0.8, ...},
    "indices": {"liver": 1, "kidney": 2, ...},
    "orientation": {"liver": "hfsi", "kidney": "ap", ...}
  }
}
"""

import json
from pathlib import Path

from config import TISSUE_TO_STEM


def parse_json(fn_path):
    """
    Parsuje plik JSON z konfiguracją atlasu anatomicznego.
    
    Ta funkcja wczytuje plik JSON, waliduje jego zawartość i zwraca słownik
    z parametrami gotowymi do użycia w aplikacji. Sprawdza czy wszystkie
    wymagane pliki VTK istnieją na dysku.
    
    STRUKTURA WYNIKU:
    Zwracany słownik zawiera:
    - 'vtk_files': {stem: Path} - mapowanie nazw plików na pełne ścieżki
    - 'names': [str] - lista nazw tkanek do wyświetlenia
    - 'opacity': {tkanka: float} - przezroczystość każdej tkanki (0.0-1.0)
    - 'indices': {tkanka: int} - indeks koloru w LUT dla każdej tkanki
    - 'orientation': {tkanka: str} - orientacja danych
    
    Argumenty:
        fn_path (Path): Ścieżka do pliku JSON z konfiguracją
    
    Returns:
        tuple: (success: bool, parameters: dict)
            - success: True jeśli parsowanie powiodło się
            - parameters: Słownik z parametrami lub None w przypadku błędu
    
    Raises:
        FileNotFoundError: Jeśli plik JSON, katalog root lub pliki VTK nie istnieją
        ValueError: Jeśli brak plików VTK w konfiguracji
        json.JSONDecodeError: Jeśli plik JSON jest niepoprawny
    
    Przykład:
        >>> ok, params = parse_json(Path("liver_config.json"))
        >>> if ok:
        >>>     print(f"Znaleziono {len(params['names'])} tkanek")
        >>>     for tissue in params['names']:
        >>>         print(f"- {tissue}: opacity={params['opacity'][tissue]}")
    """
    
    # 1: Wczytaj plik JSON 
    
    # Otwórz plik i sparsuj JSON do słownika Pythona
    # 'with' zapewnia że plik zostanie zamknięty nawet jeśli wystąpi błąd
    with open(fn_path) as f:
        data = json.load(f)
    
    # 2: Przygotuj pusty słownik na parametry 
    
    parameters = {}
    
    # 3: Sprawdź i wczytaj katalog główny (root) 
    
    # Katalog root zawiera wszystkie pliki VTK
    # Ścieżki w JSON są relatywne względem tego katalogu
    root = Path(data['files']['root'])
    
    # Sprawdź czy katalog istnieje
    if not root.exists():
        raise FileNotFoundError(f"Katalog root nie istnieje: {root}")
    
    # 4: Wczytaj i waliduj pliki VTK 
    
    # vtk_map będzie słownikiem: {stem: pełna_ścieżka}
    # gdzie stem to nazwa pliku bez rozszerzenia (np. "Liver_mesh")
    vtk_map = {}
    
    # Iteruj po wszystkich plikach VTK wymienionych w JSON
    for f in data['files']['vtk_files']:
        # Połącz root + relatywna ścieżka = pełna ścieżka
        p = root / f
        
        # Sprawdź czy plik naprawdę istnieje
        if not p.is_file():
            raise FileNotFoundError(f"Plik VTK nie istnieje: {p}")
        
        # Dodaj do mapy: nazwa_bez_rozszerzenia -> Path
        # p.stem to nazwa pliku bez rozszerzenia i bez katalogu
        # Przykład: "/data/meshes/Liver_mesh.vtk" -> "Liver_mesh"
        vtk_map[p.stem] = p
    
    # Zapisz mapę plików w parameters
    parameters['vtk_files'] = vtk_map
    
    # 5: Wczytaj parametry tkanek 
    
    # JSON może mieć sekcje 'tissues' i 'figures' z różnymi parametrami
    # Przechodzimy przez obie sekcje i łączymy dane
    for section in ['tissues', 'figures']:
        # Pobierz sekcję (lub pusty dict jeśli nie istnieje)
        section_data = data.get(section, {})
        
        # Dla każdego parametru w sekcji (np. 'names', 'opacity', 'indices')
        for k, v in section_data.items():
            # Zapisz bezpośrednio do parameters
            # Jeśli ten sam klucz występuje w obu sekcjach, drugi nadpisuje pierwszy
            parameters[k] = v
    
    # 6: Walidacja - sprawdź czy są jakieś pliki VTK 
    
    if len(parameters['vtk_files']) == 0:
        raise ValueError('Brak plików VTK w konfiguracji - oczekiwano przynajmniej jednego')
    
    # 7: Zwróć wynik 
    
    # Zwracamy tuple: (True, parameters) oznacza sukces
    # W przypadku błędu funkcja rzuci wyjątek przed dotarciem tutaj
    return True, parameters


def resolve_vtk_file(tissue, vtk_map):
    """
    Znajduje plik VTK dla danej nazwy tkanki.
    
    Ta funkcja tłumaczy "przyjazną" nazwę tkanki (np. "liver", "left_kidney")
    na rzeczywistą ścieżkę do pliku VTK. Używa mapowania TISSUE_TO_STEM z config.py
    żeby znaleźć wzorzec w nazwach plików.
    
    PROCES:
    1. Zamień nazwę tkanki na lowercase (unifikacja)
    2. Znajdź wzorzec nazwy (stem) w TISSUE_TO_STEM
    3. Przeszukaj vtk_map szukając pliku zawierającego ten stem
    4. Zwróć pełną ścieżkę do pliku
    
    Argumenty:
        tissue (str): Nazwa tkanki (np. "liver", "left_kidney", "ivc")
            Może być w dowolnym case - funkcja zamienia na lowercase
        vtk_map (dict): Słownik {stem: Path} z plików VTK
            Zwykle pochodzi z parse_json()
    
    Returns:
        Path: Pełna ścieżka do pliku VTK dla tej tkanki
    
    Raises:
        KeyError: Jeśli:
            - Nazwa tkanki nie jest w TISSUE_TO_STEM (nieznana tkanka)
            - Nie znaleziono pliku VTK zawierającego odpowiedni stem
    
    DLACZEGO TO JEST POTRZEBNE?
    W kodzie wygodnie jest używać prostych nazw jak "liver" czy "kidney".
    Ale pliki VTK mają zwykle długie skomplikowane nazwy jak:
    - "Liver_Segment_IVa_Smoothed_Final.vtk"
    - "RightKidney_Preprocessed_v2.vtk"
    
    Zamiast pisać pełne nazwy w kodzie, mapujemy proste nazwy na wzorce:
    - "liver_segment_iva" -> szukaj pliku zawierającego "LiverSegment_IVa"
    - "right_kidney" -> szukaj pliku zawierającego "RightKidney"
    """
    
    # 1: Normalizuj nazwę tkanki (zamień na lowercase) 
    
    key = tissue.lower()
    
    # 2: Znajdź token (wzorzec) dla tej tkanki 
    
    # Sprawdź czy ta tkanka jest w naszym mapowaniu
    if key not in TISSUE_TO_STEM:
        # Jeśli nie ma w mapowaniu, rzuć błąd z pomocną wiadomością
        raise KeyError(
            f'Nie znaleziono aliasu dla tkanki "{tissue}". '
            f'Dostępne tkanki: {", ".join(TISSUE_TO_STEM.keys())}'
        )
    
    # Pobierz token (wzorzec nazwy) z mapowania
    # Przykład: "liver_segment_i" -> "LiverSegment_I"
    token = TISSUE_TO_STEM[key]
    
    # 3: Przeszukaj pliki VTK szukając tego tokenu 
    
    # Iteruj po wszystkich plikach VTK w mapie
    for stem, path in vtk_map.items():
        # Sprawdź czy token występuje w nazwie pliku (stem)
        # Przykład: czy "LiverSegment_I" występuje w "Liver_Segment_I_Final"?
        if token in stem:
            # Znaleziono! Zwróć pełną ścieżkę do tego pliku
            return path
    
    # 4: Nie znaleziono pliku - rzuć błąd 
    
    # Jeśli dotarliśmy tutaj, oznacza to że:
    # - Tkanka jest w TISSUE_TO_STEM (ma zdefiniowany alias)
    # - ALE nie ma pliku VTK zawierającego odpowiedni token
    #
    # To może oznaczać:
    # - Plik VTK ma inną nazwę niż oczekiwano
    # - Plik VTK nie został dodany do konfiguracji JSON
    # - Błąd w TISSUE_TO_STEM (token nie pasuje do rzeczywistych nazw plików)
    
    raise KeyError(
        f'Nie znaleziono pliku VTK dla tkanki "{tissue}". '
        f'Szukano pliku zawierającego token "{token}" w nazwach: '
        f'{", ".join(vtk_map.keys())}'
    )
