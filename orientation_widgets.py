"""
Moduł do tworzenia widgetów orientacji - wskaźników kierunków w przestrzeni 3D.

Widgety orientacji to małe wskaźniki pokazujące:
- Kierunki osi X, Y, Z (strzałki w różnych kolorach)
- Etykiety opisujące strony (R=Right, L=Left, A=Anterior itd.)
- Opcjonalnie kostka z oznaczeniami na każdej ścianie

Ten moduł tworzy dwa typy widgetów:
1. Osie 3D (vtkAxesActor) - kolorowe strzałki X, Y, Z
2. Kostka z opisami (vtkAnnotatedCubeActor) - kostka z literami na ścianach
3. Połączenie obu (vtkPropAssembly) - osie + kostka razem

Widgety orientacji są zwykle wyświetlane w rogu ekranu jako małe overlay.
Obracają się razem z kamerą więc zawsze wiadomo "gdzie jesteśmy" w przestrzeni.

"""

from vtkmodules.vtkRenderingAnnotation import vtkAxesActor, vtkAnnotatedCubeActor
from vtkmodules.vtkRenderingCore import vtkPropAssembly


def make_annotated_cube_actor(cube_labels, colors):
    """
    Tworzy kostkę z tekstowymi opisami na każdej ścianie.
    
    Kostka ma 6 ścian, więc potrzebujemy 6 etykiet. Każda ściana reprezentuje
    jedną stronę przestrzeni 3D (np. +X, -X, +Y, -Y, +Z, -Z).
    
    W aplikacjach medycznych etykiety to zwykle:
    - R/L (Right/Left - prawa/lewa strona pacjenta)
    - A/P (Anterior/Posterior - przód/tył ciała)
    - S/I (Superior/Inferior - góra/dół ciała)
    
    Args:
        cube_labels (list): Lista 6 stringów z etykietami dla ścian w kolejności:
            [0]=XPlus, [1]=XMinus, [2]=YPlus, [3]=YMinus, [4]=ZPlus, [5]=ZMinus
            Przykład: ['R', 'L', 'S', 'I', 'P', 'A']
        colors (vtkNamedColors): Obiekt z paletą kolorów VTK
    
    Returns:
        vtkAnnotatedCubeActor: Gotowa kostka z opisami, gotowa do wyświetlenia
    
    Przykład:
        >>> colors = vtkNamedColors()
        >>> labels = ['R', 'L', 'S', 'I', 'P', 'A']  # Right, Left, Superior...
        >>> cube = make_annotated_cube_actor(labels, colors)
    """
    
    # 1: Stwórz kostkę
    
    cube = vtkAnnotatedCubeActor()
    
    # 2: Ustaw teksty na ścianach
    
    # Kostka ma 6 ścian odpowiadających kierunkom w przestrzeni 3D:
    # - XPlus/XMinus = prawo/lewo (oś X)
    # - YPlus/YMinus = góra/dół lub przód/tył (oś Y, zależy od konwencji)
    # - ZPlus/ZMinus = przód/tył lub góra/dół (oś Z, zależy od konwencji)
    
    cube.SetXPlusFaceText(cube_labels[0])    # Tekst na ścianie +X (prawo)
    cube.SetXMinusFaceText(cube_labels[1])   # Tekst na ścianie -X (lewo)
    cube.SetYPlusFaceText(cube_labels[2])    # Tekst na ścianie +Y
    cube.SetYMinusFaceText(cube_labels[3])   # Tekst na ścianie -Y
    cube.SetZPlusFaceText(cube_labels[4])    # Tekst na ścianie +Z
    cube.SetZMinusFaceText(cube_labels[5])   # Tekst na ścianie -Z
    
    # 3: Ustaw rozmiar tekstu
    
    # FaceTextScale kontroluje wielkość liter na ścianach
    # 0.5 = litery zajmują połowę wysokości ściany
    cube.SetFaceTextScale(0.5)
    
    # 4: Ustaw kolory elementów kostki
    
    # Kolor głównej kostki (korpus)
    cube.GetCubeProperty().SetColor(colors.GetColor3d('Gainsboro'))  # Jasnoszary
    
    # Kolor krawędzi między ścianami
    cube.GetTextEdgesProperty().SetColor(colors.GetColor3d('LightSlateGray'))  # Ciemnoszary
    
    # 5: Pokoloruj poszczególne pary ścian
    
    # Konwencja kolorów:
    # - X (prawo/lewo) = czerwony
    # - Y (góra/dół lub przód/tył) = niebieski
    # - Z (przód/tył lub góra/dół) = zielony
    
    # Ściany X (prawo/lewo) - czerwone 
    cube.GetXPlusFaceProperty().SetColor(colors.GetColor3d('Tomato'))
    cube.GetXMinusFaceProperty().SetColor(colors.GetColor3d('Tomato'))
    
    # Ściany Y - niebieskie 
    cube.GetYPlusFaceProperty().SetColor(colors.GetColor3d('DeepSkyBlue'))
    cube.GetYMinusFaceProperty().SetColor(colors.GetColor3d('DeepSkyBlue'))
    
    # Ściany Z - zielone
    cube.GetZPlusFaceProperty().SetColor(colors.GetColor3d('SeaGreen'))
    cube.GetZMinusFaceProperty().SetColor(colors.GetColor3d('SeaGreen'))
    
    # Zwróć gotową kostkę
    return cube


def make_axes_actor(scale, xyz_labels):
    """
    Tworzy aktor z osiami 3D - trzema kolorowymi strzałkami.

    - Czerwona strzałka = oś X
    - Zielona strzałka = oś Y  
    - Niebieska strzałka = oś Z
    
    Każda strzałka jest oznaczona literą (+X, +Y, +Z) żeby nie było wątpliwości.
    
    Argumenty:
        scale (list): Skala osi jako [sx, sy, sz], np. [1.5, 1.5, 1.5]
            Większa skala = dłuższe strzałki
        xyz_labels (list): Lista 3 stringów z etykietami osi: [X_label, Y_label, Z_label]
            Przykład: ['+X', '+Y', '+Z'] lub ['Right', 'Front', 'Up']
    
    Returns:
        vtkAxesActor: Gotowy aktor z osiami, gotowy do dodania do sceny
    
    Przykład:
        >>> axes = make_axes_actor([2.0, 2.0, 2.0], ['X', 'Y', 'Z'])
        >>> renderer.AddActor(axes)
    """
    
    # 1: Stwórz aktor osi
    
    axes = vtkAxesActor()
    
    # 2: Ustaw skalę (długość strzałek)
    
    # SetScale przyjmuje tuple/listę (sx, sy, sz)
    # Większe wartości = dłuższe strzałki
    # [1.5, 1.5, 1.5] = osie są 1.5x dłuższe niż domyślne
    axes.SetScale(scale)
    
    # 3: Ustaw styl trzpienia strzałki
    
    # Trzpień (shaft) to długa część strzałki (nie grot)
    # Może być walcem (cylinder) lub stożkiem (cone)
    # Walec wygląda bardziej profesjonalnie
    axes.SetShaftTypeToCylinder()
    
    # 4: Ustaw etykiety osi
    
    # Tekst wyświetlany przy każdej strzałce
    axes.SetXAxisLabelText(xyz_labels[0])  # Etykieta osi X (czerwona)
    axes.SetYAxisLabelText(xyz_labels[1])  # Etykieta osi Y (zielona)
    axes.SetZAxisLabelText(xyz_labels[2])  # Etykieta osi Z (niebieska)
    
    # 5: Dostosuj proporcje elementów strzałek
       
    # Zmniejsz promień walca o połowę (0.5x)
    axes.SetCylinderRadius(0.5 * axes.GetCylinderRadius())
    
    # Lekko zwiększ promień stożka (grotu) - 1.025x
    axes.SetConeRadius(1.025 * axes.GetConeRadius())
    
    # Zwiększ promień kuli - 1.5x
    axes.SetSphereRadius(1.5 * axes.GetSphereRadius())
    
    # 6: Dostosuj wygląd tekstu etykiet
    
    # Pobierz właściwości tekstu dla osi X (jako szablon)
    tprop = axes.GetXAxisCaptionActor2D().GetCaptionTextProperty()
    
    # Włącz kursywę
    tprop.ItalicOn()
    
    # Włącz cień pod tekstem - poprawia czytelność na różnych tłach
    tprop.ShadowOn()
    
    # Ustaw czcionkę Times 
    tprop.SetFontFamilyToTimes()
    
    # 7: Skopiuj właściwości tekstu do pozostałych osi
    
    axes.GetYAxisCaptionActor2D().GetCaptionTextProperty().ShallowCopy(tprop)
    axes.GetZAxisCaptionActor2D().GetCaptionTextProperty().ShallowCopy(tprop)
    
    # Zwróć gotowy aktor osi
    return axes


def make_cube_actor(label_selector, colors):
    """
    Tworzy połączenie kostki i osi - kompletny widget orientacji.
    
    Ta funkcja łączy vtkAnnotatedCubeActor (kostka z literami) z vtkAxesActor
    (kolorowe strzałki) w jeden obiekt 
    
    Args:
        label_selector (str): Nazwa układu współrzędnych 
        colors (vtkNamedColors): Obiekt z paletą kolorów VTK
    
    Returns:
        vtkPropAssembly: Złożony obiekt zawierający osie + kostkę
    
    Przykład:
        >>> colors = vtkNamedColors()
        >>> widget = make_cube_actor('rsp', colors)
        >>> renderer.AddActor(widget)
    """
    
    # 1: Wybranie odpowiedniego układ współrzędnych na podstawie label_selector
    
    if label_selector == 'sal':
        # SAL (Superior-Anterior-Left)
        # Układ gdzie:
        # +X = Superior (góra)
        # +Y = Anterior (przód)
        # +Z = Left (lewa strona pacjenta)
        
        xyz_labels = ['+X', '+Y', '+Z']
        cube_labels = ['S', 'I',   # X: Superior (góra), Inferior (dół)
                      'A', 'P',   # Y: Anterior (przód), Posterior (tył)
                      'L', 'R']   # Z: Left (lewo), Right (prawo)
        scale = [1.5, 1.5, 1.5]
        
    elif label_selector == 'rsp':
        # RSP (Right-Superior-Posterior)
        # Układ używany w naszej aplikacji:
        # +X = Right (prawa strona pacjenta, NASZA LEWA!)
        # +Y = Superior (góra ciała)
        # +Z = Posterior (tył ciała)
        
        xyz_labels = ['+X', '+Y', '+Z']
        cube_labels = ['R', 'L',   # X: Right (prawo), Left (lewo)
                      'S', 'I',   # Y: Superior (góra), Inferior (dół)
                      'P', 'A']   # Z: Posterior (tył), Anterior (przód)
        scale = [1.5, 1.5, 1.5]
        
    elif label_selector == 'lsa':
        # LSA (Left-Superior-Anterior)
        # Alternatywny układ (lustrzane odbicie RSP):
        # +X = Left (lewa strona pacjenta)
        # +Y = Superior (góra)
        # +Z = Anterior (przód)
        
        xyz_labels = ['+X', '+Y', '+Z']
        cube_labels = ['L', 'R',   # X: Left (lewo), Right (prawo)
                      'S', 'I',   # Y: Superior (góra), Inferior (dół)
                      'A', 'P']   # Z: Anterior (przód), Posterior (tył)
        scale = [1.5, 1.5, 1.5]
        
    else:
        # Domyślny układ (prosty matematyczny XYZ)
        # Jeśli nie rozpoznano label_selector, użyj standardowego układu        
        xyz_labels = ['+X', '+Y', '+Z']
        cube_labels = ['+X', '-X',  # X Plus, X Minus
                      '+Y', '-Y',  # Y Plus, Y Minus
                      '+Z', '-Z']  # Z Plus, Z Minus
        scale = [1.5, 1.5, 1.5]

    # 2: Stwórz kostkę i osie
    
    cube = make_annotated_cube_actor(cube_labels, colors)
    axes = make_axes_actor(scale, xyz_labels)

    # 3: Połącz kostkę i osie w jeden obiekt
    
    assembly = vtkPropAssembly()
    
    # Dodaj osie do assembly
    assembly.AddPart(axes)
    
    # Dodaj kostkę do assembly
    # Kostka będzie wyświetlona "w środku" osi, w punkcie (0,0,0)
    assembly.AddPart(cube)
    
    # Zwróć złożony obiekt
    return assembly
