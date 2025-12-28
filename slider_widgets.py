"""
Moduł do tworzenia interaktywnych suwaków (sliderów) w interfejsie VTK.

Suwaki to elementy UI które pozwalają użytkownikowi kontrolować parametry
w czasie rzeczywistym:
- Przezroczystość (opacity) obiektów 3D
- Pozycję płaszczyzn przekroju

Ten moduł dostarcza:
1. Klasę SliderProperties - szablon z domyślnymi ustawieniami wyglądu
2. Funkcje do tworzenia różnych typów suwaków
3. Konwencje pozycjonowania suwaków w oknie aplikacji

UKŁAD SUWAKÓW:
W programie suwaki są rozmieszczone w prawej części okna w dwóch kolumnach.
Pozycje są określone we współrzędnych znormalizowanych (0.0-1.0), gdzie:
- (0,0) = lewy dolny róg
- (1,1) = prawy górny róg
"""

from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkInteractionWidgets import vtkSliderRepresentation2D, vtkSliderWidget


class SliderProperties:
    """
    Klasa z domyślnymi właściwościami wyglądu suwaków.
    
    To jest szablon (template) który definiuje jak suwaki powinny wyglądać.
    Zamiast ustawiać te same parametry dla każdego suwaka osobno, tworzymy
    instancję tej klasy i modyfikujemy tylko to co potrzebne (np. pozycję).
    
    WZORZEC PROJEKTOWY: Value Object / Configuration Object
    
    Atrybuty geometryczne (rozmiary w jednostkach znormalizowanych):
        tube_width: Grubość paska suwaka
        slider_length: Długość "uchwytu" który się przesuwa
        slider_width: Szerokość uchwytu
        end_cap_length: Długość "czapeczek" na końcach paska
        end_cap_width: Szerokość czapeczek
        title_height: Wysokość tekstu tytułu
        label_height: Wysokość tekstu wartości liczbowej
    
    Atrybuty wartości:
        value_minimum: Minimalna wartość suwaka (domyślnie 0.0)
        value_maximum: Maksymalna wartość suwaka (domyślnie 1.0)
        value_initial: Początkowa wartość (domyślnie 1.0 = maksimum)
    
    Atrybuty pozycji (współrzędne znormalizowane):
        p1: [x, y] - początek suwaka (lewy koniec)
        p2: [x, y] - koniec suwaka (prawy koniec)
    
    Atrybuty kolorów (nazwy kolorów z vtkNamedColors):
        title_color: Kolor tytułu suwaka
        value_color: Kolor wyświetlanej wartości
        slider_color: Kolor ruchomego uchwytu
        selected_color: Kolor uchwytu gdy jest aktywny
        bar_color: Kolor paska po którym się przesuwa
        bar_ends_color: Kolor czapeczek na końcach
    
    Przykład użycia:
        >>> props = SliderProperties()
        >>> props.title = "Opacity"
        >>> props.p1 = [0.8, 0.5]  # Zmień pozycję
        >>> props.p2 = [0.95, 0.5]
        >>> slider = make_slider_widget(props, lut, 0)
    """
    
    # ROZMIARY ELEMENTÓW (w jednostkach znormalizowanych)
    # Te wartości są dobrane eksperymentalnie żeby suwak wyglądał proporcjonalnie
    
    tube_width = 0.004        # Pasek - dość cienki żeby nie zasłaniał sceny
    slider_length = 0.015     # Uchwyt - wystarczająco długi żeby łatwo złapać
    slider_width = 0.008      # Uchwyt - szerszy niż pasek, łatwiej kliknąć
    end_cap_length = 0.008    # Czapeczki - widoczne ale dyskretne
    end_cap_width = 0.02      # Czapeczki - szersze od paska, ładnie wyglądają
    title_height = 0.02       # Tytuł - wystarczająco duży żeby przeczytać
    label_height = 0.02       # Wartość - taki sam rozmiar jak tytuł
    
    # ZAKRES WARTOŚCI
    # Domyślnie suwak kontroluje wartości od 0.0 do 1.0 (typowe dla opacity)
    
    value_minimum = 0.0       # Minimum (często 0 = całkowicie przezroczysty)
    value_maximum = 1.0       # Maximum (często 1 = całkowicie nieprzezroczysty)
    value_initial = 1.0       # Początkowa wartość (zaczynamy od maximum)
    
    # POZYCJA W OKNIE
    # Domyślnie suwak jest w lewym dolnym rogu (p1=[0.02, 0.1], p2=[0.18, 0.1])
    # Te wartości są zwykle nadpisywane podczas tworzenia konkretnego suwaka
    
    p1 = [0.02, 0.1]          # Początek (lewy koniec paska)
    p2 = [0.18, 0.1]          # Koniec (prawy koniec paska)
    
    # DODATKOWE
    
    title = None              # Tytuł suwaka (np. "liver" lub "Opacity")
    
    # KOLORY
    # Używamy nazw z vtkNamedColors - są to standardowe kolory CSS/X11
    # Lista dostępnych: https://www.vtk.org/doc/nightly/html/classvtkNamedColors.html
    
    title_color = 'Black'         # Tytuł - czarny, czytelny na jasnym tle
    label_color = 'Black'         # Wartość - też czarna (obecnie nieużywana?)
    value_color = 'DarkSlateGray' # Wyświetlana liczba - ciemny szary
    slider_color = 'BurlyWood'    # Uchwyt - beżowy, neutralny
    selected_color = 'Lime'       # Uchwyt aktywny - jaskrawa zieleń, dobrze widoczna
    bar_color = 'Black'           # Pasek - czarny, kontrastuje z tłem
    bar_ends_color = 'Indigo'     # Czapeczki - ciemny fiolet, ozdobne


def make_slider_widget(properties, lut, idx):
    """
    Tworzy widget suwaka z kolorem tytułu pobranym z lookup table.
    
    Ta funkcja jest używana do suwaków kontrolujących przezroczystość tkanek.
    Tytuł suwaka jest pokolorowany tym samym kolorem co tkanka, dzięki czemu
    użytkownik od razu wie którego organu dotyczy dany suwak.
    
    Argumenty:
        properties (SliderProperties): Obiekt z ustawieniami wyglądu
        lut (vtkLookupTable): Tablica kolorów z której pobieramy kolor tytułu
        idx (int): Indeks w LUT odpowiadający tej tkance
            - Jeśli idx jest w zakresie 0-22, używamy koloru z LUT
            - W przeciwnym razie używamy domyślnego czarnego
    
    Returns:
        vtkSliderWidget: Gotowy widget suwaka, gotowy do podłączenia do interaktora
    
    Przykład:
        >>> props = SliderProperties()
        >>> props.title = "liver"
        >>> props.p1 = [0.82, 0.80]
        >>> props.p2 = [0.97, 0.80]
        >>> widget = make_slider_widget(props, lut, 5)
        >>> widget.SetInteractor(interactor)
        >>> widget.EnabledOn()
    """
    
    # 1: Stwórz reprezentację (wygląd) suwaka
    
    # vtkSliderRepresentation2D definiuje jak suwak wygląda i gdzie się znajduje
    # "2D" oznacza że suwak jest płaski (nakładka na ekran), nie obiekt 3D w scenie
    slider = vtkSliderRepresentation2D()

    # 2: Ustaw zakres wartości
    
    slider.SetMinimumValue(properties.value_minimum)  # Najniższa wartość (lewy koniec)
    slider.SetMaximumValue(properties.value_maximum)  # Najwyższa wartość (prawy koniec)
    slider.SetValue(properties.value_initial)         # Początkowa pozycja uchwytu

    # 3: Ustaw tytuł
    
    slider.SetTitleText(properties.title)  # Tekst wyświetlany nad suwakiem

    # 4: Ustaw pozycję w oknie
    
    # Współrzędne są znormalizowane: (0,0)=lewy dolny róg, (1,1)=prawy górny róg
    # To pozwala suwakom działać poprawnie niezależnie od rozmiaru okna
    
    # Point1 = początek (lewy koniec paska)
    slider.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
    slider.GetPoint1Coordinate().SetValue(properties.p1[0], properties.p1[1])
    
    # Point2 = koniec (prawy koniec paska)
    slider.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()
    slider.GetPoint2Coordinate().SetValue(properties.p2[0], properties.p2[1])

    # 5: Ustaw rozmiary elementów
    
    slider.SetTubeWidth(properties.tube_width)
    slider.SetSliderLength(properties.slider_length)
    slider.SetSliderWidth(properties.slider_width)
    slider.SetEndCapLength(properties.end_cap_length)
    slider.SetEndCapWidth(properties.end_cap_width)
    slider.SetTitleHeight(properties.title_height)
    slider.SetLabelHeight(properties.label_height)

    # 6: Ustaw kolory
    
    # vtkNamedColors pozwala używać nazw kolorów zamiast wartości RGB
    colors = vtkNamedColors()
    
    # Kolory poszczególnych elementów suwaka
    slider.GetTubeProperty().SetColor(colors.GetColor3d(properties.bar_color))
    slider.GetCapProperty().SetColor(colors.GetColor3d(properties.bar_ends_color))
    slider.GetSliderProperty().SetColor(colors.GetColor3d(properties.slider_color))
    slider.GetSelectedProperty().SetColor(colors.GetColor3d(properties.selected_color))
    slider.GetLabelProperty().SetColor(colors.GetColor3d(properties.value_color))

    # 7: Ustaw kolor tytułu (specjalny przypadek)
    
    # Jeśli indeks jest w poprawnym zakresie (0-22), używamy koloru z LUT
    # To sprawia że tytuł ma kolor odpowiadający tkance
    if 0 <= idx < 23:
        # GetTableValue zwraca (R, G, B, Alpha), bierzemy tylko RGB ([:3])
        slider.GetTitleProperty().SetColor(lut.GetTableValue(idx)[:3])
        # Wyłączamy cień pod tekstem (ładniej wygląda kolorowy tekst bez cienia)
        slider.GetTitleProperty().ShadowOff()
    else:
        # Dla indeksów poza zakresem używamy domyślnego koloru
        slider.GetTitleProperty().SetColor(colors.GetColor3d(properties.title_color))

    # 8: Stwórz widget i przypisz reprezentację
    
    # vtkSliderWidget to wrapper który łączy reprezentację (wygląd) z interakcją
    slider_widget = vtkSliderWidget()
    slider_widget.SetRepresentation(slider)
    
    # Zwracamy gotowy widget (jeszcze nie podłączony do interaktora)
    return slider_widget


def make_slider_widget_with_color(properties, rgb_color):
    """
    Tworzy widget suwaka z własnym kolorem RGB tytułu.
    
    Ta funkcja jest używana do suwaków kontrolujących modele 3D segmentacji.
    W przeciwieństwie do make_slider_widget(), tutaj kolor tytułu jest przekazywany
    bezpośrednio jako RGB, nie z LUT. To pozwala użyć dokładnie tego samego koloru
    co model 3D.
    
    Args:
        properties (SliderProperties): Obiekt z ustawieniami wyglądu
        rgb_color (tuple): Kolor tytułu jako (R, G, B) w zakresie 0.0-1.0
            Przykład: (1.0, 0.0, 0.0) = czysty czerwony
    
    Returns:
        vtkSliderWidget: Gotowy widget suwaka
    
    Przykład:
        >>> props = SliderProperties()
        >>> props.title = "Seg 15"
        >>> props.p1 = [0.82, 0.75]
        >>> props.p2 = [0.97, 0.75]
        >>> color = (0.8, 0.3, 0.2)  # Pomarańczowo-czerwony
        >>> widget = make_slider_widget_with_color(props, color)
    """
    
    # KROKI 1-6: Identyczne jak w make_slider_widget()
    
    slider = vtkSliderRepresentation2D()
    slider.SetMinimumValue(properties.value_minimum)
    slider.SetMaximumValue(properties.value_maximum)
    slider.SetValue(properties.value_initial)
    slider.SetTitleText(properties.title)

    slider.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
    slider.GetPoint1Coordinate().SetValue(properties.p1[0], properties.p1[1])
    slider.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()
    slider.GetPoint2Coordinate().SetValue(properties.p2[0], properties.p2[1])

    slider.SetTubeWidth(properties.tube_width)
    slider.SetSliderLength(properties.slider_length)
    slider.SetSliderWidth(properties.slider_width)
    slider.SetEndCapLength(properties.end_cap_length)
    slider.SetEndCapWidth(properties.end_cap_width)
    slider.SetTitleHeight(properties.title_height)
    slider.SetLabelHeight(properties.label_height)

    colors = vtkNamedColors()
    slider.GetTubeProperty().SetColor(colors.GetColor3d(properties.bar_color))
    slider.GetCapProperty().SetColor(colors.GetColor3d(properties.bar_ends_color))
    slider.GetSliderProperty().SetColor(colors.GetColor3d(properties.slider_color))
    slider.GetSelectedProperty().SetColor(colors.GetColor3d(properties.selected_color))
    slider.GetLabelProperty().SetColor(colors.GetColor3d(properties.value_color))
    
    # 7: Ustaw własny kolor tytułu (różnica względem make_slider_widget)
    
    # Bezpośrednio ustawiamy przekazany kolor RGB
    slider.GetTitleProperty().SetColor(rgb_color)
    # Wyłączamy cień (kolorowy tekst ładniej wygląda bez cienia)
    slider.GetTitleProperty().ShadowOff()

    # 8: Stwórz i zwróć widget
    
    slider_widget = vtkSliderWidget()
    slider_widget.SetRepresentation(slider)
    return slider_widget


def make_slice_slider(properties, min_val, max_val, initial_val, title):
    """
    Tworzy suwak do kontroli pozycji płaszczyzny przekroju (slice).
    
    Ten typ suwaka ma inne przeznaczenie niż suwaki opacity - kontroluje pozycję
    (numer slice'a) zamiast przezroczystości. Dlatego ma inny zakres wartości
    (może być ujemny!) i zawsze czarny tytuł.
    
    RÓŻNICE względem make_slider_widget():
    - Zakres wartości jest parametrem (może być np. -100 do 100)
    - Tytuł jest zawsze czarny (nie kolorowany)
    - Używany do slice'ów XY, XZ, YZ (przekroje anatomiczne)
    
    Argumenty
        properties (SliderProperties): Obiekt z ustawieniami wyglądu
        min_val (int/float): Minimalna wartość (może być ujemna!)
        max_val (int/float): Maksymalna wartość
        initial_val (int/float): Początkowa pozycja
        title (str): Tytuł suwaka (np. "X Slice", "Y Slice", "Z Slice")
    
    Returns:
        vtkSliderWidget: Gotowy widget suwaka
    
    Przykład:
        >>> props = SliderProperties()
        >>> props.p1 = [0.25, 0.05]  # Dolny środek ekranu
        >>> props.p2 = [0.40, 0.05]
        >>> # Suwak od -50 do 50, zaczynając od 0
        >>> widget = make_slice_slider(props, -50, 50, 0, "Z Slice")
    """
    
    # 1-4: Stwórz reprezentację i ustaw podstawowe parametry
    
    slider = vtkSliderRepresentation2D()
    
    # Tutaj używamy przekazanych wartości zamiast z properties
    slider.SetMinimumValue(min_val)
    slider.SetMaximumValue(max_val)
    slider.SetValue(initial_val)
    slider.SetTitleText(title)
    
    # Pozycja w oknie
    slider.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
    slider.GetPoint1Coordinate().SetValue(properties.p1[0], properties.p1[1])
    slider.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()
    slider.GetPoint2Coordinate().SetValue(properties.p2[0], properties.p2[1])
    
    # 5: Rozmiary
    
    slider.SetTubeWidth(properties.tube_width)
    slider.SetSliderLength(properties.slider_length)
    slider.SetSliderWidth(properties.slider_width)
    slider.SetEndCapLength(properties.end_cap_length)
    slider.SetEndCapWidth(properties.end_cap_width)
    slider.SetTitleHeight(properties.title_height)
    slider.SetLabelHeight(properties.label_height)
    
    # 6: Kolory
    
    colors = vtkNamedColors()
    slider.GetTubeProperty().SetColor(colors.GetColor3d(properties.bar_color))
    slider.GetCapProperty().SetColor(colors.GetColor3d(properties.bar_ends_color))
    slider.GetSliderProperty().SetColor(colors.GetColor3d(properties.slider_color))
    slider.GetSelectedProperty().SetColor(colors.GetColor3d(properties.selected_color))
    slider.GetLabelProperty().SetColor(colors.GetColor3d(properties.value_color))
    
    # Tytuł zawsze czarny (nie kolorowany jak w innych suwaków)
    slider.GetTitleProperty().SetColor(colors.GetColor3d(properties.title_color))
    
    # 7: Stwórz i zwróć widget
    
    slider_widget = vtkSliderWidget()
    slider_widget.SetRepresentation(slider)
    return slider_widget

