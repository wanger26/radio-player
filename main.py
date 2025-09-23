from flask import Flask, render_template_string, request, jsonify
import subprocess
import threading
import signal
import os

app = Flask(__name__)

# List of radio stations (name and stream URL)
RADIO_STATIONS = [
    {"name": "Hitradio Ö3", "url": "http://orf-live.ors-shoutcast.at/oe3-q2a"},
    {"name": "Antenna Bayern", "url": "https://s7-webradio.antenne.de/antenne/stream/mp3"},
    {"name": "NPR", "url": "https://npr-ice.streamguys1.com/live.mp3"},
    {"name": "Classic FM", "url": "http://media-ice.musicradio.com/ClassicFMMP3"},
    {"name": "Radio Swiss Pop", "url": "http://stream.srg-ssr.ch/m/rsj/mp3_128"}
]

# Store the current VLC process
vlc_process = None
vlc_lock = threading.Lock()

def stop_vlc():
    global vlc_process
    with vlc_lock:
        if vlc_process and vlc_process.poll() is None:
            vlc_process.terminate()
            try:
                vlc_process.wait(timeout=3)
            except Exception:
                vlc_process.kill()
        vlc_process = None

def play_station(url):
    stop_vlc()
    global vlc_process
    with vlc_lock:
        vlc_process = subprocess.Popen([
            "cvlc", url, "--no-video", "--quiet"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@app.route("/api/stations")
def get_stations():
    return jsonify(RADIO_STATIONS)

@app.route("/api/play", methods=["POST"])
def play():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    threading.Thread(target=play_station, args=(url,), daemon=True).start()
    return jsonify({"status": "playing", "url": url})

@app.route("/api/stop", methods=["POST"])
def stop():
    threading.Thread(target=stop_vlc, daemon=True).start()
    return jsonify({"status": "stopped"})

# Sleek, responsive UI using Bootstrap
HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Radio Player Controller</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #222; color: #fff; }
        .station-card { background: #333; border-radius: 1rem; margin-bottom: 1rem; }
        .btn-play { background: #28a745; color: #fff; }
        .btn-stop { background: #dc3545; color: #fff; }
        .station-title { font-size: 1.3rem; font-weight: 500; }
        @media (max-width: 600px) {
            .station-title { font-size: 1rem; }
        }
    </style>
</head>
<body>
<div class="container py-4">
    <h1 class="mb-4 text-center">Radio Player Controller</h1>
    <div id="stations"></div>
    <div class="text-center mt-4">
        <button class="btn btn-stop" onclick="stopRadio()">Stop</button>
    </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
let currentUrl = null;
function loadStations() {
    fetch('/api/stations').then(r => r.json()).then(stations => {
        const container = document.getElementById('stations');
        container.innerHTML = '';
        stations.forEach(station => {
            const card = document.createElement('div');
            card.className = 'station-card p-3 d-flex justify-content-between align-items-center';
            card.innerHTML = `
                <span class="station-title">${station.name}</span>
                <button class="btn btn-play" onclick="playRadio('${station.url}')">Play</button>
            `;
            container.appendChild(card);
        });
    });
}
function playRadio(url) {
    fetch('/api/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    }).then(r => r.json()).then(res => {
        currentUrl = url;
    });
}
function stopRadio() {
    fetch('/api/stop', { method: 'POST' }).then(r => r.json()).then(res => {
        currentUrl = null;
    });
}
document.addEventListener('DOMContentLoaded', loadStations);
</script>
</body>
</html>
'''

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
