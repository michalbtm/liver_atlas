"""
Moduł z narzędziami do analizy i porównywania geometrii obiektów 3D (polydata).

W VTK obiekty 3D (siatki trójkątów, powierzchnie) są reprezentowane jako polydata.
Ten moduł pozwala na:
- Obliczanie "sygnatury" obiektu (liczba punktów, komórek, objętość, położenie)
- Porównywanie dwóch obiektów pod kątem podobieństwa
- Wykrywanie duplikatów w danych 

Ale dlaczego pojawiają się duplikaty? Odpowiedź brzmi nie jestem do końca pewien.
Implementacja wyznaczania danych 3d z segmentacji zwracała mi ponad 40 brył, problem tylko polegał na tym
że bryły te w większości były niemal zupełnie identyczne. Uznałem że najprostszym rozwiązaniem będzie
jesli przeprowadze wykrycie duplikatów i nie będę ich wyświetlał 

"""

import math


def calculate_polydata_signature(polydata):
    """
    Oblicza "sygnaturę" obiektu polydata - zestaw metryk opisujących jego geometrię.
    
    Sygnatura to słownik zawierający kluczowe cechy obiektu 3D:
    - Liczba punktów (wierzchołków siatki)
    - Liczba komórek (trójkątów/wielokątów)
    - Objętość (przybliżona przez bounding box)
    - Granice przestrzenne (min/max w każdej osi)
    
    Ta "sygnatura" pozwala szybko sprawdzić czy dwa obiekty są podobne bez szczegółowego porównywania geometrii.
    
    Args:
        polydata: Obiekt vtkPolyData do analizy
        
    Returns:
        dict: Słownik z metrykami:
            - 'num_points': liczba wierzchołków (int)
            - 'num_cells': liczba komórek/trójkątów (int)
            - 'volume': przybliżona objętość (float)
            - 'bounds': tuple z 6 wartości (xmin, xmax, ymin, ymax, zmin, zmax)
    
    Przykład:
        >>> sig = calculate_polydata_signature(liver_polydata)
        >>> print(sig['num_points'])  # np. 15420
        >>> print(sig['volume'])      # np. 1250000.5
    """
    
    # 1: Pobierz podstawowe informacje o siatce 
    
    # Liczba punktów (wierzchołków) w siatce 3D
    num_points = polydata.GetNumberOfPoints()
    
    # Liczba poligonów
    num_cells = polydata.GetNumberOfCells()
    
    # 2: Pobierz granice przestrzenne (bounding box) 
    
    # GetBounds() zwraca tuple z 6 wartości:
    # (x_min, x_max, y_min, y_max, z_min, z_max)
    bounds = polydata.GetBounds()
    
    # 3: Oblicz przybliżoną objętość 
    
    # Obliczamy objętość bounding box'a jako przybliżenie objętości obiektu
    # To NIE jest dokładna objętość siatki, ale wystarcza do porównań
    #
    # Wymiary prostopadłościanu:
    # - szerokość (X): bounds[1] - bounds[0]
    # - głębokość (Y): bounds[3] - bounds[2]
    # - wysokość (Z): bounds[5] - bounds[4]
    volume = (bounds[1] - bounds[0]) * (bounds[3] - bounds[2]) * (bounds[5] - bounds[4])
    
    # 4: Zwróć wszystkie metryki jako słownik 
    
    return {
        'num_points': num_points,  # Rozdzielczość siatki
        'num_cells': num_cells,    # Liczba wielokątów
        'volume': volume,          # Rozmiar obiektu
        'bounds': bounds           # Położenie w przestrzeni
    }


def are_polydata_similar(sig1, sig2, threshold=0.90):
    """
    Sprawdza czy dwa obiekty są podobne na podstawie ich sygnatur.
    
    Funkcja porównuje dwie sygnatury (utworzone przez calculate_polydata_signature)
    i określa czy obiekty są wystarczająco podobne żeby uznać je za duplikaty.
    
    ALGORYTM PORÓWNANIA:
    1. Sprawdź czy żadna metryka nie jest zerowa (obiekty puste -> nie podobne)
    2. Oblicz stosunek dla każdej metryki (mniejsza/większa)
    3. Oblicz podobieństwo położenia (centra muszą być blisko siebie)
    4. Wszystkie metryki muszą być powyżej progu żeby uznać obiekty za podobne
    
    Args:
        sig1 (dict): Pierwsza sygnatura (z calculate_polydata_signature)
        sig2 (dict): Druga sygnatura (z calculate_polydata_signature)
        threshold (float): Próg podobieństwa 0.0-1.0 (domyślnie 0.90 = 90%)
            - 1.0 = obiekty muszą być identyczne
            - 0.9 = obiekty mogą różnić się o 10%
            - 0.5 = obiekty mogą różnić się o 50%
    
    Returns:
        bool: True jeśli obiekty są podobne, False w przeciwnym razie
    
    Przykład:
        >>> sig_liver1 = calculate_polydata_signature(polydata1)
        >>> sig_liver2 = calculate_polydata_signature(polydata2)
        >>> if are_polydata_similar(sig_liver1, sig_liver2, threshold=0.95):
        >>>     print("To prawdopodobnie ten sam obiekt!")
    """
    
    # 1: Sprawdź czy obiekty nie są puste 
    
    # Jeśli którykolwiek obiekt ma 0 punktów, od razu zwracamy False
    # (nie możemy porównywać pustych obiektów)
    if sig1['num_points'] == 0 or sig2['num_points'] == 0:
        return False
    
    # Analogicznie dla komórek
    if sig1['num_cells'] == 0 or sig2['num_cells'] == 0:
        return False
    
    # I dla objętości (choć teoretycznie objętość może być bliska 0 dla płaskich obiektów)
    if sig1['volume'] == 0 or sig2['volume'] == 0:
        return False
    
    # 2: Oblicz stosunek podobieństwa dla każdej metryki 
    
    # Stosunek punktów: zawsze dzielimy mniejszą przez większą
    # Wynik będzie w zakresie (0, 1], gdzie 1.0 = identyczna liczba punktów
    points_ratio = min(sig1['num_points'], sig2['num_points']) / max(sig1['num_points'], sig2['num_points'])
    
    # Analogicznie dla komórek
    cells_ratio = min(sig1['num_cells'], sig2['num_cells']) / max(sig1['num_cells'], sig2['num_cells'])
    
    # I dla objętości
    volume_ratio = min(sig1['volume'], sig2['volume']) / max(sig1['volume'], sig2['volume'])
    
    # 3: Porównaj położenie przestrzenne (centra obiektów) 
    
    bounds1 = sig1['bounds']
    bounds2 = sig2['bounds']
    
    # Oblicz środek bounding box'a dla każdego obiektu
    # Centrum to punkt (x_śr, y_śr, z_śr) w środku prostopadłościanu
    center1 = [
        (bounds1[0] + bounds1[1]) / 2,  # x_środek = (x_min + x_max) / 2
        (bounds1[2] + bounds1[3]) / 2,  # y_środek = (y_min + y_max) / 2
        (bounds1[4] + bounds1[5]) / 2   # z_środek = (z_min + z_max) / 2
    ]
    
    center2 = [
        (bounds2[0] + bounds2[1]) / 2,
        (bounds2[2] + bounds2[3]) / 2,
        (bounds2[4] + bounds2[5]) / 2
    ]
    
    # Oblicz odległość euklidesową między centrami
    # Wzór: sqrt((x1-x2)² + (y1-y2)² + (z1-z2)²)
    # zip(center1, center2) daje pary [(x1,x2), (y1,y2), (z1,z2)]
    center_dist = math.sqrt(sum((c1 - c2)**2 for c1, c2 in zip(center1, center2)))
    
    # Oblicz średni rozmiar obiektów (żeby znormalizować odległość)
    # Bierzemy średnią z szerokości, głębokości i wysokości obu obiektów
    avg_size = (
        abs(bounds1[1] - bounds1[0]) +  # szerokość obiektu 1
        abs(bounds1[3] - bounds1[2]) +  # głębokość obiektu 1
        abs(bounds1[5] - bounds1[4]) +  # wysokość obiektu 1
        abs(bounds2[1] - bounds2[0]) +  # szerokość obiektu 2
        abs(bounds2[3] - bounds2[2]) +  # głębokość obiektu 2
        abs(bounds2[5] - bounds2[4])    # wysokość obiektu 2
    ) / 6.0  # Dzielimy przez 6 bo mamy 6 wymiarów
    
    # Oblicz podobieństwo położenia (1.0 = idealne, 0.0 = bardzo daleko)
    # Jeśli avg_size == 0, obiekty są punktowe więc uznajemy za podobne
    if avg_size == 0:
        center_similarity = 1.0
    else:
        # Im mniejsza odległość względem rozmiaru, tym większe podobieństwo
        center_similarity = max(0, 1.0 - (center_dist / avg_size))
    
    # 4: Sprawdź czy wszystkie metryki są powyżej progu 
    if (points_ratio >= threshold and 
        cells_ratio >= threshold and 
        volume_ratio >= threshold and
        center_similarity >= 0.95):
        return True
    
    # Jeśli którakolwiek metryka jest poniżej progu, obiekty NIE są podobne
    return False
