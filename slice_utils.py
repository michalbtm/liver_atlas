"""
Moduł do tworzenia płaszczyzn przekroju (slice planes) z danych obrazowych 3D.

Ten moduł obsługuje trzy podstawowe orientacje anatomiczne:
- XY (aksjalny/poziomy) - patrząc od góry/dołu na ciało
- XZ (koronalny/czołowy) - patrząc od przodu/tyłu
- YZ (sagitalny/boczny) - patrząc z boku

TERMINOLOGIA MEDYCZNA:
- Superior/Inferior = góra/dół ciała
- Anterior/Posterior = przód/tył ciała  
- Left/Right = lewa/prawa strona pacjenta (nie nasza!)
"""

from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkImagingCore import vtkImageReslice, vtkImageMapToColors
from vtkmodules.vtkRenderingCore import vtkImageActor


def create_slice_plane(reader, label_reader, orientation, slice_num, lut):
    """
    Tworzy płaszczyznę przekroju (slice) z danych 3D z opcjonalną nakładką etykiet.
    
    Ta funkcja wykonuje "reslicing" - wycina 2D obraz z objętości 3D w określonej
    orientacji i pozycji. Dodatkowo może nałożyć kolorowe etykiety segmentacji.
    
    Argumenty:
        reader (vtkNrrdReader): Źródło danych obrazowych (CT/MRI w skali szarości)
        label_reader (vtkNrrdReader lub None): Źródło etykiet segmentacji (opcjonalne)
        orientation (str): Orientacja przekroju - 'XY', 'XZ' lub 'YZ'
        slice_num (int): Numer slice'a (względem środka objętości, może być ujemny)
        lut (vtkLookupTable): Tablica kolorów do mapowania etykiet
        
    Returns:
        tuple: (actor_gray, actor_labels, reslice, reslice_labels, orientation, transform)
            - actor_gray: Aktor VTK z obrazem w skali szarości
            - actor_labels: Aktor VTK z kolorowymi etykietami (lub None)
            - reslice: Filtr reslice dla obrazu w skali szarości
            - reslice_labels: Filtr reslice dla etykiet (lub None)
            - orientation: Zwrócona orientacja (ten sam co input)
            - transform: Transformacja przestrzenna użyta do pozycjonowania
    
    UWAGA: 
    Funkcja automatycznie stosuje transformacje żeby obraz był dobrze zorientowany
    w układzie współrzędnych VTK (System RAS - Right-Anterior-Superior).
    """
    
    #  1: Pobierz właściwości obrazu 3D
    
    # Upewnij się że dane są zaktualizowane
    reader.Update()
    image_data = reader.GetOutput()
    
    # Spacing - odstępy między voxelami w mm (rozdzielczość przestrzenna)
    # Przykład: (0.5, 0.5, 2.0) = 0.5mm w płaszczyźnie XY, 2mm między slice'ami
    spacing = image_data.GetSpacing()
    
    # Dimensions - rozmiar objętości w voxelach (szerokość, głębokość, wysokość)
    # Przykład: (512, 512, 200) = 512x512 pikseli na slice, 200 slice'ów
    dims = image_data.GetDimensions()
    
    #  2: Stwórz filtr reslice dla obrazu w skali szarości
    
    # vtkImageReslice to filtr który "wycina" 2D płaszczyznę z objętości 3D
    reslice = vtkImageReslice()
    reslice.SetInputConnection(reader.GetOutputPort())
    
    # Ustawiamy wymiarowość wyjściową na 2D (bo chcemy płaski obraz)
    # Domyślnie byłoby 3D
    reslice.SetOutputDimensionality(2)
    
    #  3: stwórz reslice dla etykiet segmentacji
    
    reslice_labels = None
    if label_reader:
        # Tworzymy osobny reslice dla etykiet (te same parametry co dla obrazu)
        reslice_labels = vtkImageReslice()
        reslice_labels.SetInputConnection(label_reader.GetOutputPort())
        reslice_labels.SetOutputDimensionality(2)
        
        reslice_labels.SetInterpolationModeToNearestNeighbor()
    
    #  4: Stwórz transformację przestrzenną
    
    # Transform określa jak obracamy i przesuwamy slice w przestrzeni 3D
    transform = vtkTransform()
    
    # Bazowa transformacja: odbijamy Y i Z (konwersja między układami współrzędnych)
    # Scale(1, -1, -1) oznacza: X bez zmian, Y i Z odbite lustrzanie
    # To jest potrzebne bo VTK używa innego układu niż DICOM/NRRD
    transform.Scale(1, -1, -1)
    
    #  5: Ustaw orientację i pozycję slice'a
    
    if orientation == 'XY':
        #======= PŁASZCZYZNA XY (AKSJALNA/POZIOMA)=======
        # Patrzymy wzdłuż osi Z (od góry lub dołu)
        
        # Direction cosines definiują orientację osi lokalnych slice'a
        # (1,0,0, 0,1,0, 0,0,1) = osie lokalne równoległe do globalnych
        direction_cosines = (1, 0, 0, 0, 1, 0, 0, 0, 1)
        reslice.SetResliceAxesDirectionCosines(*direction_cosines)
        if reslice_labels:
            reslice_labels.SetResliceAxesDirectionCosines(*direction_cosines)
        
        # Oblicz rzeczywistą pozycję Z w danych
        # slice_num jest względem środka, więc dodajemy dims[2]//2 żeby dostać indeks absolutny
        actual_slice = slice_num + dims[2] // 2
        
        # Przelicz indeks voxela na pozycję w mm (indeks * spacing)
        z_pos = actual_slice * spacing[2]
        
        # Ustaw początek układu współrzędnych slice'a
        reslice.SetResliceAxesOrigin(0, 0, z_pos)
        if reslice_labels:
            reslice_labels.SetResliceAxesOrigin(0, 0, z_pos)
        
        # Przesuń transform żeby slice był we właściwej pozycji
        # Minus bo mamy odbity układ współrzędnych
        transform.Translate(0, 0, -z_pos)
        
    elif orientation == 'XZ':
        #======= PŁASZCZYZNA XZ (KORONALNA/CZOŁOWA)=======
        # Patrzymy wzdłuż osi Y (od przodu lub tyłu)
        # Widok jak na zdjęcie rentgenowskie klatki piersiowej
        
        # Direction cosines: odbijamy X (dla lepszej orientacji anatomicznej)
        # Rotujemy osie żeby XZ było płaszczyzną widoku
        direction_cosines = (-1, 0, 0, 0, 0, 1, 0, 1, 0)
        reslice.SetResliceAxesDirectionCosines(*direction_cosines)
        if reslice_labels:
            reslice_labels.SetResliceAxesDirectionCosines(*direction_cosines)
        
        # Dla XZ używamy ujemnego slice_num (konwencja w naszych danych)
        actual_slice = -slice_num + dims[1] // 2
        y_pos = actual_slice * spacing[1]
        
        reslice.SetResliceAxesOrigin(0, y_pos, 0)
        if reslice_labels:
            reslice_labels.SetResliceAxesOrigin(0, y_pos, 0)
        
        # Rotacje żeby wyświetlić w odpowiedniej orientacji
        # Najpierw obracamy o 90° wokół X (żeby Z wskazywało w górę)
        transform.RotateX(90)
        # Potem obracamy o 180° wokół Z (żeby lewa/prawa strona była poprawna)
        transform.RotateZ(180)
        # Na koniec przesuwamy do właściwej pozycji Y
        transform.Translate(0, 0, -y_pos)
        
    elif orientation == 'YZ':
        #======= PŁASZCZYZNA YZ (SAGITALNA/BOCZNA)=======
        # Patrzymy wzdłuż osi X (z boku)
        # Widok profilu ciała
        
        # Direction cosines dla płaszczyzny YZ
        direction_cosines = (0, 1, 0, 0, 0, 1, 1, 0, 0)
        reslice.SetResliceAxesDirectionCosines(*direction_cosines)
        if reslice_labels:
            reslice_labels.SetResliceAxesDirectionCosines(*direction_cosines)
        
        actual_slice = slice_num + dims[0] // 2
        x_pos = actual_slice * spacing[0]
        
        reslice.SetResliceAxesOrigin(x_pos, 0, 0)
        if reslice_labels:
            reslice_labels.SetResliceAxesOrigin(x_pos, 0, 0)
        
        # Rotacje dla widoku sagitalnego
        # -90° wokół Y (obracamy z widoku przedniego na boczny)
        transform.RotateY(-90)
        # 90° wokół Z (żeby góra była na górze)
        transform.RotateZ(90)
        # Przesunięcie do właściwej pozycji X
        transform.Translate(0, 0, -x_pos)
    
    #  6: Wykonaj reslicing (wygeneruj obrazy 2d)
    
    # Update() wymusza obliczenie - bez tego mamy tylko pipeline bez danych
    reslice.Update()
    if reslice_labels:
        reslice_labels.Update()
    
    #  7: Stwórz aktora dla obrazu w skali szarości
    
    # vtkImageActor to obiekt który potrafi wyświetlić 2D obraz w scenie 3D
    actor_gray = vtkImageActor()
    
    # Podłączamy wyjście z reslice jako źródło danych dla aktora
    actor_gray.GetMapper().SetInputConnection(reslice.GetOutputPort())
    
    # Stosujemy transformację przestrzenną (rotacje i przesunięcia)
    actor_gray.SetUserTransform(transform)
    
    # Ustawiamy przezroczystość - 0.7 = 70% nieprzezroczystości
    # Dzięki temu możemy widzieć obiekty 3D "przez" slice
    actor_gray.SetOpacity(0.7)
    
    #  8: Opcjonalnie stwórz aktor dla kolorowych etykiet
    
    actor_labels = None
    if reslice_labels:
        # vtkImageMapToColors zamienia wartości liczbowe (etykiety) na kolory
        # używając lookup table (LUT)
        map_to_colors = vtkImageMapToColors()
        map_to_colors.SetInputConnection(reslice_labels.GetOutputPort())
        map_to_colors.SetLookupTable(lut)
        
        # Ustawiamy format wyjściowy na RGBA (Red-Green-Blue-Alpha)
        # Alpha = kanał przezroczystości, potrzebny żeby tło było przezroczyste
        map_to_colors.SetOutputFormatToRGBA()
        
        # PassAlphaToOutput = przepuść informację o przezroczystości z LUT
        # Dzięki temu tło (wartość 0) będzie przezroczyste
        map_to_colors.PassAlphaToOutputOn()
        map_to_colors.SetPassAlphaToOutput(1)
        
        # Generujemy kolorowy obraz
        map_to_colors.Update()

        # Tworzymy aktor dla etykiet
        actor_labels = vtkImageActor()
        actor_labels.GetMapper().SetInputConnection(map_to_colors.GetOutputPort())
        actor_labels.SetUserTransform(transform)  # Ta sama transformacja co obraz szarościowy
        
        # Etykiety są w pełni nieprzezroczyste (ale tło jest przezroczyste dzięki Alpha)
        actor_labels.SetOpacity(1.0)
        
        # Wyłączamy interpolację dla etykiet - chcemy ostre krawędzie
        # Interpolacja rozmywałaby granice między różnymi strukturami
        actor_labels.InterpolateOff()
    
    #  9: Zwróć wszystko co może być potrzebne
    
    # Zwracamy aktory (do wyświetlenia), filtry (do aktualizacji) i transformację
    return actor_gray, actor_labels, reslice, reslice_labels, orientation, transform
