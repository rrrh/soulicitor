import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
import os

DB_FILE = "vinyl.db"
STYLES_LIST = ["House", "Techno", "Ambient", "Disco", "Drum & Bass", "Dubstep", "Hip Hop", "Jazz", "Rock", "Pop", "Other"]

def init_db():
    # DEVELOPMENT MODE: Completely wipe the database on startup
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print("Development state: Existing database dropped.")
        except PermissionError:
            print("Warning: Could not drop database (file might be locked).")

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        
        conn.executescript("""
        CREATE TABLE Records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('7"', '12"')),
            title TEXT,
            CONSTRAINT chk_title_type CHECK (
                (type = '12"' AND title IS NOT NULL AND title != '') OR 
                (type = '7"' AND title IS NULL)
            )
        );
        CREATE TABLE Tracks (
            track_id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            artist TEXT,
            title TEXT NOT NULL,
            bpm INTEGER CHECK(bpm > 0),
            style TEXT,
            runtime TEXT,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            FOREIGN KEY (record_id) REFERENCES Records(record_id) ON DELETE CASCADE
        );
        """)

class VinylApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Vinyl Database (Dev Mode)")
        self.geometry("1100x550")
        
        self.active_editor = None 
        
        init_db()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        left = tk.Frame(self, padx=10, pady=10)
        left.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(left, text="Format").grid(row=0, column=0, sticky="w")
        self.type_var = tk.StringVar(value='12"')
        self.type_cb = ttk.Combobox(left, textvariable=self.type_var, values=['12"', '7"'], state="readonly")
        self.type_cb.grid(row=0, column=1, pady=2)
        self.type_cb.bind("<<ComboboxSelected>>", self.toggle_title)

        # REARRANGED: Artist is now row 1
        tk.Label(left, text="Artist").grid(row=1, column=0, sticky="w")
        self.artist = tk.Entry(left)
        self.artist.grid(row=1, column=1, pady=2)

        # REARRANGED: Record Title is now row 2
        tk.Label(left, text="Record Title").grid(row=2, column=0, sticky="w")
        self.rec_title = tk.Entry(left)
        self.rec_title.grid(row=2, column=1, pady=2)

        tk.Label(left, text="Track Title").grid(row=3, column=0, sticky="w")
        self.trk_title = tk.Entry(left)
        self.trk_title.grid(row=3, column=1, pady=2)

        tk.Label(left, text="BPM").grid(row=4, column=0, sticky="w")
        self.bpm = tk.Entry(left)
        self.bpm.grid(row=4, column=1, pady=2)

        tk.Label(left, text="Style").grid(row=5, column=0, sticky="w")
        self.style = ttk.Combobox(left, values=STYLES_LIST)
        self.style.grid(row=5, column=1, pady=2)

        tk.Label(left, text="Runtime").grid(row=6, column=0, sticky="w")
        self.runtime = tk.Entry(left)
        self.runtime.grid(row=6, column=1, pady=2)

        tk.Label(left, text="Rating (1-5)").grid(row=7, column=0, sticky="w")
        self.rating = ttk.Combobox(left, values=[1, 2, 3, 4, 5], state="readonly")
        self.rating.set(5)
        self.rating.grid(row=7, column=1, pady=2)

        tk.Label(left, text="Comment").grid(row=8, column=0, sticky="w")
        self.comment = tk.Entry(left)
        self.comment.grid(row=8, column=1, pady=2)

        tk.Button(left, text="Save Record", command=self.save_record, bg="#333", fg="white").grid(row=9, columnspan=2, pady=10, sticky="we")
        tk.Frame(left, height=2, bd=1, relief=tk.SUNKEN).grid(row=10, columnspan=2, sticky="we", pady=10)
        tk.Button(left, text="Export CSV", command=self.export_csv).grid(row=11, column=0, sticky="we", padx=2)
        tk.Button(left, text="Import CSV", command=self.import_csv).grid(row=11, column=1, sticky="we", padx=2)

        right = tk.Frame(self, padx=10, pady=10)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # REARRANGED: Artist comes before Record
        columns = ("Type", "Artist", "Record", "Track", "BPM", "Style", "Time", "Rating", "RecID", "TrkID")
        display_cols = ("Type", "Artist", "Record", "Track", "BPM", "Style", "Time", "Rating")
        
        self.tree = ttk.Treeview(right, columns=columns, show="headings", displaycolumns=display_cols)
        for col in display_cols:
            self.tree.heading(col, text=col)
            width = 60 if col in ("Type", "BPM", "Time", "Rating") else 120
            self.tree.column(col, width=width)
        
        scrollbar = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-1>", self.on_tree_single_click)

    def toggle_title(self, event=None):
        if self.type_var.get() == '7"':
            self.rec_title.delete(0, tk.END)
            self.rec_title.config(state="disabled")
        else:
            self.rec_title.config(state="normal")

    def load_data(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # REARRANGED: Select Artist before Title
            cursor.execute("""
                SELECT r.type, t.artist, r.title, t.title, t.bpm, t.style, t.runtime, t.rating, r.record_id, t.track_id
                FROM Records r JOIN Tracks t ON r.record_id = t.record_id
            """)
            for row in cursor.fetchall():
                display_row = list(row)
                display_row[1] = row[1] if row[1] else "" # Artist
                display_row[2] = row[2] if row[2] else "" # Record Title
                display_row[7] = "★" * int(row[7]) if row[7] else "" 
                self.tree.insert("", tk.END, values=display_row)

    def on_tree_single_click(self, event):
        if self.active_editor and self.active_editor.winfo_exists():
            self.active_editor.destroy()
            self.active_editor = None

    def on_double_click(self, event):
        if self.active_editor and self.active_editor.winfo_exists():
            self.active_editor.destroy()

        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or not column: return

        col_idx = int(column.replace('#', '')) - 1
        record_type = self.tree.item(item, 'values')[0]

        # MODIFIED: Record Title is now at col_idx == 2
        if col_idx == 2 and record_type == '7"':
            return

        x, y, w, h = self.tree.bbox(item, column)
        current_value = self.tree.item(item, 'values')[col_idx]
        
        if col_idx == 7: current_value = len(current_value) if current_value else ""

        def save_edit(event=None):
            new_value = entry.get()
            if entry.winfo_exists():
                entry.destroy()
            self.active_editor = None
            self.update_database(item, col_idx, new_value)

        if col_idx == 0:  
            entry = ttk.Combobox(self.tree, values=['12"', '7"'], state="readonly")
            entry.set(current_value)
            entry.bind('<<ComboboxSelected>>', save_edit)
        elif col_idx == 5: 
            entry = ttk.Combobox(self.tree, values=STYLES_LIST)
            entry.set(current_value)
            entry.bind('<<ComboboxSelected>>', save_edit)
        elif col_idx == 7: 
            entry = ttk.Combobox(self.tree, values=[1, 2, 3, 4, 5], state="readonly")
            entry.set(current_value)
            entry.bind('<<ComboboxSelected>>', save_edit)
        else:  
            entry = tk.Entry(self.tree)
            entry.insert(0, current_value)

        entry.place(x=x, y=y, width=w, height=h)
        entry.focus()
        
        self.active_editor = entry

        entry.bind('<Return>', save_edit)
        entry.bind('<Escape>', lambda e: entry.destroy())
        
        if not isinstance(entry, ttk.Combobox):
            entry.bind('<FocusOut>', lambda e: entry.destroy() if entry.winfo_exists() else None)

    def update_database(self, item, col_idx, new_value):
        values = list(self.tree.item(item, 'values'))
        record_id = values[8] 
        track_id = values[9]  

        # REARRANGED mapping dictionary
        col_map = {
            0: ("Records", "type", record_id, "record_id"),
            1: ("Tracks", "artist", track_id, "track_id"),
            2: ("Records", "title", record_id, "record_id"),
            3: ("Tracks", "title", track_id, "track_id"),
            4: ("Tracks", "bpm", track_id, "track_id"),
            5: ("Tracks", "style", track_id, "track_id"),
            6: ("Tracks", "runtime", track_id, "track_id"),
            7: ("Tracks", "rating", track_id, "track_id")
        }
        
        table, field, pk_val, pk_col = col_map[col_idx]

        if field == "rating":
            try: new_value = int(new_value)
            except ValueError: return messagebox.showerror("Error", "Rating must be an integer (1-5).")
        elif field == "bpm":
            if new_value:
                try: new_value = int(new_value)
                except ValueError: return messagebox.showerror("Error", "BPM must be an integer.")
            else: new_value = None
        elif field == "title" and table == "Records":
            if not new_value: return messagebox.showerror("Error", "12\" records must have a title.")

        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("PRAGMA foreign_keys = ON;")
                cursor = conn.cursor()
                
                if field == "type":
                    if new_value == '7"':
                        cursor.execute(f"UPDATE {table} SET type = ?, title = NULL WHERE {pk_col} = ?", (new_value, pk_val))
                    else:
                        cursor.execute(f"SELECT title FROM {table} WHERE {pk_col} = ?", (pk_val,))
                        curr_title = cursor.fetchone()[0]
                        if not curr_title:
                            cursor.execute(f"UPDATE {table} SET type = ?, title = 'New 12\"' WHERE {pk_col} = ?", (new_value, pk_val))
                        else:
                            cursor.execute(f"UPDATE {table} SET type = ? WHERE {pk_col} = ?", (new_value, pk_val))
                else:
                    cursor.execute(f"UPDATE {table} SET {field} = ? WHERE {pk_col} = ?", (new_value, pk_val))
            
            self.load_data()
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Database Constraint Error", f"Action rejected: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_record(self):
        r_type = self.type_var.get()
        r_title = self.rec_title.get() if r_type == '12"' else None
        
        t_title = self.trk_title.get()
        t_artist = self.artist.get() 

        if not t_title or (r_type == '12"' and not r_title):
            messagebox.showerror("Error", "Required fields missing.")
            return

        bpm_val = self.bpm.get()
        bpm_val = int(bpm_val) if bpm_val.isdigit() else None
        
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("PRAGMA foreign_keys = ON;")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Records (type, title) VALUES (?, ?)", (r_type, r_title))
                rec_id = cursor.lastrowid
                
                cursor.execute("""
                    INSERT INTO Tracks (record_id, artist, title, bpm, style, runtime, rating, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (rec_id, t_artist, t_title, bpm_val, self.style.get(), self.runtime.get(), self.rating.get(), self.comment.get()))
            
            self.artist.delete(0, tk.END)
            self.trk_title.delete(0, tk.END)
            self.bpm.delete(0, tk.END)
            self.load_data()
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

    def export_csv(self):
        file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not file: return
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # REARRANGED: Artist before Record Title
            cursor.execute("SELECT r.type, t.artist, r.title, t.title, t.bpm, t.style, t.runtime, t.rating, t.comment FROM Records r JOIN Tracks t ON r.record_id = t.record_id")
            rows = cursor.fetchall()
            
        with open(file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Record_Type", "Artist", "Record_Title", "Track_Title", "BPM", "Style", "Runtime", "Rating", "Comment"])
            writer.writerows(rows)
        messagebox.showinfo("Success", "Export complete!")

    def import_csv(self):
        file = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not file: return
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                with sqlite3.connect(DB_FILE) as conn:
                    cursor = conn.cursor()
                    for row in reader:
                        rtype = row.get("Record_Type", '12"')
                        rtitle = row.get("Record_Title") if rtype == '12"' else None
                        
                        cursor.execute("INSERT INTO Records (type, title) VALUES (?, ?)", (rtype, rtitle))
                        rec_id = cursor.lastrowid
                        
                        bpm = int(row.get("BPM")) if row.get("BPM") else None
                        rating = int(row.get("Rating")) if row.get("Rating") else 3
                        
                        cursor.execute("""
                            INSERT INTO Tracks (record_id, artist, title, bpm, style, runtime, rating, comment)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (rec_id, row.get("Artist", ""), row.get("Track_Title"), bpm, row.get("Style"), row.get("Runtime"), rating, row.get("Comment")))
            self.load_data()
            messagebox.showinfo("Success", "Import complete!")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))

if __name__ == "__main__":
    app = VinylApp()
    app.mainloop()
