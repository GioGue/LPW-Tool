import tkinter as tk
from tkinter import filedialog, messagebox
import plotly.graph_objects as go
import os
import csv

import sys
import os




TESTO_GUIDA = """\
🧠 LPW – Liquidation Preference Waterfall

📄 Come funziona il programma

Questo strumento permette di calcolare il ritorno per LIFTT in scenari di liquidation preference,
sia in modalità puntuale che iterativa. Il programma utilizza file .csv che rappresentano la
struttura dei round di investimento e permette due tipi di analisi:

🎯 Modalità disponibili:

1. Singolo file:
   Calcola il risultato per LIFTT sulla base di un solo scenario di capitalizzazione.

2. Confronto scenario (due file):
   Confronta due scenari distinti caricando due file .csv separati.

3. Calcolo EXIT puntuale:
   Inserisci un valore specifico di EXIT e calcola quanto spetterebbe a LIFTT in ciascuno scenario.

4. Grafico iterativo:
   Calcola per 100 iterazioni il ritorno a LIFTT variando l’EXIT da un minimo a un massimo scelto,
   e crea un grafico per osservare l’andamento del MoIC e dell’EXIT ricevuto.

📁 Requisiti del file .csv

- Formato UTF-8 delimitato da punto e virgola (;)
- Nessun carattere speciale o formule Excel nel file
- Pulire il file da celle vuote o formule nascoste ("Elimina" su righe/colonne Excel vicino ai dati)
- Formato numerico:
  - Interi: 1, 0, 4 (senza decimali)
  - Float: 1.000.000,00 oppure 1000000.00

📑 Template del file .csv

Campi obbligatori (in ordine):

- Seniority: int
  Ordine di liquidazione. 1 = maggiore priorità

- Category_Amount: float
  Valore totale investito per quella classe di azioni

- Liftt_Amount: float
  Come Category_Amount ma quota di investimento LIFTT

- Category_Shares: float
  Totale azioni assegnate alla categoria

- Liftt_Shares: float
  Come Category_Shares ma per azioni LIFTT

- Preferred: int (0 o 1)
  1 = Preferred, 0 = Common

- Participating: int (0 o 1)
  1 = Participating, 0 = Non participating

- CAP: float
  CAP massimo (es. 3.0 per 3x) – 0 se non presente

- MP: float
  Moltiplicatore dell’investimento – tipicamente 1 (anche per le common)

- Common_Pool: int (0 o 1)
  1 = la categoria partecipa alla distribuzione finale del residuo insieme a tutte le altre (waterfall finale),
  0 = la categoria viene esclusa da questa fase. Utile per gestire i casi di participating preferred con CAP.

🔁 Nota sul campo Common_Pool:
Serve a indicare se una categoria partecipa anche alla distribuzione **finale e residuale** dell'EXIT,
dopo che le liquidation preference sono state soddisfatte, quindi dopo aver ricevuto il valore maggiore tra:
    - Conversione in common
    - MP * Amount investito
Si tratta di un caso particolare specificato in alcuni contratti, normalmente non è così.

🛠 Risoluzione errori comuni:

- Controlla che il file sia .csv UTF-8 delimitato da ;
- Rimuovi celle vuote e formule nascoste in Excel
- Verifica il formato dei dati:
  • Interi → numeri come 1 o 0
  • Float → 1.000.000,00 oppure 1000000.00 (il programma li interpreta correttamente)

"""




# Variabili globali per contenere i record dei CSV:
records1 = []  # Scenario 1
records2 = []  # Scenario 2 (opzionale)

# Variabile globale per gestire il pulsante Stop.
stop_flag = False



import locale

# Imposta il formato italiano
locale.setlocale(locale.LC_ALL, 'it_IT.UTF-8')

def formatta_valore_exit(event, entry_widget):
    try:
        testo = entry_widget.get()

        # Rimuovi formattazioni precedenti (punti/virgole)
        testo_pulito = testo.replace('.', '').replace(',', '.')

        # Converti a float e riformatta in stile italiano
        numero = float(testo_pulito)
        testo_formattato = "{:,.2f}".format(numero).replace(",", "X").replace(".", ",").replace("X", ".")

        # Aggiorna campo
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, testo_formattato)

    except ValueError:
        pass  # Ignora se input invalido (non numerico)

# === Funzione per leggere il CSV ===
def parse_float_it(s):
    return float(s.replace('.', '').replace(',', '.'))  # da "1.000.000,00" → "1000000.00"


from PIL import Image, ImageTk
import io
'''
def mostra_grafico_in_tk(fig):
    img_bytes = fig.to_image(format="png")  # ← usa kaleido
    image = Image.open(io.BytesIO(img_bytes))

    win = tk.Toplevel()
    win.title("Grafico LIFTT")
    canvas = tk.Canvas(win, width=image.width, height=image.height)
    canvas.pack()
    tk_img = ImageTk.PhotoImage(image)
    canvas.create_image(0, 0, anchor='nw', image=tk_img)
    canvas.image = tk_img  # evita che l'immagine venga garbage collected
'''

# === Funzione per leggere il CSV ===
def leggi_csv(filepath):
    with open(filepath, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        header = next(reader)  # Legge l'intestazione
        recs = []
        for row in reader:
            # Salta le righe incomplete (ci aspettiamo almeno 9 colonne)
            if len(row) < 9:
                continue
            rec = {
                "Seniority": int(row[0]),
                "Round_Amount": parse_float_it(row[1]),
                "Liftt_Amount": parse_float_it(row[2]),
                "Round_Shares": parse_float_it(row[3]),
                "Liftt_Shares": parse_float_it(row[4]),
                "Preferred": int(row[5]),
                "Participating": int(row[6]),
                "CAP": parse_float_it(row[7]),
                "mp": parse_float_it(row[8]),
                "Common_Pool":int(row[9]),
                "Converto": 0, #questi sono valori che andrò ad aggiornare e che saranno dianmici
                "MP_amount": 0,
                "Y_common": 0,
                "Y_participating": 0,
                "Partecipazione_residua": 0,
                "EXIT_category": 0,
                "EXIT_category_LIFTT": 0,
                "assegnato": 0,
                "Residuo_EXIT_turno": 0
            }
            recs.append(rec)
    return recs

# === Funzioni per caricare i file CSV per Scenario 1 e Scenario 2 ===
def carica_csv1():
    global records1
    filepath = filedialog.askopenfilename(
        title="Carica CSV per Scenario 1",
        filetypes=[("CSV Files", "*.csv")]
    )
    if filepath:
        if not filepath.lower().endswith(".csv"):
            messagebox.showerror("Errore", "Il file selezionato non è un CSV.")
            return
        try:
            records1 = leggi_csv(filepath)
            label_file1.config(text=f"Scenario 1: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel caricamento del file:\n{e}")

def carica_csv2():
    global records2
    filepath = filedialog.askopenfilename(
        title="Carica CSV per Scenario 2",
        filetypes=[("CSV Files", "*.csv")]
    )
    if filepath:
        if not filepath.lower().endswith(".csv"):
            messagebox.showerror("Errore", "Il file selezionato non è un CSV.")
            return
        try:
            records2 = leggi_csv(filepath)
            label_file2.config(text=f"Scenario 2: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel caricamento del file:\n{e}")

# === Funzione di simulazione del modello Waterfall (algoritmo invariato) ===

#non preferred -> trattate alla fine come common sempre
#preferred non participating -> o prendono l'amount investito o convertono, ma quando decidono di convertire?
#quando tocca a loro decidere cosa fare e prendono sulla base della % a prescidere se "rubano" una aprte protetta nelle preferred successive
#oppure invece è come se decidessero di convertire e rimangono in attesa, si va a verificare quando gli spetterebbe alla fine parteciapndo
#al pool finale e poi se non conviene si torna indietro decidono di non convertire si assegna e si procede con gli altri?
#preferred participating invece:
#- assegnano la parte coperta dall'amount investito e poi la % di quello che rimane se non hanno cap
#- assegnano la parte participating e poi quello che rimane solo alla fine dopo la distribuzione a tutte le altre prefferred participating e non
#-se hanno cap ovvimente bisogna verificare alla fine se viene applicato o meno, nel caso in cui venga applicato bisogna tornare indietro teoricamente
#cambiare la decisione di assegnazione e ricalcolare sulla base di essa tutte le successsive
#qual'è quella giusta tra queste??

#METODO TRATTAMENTO DEFINITIVO:
#common alla fine insieme agli atlri
#non participating -> prendono o convertono nel turno se presentano la clausula di conversione
#participating no cap -> mp*amount subito e poi nel pull finale insieme alle common
#participating con cap -> mp*amount subito poi pull finale insieme alle common,se superano il CAP allora si guarda se conviene tagliare al CAP oppure a convertire


def run_waterfall(records, EXIT_input):

    #reset valori iniziali
    for record in records:
        record["Converto"] = 0
        record["MP_amount"] = 0
        record["Y_common"] = 0
        record["Y_participating"] = 0
        record["Partecipazione_residua"] = 0
        record["EXIT_category"] = 0
        record["EXIT_category_LIFTT"] = 0
        record["assegnato"] = 0
        record["Residuo_EXIT_turno"] = 0

    N_TOT = sum(record["Round_Shares"] for record in records) #mi serve il totale di shares per sapere i valori da convertire in common
    EXIT_LIFTT = 0 #questo è il valore che andrò ad aggiornare ad ogni step della waterfall per capir quanto spetta a LIFTT
    N_Common = 0
    N_Common_LIFTT = 0
    LIFTT_Invested = sum(record["Liftt_Amount"] for record in records)
    #print(LIFTT_Invested)


    records_sorted = sorted(records, key=lambda x: x["Seniority"])


    EXIT = EXIT_input
    for record in records_sorted:

        print(record["Seniority"])
        if record["Preferred"] == 1:
            if record["Participating"] == 0:
                #alfa = record["Round_Shares"] / N_TOT
                record["Y_common"] = (record["Round_Shares"] / N_TOT) * EXIT
                record["Y_preferred"] = record["mp"]*record["Round_Amount"]
                #Y_Preferred_LIFTT = Y_Preferred*(record["Liftt_Amount"]/record["Round_Amount"])
                record["EXIT_category"] = max(record["Y_common"], record["Y_preferred"])
                record["EXIT_category_LIFTT"] = record["EXIT_category"]*(record["Liftt_Shares"]/record["Round_Shares"])
                if EXIT < record["EXIT_category"]:
                    print("non c'è più disponibilità e finisco di distribuire")
                    #if EXIT < record["Y_preferred"]:
                        #record["EXIT_category"] = EXIT
                        #record["EXIT_category_LIFTT"] = record["EXIT_category"]*(record["Liftt_Amount"]/record["Round_Amount"])
                    #else:
                    record["EXIT_category"] = EXIT
                    record["EXIT_category_LIFTT"] = record["EXIT_category"] *record["Liftt_Shares"]/record["Round_Shares"]

                #le assegno quindi le possso togliere dal totale
                record["assegnato"] = 1
                EXIT -= record["EXIT_category"]
                #print(record["EXIT_category"])
                #print("rimane:")
                #print(EXIT)
                N_TOT -= record["Round_Shares"]

            if record["Participating"] == 1:
                #record["Residuo_EXIT_turno"] = EXIT
                #alfa = record["Round_Shares"] / N_TOT
                record["Y_common"] = (record["Round_Shares"] / N_TOT) * EXIT
                record["MP_amount"] = record["mp"]*record["Round_Amount"]
                #Y_Preferred_LIFTT = Y_Preferred*(record["Liftt_Amount"]/record["Round_Amount"])
                if EXIT <= record["MP_amount"]: #aasegno subito non ha senso andare avanti se termina il valore di EXIT distribuibile
                        print("valore exit non super mp*amount")
                        record["EXIT_category"] = EXIT
                        record["EXIT_category_LIFTT"] =  record["EXIT_category"]*(record["Liftt_Shares"]/record["Round_Shares"])
                        record["assegnato"] = 1
                        EXIT -= record["EXIT_category"]
                        N_TOT -= record["Round_Shares"]

                else: #se il valore di exit disponibile supera il valore che prenderebbe come preffered ha senso continuare i calcoli
                    print("ho ancora exit disponibile)")
                    if record["CAP"] == 0: #+ una participating senza CAP
                        record["EXIT_category"] = record["MP_amount"]
                        record["EXIT_category_LIFTT"] = record["EXIT_category"]*(record["Liftt_Shares"]/record["Round_Shares"])
                        #print(record["EXIT_category"])
                        EXIT -= record["EXIT_category"]
                        #però devo ancora assegnare il resto
                    if record["CAP"] > 0: #ha il CAP
                        if (record["CAP"]*record["Round_Amount"]) <= record["Y_common"]: #se convertissi subito e ottennessi un valore maggiore del CAP*Amount allora mi conviene convertire (approssimazione, ma buona)
                            print("mi conviene convertire")
                            record["EXIT_category"] = record["Y_common"] #assegno il valore convertito
                            #print(record["EXIT_category"])
                            record["EXIT_category_LIFTT"] = record["EXIT_category"] *record["Liftt_Shares"]/record["Round_Shares"]
                            record["assegnato"] = 1
                            EXIT -= record["EXIT_category"]
                            N_TOT -= record["Round_Shares"]

                        elif record["CAP"]*record["Round_Amount"] > record["Y_common"]: #se invece non è così che faccio? Assehno la parte coperta mp*Amount e aspetto per la parte partecipativa la fine
                            print("si ho una preffered participating")
                            record["EXIT_category"] = record["MP_amount"]
                            record["EXIT_category_LIFTT"] = record["EXIT_category"] *(record["Liftt_Shares"]/record["Round_Shares"])
                            EXIT -= record["EXIT_category"] #devo toglierlo perchè è come fosse già stata assegnata quella parte


#PROBLEMA: assegno l'MP amount però se poi per la participating supero il CAP e decido di convertire che faccio?? devo tornare indietro e trovare un modo per tenere a mente la scelta
    #e cambiare tutte le decisioni successive -> oppure facciò in modo che se converto prendo il valore più alto si alla fine
    #ma questo va a cambiare ad esempio i valori di una non participating che viene dopo? non capisco come fare questa cosa

    print("ora inizio ad assegnare la parte partecipativa")
    for record in records_sorted: #itero su tutti i rimasti
        #print(record["Seniority"])
        if record["assegnato"] == 0: #guardo solo quelli ceh non sono già stati assegnati (così non devo eliminare nessuno
            #record["partecipazione_residua"] = EXIT* (record["Round_Shares"] / N_TOT)
           # print("non è stata ancora assegnata")
            valore_prec =record["EXIT_category"]
            if record["Preferred"] == 1 and record["Participating"] == 1 and record["CAP"] > 0: #se è una preffered participating
                print("è una participating, parte participating")
                #valore_prec = record["EXIT_category"]
                #ho il cap
                print("ha il CAP")
                print("valore precedente category")
                print(record["EXIT_category"])
                partecipazione = EXIT * (record["Round_Shares"] / N_TOT)
                totale_exit = record["MP_amount"] + partecipazione
                #record["EXIT_category"] = record["MP_amount"] + (EXIT * (record["Round_Shares"] / N_TOT))
                #record["EXIT_category_LIFTT"] = record["EXIT_category"]*(record["Liftt_Shares"]/record["Round_Shares"])

                if totale_exit > (record["CAP"]*record["Round_Amount"]): #supero il cap ?
                        totale_exit = record["CAP"]*record["Round_Amount"]
                        #record["EXIT_category"] = record["CAP"]*record["Round_Amount"] #taglio al cap
                        #record["EXIT_category_LIFTT"] = record["EXIT_category"]*(record["Liftt_Amount"]/record["Round_Amount"]) #da controllare

                extra_assegnato = totale_exit - record["EXIT_category"]
                record["EXIT_category"] = totale_exit
                record["EXIT_category_LIFTT"] = record["EXIT_category"]*(record["Liftt_Shares"]/record["Round_Shares"])
                #new_value = record["EXIT_category"]- valore_prec
                print("valore successivo category")
                print(record["EXIT_category"])

                EXIT -= extra_assegnato
                N_TOT -= record["Round_Shares"]
                record["assegnato"] = 1



    print("ora inizio ad assegnare la parte partecipativa")
    for record in records_sorted: #itero su tutti i rimasti
        print(record["Seniority"])
        if record["assegnato"] == 0: #guardo solo quelli ceh non sono già stati assegnati (così non devo eliminare nessuno
            #record["partecipazione_residua"] = EXIT* (record["Round_Shares"] / N_TOT)
            print("non è stata ancora assegnata")
            if record["Preferred"] == 1 and record["Participating"] == 1: #se è una preffered participating
                print("è una participating, parte participating")
                #valore_prec = record["EXIT_category"]
                if record["CAP"] == 0: #senza cap-> semplicemento assegno anche la nuova parte di valore pari alla partecipazione all'ammontare già presente
                    print("si è una participating senza cap")
                    print()
                    record["EXIT_category"] += (EXIT* (record["Round_Shares"] / N_TOT))
                    record["EXIT_category_LIFTT"] = record["EXIT_category"]*record["Liftt_Shares"]/record["Round_Shares"]
                    EXIT -= (EXIT* (record["Round_Shares"] / N_TOT))
                    N_TOT -= record["Round_Shares"]
                    record["assegnato"] = 1

            if record["Preferred"] == 0:
                print(N_TOT)
                print(EXIT)
                record["EXIT_category"] = (EXIT* (record["Round_Shares"] / N_TOT))
                record["EXIT_category_LIFTT"] = (record["EXIT_category"]*(record["Liftt_Shares"]/record["Round_Shares"]))
                EXIT -= record["EXIT_category"]
                print("finita")
                print(EXIT)
                print(record["EXIT_category_LIFTT"])
                N_TOT -= record["Round_Shares"]
                record["assegnato"] = 1



#usata solo per calcolare i totali alla fine
    for record in records_sorted:
        print(record["Seniority"])
        print(record["assegnato"])
        print(record["EXIT_category"])
        print("si è lui")
        print(record["EXIT_category_LIFTT"])
        EXIT_LIFTT += record["EXIT_category_LIFTT"]
    if LIFTT_Invested > 0:
        MoIC = EXIT_LIFTT/LIFTT_Invested
    else:
        MoIC = 0

    return EXIT_LIFTT, MoIC





# === Funzione per fermare il calcolo (button Stop) ===
def stop_calculation():
    global stop_flag
    stop_flag = True

def reset_app():
    global records1, records2, stop_flag
    stop_flag = False
    records1 = []
    records2 = []

    # Reset etichette file
    label_file1.config(text="Nessun file caricato per Scenario 1")
    label_file2.config(text="(Opzionale) Nessun file caricato per Scenario 2")

    # Svuota campi EXIT
    entry_single.delete(0, tk.END)
    entry_min.delete(0, tk.END)
    entry_max.delete(0, tk.END)

    # Reset vista calcolo puntuale come default
    mode_var.set(1)
    aggiorna_modalita()

def mostra_guida():
    guida = tk.Toplevel(root)
    guida.title("Guida - LPW")
    guida.geometry("700x500")
    text = tk.Text(guida, wrap="word")
    text.insert("1.0", TESTO_GUIDA)  # TESTO_GUIDA è una stringa multilinea con la guida qui sopra
    text.pack(expand=True, fill="both")
    text.config(state="disabled")

# === Funzione per il calcolo in base alle combinazioni ---
def calcola():
    global stop_flag
    stop_flag = False  # Reset della flag all'inizio
    # Verifica che almeno un file sia stato caricato
    if not records1 and not records2:
        messagebox.showerror("Errore", "Carica almeno un file CSV (Scenario 1 o Scenario 2).")
        return

    mode = mode_var.get()  # 1 = Calcolo Puntuale, 2 = Grafico Iterativo
    if mode == 1:  # Modalità Calcolo Puntuale
        try:
            exit_value = float(parse_float_it(entry_single.get()))
        except ValueError:
            messagebox.showerror("Errore", "Inserisci un valore numerico valido per EXIT.")
            return
        risultati = ""
        if records1:
            res1, MoIC1 = run_waterfall(records1, exit_value)
            res1_str = f"{res1:,.0f}".replace(",", ".")
            risultati += f"Scenario 1: LIFTT EXIT = {res1_str} €\n"
            risultati += f"Scenario 1: LIFTT MoIC = {MoIC1:,.3f}\n"
        if records2:
            res2, MoIC2 = run_waterfall(records2, exit_value)
            res2_str = f"{res2:,.0f}".replace(",", ".")
            risultati += f"Scenario 2: LIFTT EXIT = {res2_str} €\n"
            risultati += f"Scenario 2: LIFTT MoIC = {MoIC2:,.3f}\n"
        messagebox.showinfo("Risultato", risultati)
    elif mode == 2:  # Modalità Grafico Iterativo
        try:
            exit_min = float(parse_float_it(entry_min.get()))
            exit_max = float(parse_float_it(entry_max.get()))
        except ValueError:
            messagebox.showerror("Errore", "Inserisci valori numerici validi per EXIT Min e EXIT Max.")
            return
        if exit_min >= exit_max:
            messagebox.showerror("Errore", "EXIT Min deve essere minore di EXIT Max.")
            return

        iterations = 100
        passo = (exit_max - exit_min) / iterations
        exit_vals = []
        liftt_vals_1 = []
        moic_vals_1 = []
        liftt_vals_2 = []
        moic_vals_2 = []
        curr = exit_min
        while curr <= exit_max:
            if stop_flag:
                messagebox.showinfo("Interrotto", "Il calcolo iterativo è stato interrotto.")
                break
            exit_vals.append(curr)
            if records1:
                res1, MoIC1 = run_waterfall(records1, curr)
                liftt_vals_1.append(res1)
                moic_vals_1.append(MoIC1)
            else:
                liftt_vals_1.append(None)
                moic_vals_1.append(None)
            if records2:
                res2, MoIC2 = run_waterfall(records2, curr)
                liftt_vals_2.append(res2)
                moic_vals_2.append(MoIC2)
            else:
                liftt_vals_2.append(None)
                moic_vals_2.append(None)
            curr += passo

        from plotly.subplots import make_subplots

        fig = make_subplots(rows=2, cols=1, shared_xaxes=False,
                            vertical_spacing=0.15,
                            subplot_titles=("LIFTT EXIT vs Total EXIT", "MoIC vs Total EXIT"))

        if records1:
            fig.add_trace(go.Scatter(
                x=exit_vals,
                y=liftt_vals_1,
                mode='lines+markers',
                name='Scenario 1 LIFTT EXIT',
                line=dict(color='royalblue', width=2),
                marker=dict(size=4)
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=exit_vals,
                y=moic_vals_1,
                mode='lines+markers',
                name='Scenario 1 MoIC',
                line=dict(color='royalblue', width=2),
                marker=dict(size=4)
            ), row=2, col=1)
        if records2:
            fig.add_trace(go.Scatter(
                x=exit_vals,
                y=liftt_vals_2,
                mode='lines+markers',
                name='Scenario 2 LIFTT EXIT',
                line=dict(color='firebrick', width=2),
                marker=dict(size=4)
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=exit_vals,
                y=moic_vals_2,
                mode='lines+markers',
                name='Scenario 2 MoIC',
                line=dict(color='firebrick', width=2),
                marker=dict(size=4)
            ), row=2, col=1)

        # Aggiunta della linea target per il MoIC (target = 3)
        fig.add_shape(
            type="line",
            x0=min(exit_vals),
            x1=max(exit_vals),
            y0=3,
            y1=3,
            line=dict(color="green", dash="dash", width=2),
            xref="x",
            yref="y2"  # Riferisce l'asse Y del secondo subplot
        )

        fig.update_layout(
        title="Confronto: LIFTT EXIT e MoIC vs Total EXIT",
        template="plotly_white",
        hovermode="x unified",
        width=1100,
        height=800,
        xaxis=dict(title="Total EXIT (€)"),
        yaxis=dict(title="LIFTT EXIT (€)"),
        xaxis2=dict(title="Total EXIT (€)"),
        yaxis2=dict(title="MoIC (x)"),
        )
        fig.update_xaxes(tickformat=",.0f", row=1, col=1)
        fig.update_xaxes(tickformat=",.0f", row=2, col=1)
        fig.update_yaxes(tickformat=",.0f", row=1, col=1)
        fig.update_yaxes(tickformat=",.3f", row=2, col=1)
        fig.show()
        #mostra_grafico_in_tk(fig)

    else:
        messagebox.showerror("Errore", "Seleziona una modalità di calcolo valida.")

# === Funzione per aggiornare l'interfaccia in base alla modalità scelta ===
def aggiorna_modalita():
    mode = mode_var.get()
    if mode == 1:
        frame_single.pack(pady=10, fill='x')
        frame_graph.pack_forget()
    elif mode == 2:
        frame_graph.pack(pady=10, fill='x')
        frame_single.pack_forget()



# ==== Costruzione della GUI ====

root = tk.Tk()
root.title("Liquidation Preference Waterfall")
root.geometry("900x400")  # Dimensione della finestra
#root.iconbitmap("LPW_1.0.1.ico")

# Percorso corretto per caricare l'icona anche da eseguibile
if hasattr(sys, "_MEIPASS"):
    icon_path = os.path.join(sys._MEIPASS, "LPW_1.0.1.ico")
else:
    icon_path = "LPW_1.0.1.ico"

root.iconbitmap(icon_path)

#root.iconbitmap(icon_path)
# Frame per il caricamento dei file CSV
frame_file = tk.Frame(root, padx=10, pady=10)
frame_file.pack(fill='x')
btn_load1 = tk.Button(frame_file, text="Carica CSV Scenario 1...", command=carica_csv1)
btn_load1.pack(side='left')
label_file1 = tk.Label(frame_file, text="Nessun file caricato per Scenario 1")
label_file1.pack(side='left', padx=10)
btn_load2 = tk.Button(frame_file, text="Carica CSV Scenario 2...", command=carica_csv2)
btn_load2.pack(side='left', padx=(20,0))
label_file2 = tk.Label(frame_file, text="(Opzionale) Nessun file caricato per Scenario 2")
label_file2.pack(side='left', padx=10)

# Frame per la scelta della modalità di calcolo (Radio Buttons)
frame_mode = tk.Frame(root, padx=10, pady=10)
frame_mode.pack(fill='x')
mode_var = tk.IntVar(value=1)
tk.Label(frame_mode, text="Modalità di calcolo:").pack(side='left')
radio_puntuale = tk.Radiobutton(frame_mode, text="Calcolo puntuale", variable=mode_var, value=1, command=aggiorna_modalita)
radio_puntuale.pack(side='left', padx=10)
radio_grafico = tk.Radiobutton(frame_mode, text="Grafico iterativo", variable=mode_var, value=2, command=aggiorna_modalita)
radio_grafico.pack(side='left', padx=10)

#
# Frame per il calcolo puntuale (un solo valore EXIT)
frame_single = tk.Frame(root, padx=10, pady=10)
frame_single.pack(fill='x')
tk.Label(frame_single, text="Inserisci valore EXIT (€):").pack(side='left')

entry_single = tk.Entry(frame_single)
entry_single.pack(side='left', padx=5)

# 🔁 Collega la funzione al campo per formattare mentre si scrive
entry_single.bind("<FocusOut>", lambda event: formatta_valore_exit(event, entry_single))
#

# Frame per il grafico iterativo (campi EXIT Min e EXIT Max)
'''frame_graph = tk.Frame(root, padx=10, pady=10)
tk.Label(frame_graph, text="EXIT Min (€):").grid(row=0, column=0, padx=5, pady=5)
entry_min = tk.Entry(frame_graph)
entry_min.grid(row=0, column=1, padx=5, pady=5)
tk.Label(frame_graph, text="EXIT Max (€):").grid(row=1, column=0, padx=5, pady=5)
entry_max = tk.Entry(frame_graph)
entry_max.grid(row=1, column=1, padx=5, pady=5)
'''
# Frame per il grafico iterativo (campi EXIT Min e EXIT Max)
frame_graph = tk.Frame(root, padx=10, pady=10)
tk.Label(frame_graph, text="EXIT Min (€):").grid(row=0, column=0, padx=5, pady=5)

entry_min = tk.Entry(frame_graph)
entry_min.grid(row=0, column=1, padx=5, pady=5)
entry_min.bind("<FocusOut>", lambda event: formatta_valore_exit(event, entry_min))  # 🔁 formatta

tk.Label(frame_graph, text="EXIT Max (€):").grid(row=1, column=0, padx=5, pady=5)

entry_max = tk.Entry(frame_graph)
entry_max.grid(row=1, column=1, padx=5, pady=5)
entry_max.bind("<FocusOut>", lambda event: formatta_valore_exit(event, entry_max))  # 🔁 formatta

if mode_var.get() == 2:
    frame_graph.pack(fill='x', padx=10, pady=10)
else:
    frame_graph.pack_forget()

# Bottone per eseguire il calcolo
btn_calc = tk.Button(root, text="Calcola", command=calcola)
btn_calc.pack(pady=10)

# Bottone per RESET
btn_reset = tk.Button(root, text="Reset", command=reset_app, fg="darkblue")
btn_reset.pack(pady=5)

#Bottone GUIDA
btn_help = tk.Button(root, text="Guida ℹ️", command=mostra_guida)
btn_help.pack(pady=5)



root.mainloop()


