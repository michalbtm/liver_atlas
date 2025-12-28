"""
Moduł z transformacjami układów współrzędnych dla obrazowania medycznego.

W obrazowaniu medycznym (CT, MRI) dane mogą być zapisane w różnych orientacjach
w zależności od tego jak pacjent leżał w skanerze. Żeby wyświetlić dane poprawnie
(tak żeby głowa była na górze, prawa strona pacjenta po prawej stronie ekranu itd.)
musimy zastosować odpowiednie transformacje geometryczne.

Ten moduł implementuje klasę SliceOrder która zawiera wszystkie standardowe
transformacje używane w radiologii i obrazowaniu medycznym.


KONWENCJE ORIENTACJI:
Obrazy medyczne mogą być zapisane w różnych orientacjach, np:
- SI (Superior-Inferior): od góry do dołu
- AP (Anterior-Posterior): od przodu do tyłu
- LR (Left-Right): od lewej do prawej strony pacjenta

VTK używa standardowego układu komputerowego (Y w dół)
który jest zmieniony na Z w programie dla ładniejszej przezentacji danych
Stąd potrzeba transformacji.
"""

from vtkmodules.vtkCommonMath import vtkMatrix4x4
from vtkmodules.vtkCommonTransforms import vtkTransform


class SliceOrder:
    """
    Klasa zawierająca transformacje dla różnych orientacji danych medycznych.
    
    Każda transformacja reprezentuje jedno z możliwych ułożeń danych obrazowych.
    Po zastosowaniu transformacji dane są w standardowym układzie gdzie:
    - Prawa strona pacjenta jest po prawej stronie ekranu
    - Przód ciała jest z przodu (w kierunku patrzącego)
    - Góra ciała jest u góry
    
    Niektóre transformacje mają ujemny współczynnik skalowania (-1)
    dla jednej z osi. To powoduje odbicie lustrzane, co może zmienić orientację
    normalnych powierzchni. Dlatego po transformacji należy użyć vtkPolyDataNormals
    żeby poprawić orientację wielokątów.
    
    NAZEWNICTWO TRANSFORMACJI:
    Nazwy składają się z 2 liter oznaczających kierunek osi:
    - 'si' = Superior to Inferior (oś idzie od góry do dołu)
    - 'ap' = Anterior to Posterior (oś idzie od przodu do tyłu)
    - 'lr' = Left to Right (oś idzie od lewej do prawej)
    - 'hf' = prefix oznaczający "head first" (głowa do skanera)
    
    Przykład: 'hfsi' = head-first + superior-inferior
    
    Atrybuty:
        si_mat, is_mat, lr_mat, rl_mat, hf_mat: Macierze transformacji 4x4
        transform (dict): Słownik {nazwa: vtkTransform} ze wszystkimi transformacjami
    """
    
    def __init__(self):
        """
        Inicjalizuje wszystkie transformacje.
        
        Tworzy macierze 4x4 dla różnych orientacji i konwertuje je na obiekty
        vtkTransform. Macierze są tworzone ręcznie (element po elemencie) zamiast
        przez mnożenie, co jest szybsze i bardziej czytelne.
        """
        
        # MACIERZ SI (SUPERIOR-INFERIOR)
        # Transformacja dla danych gdzie oś Z idzie od góry do dołu ciała
        
        self.si_mat = vtkMatrix4x4()
        self.si_mat.Zero()  # Wypełnij zerami
        
        # Ustaw macierz element po elemencie
        # Macierz 4x4 ma indeksy (row, col) od 0 do 3
        self.si_mat.SetElement(0, 0, 1)   # X' = X (bez zmian)
        self.si_mat.SetElement(1, 2, 1)   # Y' = Z (Y staje się Z)
        self.si_mat.SetElement(2, 1, -1)  # Z' = -Y (Z staje się -Y, odbicie!)
        self.si_mat.SetElement(3, 3, 1)   # W' = W (współrzędna jednorodna)
        
        # Matematycznie to jest:
        # [X']   [1  0  0  0] [X]
        # [Y'] = [0  0  1  0] [Y]
        # [Z']   [0 -1  0  0] [Z]
        # [W']   [0  0  0  1] [W]

        # MACIERZ IS (INFERIOR-SUPERIOR)
        # Odwrotność SI - oś Z idzie od dołu do góry ciała
        
        self.is_mat = vtkMatrix4x4()
        self.is_mat.Zero()
        self.is_mat.SetElement(0, 0, 1)   # X' = X
        self.is_mat.SetElement(1, 2, -1)  # Y' = -Z (inne odbicie niż SI)
        self.is_mat.SetElement(2, 1, -1)  # Z' = -Y
        self.is_mat.SetElement(3, 3, 1)   # W' = W

        # MACIERZ LR (LEFT-RIGHT)
        # Transformacja dla danych gdzie oś X idzie od lewej do prawej
        
        self.lr_mat = vtkMatrix4x4()
        self.lr_mat.Zero()
        self.lr_mat.SetElement(0, 2, -1)  # X' = -Z (zamiana osi z odbiciem)
        self.lr_mat.SetElement(1, 1, -1)  # Y' = -Y (odbicie Y)
        self.lr_mat.SetElement(2, 0, 1)   # Z' = X (zamiana)
        self.lr_mat.SetElement(3, 3, 1)   # W' = W

        # MACIERZ RL (RIGHT-LEFT)
        # Odwrotność LR - oś X idzie od prawej do lewej
        
        self.rl_mat = vtkMatrix4x4()
        self.rl_mat.Zero()
        self.rl_mat.SetElement(0, 2, 1)   # X' = Z (bez odbicia tym razem)
        self.rl_mat.SetElement(1, 1, -1)  # Y' = -Y (odbicie Y)
        self.rl_mat.SetElement(2, 0, 1)   # Z' = X
        self.rl_mat.SetElement(3, 3, 1)   # W' = W

        # MACIERZ HF (HEAD FIRST)
        # Transformacja dla orientacji "head first" (głowa pierwsza do skanera)
        # To jest bazowa transformacja którą potem łączymy z innymi
        
        self.hf_mat = vtkMatrix4x4()
        self.hf_mat.Zero()
        self.hf_mat.SetElement(0, 0, -1)  # X' = -X (odbicie X)
        self.hf_mat.SetElement(1, 1, 1)   # Y' = Y (bez zmian)
        self.hf_mat.SetElement(2, 2, -1)  # Z' = -Z (odbicie Z)
        self.hf_mat.SetElement(3, 3, 1)   # W' = W

        # SŁOWNIK TRANSFORMACJI
        # Tutaj przechowujemy wszystkie transformacje jako obiekty vtkTransform
        
        self.transform = {}

        # Proste transformacje (jedna macierz) 
        
        # SI - Superior-Inferior
        si_trans = vtkTransform()
        si_trans.SetMatrix(self.si_mat)
        self.transform['si'] = si_trans

        # IS - Inferior-Superior
        is_trans = vtkTransform()
        is_trans.SetMatrix(self.is_mat)
        self.transform['is'] = is_trans

        # AP - Anterior-Posterior (używa Scale zamiast macierzy)
        # Scale(1, -1, 1) = odbij tylko Y
        ap_trans = vtkTransform()
        ap_trans.Scale(1, -1, 1)
        self.transform['ap'] = ap_trans

        # PA - Posterior-Anterior
        # Scale(1, -1, -1) = odbij Y i Z
        pa_trans = vtkTransform()
        pa_trans.Scale(1, -1, -1)
        self.transform['pa'] = pa_trans

        # LR - Left-Right
        lr_trans = vtkTransform()
        lr_trans.SetMatrix(self.lr_mat)
        self.transform['lr'] = lr_trans

        # RL - Right-Left
        rl_trans = vtkTransform()
        rl_trans.SetMatrix(self.rl_mat)
        self.transform['rl'] = rl_trans

        # HF - Head First (bazowa)
        hf_trans = vtkTransform()
        hf_trans.SetMatrix(self.hf_mat)
        self.transform['hf'] = hf_trans

        #Złożone transformacje (kombinacje macierzy)
        # Używamy Concatenate() żeby połączyć dwie transformacje
        # Kolejność jest WAŻNA: Concatenate(B) oznacza "najpierw obecna, potem B"
        
        # HFSI - Head First + Superior-Inferior
        hf_si_trans = vtkTransform()
        hf_si_trans.SetMatrix(self.hf_mat)      # Najpierw HF
        hf_si_trans.Concatenate(self.si_mat)    # Potem SI
        self.transform['hfsi'] = hf_si_trans

        # HFIS - Head First + Inferior-Superior
        hf_is_trans = vtkTransform()
        hf_is_trans.SetMatrix(self.hf_mat)
        hf_is_trans.Concatenate(self.is_mat)
        self.transform['hfis'] = hf_is_trans

        # HFAP - Head First + Anterior-Posterior
        hf_ap_trans = vtkTransform()
        hf_ap_trans.SetMatrix(self.hf_mat)
        hf_ap_trans.Scale(1, -1, 1)  # Concatenate Scale jako operację
        self.transform['hfap'] = hf_ap_trans

        # HFPA - Head First + Posterior-Anterior
        hf_pa_trans = vtkTransform()
        hf_pa_trans.SetMatrix(self.hf_mat)
        hf_pa_trans.Scale(1, -1, -1)
        self.transform['hfpa'] = hf_pa_trans

        # HFLR - Head First + Left-Right
        hf_lr_trans = vtkTransform()
        hf_lr_trans.SetMatrix(self.hf_mat)
        hf_lr_trans.Concatenate(self.lr_mat)
        self.transform['hflr'] = hf_lr_trans

        # HFRL - Head First + Right-Left
        hf_rl_trans = vtkTransform()
        hf_rl_trans.SetMatrix(self.hf_mat)
        hf_rl_trans.Concatenate(self.rl_mat)
        self.transform['hfrl'] = hf_rl_trans

        # Specjalne transformacje 
        
        # I - Identity (transformacja tożsamościowa, nic nie zmienia)
        # Używana gdy dane są już w poprawnej orientacji
        self.transform['I'] = vtkTransform()

        # Z - Zero (skaluje wszystko do 0, efektywnie "ukrywa" obiekt)
        # używane do debugowania 
        z_trans = vtkTransform()
        z_trans.Scale(0, 0, 0)
        self.transform['Z'] = z_trans

    def get(self, order):
        """
        Pobiera transformację dla danej orientacji.
        
        Argumenty:
            order (str): Nazwa orientacji (np. 'si', 'hfap', 'lr')
                Zobacz self.transform.keys() dla pełnej listy
        
        Returns:
            vtkTransform: Obiekt transformacji gotowy do użycia
        
        Raises:
            Exception: Jeśli podana orientacja nie istnieje
        
        Przykład:
            >>> slice_order = SliceOrder()
            >>> transform = slice_order.get('hfsi')
            >>> filter.SetTransform(transform)
        """
        if order in self.transform:
            return self.transform[order]
        
        # Jeśli orientacja nie istnieje, rzuć wyjątek
        raise Exception(f'No such transform "{order}" exists.')

