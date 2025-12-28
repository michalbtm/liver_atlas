"""
Moduł z callbackami VTK - funkcjami wywoływanymi w odpowiedzi na zdarzenia użytkownika.

W programowaniu GUI callback to funkcja która jest wywoływana automatycznie
gdy coś się wydarzy (kliknięcie myszką, naciśnięcie klawisza, przesunięcie suwaka).

VTK używa wzorca Observer - rejestrujemy callback mówiąc "gdy się stanie X, wywołaj Y".
Przykład: widget.AddObserver('InteractionEvent', moj_callback)

Ten moduł zawiera trzy główne typy callbacków:
1. SliderCallback - reaguje na przesunięcie suwaka (zmienia przezroczystość)
2. SlicePlaneCallback - reaguje na zmianę pozycji slice'a (przesuwa płaszczyznę)
3. SliderToggleCallback - reaguje na klawisze (przełącza tryby wyświetlania)

WZORZEC CALLABLE:
Wszystkie callbacki są klasami z metodą __call__(), co pozwala używać ich jak funkcji.
Dzięki temu możemy przechowywać stan (self.xxx) między wywołaniami.
"""

from vtkmodules.vtkCommonCore import vtkCommand
from vtkmodules.vtkImagingCore import vtkImageReslice, vtkImageMapToColors

from config import top_y, step_y, right_x0_col1, right_x1_col1, right_x0_col2, right_x1_col2
from slider_widgets import SliderProperties, make_slider_widget_with_color
from segmentation_utils import create_segmentation_3d_model


class SliderCallback:
    """
    Callback dla suwaków kontrolujących przezroczystość obiektów.
    
    Ten prosty callback zmienia przezroczystość materiału aktora 3D
    zgodnie z pozycją suwaka. Jest używany dla wszystkich suwaków tkanek
    i modeli segmentacji.
    
    DZIAŁANIE:
    1. Użytkownik przesuwa suwak
    2. VTK wywołuje __call__ przekazując widget jako 'caller'
    3. Odczytujemy wartość z suwaka (0.0 - 1.0)
    4. Ustawiamy opacity materiału aktora
    5. Aktor jest automatycznie przerysowywany
    
    Atrybuty:
        actor_property (vtkProperty): Właściwości materiału aktora do modyfikacji
    """
    
    def __init__(self, actor_property):
        """
        Inicjalizuje callback z referencją do właściwości aktora.
        
        Argumenty:
            actor_property (vtkProperty): Obiekt reprezentujący materiał aktora 3D.
                Zwykle pobierany przez actor.GetProperty()
        
        Zapamiętujemy referencję do właściwości materiału, Dzięki temu możemy je modyfikować z poziomu __call__
        """
        self.actor_property = actor_property

    def __call__(self, caller, ev):
        """
        Wywoływane automatycznie gdy użytkownik przesuwa suwak.
        
        Argumenty:
            caller: Widget suwaka który wywołał callback (vtkSliderWidget)
            ev: Typ zdarzenia (string, np. 'InteractionEvent')
                W praktyce ignorujemy ten parametr bo wiemy że to suwak
        """
        # Pobierz aktualną wartość z suwaka
        # GetRepresentation() zwraca vtkSliderRepresentation2D
        # GetValue() zwraca float w zakresie min-max (zazwyczaj 0.0-1.0)
        value = caller.GetRepresentation().GetValue()
        
        # Ustaw nową przezroczystość materiału
        # 0.0 = całkowicie przezroczysty (niewidoczny)
        # 1.0 = całkowicie nieprzezroczysty (widoczny w pełni)
        self.actor_property.SetOpacity(value)
        
        # VTK odświeża widok automatycznie


class SlicePlaneCallback:
    """
    Callback dla suwaków kontrolujących pozycję płaszczyzn przekroju (slice planes).
    
    Ten bardziej skomplikowany callback regeneruje płaszczyznę przekroju gdy użytkownik
    przesuwa suwak. Musi wykonać reslicing (wycięcie 2D z objętości 3D) zarówno dla
    obrazu w skali szarości jak i dla kolorowych etykiet segmentacji.
    
    PROCES :
    1. Użytkownik przesuwa suwak X/Y/Z Slice
    2. Odczytujemy nową pozycję (numer slice'a)
    3. Tworzymy nowe filtry reslice z zaktualizowaną pozycją
    4. Obliczamy nową transformację przestrzenną (rotacje + przesunięcie)
    5. Generujemy nowe obrazy 2D (szary + etykiety)
    6. Aktualizujemy aktory żeby wyświetlały nowe obrazy
    
    Atrybuty:
        reader (vtkNrrdReader): Źródło danych obrazowych (CT/MRI)
        label_reader (vtkNrrdReader): Źródło etykiet segmentacji
        image_actor_gray (vtkImageActor): Aktor wyświetlający obraz w sakli szarości
        image_actor_labels (vtkImageActor): Aktor wyświetlający etykiety
        orientation (str): Orientacja płaszczyzny ('XY', 'XZ', lub 'YZ')
        transform (vtkTransform): Transformacja przestrzenna płaszczyzny
        lut (vtkLookupTable): Tablica kolorów dla etykiet
        spacing (tuple): Odstępy między voxelami w mm
        origin (tuple): Punkt odniesienia w przestrzeni
        dims (tuple): Rozmiary objętości w voxelach (
    """
    
    def __init__(self, reader, label_reader, image_actor_gray, image_actor_labels, 
                 orientation, transform, lut):
        """
        Inicjalizuje callback z wszystkimi potrzebnymi obiektami VTK.
        
        Argumenty:
            reader: Reader z danymi obrazowymi (szare)
            label_reader: Reader z etykietami 
            image_actor_gray: Aktor do wyświetlania obrazu w skali szarości
            image_actor_labels: Aktor do wyświetlania etykiet 
            orientation: 'XY', 'XZ' lub 'YZ'
            transform: Transformacja przestrzenna do aktualizacji
            lut: Lookup table dla kolorowania etykiet
        """
        # Zapamiętaj wszystkie obiekty (będziemy ich potrzebować w __call__)
        self.reader = reader
        self.label_reader = label_reader
        self.image_actor_gray = image_actor_gray
        self.image_actor_labels = image_actor_labels
        self.orientation = orientation
        self.transform = transform
        self.lut = lut
        
        #Pobierz właściwości geometryczne obrazu
        
        # Upewnij się że dane są zaktualizowane
        self.reader.Update()
        image_data = self.reader.GetOutput()
        
        # Spacing - odstępy między voxelami w mm (rozdzielczość przestrzenna)
        # Przykład: (0.5, 0.5, 2.0) = 0.5mm w XY, 2mm między slice'ami
        self.spacing = image_data.GetSpacing()
        
        # Origin - punkt odniesienia (zazwyczaj 0,0,0 lub centrum skanera)
        self.origin = image_data.GetOrigin()
        
        # Dimensions - rozmiar objętości w voxelach
        # Przykład: (512, 512, 200) = 512x512 pikseli, 200 slice'ów
        self.dims = image_data.GetDimensions()
        
    def __call__(self, caller, ev):
        """
        Wywoływane gdy użytkownik przesuwa suwak pozycji slice'a.
        
        Regeneruje całą płaszczyznę przekroju w nowej pozycji.
        
        Argumenty:
            caller: Widget suwaka (vtkSliderWidget)
            ev: Typ zdarzenia
        """
        
        # 1: Odczytaj nową pozycję sliców
        
        # Pobierz wartość z suwaka i zamień na int (numery slice'ów to floaty)
        value = int(caller.GetRepresentation().GetValue())
        
        # 2: Stwórz nowy filtr reslice dla obrazu szarościowego
        
        reslice = vtkImageReslice()
        reslice.SetInputConnection(self.reader.GetOutputPort())
        # Wymiar wyjściowy = 2D (płaski obraz, nie objętość)
        reslice.SetOutputDimensionality(2)
        
        # 3: stwórz reslice dla etykiet
        
        reslice_labels = None
        if self.label_reader:
            reslice_labels = vtkImageReslice()
            reslice_labels.SetInputConnection(self.label_reader.GetOutputPort())
            reslice_labels.SetOutputDimensionality(2)
            # Etykiety interpolujemy metodą najbliższego sąsiada
            reslice_labels.SetInterpolationModeToNearestNeighbor()
        
        # 4: Zresetuj transformację 
        
        # Zacznij od czystej transformacji (jednostkowa macierz)
        self.transform.Identity()
        # Zastosuj bazowe odbicie lustrzane (konwersja układów współrzędnych)
        self.transform.Scale(1, -1, -1)
        
        # 5: Ustaw orientację i pozycję w zależności od typu płaszczyzny 
        
        if self.orientation == 'XY':
            # PŁASZCZYZNA XY 
            # Patrzymy wzdłuż osi Z (od góry lub dołu ciała)
            
            # Direction cosines - osie lokalne równoległe do globalnych
            direction_cosines = (1, 0, 0, 0, 1, 0, 0, 0, 1)
            reslice.SetResliceAxesDirectionCosines(*direction_cosines)
            if reslice_labels:
                reslice_labels.SetResliceAxesDirectionCosines(*direction_cosines)
            
            # Przelicz numer slice'a na indeks absolutny
            # value jest względem środka, więc dodajemy połowę wymiaru
            actual_slice = value + self.dims[2] // 2
            
            # Przelicz indeks na pozycję w mm
            z_pos = actual_slice * self.spacing[2]
            
            # Ustaw punkt odniesienia dla płaszczyzny reslice
            reslice.SetResliceAxesOrigin(0, 0, z_pos)
            if reslice_labels:
                reslice_labels.SetResliceAxesOrigin(0, 0, z_pos)
            
            # Zaktualizuj transformację (przesunięcie w Z)
            self.transform.Translate(0, 0, -z_pos)
            
        elif self.orientation == 'XZ':
            # PŁASZCZYZNA XZ 
            # Patrzymy wzdłuż osi Y (od przodu lub tyłu)
            
            # Direction cosines z odbiciem X (dla lepszej anatomicznej orientacji)
            direction_cosines = (-1, 0, 0, 0, 0, 1, 0, 1, 0)
            reslice.SetResliceAxesDirectionCosines(*direction_cosines)
            if reslice_labels:
                reslice_labels.SetResliceAxesDirectionCosines(*direction_cosines)
            
            # Dla XZ używamy ujemnego value (taką konwencje przyjłem dla ładniejszego wyświetlania się danych)
            actual_slice = -value + self.dims[1] // 2
            y_pos = actual_slice * self.spacing[1]
            
            reslice.SetResliceAxesOrigin(0, y_pos, 0)
            if reslice_labels:
                reslice_labels.SetResliceAxesOrigin(0, y_pos, 0)
            
            # Rotacje dla prawidłowej orientacji anatomicznej
            self.transform.RotateX(90)   # Obróć żeby Z wskazywało w górę
            self.transform.RotateZ(180)  # Obróć dla lewej/prawej strony
            self.transform.Translate(0, 0, -y_pos)
            
        elif self.orientation == 'YZ':
            # PŁASZCZYZNA YZ 
            # Patrzymy wzdłuż osi X (z boku ciała)
            
            direction_cosines = (0, 1, 0, 0, 0, 1, 1, 0, 0)
            reslice.SetResliceAxesDirectionCosines(*direction_cosines)
            if reslice_labels:
                reslice_labels.SetResliceAxesDirectionCosines(*direction_cosines)
            
            actual_slice = value + self.dims[0] // 2
            x_pos = actual_slice * self.spacing[0]
            
            reslice.SetResliceAxesOrigin(x_pos, 0, 0)
            if reslice_labels:
                reslice_labels.SetResliceAxesOrigin(x_pos, 0, 0)
            
            # Rotacje dla widoku sagitalnego
            self.transform.RotateY(-90)  # Obróć na widok z boku
            self.transform.RotateZ(90)   # Obróć żeby góra była na górze
            self.transform.Translate(0, 0, -x_pos)
        
        # 6: Wykonaj reslicing (wygeneruj obrazy 2D) 
        
        reslice.Update()
        if reslice_labels:
            reslice_labels.Update()
        
        # 7: Zaktualizuj aktor z obrazem szarościowym 
        
        # Podłącz nowy reslice jako źródło danych dla aktora
        self.image_actor_gray.GetMapper().SetInputConnection(reslice.GetOutputPort())
        
        # 8: Opcjonalnie zaktualizuj aktor z etykietami 
        
        if self.image_actor_labels and reslice_labels:
            # Zamień wartości liczbowe (etykiety) na kolory
            map_to_colors = vtkImageMapToColors()
            map_to_colors.SetInputConnection(reslice_labels.GetOutputPort())
            map_to_colors.SetLookupTable(self.lut)
            
            # Format wyjściowy RGBA (z kanałem Alpha dla przezroczystości)
            map_to_colors.SetOutputFormatToRGBA()
            map_to_colors.PassAlphaToOutputOn()
            map_to_colors.Update()

            # Podłącz do aktora
            self.image_actor_labels.GetMapper().SetInputConnection(map_to_colors.GetOutputPort())
            # Wyłącz interpolację dla ostrych krawędzi etykiet
            self.image_actor_labels.InterpolateOff()
        
        # VTK automatycznie odświeży widok


class SliderToggleCallback:
    """
    Callback obsługujący skróty klawiszowe do przełączania trybów wyświetlania.
    
    To jest najbardziej złożony callback w aplikacji. Obsługuje kilka klawiszy:
    - 'N' (Niewidzialny) - pokazuje/ukrywa wszystkie suwaki
    - 'L' (Labels) - pokazuje/ukrywa etykiety na slice'ach
    - 'M' (Mode) - przełącza między 4 trybami wizualizacji:
        0: Normalny (mesh z powierzchniami)
        1: Wireframe (tylko krawędzie)
        2: Przezroczysty (prawie niewidoczny) dla włączania pojedyczych struktur manualnie
        3: Model 3D segmentacji (generuje modele z etykiet)
    
    
    Przełączanie między trybami jest cykliczne (0->1->2->3->0)
    
    Atrybuty:
        sliders (dict): Słownik wszystkich suwaków {nazwa: widget}
        label_actors (dict): Słownik aktorów etykiet na slice'ach
        mesh_actors_dict (dict): Słownik aktorów mesh'y {nazwa_tkanki: actor}
        label_reader (vtkNrrdReader): Reader z etykietami (do generowania modeli 3D)
        renderer (vtkRenderer): Renderer do dodawania/usuwania aktorów
        lut (vtkLookupTable): Tablica kolorów
        iren (vtkRenderWindowInteractor): Interaktor (do tworzenia nowych suwaków)
        mode_state (int): Aktualny tryb (0-3)
        segmentation_actors (list): Lista aktorów modeli segmentacji (tryb 3)
        segmentation_sliders (dict): Suwaki dla modeli segmentacji (tryb 3)
    """
    
    def __init__(self, sliders, label_actors=None, mesh_actors_dict=None, 
                 label_reader=None, renderer=None, lut=None, iren=None):
        """
        Inicjalizuje callback z referencjami do wszystkich potrzebnych obiektów.
        
        Args:
            sliders: Słownik wszystkich suwaków w aplikacji
            label_actors: Słownik aktorów etykiet 
            mesh_actors_dict: Słownik aktorów mesh'y 
            label_reader: Reader z danymi segmentacji 
            renderer: Renderer VTK 
            lut: Lookup table 
            iren: Interactor (
        """
        # Zapamiętaj wszystkie przekazane obiekty
        self.sliders = sliders
        self.label_actors = label_actors or {}
        self.mesh_actors_dict = mesh_actors_dict or {}
        self.label_reader = label_reader
        self.renderer = renderer
        self.lut = lut
        self.iren = iren
        
        # Stan wewnętrzny
        self.mode_state = 0                    # Zaczynamy w trybie normalnym
        self.segmentation_actors = []          # Lista modeli 3D (tryb 3)
        self.segmentation_sliders = {}         # Suwaki dla modeli 3D (tryb 3)
        
    def __call__(self, caller, ev):
        """
        Wywoływane gdy użytkownik naciska klawisz.
        
        Argumenty:
            caller: Interactor (vtkRenderWindowInteractor)
            ev: Typ zdarzenia ('KeyPressEvent')
        """
        
        # Pobierz nazwę naciśniętego klawisza i zamień na lowercase
        key = caller.GetKeySym().lower()
        
        # OBSŁUGA KLAWISZA 'N' - toggle suwaków 
        
        if key == "n":
            # Przełącz widoczność WSZYSTKICH suwaków
            for v in self.sliders.values():
                # Jeśli suwak był włączony, wyłącz go (i odwrotnie)
                v.SetEnabled(not v.GetEnabled())
        
        # OBSŁUGA KLAWISZA 'L' - toggle etykiet 
                    
        elif key == "l" and self.label_actors:
            # Przełącz widoczność etykiet na slice'ach
            for actor in self.label_actors.values():
                if actor:  # Sprawdź czy aktor istnieje (może być None)
                    # Przełącz widoczność
                    actor.SetVisibility(not actor.GetVisibility())

        # OBSŁUGA KLAWISZA 'M' - zmiana trybu 
        
        elif key == "m":
            # Przejdź do następnego trybu (cyklicznie 0→1→2→3→0)
            self.mode_state = (self.mode_state + 1) % 4
            
            # ---------------- TRYB 3: MODEL 3D SEGMENTACJI 
            if self.mode_state == 3:
                # Ukryj suwaki tkanek (ale bez ukrywania suwaków płaszczyzn)
                for name, slider in self.sliders.items():
                    if name not in ['X Slice', 'Y Slice', 'Z Slice']:
                        slider.SetEnabled(False)
                
                # Ukryj oryginalne mesh'e tkanek
                for actor in self.mesh_actors_dict.values():
                    actor.SetVisibility(False)
                
                # Wygeneruj modele 3D z segmentacji
                if self.label_reader and self.renderer and self.lut:
                    self.segmentation_actors = create_segmentation_3d_model(
                        self.label_reader, self.lut, self.renderer, 
                        self.mesh_actors_dict,
                        similarity_threshold=0.0  # 0.0 = wyłącz wykrywanie duplikatów - wyjaśnienia o co chodzi z duplikatami w geometry utils.py
                    )
                    # Stwórz suwaki dla wygenerowanych modeli
                    self.create_segmentation_sliders()
            
            # ---------------- TRYB 0: NORMALNY       
            elif self.mode_state == 0:
                # Usuń suwaki modeli segmentacji
                self.remove_segmentation_sliders()
                
                # Pokaż wszystkie oryginalne suwaki
                for slider in self.sliders.values():
                    slider.SetEnabled(True)
                
                # Usuń modele 3D segmentacji
                for actor in self.segmentation_actors:
                    self.renderer.RemoveActor(actor)
                self.segmentation_actors = []
                
                # Przywróć oryginalne siatki
                for name, actor in self.mesh_actors_dict.items():
                    actor.SetVisibility(True)
                    prop = actor.GetProperty()
                    prop.SetRepresentationToSurface()  # Normalna powierzchnia
                    
                    # Przywróć opacity z suwaka (jeśli istnieje)
                    if name in self.sliders:
                        val = self.sliders[name].GetRepresentation().GetValue()
                        prop.SetOpacity(val)
                    else:
                        prop.SetOpacity(1.0)
                
                # Upewnij się że slice'y są widoczne
                for actor in self.label_actors.values():
                    if actor:
                        actor.SetVisibility(True)
            
            # ----------------- TRYB 1 i 2: WIREFRAME / TRANSPARENT            
            else:
                # Usuń ewentualne suwaki i modele segmentacji
                self.remove_segmentation_sliders()
                
                # Pokaż wszystkie oryginalne suwaki
                for slider in self.sliders.values():
                    slider.SetEnabled(True)
                
                # Usuń modele 3D segmentacji
                for actor in self.segmentation_actors:
                    self.renderer.RemoveActor(actor)
                self.segmentation_actors = []
                
                # Pokaż oryginalne mesh'e w odpowiednim stylu
                for actor in self.mesh_actors_dict.values():
                    actor.SetVisibility(True)
                    prop = actor.GetProperty()
                    
                    if self.mode_state == 1:
                        # WIREFRAME: tylko krawędzie, pełna nieprzezroczystość
                        prop.SetRepresentationToWireframe()
                        prop.SetOpacity(1.0)
                    elif self.mode_state == 2:
                        # TRANSPARENT: powierzchnia, prawie przezroczysta
                        prop.SetRepresentationToSurface()
                        prop.SetOpacity(0.01)  # 1% nieprzezroczystości
                
                # Upewnij się że slice'y są widoczne
                for actor in self.label_actors.values():
                    if actor:
                        actor.SetVisibility(True)
            
            # Odśwież widok żeby pokazać zmiany
            caller.GetRenderWindow().Render()
    
    def create_segmentation_sliders(self):
        """
        Tworzy suwaki do kontroli opacity modeli 3D segmentacji.
        
        Wywoływane w trybie 3 po wygenerowaniu modeli 3D.
        Każdy model dostaje swój suwak w tym samym kolorze co model.
        """
        # Sprawdź czy mamy wszystko co potrzebne
        if not self.segmentation_actors or not self.iren:
            return
        
        # Dla każdego wygenerowanego modelu stwórz suwak
        for idx, actor in enumerate(self.segmentation_actors):
            # Pobierz numer etykiety z aktora (zapamiętany w create_segmentation_3d_model)
            label_value = actor._label_value
            
            # Stwórz properties dla suwaka
            sp = SliderProperties()
            sp.title = f"Seg {label_value}"  # Tytuł: "Seg 5", "Seg 12" itd.
            sp.value_initial = 0.9           # Zaczynaj od 90% nieprzezroczystości
            
            # Oblicz pozycję suwaka (układ w dwie kolumny)
            col = idx % 2        # Kolumna: 0 lub 1
            row = idx // 2       # Rząd: 0, 1, 2, ...
            y = top_y - row * step_y  # Y = 0.80, 0.755, 0.71, ...
            
            # Ustaw współrzędne zależnie od kolumny
            if col == 0:
                sp.p1 = [right_x0_col1, y]
                sp.p2 = [right_x1_col1, y]
            else:
                sp.p1 = [right_x0_col2, y]
                sp.p2 = [right_x1_col2, y]
            
            # Pobierz kolor modelu (taki sam kolor będzie miał tytuł suwaka)
            color = actor.GetProperty().GetColor()
            
            # Stwórz widget suwaka z tym kolorem
            slider_widget = make_slider_widget_with_color(sp, color)
            slider_widget.SetInteractor(self.iren)
            slider_widget.EnabledOn()
            
            # Podłącz callback do zmiany opacity
            slider_widget.AddObserver(vtkCommand.InteractionEvent, 
                                    SliderCallback(actor.GetProperty()))
            
            # Zapamiętaj suwak
            self.segmentation_sliders[label_value] = slider_widget
        
        # Odśwież widok
        self.iren.GetRenderWindow().Render()
    
    def remove_segmentation_sliders(self):
        """
        Usuwa wszystkie suwaki modeli segmentacji.
        
        Wywoływane przy wychodzeniu z trybu 3.
        """
        for slider in self.segmentation_sliders.values():
            slider.SetEnabled(False)  # Wyłącz
            slider.Off()              # Usuń z renderowania
        self.segmentation_sliders.clear()  # Wyczyść słownik


