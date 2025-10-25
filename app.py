from flask import Flask, render_template, request, redirect, url_for
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/entry')
def entry():
    return render_template('entry.html')

@app.route('/mood-tracker')
def mood_tracker():
    return render_template('mood-tracker.html')

@app.route('/submit', methods=['POST'])
def submit_entry():
    journal_entry = request.form.get('journal-entry')

    # Ensure the output directory exists
    os.makedirs("out", exist_ok=True)

    # Path to the bash script
    bash_script_path = "send_entry.sh"

    # Write the bash script that sends the journal entry
    with open(bash_script_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"curl -sS http://127.0.0.1:8000/analyze \\\n")
        f.write("  -H 'Content-Type: application/json' \\\n")
        f.write(f"  -d '{{\"text\":\"{journal_entry}\"}}' \\\n")
        f.write("  | python -m json.tool > out/response-$(date +%Y%m%d-%H%M%S).json\n")

    # Make the script executable
    os.chmod(bash_script_path, 0o755)

    return redirect(url_for('mood_tracker'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)