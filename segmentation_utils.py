"""
Moduł do tworzenia modeli 3D z danych segmentacji medycznej.

Ten moduł przekształca takie dane segmentacji na wygładzone modele 3D
które można wyświetlić w przeglądarce VTK.

PROCES GENEROWANIA MODELU 3D:
1. Wykryj powierzchnię (contouring) - znajdź granicę etykiety
2. Wygładź powierzchnię (smoothing) - usuń ostre krawędzie i artefakty
3. Oblicz normalne (normals) - potrzebne do prawidłowego oświetlenia
4. Transformuj (transform) - dostosuj do układu współrzędnych sceny
5. Stwórz aktora (actor) - obiekt który można wyświetlić

WYKRYWANIE DUPLIKATÓW:
wykorzystywana jest geometry_utils.py do wykrywania i eliminacji duplikatów
"""

from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals, vtkSmoothPolyDataFilter, vtkContourFilter
from vtkmodules.vtkFiltersGeneral import vtkTransformPolyDataFilter
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

from geometry_utils import calculate_polydata_signature, are_polydata_similar


def create_segmentation_3d_model(label_reader, lut, renderer, mesh_actors_list, similarity_threshold=0.90):
    """
    Tworzy modele 3D ze wszystkich etykiet w danych segmentacji, pomijając duplikaty.
    
    Ta funkcja przetwarza plik z etykietami segmentacji i generuje osobny model 3D
    dla każdej unikalnej struktury anatomicznej.
    
    ALGORYTM:
    1. Usuń stare modele segmentacji (jeśli istnieją)
    2. Dla każdej etykiety (1, 2, 3, ... max):
       a) Wygeneruj powierzchnię metodą marching cubes (contouring)
       b) Wygładź powierzchnię filtrem Laplace'a
       c) Oblicz normalne do powierzchni
       d) Sprawdź czy to nie duplikat (porównaj z już przetworzonymi)
       e) Jeśli unikalny - dodaj do sceny
    
    Args:
        label_reader (vtkNrrdReader): Źródło danych z etykietami segmentacji
        lut (vtkLookupTable): Tablica kolorów do pokolorowania modeli
        renderer (vtkRenderer): Renderer do którego dodajemy wygenerowane modele
        mesh_actors_list (dict): Słownik z istniejącymi aktorami (do referencji)
        similarity_threshold (float): Próg podobieństwa do wykrywania duplikatów (0.0-1.0)
            - 0.90 (domyślnie) = obiekty o 90%+ podobieństwie to duplikaty
            - 1.0 = tylko identyczne obiekty
            - 0.0 = wyłącza wykrywanie duplikatów (przydatne do debugowania)
    
    Returns:
        list: Lista vtkActor z wygenerowanymi modelami 3D
        
    Side Effects:
        - Dodaje nowe aktory do renderera
        - Usuwa stare aktory segmentacji z renderera
        - Ustawia zakres clipping kamery
    
    Przykład:
        >>> actors = create_segmentation_3d_model(
        ...     label_reader, lut, renderer, {}, 
        ...     similarity_threshold=0.95
        ... )
        >>> print(f"Wygenerowano {len(actors)} unikalnych modeli")
    """
    
    # 1: Usuń stare modele segmentacji (jeśli istnieją)
    
    # Przechodzimy przez wszystkich aktorów w scenie
    for actor in list(renderer.GetActors()):
        # Sprawdzamy czy aktor ma flagę "_is_segmentation_3d"
        # (taką flagę ustawiamy na aktorach tworzonych przez tę funkcję)
        if hasattr(actor, "_is_segmentation_3d"):
            # Usuwamy stary model żeby nie nakładały się na siebie
            renderer.RemoveActor(actor)

    # 2: Przygotuj dane wejściowe
    
    # Upewnij się że dane są aktualne
    label_reader.Update()
    image_data = label_reader.GetOutput()
    
    # Sprawdź zakres wartości etykiet w danych
    # GetScalarRange() zwraca (min, max) wartości w obrazie
    scalar_min, scalar_max = image_data.GetScalarRange()

    # 3: Przygotuj struktury do przechowywania wyników
    
    # Lista na wygenerowane aktory (to będzie wynik funkcji)
    segmentation_actors = []
    
    # Lista na sygnatury już przetworzonych obiektów (do wykrywania duplikatów)
    # Każdy element to tuple: (numer_etykiety, sygnatura_geometrii)
    processed_signatures = []

    # 4: GŁÓWNA PĘTLA - przetwarzaj każdą etykietę
    
    # Pomijamy 0 (to zwykle tło), zaczynamy od 1
    for label in range(1, int(scalar_max) + 1):
        
        # 4a: Wykryj powierzchnię (contouring)
        
        # vtkContourFilter implementuje algorytm "marching cubes"
        # Znajduje powierzchnię między voxelami o różnych wartościach
        contour = vtkContourFilter()
        contour.SetInputConnection(label_reader.GetOutputPort())
        
        # SetValue(0, label) oznacza:
        # "Znajdź powierzchnię gdzie wartość = label"
        # 0 to indeks izolinii (możemy mieć wiele, ale tutaj tylko jedną)
        contour.SetValue(0, label)
        contour.Update()
        
        # Sprawdź czy contour nie jest pusty
        # Pusta siatka = ta etykieta nie istnieje w danych
        if contour.GetOutput().GetNumberOfPoints() == 0:
            continue  # Pomijamy i przechodzimy do następnej etykiety

        # 4b: Wygładź powierzchnię (smoothing)
        
        # vtkSmoothPolyDataFilter używa algorytmu Laplace'a
        # Przesuwa każdy wierzchołek w kierunku średniej pozycji sąsiadów
        smoother = vtkSmoothPolyDataFilter()
        smoother.SetInputConnection(contour.GetOutputPort())
        
        # Liczba iteracji - im więcej, tym gładszy model
        # 20 to dobry kompromis między gładkością a zachowaniem kształtu
        smoother.SetNumberOfIterations(20)
        
        # Współczynnik relaksacji (0.0 - 1.0)
        # Kontroluje jak bardzo wierzchołki mogą się przesuwać
        # 0.1 = konserwatywne wygładzanie, zachowuje szczegóły
        # 0.5 = agresywne, może zniekształcić model
        smoother.SetRelaxationFactor(0.1)
        
        # FeatureEdgeSmoothing = wygładzanie ostrych krawędzi
        # Wyłączamy bo chcemy zachować anatomiczne cechy (np. ostre załamania)
        smoother.FeatureEdgeSmoothingOff()
        
        # BoundarySmoothing = wygładzanie brzegów dziur w siatce
        # Włączamy bo pomaga zamknąć małe luki w segmentacji
        smoother.BoundarySmoothingOn()
        
        smoother.Update()

        # 4c: Sprawdź czy to nie duplikat
        
        # Oblicz "odcisk palca" geometryczny dla tego obiektu
        current_signature = calculate_polydata_signature(smoother.GetOutput())
        
        # Porównaj z wszystkimi już przetworzonymi obiektami
        is_duplicate = False
        for prev_label, prev_sig in processed_signatures:
            # Jeśli geometrie są bardzo podobne, to prawdopodobnie duplikat
            if are_polydata_similar(current_signature, prev_sig, similarity_threshold):
                is_duplicate = True
                break  # Nie musimy sprawdzać dalej
        
        # Jeśli to duplikat, pomijamy i idziemy dalej
        if is_duplicate:
            continue
        
        # To nie jest duplikat, zapisujemy sygnaturę na przyszłość
        processed_signatures.append((label, current_signature))

        # 4d: Oblicz normalne do powierzchni
        
        # Normalne to wektory prostopadłe do powierzchni
        # Są potrzebne do prawidłowego oświetlenia (shading) modelu
        normals = vtkPolyDataNormals()
        normals.SetInputConnection(smoother.GetOutputPort())
        
        # FeatureAngle określa kąt poniżej którego krawędź jest "gładka"
        # 60° = krawędzie ostrzejsze niż 60° będą miały wyraźne załamanie
        normals.SetFeatureAngle(60.0)
        
        # SplittingOff = nie rozdzielaj siatki na osobne kawałki
        # (nawet jeśli są ostre krawędzie)
        normals.SplittingOff()

        # 4e: Zastosuj transformację przestrzenną
        
        # Tworzymy transformację żeby dostosować model do układu sceny
        transform = vtkTransform()
        
        # Scale(1, -1, 1) = odbij lustrzanie względem osi Y
        # To jest potrzebne bo VTK i NRRD mają różne konwencje układu współrzędnych
        # UWAGA: Używamy (1,-1,1) a nie (1,-1,-1) jak dla slice'ów!
        # To dlatego że modele 3D wymagają innej orientacji niż płaszczyzny 2D
        transform.Scale(1, -1, 1)

        # Zastosuj transformację do geometrii
        tf = vtkTransformPolyDataFilter()
        tf.SetInputConnection(normals.GetOutputPort())
        tf.SetTransform(transform)
        tf.Update()

        # 4f: Stwórz mapper (konwerter geometria->obraz)
        
        # vtkPolyDataMapper konwertuje geometrię 3D na piksele 2D do wyświetlenia
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(tf.GetOutputPort())
        
        # ScalarVisibilityOff = nie koloruj według wartości w danych
        # (będziemy kolorować ręcznie według LUT)
        mapper.ScalarVisibilityOff()

        # 4g: Stwórz aktor (obiekt do wyświetlenia)
        
        actor = vtkActor()
        actor.SetMapper(mapper)
        
        # Pobierz kolor dla tej etykiety z LUT
        # GetTableValue zwraca (R, G, B, Alpha), bierzemy tylko RGB ([:3])
        color = lut.GetTableValue(label)[:3]
        actor.GetProperty().SetColor(color)
        
        # Właściwości materiału (PBR - Physically Based Rendering)
        
        # Opacity = nieprzezroczystość (0.0=przezroczysty, 1.0=nieprzezroczysty)
        actor.GetProperty().SetOpacity(0.9)  # 90% nieprzezroczysty
        
        # Ambient = oświetlenie otoczenia (światło które jest wszędzie)
        # 0.5 = 50% koloru pochodzi ze światła otoczenia
        actor.GetProperty().SetAmbient(0.5)
        
        # Specular = odbicia lustrzane (błyski światła)
        # 0.5 = średnie odbicia, model wygląda jak półmatowy plastik
        actor.GetProperty().SetSpecular(0.5)
        
        # SpecularPower = ostrość odbić (im wyższe, tym ostrzejsze błyski)
        # 50 = dość ostre odbicia, wygląda jak gładka powierzchnia
        actor.GetProperty().SetSpecularPower(50)

        # 4h: Oznacz aktor i dodaj do sceny
        
        # Dodajemy własne atrybuty do aktora (do późniejszej identyfikacji)
        actor._is_segmentation_3d = True  # Flaga że to model segmentacji
        actor._label_value = label        # Zapamiętaj numer etykiety

        # Dodaj aktor do renderera (teraz będzie widoczny w scenie)
        renderer.AddActor(actor)
        
        # Dodaj do listy zwracanych aktorów
        segmentation_actors.append(actor)

    # 5: Finalizacja
    
    # Zaktualizuj zakres clipping kamery
    # (potrzebne żeby wszystkie obiekty były widoczne)
    renderer.ResetCameraClippingRange()
    
    # Zwróć listę wygenerowanych aktorów
    return segmentation_actors

