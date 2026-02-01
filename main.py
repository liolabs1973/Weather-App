import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import pandas as pd
import requests
import json
import os
from io import StringIO
from datetime import date, datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys

# =============================================================================
# CONFIGURATION GLOBALE ET CONSTANTES
# =============================================================================
MONS_WEATHER_VERSION = "3.5"
API_KEY = "PNA5TGQMVBGKRG3YMH3ELMHQG"
VILLE = "Mons,BE"
JSON_PATH = "historique_intemperies_mons_2026.json" # Base de données locale
CONFIG_PATH = "threshold.json"                     # Paramètres de seuils
START_DATE_ROOT = "2024-01-01"                     # Point de départ historique

class MonsWeatherApp:
    def __init__(self, root):
        """Initialisation de l'application et de l'interface."""
        self.root = root
        
        # GESTION DE LA FERMETURE : On intercepte la croix (X) pour une sortie propre
        self.root.protocol("WM_DELETE_WINDOW", self.quitter_application)
        
        self.data = pd.DataFrame()
        self.thresholds = {}

        # Chargement des fichiers au démarrage
        self.charger_configuration()
        self.charger_donnees_locales()
        
        # Paramétrage de la fenêtre principale
        self.root.geometry("1024x768")
        self.maj_titre_fenetre()
        self.creer_menu()
        self.creer_widgets()
        
        # Lancement de la synchronisation automatique (Vérifie si données manquantes)
        self.refresh_data_logic(auto=True)

    def quitter_application(self):
        """Ferme proprement les boucles et les processus système."""
        print("Arrêt de l'application Mons_Weather...")
        self.root.quit()
        self.root.destroy()
        sys.exit()

    def charger_configuration(self):
        """Gère les seuils personnalisés. Crée le fichier s'il est absent."""
        default_config = {
            "temp_min": -2.0, "temp_max": 35.0, 
            "precip_max": 5.0, "wind_max": 65.0
        }
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            self.thresholds = default_config
        else:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                self.thresholds = json.load(f)

    def maj_titre_fenetre(self):
        """Affiche dynamiquement la fraîcheur des données dans la barre de titre."""
        date_max = self.data['datetime'].max() if not self.data.empty else "Aucune donnée"
        self.root.title(f"Gestion Intempérie Par Lionel PAUL - v{MONS_WEATHER_VERSION} - Dataset till: {date_max}")

    def charger_donnees_locales(self):
        """Récupère l'historique stocké en JSON sans appeler l'API."""
        if os.path.exists(JSON_PATH):
            try:
                with open(JSON_PATH, 'r', encoding='utf-8') as f:
                    self.data = pd.DataFrame(json.load(f))
            except Exception as e:
                print(f"Erreur lors de la lecture du JSON : {e}")

    def refresh_data_logic(self, auto=False):
        """Logique 'Delta' : Ne télécharge que ce qui manque depuis la dernière date."""
        aujourdhui = date.today().isoformat()
        if not self.data.empty:
            derniere_date = self.data['datetime'].max()
            if derniere_date < aujourdhui:
                # On calcule le lendemain de la dernière date connue
                dt_obj = datetime.strptime(derniere_date, '%Y-%m-%d') + timedelta(days=1)
                start_str = dt_obj.strftime('%Y-%m-%d')
                if auto:
                    if messagebox.askyesno("Refresh", f"Données manquantes. Sync depuis {start_str} ?"):
                        self.telecharger_donnees(start_str, aujourdhui)
                else: 
                    self.telecharger_donnees(start_str, aujourdhui)
        else:
            # Si base vide, on télécharge tout depuis 2024
            self.telecharger_donnees(START_DATE_ROOT, aujourdhui)
        
        self.maj_titre_fenetre()
        self.refresh_table()

    def telecharger_donnees(self, start, end):
        """Exécute la requête API Visual Crossing et fusionne avec le local."""
        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{VILLE}/{start}/{end}?unitGroup=metric&include=days&key={API_KEY}&contentType=csv"
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                df_new = pd.read_csv(StringIO(response.text))
                cols = ['datetime', 'temp', 'precip', 'windgust', 'conditions']
                df_new = df_new[cols].copy()
                
                # Fusion (Concat) + Suppression des doublons de dates
                self.data = pd.concat([self.data, df_new], ignore_index=True).drop_duplicates(subset=['datetime'])
                self.data = self.data.sort_values(by='datetime', ascending=False)
                
                # Sauvegarde au format technique (JSON) et bureautique (Excel)
                self.data.to_json(JSON_PATH, orient='records', indent=4)
                self.data.to_excel(JSON_PATH.replace(".json", ".xlsx"), index=False)
        except Exception as e:
            messagebox.showerror("Erreur API", f"Impossible de récupérer les données : {e}")

    def creer_menu(self):
        """Définit la structure de la barre de menus supérieure."""
        menubar = tk.Menu(self.root)
        
        # Menu APPLICATION
        menu_app = tk.Menu(menubar, tearoff=0)
        menu_app.add_command(label="Refresh Data", command=lambda: self.refresh_data_logic(auto=False))
        menu_app.add_command(label="Rainy Day List", command=self.ouvrir_filtre_dates)
        menu_app.add_separator()
        menu_app.add_command(label="Quit", command=self.quitter_application)
        menubar.add_cascade(label="Application", menu=menu_app)
        
        # Menu ANALYSE (Stats et Graphiques)
        menu_stat = tk.Menu(menubar, tearoff=0)
        menu_stat.add_command(label="Data Stat", command=self.afficher_stats)
        menu_stat.add_command(label="Graphics", command=self.afficher_graphiques)
        menubar.add_cascade(label="Graph & Stat", menu=menu_stat)
        
        self.root.config(menu=menubar)

    def refresh_table(self, df_to_show=None):
        """Alimente le tableau et applique le style visuel (⚠️ et Gris)."""
        for item in self.tree.get_children(): self.tree.delete(item)
        display_df = df_to_show if df_to_show is not None else self.data
        if display_df.empty: return

        for _, row in display_df.iterrows():
            t, p, w = row['temp'], row['precip'], row['windgust'] if pd.notnull(row['windgust']) else 0
            
            # Analyse des seuils par colonne pour marquer les coupables
            symbole = "⚠️ "
            t_str = f"{symbole}{t}" if (t <= self.thresholds['temp_min'] or t >= self.thresholds['temp_max']) else str(t)
            p_str = f"{symbole}{p}" if (p >= self.thresholds['precip_max']) else str(p)
            w_str = f"{symbole}{w}" if (w >= self.thresholds['wind_max']) else str(w)
            
            # Si un symbole ⚠️ est présent, toute la ligne est marquée comme intempérie
            tag = 'ligne_intemperie' if (symbole in t_str or symbole in p_str or symbole in w_str) else 'normal'
            alerte = "OUI" if tag == 'ligne_intemperie' else "NON"
            
            self.tree.insert("", "end", values=(row['datetime'], t_str, p_str, w_str, alerte), tags=(tag,))

    def ouvrir_filtre_dates(self):
        """Interface utilisateur pour filtrer les jours de chômage intempéries."""
        self.win_filtre = tk.Toplevel(self.root)
        self.win_filtre.title("Filtrage Temporel")
        self.win_filtre.geometry("400x320")
        self.win_filtre.grab_set() # Bloque la fenêtre principale
        
        frame = tk.Frame(self.win_filtre, padx=25, pady=20)
        frame.pack(expand=True, fill="both")
        
        tk.Label(frame, text="PARAMÈTRES DE RECHERCHE", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 15))
        tk.Label(frame, text="1. Date de début (incluse) :").grid(row=1, column=0, sticky="w")
        self.cal_debut = DateEntry(frame, width=15, date_pattern='yyyy-mm-dd')
        self.cal_debut.grid(row=2, column=0, pady=(5, 15))
        
        tk.Label(frame, text="2. Date de fin (incluse) :").grid(row=3, column=0, sticky="w")
        self.cal_fin = DateEntry(frame, width=15, date_pattern='yyyy-mm-dd')
        self.cal_fin.grid(row=4, column=0, pady=(5, 25))
        
        ttk.Button(frame, text="Filtrer les intempéries", command=self.appliquer_filtre).grid(row=5, column=0)

    def appliquer_filtre(self):
        """Filtre le tableau sur une période et uniquement les alertes 'OUI'."""
        d1, d2 = self.cal_debut.get(), self.cal_fin.get()
        mask = (self.data['datetime'] >= d1) & (self.data['datetime'] <= d2)
        df_temp = self.data.loc[mask].copy()
        
        # Filtre sur la logique métier "Seuils du JSON"
        df_temp['is_int'] = df_temp.apply(lambda r: "OUI" if (
            r['temp'] <= self.thresholds['temp_min'] or r['temp'] >= self.thresholds['temp_max'] or
            r['precip'] >= self.thresholds['precip_max'] or 
            (pd.notnull(r['windgust']) and r['windgust'] >= self.thresholds['wind_max'])
        ) else "NON", axis=1)
        
        self.refresh_table(df_temp[df_temp['is_int'] == "OUI"])
        self.win_filtre.destroy()

    def afficher_stats(self):
        """Génère un rapport texte et propose la copie presse-papier."""
        items = self.tree.get_children()
        total = len(items)
        rapport = f"Mons_Weather - Dataset till: {self.data['datetime'].max()}\nTotal affiché : {total} jours."
        if messagebox.askyesno("Statistiques", rapport + "\n\nCopier ce rapport ?"):
            self.root.clipboard_clear()
            self.root.clipboard_append(rapport)

    def afficher_graphiques(self):
        """Analyse graphique triple (Pluie, Temp, Vent) côte à côte."""
        data_liste = []
        for item in self.tree.get_children():
            v = self.tree.item(item)['values']
            # Nettoyage des caractères spéciaux pour le calcul numérique
            t = float(str(v[1]).replace("⚠️ ", ""))
            p = float(str(v[2]).replace("⚠️ ", ""))
            w = float(str(v[3]).replace("⚠️ ", "")) if v[3] != 'None' else 0
            data_liste.append({'dt': v[0], 'tp': t, 'pr': p, 'wd': w})
            
        if not data_liste: return
        
        df_g = pd.DataFrame(data_liste).sort_values('dt')
        df_g['dt'] = pd.to_datetime(df_g['dt'])
        
        win_g = tk.Toplevel(self.root)
        win_g.geometry("1400x500")
        
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 5))
        
        # Graphique Pluie
        ax1.bar(df_g['dt'], df_g['pr'], color='#e74c3c', alpha=0.6)
        ax1.axhline(y=self.thresholds['precip_max'], color='black', ls='--')
        ax1.set_title("Précipitations (mm)")
        
        # Graphique Températures
        ax2.plot(df_g['dt'], df_g['tp'], color='#3498db', marker='.')
        ax2.axhline(y=self.thresholds['temp_min'], color='cyan', ls=':')
        ax2.set_title("Températures (°C)")
        
        # Graphique Vent
        ax3.bar(df_g['dt'], df_g['wd'], color='#9b59b6', alpha=0.6)
        ax3.axhline(y=self.thresholds['wind_max'], color='black', ls='--')
        ax3.set_title("Vent (km/h)")
        
        fig.autofmt_xdate()
        canvas = FigureCanvasTkAgg(fig, master=win_g)
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def creer_widgets(self):
        """Structure le tableau principal et les barres de défilement."""
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill="x")
        tk.Label(header, text="MONS WEATHER - TABLEAU DE BORD", fg="white", bg="#2c3e50", font=("Arial", 12, "bold")).pack(pady=15)
        
        container = tk.Frame(self.root)
        container.pack(expand=True, fill="both", padx=20, pady=20)
        
        scrollbar = ttk.Scrollbar(container, orient="vertical")
        self.tree = ttk.Treeview(container, columns=("d", "t", "p", "w", "a"), show="headings", yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        
        for c, t in zip(("d", "t", "p", "w", "a"), ("Date", "Temp", "Pluie", "Vent", "Alerte")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=120, anchor="center")
        
        # Configuration des couleurs de lignes (Gris clair pour alertes)
        self.tree.tag_configure('ligne_intemperie', background='#f2f2f2', foreground='#d35400') 
        self.tree.pack(expand=True, fill="both")

if __name__ == "__main__":
    root = tk.Tk()
    app = MonsWeatherApp(root)
    root.mainloop()