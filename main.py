#!/usr/bin/env python3
"""
Główny plik aplikacji.
Ten skrypt:
1. Wczytuje konfigurację z pliku JSON
2. Ładuje dane medyczne (obrazy NRRD i mesh'e VTK)
3. Tworzy okno z wizualizacją 3D
4. Dodaje interaktywne elementy (suwaki, slice'y)
5. Obsługuje interakcję użytkownika

ARCHITEKTURA APLIKACJI:
- Używamy wzorca MVC (Model-View-Controller):
  - Model: Dane medyczne (NRRD, VTK)
  - View: Renderer VTK + okno
  - Controller: Callbacki obsługujące input użytkownika

BIBLIOTEKI:
- VTK: Wizualizacja 3D, rendering, interakcja
- pathlib: Obsługa ścieżek do plików
- Własne moduły: config, lut_utils, slice_utils, callbacks, file_utils, callbacks, geometry_utils, 
orientation_widgets, segmentation_utils, slider_widgets, transformations

SKRÓTY KLAWISZOWE:
- N: Pokaż/ukryj suwaki
- L: Pokaż/ukryj etykiety na slice'ach, 
- M: Przełącz tryb wyświetlania (Normal/Wireframe/Transparent/3D Segmentation)
- Mysz: Obracanie kamery (lewy), zoom (prawy), panning (środkowy)

WYMAGANIA SYSTEMOWE:
- Python 3.7+
- VTK 9.0+
- Pliki danych: JSON, NRRD, VTK (ścieżki ustawia się w config.py)
"""

from pathlib import Path

# IMPORTY VTK (biblioteka wizualizacji 3D)
import vtkmodules.vtkInteractionStyle
import vtkmodules.vtkRenderingOpenGL2
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonCore import vtkCommand
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals
from vtkmodules.vtkFiltersGeneral import vtkTransformPolyDataFilter
from vtkmodules.vtkIOImage import vtkNrrdReader
from vtkmodules.vtkIOLegacy import vtkPolyDataReader
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkInteractionWidgets import (
    vtkCameraOrientationWidget,
    vtkOrientationMarkerWidget
)
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
    vtkRenderer
)

#  IMPORT Z MOICH MODUŁÓW 
from config import (
    NRRD_FILE_PATH, NRRD_LABELS_PATH, JSON_PATH,
    top_y, step_y, right_x0_col1, right_x1_col1, right_x0_col2, right_x1_col2
)
from lut_utils import create_visible_all_lut
from slice_utils import create_slice_plane
from slider_widgets import SliderProperties, make_slider_widget, make_slice_slider
from callbacks import SliderCallback, SlicePlaneCallback, SliderToggleCallback
from transforms import SliceOrder
from orientation_widgets import make_cube_actor
from file_utils import parse_json, resolve_vtk_file


def main():
    """
    Główna funkcja aplikacji - inicjalizuje wszystko i uruchamia pętlę zdarzeń.
    
    PROCES INICJALIZACJI:
    1. Wczytaj konfigurację z JSON
    2. Stwórz okno renderowania VTK
    3. Załaduj i wyświetl dane obrazowe (NRRD)
    4. Stwórz płaszczyzny przekroju (slice planes)
    5. Dodaj suwaki do kontroli slice'ów
    6. Załaduj i wyświetl mesh'e anatomiczne (VTK)
    7. Dodaj suwaki do kontroli przezroczystości mesh'y
    8. Skonfiguruj kamerę i oświetlenie
    9. Dodaj widgety orientacji
    10. Uruchom pętlę zdarzeń (aplikacja czeka na input użytkownika)
    
    BŁĘDY:
    Funkcja może zakończyć się wcześniej jeśli:
    - Plik JSON jest niepoprawny
    - Brakuje wymaganych plików danych
    - Pliki są uszkodzone lub w złym formacie
    """
    
    # 1: WCZYTAJ KONFIGURACJĘ
    
    # Wczytaj plik JSON z konfiguracją atlasu
    ok, params = parse_json(Path(JSON_PATH))
    
    # Jeśli parsowanie się nie powiodło, zakończ
    if not ok:
        print("BŁĄD: Nie udało się wczytać konfiguracji JSON")
        return
    
    # Pobierz listę tkanek do wyświetlenia
    tissues = params['names']
    
    # 2: STWÓRZ LOOKUP TABLE (mapowanie wartości na kolory)
    # LUT przypisuje kolory do wartości liczbowych (etykiet segmentacji)
    lut = create_visible_all_lut()

    
    # 3: STWÓRZ RENDERER (odpowiada za renderowanie sceny 3D)  
    ren = vtkRenderer()
  
    # 4: STWÓRZ OKNO RENDEROWANIA
    # vtkRenderWindow to okno w którym widzimy wizualizację
    win = vtkRenderWindow()
    win.AddRenderer(ren)  # Podłącz renderer do okna

    
    # 5: STWÓRZ INTERACTOR (obsługuje input z klawiatury i myszy)
    iren = vtkRenderWindowInteractor()
    iren.SetRenderWindow(win) 
    # Ustaw styl interakcji - "trackball camera" pozwala swobodnie obracać kamerą
    iren.SetInteractorStyle(vtkInteractorStyleTrackballCamera())

    
    # 6: PRZYGOTUJ STRUKTURY DANYCH
    # Słowniki na suwaki i aktory
    sliders = {}                   # Suwaki kontrolujące opacity i pozycję slice'ów
    slice_actors_gray = {}         # Aktory z obrazami slice'ów (szare)
    slice_actors_labels = {}       # Aktory z etykietami na slice'ach (kolorowe)
    slice_transforms = {}          # Transformacje przestrzenne dla slice'ów
    
    # Readery dla danych obrazowych
    nrrd_reader = None            # Reader dla obrazu CT/MRI
    label_reader = None           # Reader dla etykiet segmentacji

    
    # 7: ZAŁADUJ DANE OBRAZOWE (NRRD)
    # Sprawdź czy plik NRRD istnieje
    if NRRD_FILE_PATH and Path(NRRD_FILE_PATH).exists():
        
        # 7a: Załaduj główny obraz (CT/MRI)
        nrrd_reader = vtkNrrdReader()
        nrrd_reader.SetFileName(NRRD_FILE_PATH)
        nrrd_reader.Update()
        
        # 7b: Załaduj etykiety segmentacji
        if NRRD_LABELS_PATH and Path(NRRD_LABELS_PATH).exists():
            label_reader = vtkNrrdReader()
            label_reader.SetFileName(NRRD_LABELS_PATH)
            label_reader.Update()    
        
        # 7c: Pobierz wymiary obrazu
        dims = nrrd_reader.GetOutput().GetDimensions()
        
        # 7d: Stwórz trzy płaszczyzny przekroju (XY, XZ, YZ)
        
        # XY (aksjalna/pozioma)
        gray_xy, labels_xy, _, _, _, transforms_xy = create_slice_plane(
            nrrd_reader, label_reader, 'XY', -50, lut)
        
        # XZ (koronalna/czołowa)
        gray_xz, labels_xz, _, _, _, transforms_xz = create_slice_plane(
            nrrd_reader, label_reader, 'XZ', dims[1] // 2, lut)
        
        # YZ (sagitalna/boczna)
        gray_yz, labels_yz, _, _, _, transforms_yz = create_slice_plane(
            nrrd_reader, label_reader, 'YZ', -dims[0] // 2, lut)
        
        # Zapisz aktory i transformacje w słownikach (dla łatwego dostępu)
        slice_actors_gray = {'XY': gray_xy, 'XZ': gray_xz, 'YZ': gray_yz}
        slice_actors_labels = {'XY': labels_xy, 'XZ': labels_xz, 'YZ': labels_yz}
        slice_transforms = {'XY': transforms_xy, 'XZ': transforms_xz, 'YZ': transforms_yz}
        
        # 7e: Dodaj aktorów do sceny
        
        # Dodaj obrazy w skali szarości
        for actor in slice_actors_gray.values():
            ren.AddActor(actor)
        
        # Dodaj etykiety 
        if label_reader:
            for actor in slice_actors_labels.values():
                if actor:  # Sprawdź czy aktor istnieje 
                    ren.AddActor(actor)
        
        # 7f: Stwórz suwaki do kontroli pozycji slice'ów
        
        # Suwaki będą na dole ekranu, obok siebie
        sp = SliderProperties()
        
        # Suwak Z (płaszczyzna XY)
        sp.p1 = [0.25, 0.05]  # Początek suwaka (dolny środek ekranu)
        sp.p2 = [0.40, 0.05]  # Koniec suwaka
        sw_xy = make_slice_slider(sp, -dims[2], dims[2] // 2, -50, "Z Slice")
        sw_xy.SetInteractor(iren)
        sw_xy.EnabledOn()
        # Callback który będzie wywoływany gdy użytkownik przesuwa suwak
        callback_xy = SlicePlaneCallback(nrrd_reader, label_reader, 
            slice_actors_gray['XY'], slice_actors_labels['XY'], 'XY', slice_transforms['XY'], lut)
        sw_xy.AddObserver(vtkCommand.InteractionEvent, callback_xy)
        sliders['Z Slice'] = sw_xy
        
        # Suwak Y (płaszczyzna XZ)
        sp.p1 = [0.42, 0.05]
        sp.p2 = [0.57, 0.05]
        sw_xz = make_slice_slider(sp, 0, dims[1], dims[1] // 2, "Y Slice")
        sw_xz.SetInteractor(iren)
        sw_xz.EnabledOn()
        callback_xz = SlicePlaneCallback(nrrd_reader, label_reader, 
            slice_actors_gray['XZ'], slice_actors_labels['XZ'], 'XZ', slice_transforms['XZ'], lut)
        sw_xz.AddObserver(vtkCommand.InteractionEvent, callback_xz)
        sliders['Y Slice'] = sw_xz
        
        # Suwak X (płaszczyzna YZ)
        sp.p1 = [0.59, 0.05]
        sp.p2 = [0.74, 0.05]
        sw_yz = make_slice_slider(sp, -dims[0], 0, -dims[0] // 2, "X Slice")
        sw_yz.SetInteractor(iren)
        sw_yz.EnabledOn()
        callback_yz = SlicePlaneCallback(nrrd_reader, label_reader, 
            slice_actors_gray['YZ'], slice_actors_labels['YZ'], 'YZ', slice_transforms['YZ'], lut)
        sw_yz.AddObserver(vtkCommand.InteractionEvent, callback_yz)
        sliders['X Slice'] = sw_yz
        
        # 7g: Zainicjalizuj slice'y (wywołaj callbacki raz)
        # To ustawia początkowe pozycje slice'ów
        callback_xy(sw_xy, None)
        callback_xz(sw_xz, None)
        callback_yz(sw_yz, None)
    
    
    # 8: ZAŁADUJ MESH'E ANATOMICZNE (pliki VTK)
    
    
    mesh_actors_list = {}  # Słownik przechowujący aktorów
    
    # Dla każdej tkanki z listy
    for idx, tissue in enumerate(tissues):
        
        # 8a: Wczytaj plik VTK
        reader = vtkPolyDataReader()
        vtk_path = resolve_vtk_file(tissue, params['vtk_files'])
        reader.SetFileName(str(vtk_path))
        reader.Update()

        # 8b: Zastosuj transformację orientacji
        # Dane mogą być zapisane w różnych układach współrzędnych
        # Transformacja dopasowuje je do układu
        trans = SliceOrder().get(params['orientation'][tissue])
        trans.Scale(1, -1, -1)  # Dodatkowo odbijamy Y i Z

        # Zastosuj transformację do geometrii
        tf = vtkTransformPolyDataFilter()
        tf.SetInputConnection(reader.GetOutputPort())
        tf.SetTransform(trans)

        # 8c: Oblicz normale (dla prawidłowego oświetlenia)
        normals = vtkPolyDataNormals()
        normals.SetInputConnection(tf.GetOutputPort())

        # 8d: Stwórz mapper (konwertuje geometrię na piksele)
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())

        # 8e: Stwórz aktor (obiekt do wyświetlenia)
        actor = vtkActor()
        actor.SetMapper(mapper)
        
        # Ustaw przezroczystość z konfiguracji
        actor.GetProperty().SetOpacity(params['opacity'][tissue])
        
        # Ustaw kolor z LUT (według indeksu z konfiguracji)
        actor.GetProperty().SetDiffuseColor(lut.GetTableValue(params['indices'][tissue])[:3])
        
        # Dodaj do sceny
        ren.AddActor(actor)

        # Zapisz w słowniku (potrzebne do callbacków)
        mesh_actors_list[tissue] = actor

        # 8f: Stwórz suwak do kontroli przezroczystości
        
        sp = SliderProperties()
        sp.title = tissue  # Nazwa tkanki jako tytuł

        # Oblicz pozycję suwaka (układ w dwie kolumny)
        col = idx % 2        # Kolumna: 0 lub 1
        row = idx // 2       # Rząd: 0, 1, 2, ...
        y = top_y - row * step_y  # Pozycja Y

        # Ustaw współrzędne w zależności od kolumny
        if col == 0:
            sp.p1 = [right_x0_col1, y]
            sp.p2 = [right_x1_col1, y]
        else:
            sp.p1 = [right_x0_col2, y]
            sp.p2 = [right_x1_col2, y]

        # Stwórz widget suwaka
        sw = make_slider_widget(sp, lut, params['indices'][tissue])
        sw.SetInteractor(iren)
        sw.EnabledOn()
        
        # Podłącz callback (zmiana opacity gdy użytkownik przesuwa suwak)
        sw.AddObserver(vtkCommand.InteractionEvent, SliderCallback(actor.GetProperty()))
        
        # Zapisz w słowniku
        sliders[tissue] = sw

    
    # 9: KONFIGURACJA SCENY (tło, rozmiar okna)
    
    
    # Ustaw kolor tła (SlateGray = ciemnoszary, profesjonalnie wygląda)
    ren.SetBackground(vtkNamedColors().GetColor3d('SlateGray'))
    
    # Ustaw rozmiar okna w pikselach
    win.SetSize(1400, 1000)  # Szerokość x wysokość
    
    # Ustaw tytuł okna (widoczny na pasku tytułu)
    win.SetWindowName('Liver Atlas Viewer')

    
    # 10: DODAJ WIDGETY ORIENTACJI
    
    
    # 10a: Widget orientacji kamery (nowoczesny, w rogu górnym)
    cow = vtkCameraOrientationWidget()
    cow.SetParentRenderer(ren)
    cow.On()

    # 10b: Marker orientacji (kostka + osie, w rogu dolnym)
    om = vtkOrientationMarkerWidget()
    om.SetOrientationMarker(make_cube_actor('rsp', vtkNamedColors()))
    om.SetInteractor(iren)
    om.SetViewport(0, 0, 0.2, 0.2)  # Lewy dolny róg, 20% rozmiaru
    om.EnabledOn()

    
    # 11: KONFIGURACJA KAMERY (widok początkowy)
    
    
    # Zresetuj kamerę żeby wszystko było widoczne
    ren.ResetCamera()
    
    # Pobierz kamerę (żeby ją ręcznie dostroić)
    camera = ren.GetActiveCamera()
    
    # Przesuń focal point (punkt na który patrzy kamera) i pozycję kamery w X
    fp = list(camera.GetFocalPoint())
    pos = list(camera.GetPosition())
    fp[0] += 130   # Focal point w prawo
    pos[0] += 130  # Kamera w prawo
    camera.SetFocalPoint(fp)
    camera.SetPosition(pos)
    
    # Zaktualizuj zakres clipping (żeby wszystko było widoczne)
    ren.ResetCameraClippingRange()
    
    # Dodatkowo przesuń kamerę
    pos = list(camera.GetPosition())
    pos[0] -= 150  # W lewo
    pos[2] -= 50   # W dół
    camera.SetPosition(pos)
    
    # Dolly = zoom (0.9 = lekko oddal)
    camera.Dolly(0.9)

    # Ustaw kamerę na widok od dołu (patrząc w górę)
    fp = camera.GetFocalPoint()
    dist = camera.GetDistance()
    camera.SetPosition(fp[0], fp[1] - dist, fp[2])  # Pozycja pod focal point
    camera.SetViewUp(0, 0, 1)  # Z w górę

    # Ostateczna aktualizacja clipping range
    ren.ResetCameraClippingRange()

    
    # 12: PODŁĄCZ CALLBACK DO KLAWISZY  
    # SliderToggleCallback obsługuje skróty klawiszowe (N, L, M)
    iren.AddObserver('KeyPressEvent', SliderToggleCallback(
        sliders,                                      # Wszystkie suwaki
        slice_actors_labels if label_reader else {}, # Etykiety slice'ów
        mesh_actors_list,                             # Mesh'e anatomiczne
        label_reader,                                 # Reader etykiet (dla 3D)
        ren,                                          # Renderer
        lut,                                          # Lookup table
        iren                                          # Interactor
    ))

    
    # 13: URUCHOM APLIKACJĘ (pętla zdarzeń)
    # Narysuj scenę pierwszy raz
    win.Render() 
    # Uruchom pętlę zdarzeń - aplikacja będzie działać dopóki użytkownik
    # nie zamknie okna lub nie naciśnie 'q'
    iren.Start()


# PUNKT WEJŚCIA PROGRAMU
if __name__ == '__main__':
    # Ten blok wykonuje się tylko gdy plik jest uruchamiany bezpośrednio    
    main()
