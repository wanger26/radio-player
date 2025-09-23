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

# Store the current VLC process and volume
vlc_process = None
vlc_lock = threading.Lock()
current_volume = 70  # Default volume (0-100)
current_station = {"name": None, "url": None}

# Map 0-100 to VLC's 0-512 scale
def volume_to_vlc(val):
    return int(val * 5.12)

def stop_vlc(clear_station=True):
    global vlc_process, current_station
    with vlc_lock:
        if vlc_process and vlc_process.poll() is None:
            vlc_process.terminate()
            try:
                vlc_process.wait(timeout=3)
            except Exception:
                vlc_process.kill()
        vlc_process = None
        if clear_station:
            current_station = {"name": None, "url": None}

def play_station(url):
    stop_vlc(clear_station=True)
    global vlc_process, current_volume, current_station
    # Find station name
    name = next((s["name"] for s in RADIO_STATIONS if s["url"] == url), None)
    with vlc_lock:
        vlc_process = subprocess.Popen([
            "cvlc", url, "--no-video", "--quiet", f"--volume={volume_to_vlc(current_volume)}"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        current_station = {"name": name, "url": url}

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
    threading.Thread(target=stop_vlc, kwargs={"clear_station": True}, daemon=True).start()
    return jsonify({"status": "stopped"})

# Set system volume using amixer (0-100)
def set_system_volume(vol):
    try:
        subprocess.run(["amixer", "sset", "'Master'", f"{vol}%"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Failed to set system volume: {e}")

@app.route("/api/volume", methods=["POST"])
def set_volume():
    global current_volume
    data = request.get_json()
    vol = data.get("volume")
    if vol is None or not (0 <= vol <= 100):
        return jsonify({"error": "Invalid volume"}), 400
    current_volume = vol
    set_system_volume(vol)
    return jsonify({"status": "volume set", "volume": current_volume})

@app.route("/api/status")
def status():
    return jsonify({
        "station": current_station,
        "volume": current_volume
    })

# Enhanced, professional UI with volume controls
HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Radio Player Controller</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background: #181c24; color: #fff; }
        .header { background: #23283a; box-shadow: 0 2px 8px #0002; border-radius: 0 0 1rem 1rem; padding: 1.5rem 0 1rem 0; margin-bottom: 2rem; }
        .header .logo { font-size: 2.2rem; color: #28a745; margin-right: 0.5rem; }
        .header h1 { font-size: 2rem; font-weight: 700; display: inline-block; vertical-align: middle; }
        .station-card { background: #23283a; border-radius: 1rem; margin-bottom: 1.2rem; box-shadow: 0 2px 8px #0001; transition: transform 0.1s; }
        .station-card:hover { transform: scale(1.02); box-shadow: 0 4px 16px #0002; }
        .btn-play, .btn-stop { font-weight: 500; }
        .btn-play { background: linear-gradient(90deg,#28a745 60%,#218838 100%); color: #fff; border: none; }
        .btn-play.active, .btn-play:active { background: #218838; }
        .btn-stop { background: linear-gradient(90deg,#dc3545 60%,#c82333 100%); color: #fff; border: none; }
        .station-title { font-size: 1.2rem; font-weight: 600; }
        .station-icon { font-size: 1.5rem; color: #28a745; margin-right: 0.7rem; }
        .volume-container { background: #23283a; border-radius: 1rem; padding: 1.2rem; margin-bottom: 2rem; box-shadow: 0 2px 8px #0001; }
        .volume-label { font-size: 1.1rem; font-weight: 500; margin-bottom: 0.5rem; }
        .volume-value { font-size: 1rem; font-weight: 600; color: #28a745; margin-left: 0.5rem; }
        .playing-indicator { color: #28a745; font-weight: 600; font-size: 1rem; margin-left: 0.5rem; }
        @media (max-width: 600px) {
            .header h1 { font-size: 1.3rem; }
            .station-title { font-size: 1rem; }
            .station-icon { font-size: 1.2rem; }
        }
    </style>
</head>
<body>
<div class="header text-center">
    <span class="logo"><i class="fa-solid fa-radio"></i></span>
    <h1>Radio Player Controller</h1>
    <div id="current-station" style="margin-top:0.5rem;font-size:1.1rem;color:#28a745;font-weight:600;"></div>
</div>
<div class="container">
    <div class="volume-container mb-4">
        <div class="volume-label">Volume <span class="volume-value" id="volume-value">70</span></div>
        <input type="range" min="0" max="100" value="70" class="form-range" id="volume-slider" style="width:100%">
    </div>
    <div id="stations"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
<script>
let currentUrl = null;
let currentName = null;
let currentVolume = 70;
let stationsList = [];
let volumeTimeout = null;
function loadStations() {
    fetch('/api/stations').then(r => r.json()).then(stations => {
        stationsList = stations;
        renderStations();
    });
}
function renderStations() {
    const container = document.getElementById('stations');
    container.innerHTML = '';
    stationsList.forEach(station => {
        const isPlaying = currentUrl === station.url;
        const card = document.createElement('div');
        card.className = 'station-card p-3 d-flex justify-content-between align-items-center';
        card.innerHTML = `
            <div class="d-flex align-items-center">
                <span class="station-icon"><i class="fa-solid fa-tower-broadcast"></i></span>
                <span class="station-title">${station.name}</span>
                <span class="playing-indicator" id="playing-${station.url}" style="display:${isPlaying ? 'inline' : 'none'}">Playing</span>
            </div>
            <button class="btn ${isPlaying ? 'btn-stop' : 'btn-play'} px-4 py-2" onclick="${isPlaying ? `stopRadio()` : `playRadio('${station.url}', '${station.name}')`}">
                <i class="fa-solid fa-${isPlaying ? 'stop' : 'play'}"></i> ${isPlaying ? 'Stop' : 'Play'}
            </button>
        `;
        container.appendChild(card);
    });
}
function playRadio(url, name) {
    fetch('/api/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    }).then(r => r.json()).then(res => {
        currentUrl = url;
        currentName = name;
        renderStations();
    });
}
function stopRadio() {
    fetch('/api/stop', { method: 'POST' }).then(r => r.json()).then(res => {
        currentUrl = null;
        currentName = null;
        renderStations();
    });
}
function setVolume(vol) {
    fetch('/api/volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume: vol })
    }).then(r => r.json()).then(res => {
        currentVolume = vol;
        document.getElementById('volume-value').textContent = vol;
    });
}
function pollStatus() {
    fetch('/api/status').then(r => r.json()).then(res => {
        const station = res.station;
        const vol = res.volume;
        document.getElementById('volume-value').textContent = vol;
        document.getElementById('volume-slider').value = vol;
        currentVolume = vol;
        if (station && station.name) {
            document.getElementById('current-station').textContent = `Now Playing: ${station.name}`;
            currentUrl = station.url;
            currentName = station.name;
        } else {
            document.getElementById('current-station').textContent = 'No station playing';
            currentUrl = null;
            currentName = null;
        }
        // Only re-render stations if stationsList is not empty
        if (stationsList.length > 0) {
            renderStations();
        }
    });
}
document.addEventListener('DOMContentLoaded', function() {
    loadStations();
    const slider = document.getElementById('volume-slider');
    slider.value = currentVolume;
    slider.addEventListener('input', function() {
        setVolume(parseInt(this.value));
    });
    pollStatus();
    setInterval(pollStatus, 1000);
});
</script>
</body>
</html>
'''

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
