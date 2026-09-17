import imgui
from imgui.integrations.glfw import GlfwRenderer
import glfw
import OpenGL.GL as gl
import sqlite3
import csv
import os
import subprocess
import shutil
import tkinter as tk
from tkinter import filedialog

DB_FILE = "vinyl.db"
STYLES_LIST = ["House", "Techno", "Ambient", "Disco", "Drum & Bass", "Dubstep", "Hip Hop", "Jazz", "Rock", "Pop", "Other"]

TK_ROOT = tk.Tk()
TK_ROOT.withdraw()

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS Records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('7"', '12"')),
            title TEXT,
            CONSTRAINT chk_title_type CHECK (
                (type = '12"' AND title IS NOT NULL AND title != '') OR 
                (type = '7"' AND title IS NULL)
            )
        );
        CREATE TABLE IF NOT EXISTS Tracks (
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
        CREATE TABLE IF NOT EXISTS Settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)

class AppState:
    def __init__(self):
        self.records = []
        self.row_buffers = {} 
        self.error_message = None
        self.success_message = None
        
        # Form fields for Add/Import tab
        self.f_type = 0  
        self.f_artist = ""
        self.f_record = ""
        self.f_track = ""
        self.f_bpm = ""
        self.f_style = 0
        self.f_runtime = ""
        self.f_rating = 4  
        self.f_comment = ""
        
        # Configuration fields
        self.conf_name = ""
        self.conf_email = ""
        self.conf_git_repo = ""
        self.conf_git_branch = "main"
        self.conf_git_path = ""
        
        # Git state
        self.git_output = ""
        
        # Mocked list of connected users
        self.connected_users = [
            "DJ_Spark (10.0.0.42)", 
            "VinylJunkie_99 (192.168.1.104)",
            "TechnoDad (Offline)"
        ]

    def load_data(self):
        self.records = []
        self.row_buffers = {}
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                
                # Load Collection
                cursor.execute("""
                    SELECT r.type, t.artist, r.title, t.title, t.bpm, t.style, t.runtime, t.rating, r.record_id, t.track_id, t.comment
                    FROM Records r JOIN Tracks t ON r.record_id = t.record_id
                """)
                self.records = cursor.fetchall()
                
                for row in self.records:
                    trk_id = row[9]
                    self.row_buffers[trk_id] = {
                        0: 0 if row[0] == '12"' else 1,
                        1: row[1] or "",
                        2: row[2] or "",
                        3: row[3] or "",
                        4: str(row[4]) if row[4] else "",
                        5: STYLES_LIST.index(row[5]) if row[5] in STYLES_LIST else 0,
                        6: row[6] or "",
                        7: int(row[7]) - 1 if row[7] else 4
                    }
                    
                # Load Settings
                cursor.execute("SELECT key, value FROM Settings")
                settings = dict(cursor.fetchall())
                self.conf_name = settings.get("name", "")
                self.conf_email = settings.get("email", "")
                self.conf_git_repo = settings.get("git_repo", "")
                self.conf_git_branch = settings.get("git_branch", "main")
                self.conf_git_path = settings.get("git_path", "")
                
        except Exception as e:
            self.error_message = str(e)

def update_db(state, rec_id, trk_id, col_idx, new_value):
    col_map = {
        0: ("Records", "type", rec_id, "record_id"),
        1: ("Tracks", "artist", trk_id, "track_id"),
        2: ("Records", "title", rec_id, "record_id"),
        3: ("Tracks", "title", trk_id, "track_id"),
        4: ("Tracks", "bpm", trk_id, "track_id"),
        5: ("Tracks", "style", trk_id, "track_id"),
        6: ("Tracks", "runtime", trk_id, "track_id"),
        7: ("Tracks", "rating", trk_id, "track_id")
    }
    
    table, field, pk_val, pk_col = col_map[col_idx]

    if field == "rating":
        new_value = int(new_value)
    elif field == "bpm":
        new_value = int(new_value) if new_value and str(new_value).isdigit() else None
    elif field == "title" and table == "Records":
        if not new_value: 
            state.error_message = "12\" records must have a title."
            state.load_data() 
            return

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            
            if field == "type":
                if new_value == '7"':
                    cursor.execute(f"UPDATE {table} SET type = ?, title = NULL WHERE {pk_col} = ?", (new_value, pk_val))
                else:
                    cursor.execute(f"SELECT title FROM {table} WHERE {pk_col} = ?", (pk_val,))
                    if not cursor.fetchone()[0]:
                        cursor.execute(f"UPDATE {table} SET type = ?, title = 'New 12\"' WHERE {pk_col} = ?", (new_value, pk_val))
                    else:
                        cursor.execute(f"UPDATE {table} SET type = ? WHERE {pk_col} = ?", (new_value, pk_val))
            else:
                cursor.execute(f"UPDATE {table} SET {field} = ? WHERE {pk_col} = ?", (new_value, pk_val))
        
        state.load_data()
    except Exception as e:
        state.error_message = f"Constraint Error: {str(e)}"
        state.load_data()

def save_configuration(state):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            settings_data = {
                "name": state.conf_name,
                "email": state.conf_email,
                "git_repo": state.conf_git_repo,
                "git_branch": state.conf_git_branch,
                "git_path": state.conf_git_path
            }
            
            for key, value in settings_data.items():
                cursor.execute("INSERT OR REPLACE INTO Settings (key, value) VALUES (?, ?)", (key, value))
                
        state.success_message = "Configuration saved successfully!"
    except Exception as e:
        state.error_message = f"Error saving configuration: {str(e)}"

# --- GIT HELPER FUNCTIONS ---
def run_git_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        return result.stdout + result.stderr + "\n"
    except subprocess.CalledProcessError as e:
        raise Exception(f"Git Error:\n{e.stderr}\nCommand: {' '.join(cmd)}")

def read_git_repo(state):
    if not state.conf_git_path:
        state.error_message = "Please configure your Git Local Path in the Configuration tab first."
        return
        
    state.git_output = "Starting git read/clone sequence...\n"
    try:
        if not os.path.exists(state.conf_git_path):
            os.makedirs(state.conf_git_path)
            
        git_dir = os.path.join(state.conf_git_path, ".git")
        if not os.path.exists(git_dir):
            if not state.conf_git_repo:
                raise Exception("Git Remote URL is not configured.")
            state.git_output += run_git_cmd(["git", "clone", state.conf_git_repo, "."], cwd=state.conf_git_path)
        else:
            state.git_output += run_git_cmd(["git", "fetch", "--all"], cwd=state.conf_git_path)
            
        try:
            state.git_output += run_git_cmd(["git", "checkout", state.conf_git_branch], cwd=state.conf_git_path)
            state.git_output += run_git_cmd(["git", "pull", "origin", state.conf_git_branch], cwd=state.conf_git_path)
        except Exception:
            state.git_output += f"Branch '{state.conf_git_branch}' not found remotely. Creating locally...\n"
            state.git_output += run_git_cmd(["git", "checkout", "-b", state.conf_git_branch], cwd=state.conf_git_path)

        repo_db = os.path.join(state.conf_git_path, DB_FILE)
        if os.path.exists(repo_db):
            shutil.copy(repo_db, DB_FILE)
            state.git_output += f"Database successfully copied from {state.conf_git_branch}.\n"
            state.load_data()
        else:
            state.git_output += "No vinyl.db found in repository. You have a fresh slate!\n"
            
        state.success_message = "Git Read successful!"
    except Exception as e:
        state.git_output += f"FAILED:\n{str(e)}\n"
        state.error_message = str(e)

def push_git_repo(state):
    if not state.conf_git_path or not os.path.exists(os.path.join(state.conf_git_path, ".git")):
        state.error_message = "Git repository not found. Please Read/Clone first."
        return
        
    state.git_output = "Starting git commit & push sequence...\n"
    try:
        if state.conf_name: 
            run_git_cmd(["git", "config", "user.name", state.conf_name], cwd=state.conf_git_path)
        if state.conf_email: 
            run_git_cmd(["git", "config", "user.email", state.conf_email], cwd=state.conf_git_path)

        try:
            run_git_cmd(["git", "checkout", state.conf_git_branch], cwd=state.conf_git_path)
        except Exception:
            run_git_cmd(["git", "checkout", "-b", state.conf_git_branch], cwd=state.conf_git_path)

        repo_db = os.path.join(state.conf_git_path, DB_FILE)
        shutil.copy(DB_FILE, repo_db)
        
        state.git_output += run_git_cmd(["git", "add", DB_FILE], cwd=state.conf_git_path)
        
        status = run_git_cmd(["git", "status", "--porcelain"], cwd=state.conf_git_path)
        if status.strip():
            state.git_output += run_git_cmd(["git", "commit", "-m", f"Auto-update database by {state.conf_name}"], cwd=state.conf_git_path)
            state.git_output += run_git_cmd(["git", "push", "-u", "origin", state.conf_git_branch], cwd=state.conf_git_path)
            state.success_message = "Git Push successful!"
        else:
            state.git_output += "No database changes found. Nothing to commit.\n"
            state.success_message = "No changes to commit."
            
    except Exception as e:
        state.git_output += f"FAILED:\n{str(e)}\n"
        state.error_message = str(e)


def render_ui(state):
    viewport = imgui.get_main_viewport()
    imgui.set_next_window_position(0, 0)
    imgui.set_next_window_size(viewport.size.x, viewport.size.y)
    
    flags = imgui.WINDOW_NO_DECORATION | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_BRING_TO_FRONT_ON_FOCUS
    imgui.begin("SoulSearch", flags=flags)

    # --- LEFT SIDEBAR: CONNECTED USERS ---
    sidebar_width = 250
    imgui.begin_child("Sidebar", width=sidebar_width, border=True)
    imgui.spacing()
    imgui.text("NETWORK")
    imgui.separator()
    imgui.spacing()
    
    if not state.connected_users:
        imgui.text_disabled("No users connected.")
    else:
        for user in state.connected_users:
            if "Offline" in user:
                imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
            else:
                imgui.push_style_color(imgui.COLOR_TEXT, 0.2, 0.8, 0.2, 1.0)
            
            imgui.bullet_text(user)
            imgui.pop_style_color(1)
            
    imgui.end_child()
    imgui.same_line()
    
    # --- RIGHT AREA: MAIN TABS ---
    imgui.begin_child("MainContent", border=False)

    if imgui.begin_tab_bar("MainTabBar"):
        
        # --- TAB 1: PRIVATE (SPREADSHEET GRID) ---
        expanded, _ = imgui.begin_tab_item("Private")
        if expanded:
            imgui.spacing()
            imgui.text("Edits auto-save to the database when you click away or press Enter.")
            imgui.separator()
            
            imgui.columns(8, "collection_columns")
            for h in ["Format", "Artist", "Record", "Track", "BPM", "Style", "Time", "Rating"]:
                imgui.text(h)
                imgui.next_column()
            imgui.separator()
            
            for row in state.records:
                rec_id, trk_id = row[8], row[9]
                
                if trk_id not in state.row_buffers:
                    continue
                buf = state.row_buffers[trk_id]
                
                imgui.push_item_width(-1)
                
                # Format Combo
                changed, buf[0] = imgui.combo(f"##fmt_{trk_id}", buf[0], ['12"', '7"'])
                if changed: update_db(state, rec_id, trk_id, 0, ['12"', '7"'][buf[0]])
                imgui.next_column()
                
                # Artist Text
                changed, buf[1] = imgui.input_text(f"##art_{trk_id}", buf[1], 256)
                if imgui.is_item_deactivated_after_edit(): update_db(state, rec_id, trk_id, 1, buf[1])
                imgui.next_column()
                
                # Record Text (Locked out if 7")
                if buf[0] == 1:
                    imgui.text_disabled("N/A")
                else:
                    changed, buf[2] = imgui.input_text(f"##rec_{trk_id}", buf[2], 256)
                    if imgui.is_item_deactivated_after_edit(): update_db(state, rec_id, trk_id, 2, buf[2])
                imgui.next_column()
                
                # Track Text
                changed, buf[3] = imgui.input_text(f"##trk_{trk_id}", buf[3], 256)
                if imgui.is_item_deactivated_after_edit(): update_db(state, rec_id, trk_id, 3, buf[3])
                imgui.next_column()
                
                # BPM Text
                changed, buf[4] = imgui.input_text(f"##bpm_{trk_id}", buf[4], 10)
                if imgui.is_item_deactivated_after_edit(): update_db(state, rec_id, trk_id, 4, buf[4])
                imgui.next_column()
                
                # Style Combo
                changed, buf[5] = imgui.combo(f"##sty_{trk_id}", buf[5], STYLES_LIST)
                if changed: update_db(state, rec_id, trk_id, 5, STYLES_LIST[buf[5]])
                imgui.next_column()
                
                # Runtime Text
                changed, buf[6] = imgui.input_text(f"##time_{trk_id}", buf[6], 10)
                if imgui.is_item_deactivated_after_edit(): update_db(state, rec_id, trk_id, 6, buf[6])
                imgui.next_column()
                
                # Rating Combo
                changed, buf[7] = imgui.combo(f"##rat_{trk_id}", buf[7], ["1", "2", "3", "4", "5"])
                if changed: update_db(state, rec_id, trk_id, 7, buf[7] + 1)
                imgui.next_column()
                
                imgui.pop_item_width()

            imgui.columns(1)
            imgui.end_tab_item()

        # --- TAB 2: COLOBATATIVE ---
        expanded, _ = imgui.begin_tab_item("Public")
        if expanded:
            imgui.spacing()
            imgui.text("Collaborative collection features will appear here.")
            imgui.end_tab_item()

        # --- TAB 3: ADD / IMPORT ---
        expanded, _ = imgui.begin_tab_item("Add / Import")
        if expanded:
            imgui.spacing()
            imgui.text("ADD NEW RECORD")
            imgui.separator()
            imgui.spacing()

            _, state.f_type = imgui.combo("Format", state.f_type, ['12"', '7"'])
            _, state.f_artist = imgui.input_text("Artist", state.f_artist, 256)
            
            if state.f_type == 1:
                imgui.text_disabled("Record Title (Disabled for 7\")")
                state.f_record = ""
            else:
                _, state.f_record = imgui.input_text("Record Title", state.f_record, 256)
                
            _, state.f_track = imgui.input_text("Track Title", state.f_track, 256)
            _, state.f_bpm = imgui.input_text("BPM", state.f_bpm, 10)
            _, state.f_style = imgui.combo("Style", state.f_style, STYLES_LIST)
            _, state.f_runtime = imgui.input_text("Runtime", state.f_runtime, 10)
            _, state.f_rating = imgui.combo("Rating", state.f_rating, ["1", "2", "3", "4", "5"])
            _, state.f_comment = imgui.input_text("Comment", state.f_comment, 256)
            
            imgui.spacing()
            if imgui.button("Save Record", width=200):
                save_record(state)
                
            imgui.spacing()
            imgui.separator()
            imgui.spacing()
            
            imgui.text("DATA MANAGEMENT")
            imgui.spacing()
            if imgui.button("Export CSV", width=150):
                export_csv(state)
            imgui.same_line()
            if imgui.button("Import CSV", width=150):
                import_csv(state)
                
            imgui.end_tab_item()

        # --- TAB 4: VERIFY / SHARE (GIT INTEGRATION) ---
        expanded, _ = imgui.begin_tab_item("Verify / Share")
        if expanded:
            imgui.spacing()
            imgui.text_colored("GIT SYNCHRONIZATION", 0.4, 0.8, 1.0, 1.0)
            imgui.separator()
            imgui.spacing()
            
            imgui.text(f"Configured Local Path: {state.conf_git_path}")
            imgui.text(f"Personal Branch: {state.conf_git_branch}")
            imgui.spacing()
            
            if imgui.button("Read / Clone Git Repository", width=250):
                read_git_repo(state)
                
            imgui.same_line()
            if imgui.button("Commit & Push to Personal Branch", width=250):
                push_git_repo(state)
                
            imgui.spacing()
            imgui.text("Git Log:")
            imgui.input_text_multiline(
                "##gitlog", 
                state.git_output, 
                8192, 
                -1, 
                250, 
                flags=imgui.INPUT_TEXT_READ_ONLY
            )
            
            imgui.end_tab_item()

        # --- TAB 5: CONFIGURATION ---
        expanded, _ = imgui.begin_tab_item("Configuration", flags=imgui.TAB_ITEM_TRAILING)
        if expanded:
            imgui.spacing()
            
            imgui.text_colored("PERSONAL INFORMATION", 0.4, 0.8, 1.0, 1.0)
            imgui.separator()
            imgui.spacing()
            _, state.conf_name = imgui.input_text("Display Name", state.conf_name, 256)
            _, state.conf_email = imgui.input_text("Email Address", state.conf_email, 256)
            
            imgui.spacing()
            imgui.spacing()
            
            imgui.text_colored("GIT REPOSITORY SETUP", 0.4, 0.8, 1.0, 1.0)
            imgui.separator()
            imgui.spacing()
            _, state.conf_git_repo = imgui.input_text("Remote Repo URL", state.conf_git_repo, 256)
            _, state.conf_git_branch = imgui.input_text("Branch", state.conf_git_branch, 128)
            
            imgui.spacing()
            if imgui.button("Browse..."):
                selected_dir = filedialog.askdirectory(title="Select Local Git Directory")
                if selected_dir:
                    state.conf_git_path = selected_dir
            imgui.same_line()
            _, state.conf_git_path = imgui.input_text("Local Path", state.conf_git_path, 512)
            
            imgui.spacing()
            imgui.spacing()
            
            if imgui.button("Save Configuration", width=200):
                save_configuration(state)
                
            imgui.end_tab_item()

        imgui.end_tab_bar()
        
    imgui.end_child()
    imgui.end()
    
    # Error Popup Modal
    if state.error_message:
        imgui.open_popup("Error")
    if imgui.begin_popup_modal("Error", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
        imgui.text(state.error_message)
        imgui.spacing()
        if imgui.button("OK", width=120):
            state.error_message = None
            imgui.close_current_popup()
        imgui.end_popup()

    # Success Popup Modal
    if state.success_message:
        imgui.open_popup("Success")
    if imgui.begin_popup_modal("Success", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
        imgui.text(state.success_message)
        imgui.spacing()
        if imgui.button("OK", width=120):
            state.success_message = None
            imgui.close_current_popup()
        imgui.end_popup()

def save_record(state):
    r_type = ['12"', '7"'][state.f_type]
    r_title = state.f_record if r_type == '12"' else None
    
    if not state.f_track or (r_type == '12"' and not r_title):
        state.error_message = "Required fields missing."
        return

    bpm_val = int(state.f_bpm) if state.f_bpm.isdigit() else None
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Records (type, title) VALUES (?, ?)", (r_type, r_title))
            rec_id = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO Tracks (record_id, artist, title, bpm, style, runtime, rating, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (rec_id, state.f_artist, state.f_track, bpm_val, STYLES_LIST[state.f_style], state.f_runtime, state.f_rating + 1, state.f_comment))
            
        state.f_artist, state.f_track, state.f_bpm, state.f_record = "", "", "", ""
        state.load_data()
    except Exception as e:
        state.error_message = str(e)

def export_csv(state):
    file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
    if not file: return
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT r.type, t.artist, r.title, t.title, t.bpm, t.style, t.runtime, t.rating, t.comment FROM Records r JOIN Tracks t ON r.record_id = t.record_id")
        rows = cursor.fetchall()
        
    with open(file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Record_Type", "Artist", "Record_Title", "Track_Title", "BPM", "Style", "Runtime", "Rating", "Comment"])
        writer.writerows(rows)

def import_csv(state):
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
                    
                    bpm = int(row.get("BPM")) if row.get("BPM") and row.get("BPM").isdigit() else None
                    rating = int(row.get("Rating")) if row.get("Rating") and row.get("Rating").isdigit() else 3
                    
                    cursor.execute("""
                        INSERT INTO Tracks (record_id, artist, title, bpm, style, runtime, rating, comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (rec_id, row.get("Artist", ""), row.get("Track_Title"), bpm, row.get("Style"), row.get("Runtime"), rating, row.get("Comment")))
        state.load_data()
    except Exception as e:
        state.error_message = f"Import Error: {str(e)}"

def main():
    if not glfw.init():
        print("Could not initialize OpenGL context")
        return

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)

    window = glfw.create_window(1200, 700, "SoulSearch - Vinyl Database", None, None)
    glfw.make_context_current(window)
    if not window:
        glfw.terminate()
        return

    imgui.create_context()
    impl = GlfwRenderer(window)
    
    init_db()
    state = AppState()
    state.load_data()

    while not glfw.window_should_close(window):
        glfw.poll_events()
        impl.process_inputs()
        
        imgui.new_frame()
        render_ui(state)
        
        gl.glClearColor(0.1, 0.1, 0.1, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        imgui.render()
        impl.render(imgui.get_draw_data())
        glfw.swap_buffers(window)

    impl.shutdown()
    glfw.terminate()

if __name__ == "__main__":
    main()
