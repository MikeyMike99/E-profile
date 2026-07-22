import csv
import os
import time
from flask import Blueprint, request, jsonify, render_template_string

from pathlib import Path
echos_bp = Blueprint('echos', __name__, url_prefix='/echos-calibrator')
CSV_FILE = Path("calibration_data.csv")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Echos Lab: High Precision Calibrator</title>
    <style>
        body { background: #000; color: #0f0; font-family: 'Courier New', monospace; text-align: center; margin: 0; overflow: hidden; }
        #app-container { height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        #ui-box { border: 3px solid #0f0; padding: 40px; background: #050505; width: 85%; max-width: 700px; min-height: 400px; }
        input, textarea { background: #111; border: 1px solid #0f0; color: #0f0; padding: 15px; width: 90%; font-size: 1.2em; margin: 10px 0; }
        .hidden { display: none !important; }
        .stat-text { color: #0ff; font-weight: bold; font-size: 1.8em; margin: 20px 0; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
        h2:focus { outline: none; color: #fff; }
    </style>
</head>
<body role="application">

    <div id="app-container">
        <div id="ui-box" aria-live="assertive" role="main">
            
            <div id="login-zone">
                <h2 id="login-heading" tabindex="-1">Echos Engine Login</h2>
                <p>Type your name and press Enter to read instructions.</p>
                <input type="text" id="user-input" autofocus placeholder="Name">
            </div>

            <div id="instruction-zone" class="hidden">
                <h2 id="instr-heading" tabindex="-1">Instructions</h2>
                <p>Use your headphones for this experience!</p>
                <p>Movement: Use ARROW KEYS. This is silent so you can hear the footsteps.</p>
                <p>Coordinates: Press X to hear your current X and Z position. Note! this is not real game positions this is positions on a audio chart</p>
                <p>Reset: Press R to return to 0, 0.</p>
                <p>Optional: Use NUMPAD 1-9 to log a direction instantly.</p>
                <p>8. for North, 9(. for north east), 6 for east, 3 for south east, 2 for south, 1 for south west, 4 for west, 7 for north west, 5. for center.</p>
                <p>make sure you press enter after you use the numpad keys. leave a comment in the text box that appears. so that I may understand your experience better.</p>
                <p>Feedback: Press ENTER to log a specific position and type a note.</p>
                <p>deactivate browse mode to read this again. activate browse mode to start while browse mode is active. press space.</p>
                <p>You can reload the page at any time. If you are going to spam the logs, it will not help you or me in the process. please use this tool responsibly to help me to calibrate the sound engine. I want to make sure that the sound engine is as accurate as possible for the best experience in ECHOS_OF _THE_WORLD.</p> 
                <br>
                <p style="color: #0f0;">Press SPACEBAR to begin calibration.</p>
            </div>

            <div id="move-zone" class="hidden">
                <h2 id="move-heading" tabindex="-1">Calibration Active</h2>
                <div id="announcer" class="sr-only" aria-live="polite"></div>
                <p>Silent movement active. Press X for position.</p>
                <p id="coords-visual" style="color: #444;">(Visual Coords: 0, 0)</p>
            </div>

            <div id="confirm-zone" class="hidden">
                <h2 id="comm-heading" tabindex="-1">Location Note</h2>
                <p id="freeze-text" style="color: #ff0;"></p>
                <textarea id="comment-box" placeholder="What do you hear?"></textarea>
                <p>Press Enter to save and resume.</p>
            </div>

        </div>
    </div>

    <script>
        let state = "LOGIN";
        let posX = 0.0, posZ = 0.0;
        let userName = "";
        let audioCtx, stepBuffer;

        const announcer = document.getElementById('announcer');
        const commentBox = document.getElementById('comment-box');

        async function initAudio() {
            try {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const resp = await fetch('/static/step.ogg');
                stepBuffer = await audioCtx.decodeAudioData(await resp.arrayBuffer());
            } catch(e) { console.error("Audio Load Fail"); }
        }

        function speak(text) {
            announcer.innerText = "";
            setTimeout(() => { announcer.innerText = text; }, 50);
        }

        function playFootstep(x, z) {
            if (!stepBuffer) return;
            if (audioCtx.state === 'suspended') audioCtx.resume();
            
            const source = audioCtx.createBufferSource();
            const merger = audioCtx.createChannelMerger(2);
            const leftGain = audioCtx.createGain();
            const rightGain = audioCtx.createGain();

            let dist = Math.sqrt(x*x + z*z) + 0.00001;
            let falloff = Math.max(0.0, Math.min(1.0, 1.0 - (dist / 40.0)));
            let vol = 1.0 * falloff; 
            
            if (vol <= 0) return;

            let angle = Math.atan2(x, z);
            let l_gain_val = vol * Math.max(0.0, Math.min(1.0, (1.0 - Math.sin(angle)) / 2.0));
            let r_gain_val = vol * Math.max(0.0, Math.min(1.0, (1.0 + Math.sin(angle)) / 2.0));

            // BACK MUFFLE (Ratio 1:1 with Python API)
            if (z < 0) {
                l_gain_val *= 0.65;
                r_gain_val *= 0.65;
            } else if (z > 0) {
                l_gain_val *= 1.05;
                r_gain_val *= 1.05;
            }

            leftGain.gain.value = l_gain_val;
            rightGain.gain.value = r_gain_val;

            source.connect(leftGain);
            source.connect(rightGain);
            leftGain.connect(merger, 0, 0);
            rightGain.connect(merger, 0, 1);
            merger.connect(audioCtx.destination);
            
            source.buffer = stepBuffer;
            source.start(0);
        }

        commentBox.addEventListener('keydown', (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                saveData("Manual_Comment", "Feedback");
            }
        });

        window.addEventListener('keydown', (e) => {
            const key = e.key.toLowerCase();

            if (state === "LOGIN" && e.key === "Enter") {
                userName = document.getElementById('user-input').value;
                if (userName) {
                    state = "INSTRUCT";
                    document.getElementById('login-zone').classList.add('hidden');
                    document.getElementById('instruction-zone').classList.remove('hidden');
                    initAudio();
                    document.getElementById('instr-heading').focus();
                }
                return;
            }

            if (state === "INSTRUCT" && e.key === " ") {
                e.preventDefault();
                state = "MOVE";
                document.getElementById('instruction-zone').classList.add('hidden');
                document.getElementById('move-zone').classList.remove('hidden');
                document.getElementById('move-heading').focus();
                return;
            }

            if (state === "MOVE") {
                if (document.activeElement.id === "comment-box") return;

                let moved = false;
                if (["arrowup", "arrowdown", "arrowleft", "arrowright", "enter", " ", "x", "r"].includes(key)) {
                    e.preventDefault(); 
                }

                if (e.key === "ArrowUp")    { posZ += 2.0; moved = true; }
                if (e.key === "ArrowDown")  { posZ -= 2.0; moved = true; }
                if (e.key === "ArrowLeft")  { posX -= 2.0; moved = true; }
                if (e.key === "ArrowRight") { posX += 2.0; moved = true; }
                if (key === "r") { posX = 0; posZ = 0; moved = true; }

                if (moved) {
                    playFootstep(posX, posZ);
                }

                if (key === "x") {
                    speak(`Position: X ${posX.toFixed(1)}, Z ${posZ.toFixed(1)}`);
                }

                if (e.key === "Enter") {
                    state = "CONFIRM";
                    document.getElementById('move-zone').classList.add('hidden');
                    document.getElementById('confirm-zone').classList.remove('hidden');
                    document.getElementById('freeze-text').innerText = `Observation at X ${posX.toFixed(1)}, Z ${posZ.toFixed(1)}`;
                    document.getElementById('comm-heading').focus();
                    setTimeout(() => commentBox.focus(), 150);
                }

                const choices = {
                    "Numpad8":"North","Numpad2":"South","Numpad4":"West","Numpad6":"East",
                    "Numpad7":"North-West","Numpad9":"North-East","Numpad1":"South-West",
                    "Numpad3":"South-East","Numpad5":"Center"
                };
                if (choices[e.code]) { saveData(e.code, choices[e.code]); }
            } 
        });

        function saveData(key, dir) {
            let comment = commentBox.value;
            // Target the Blueprint route
            fetch('/echos-calibrator/log', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ u: userName, x: posX, z: posZ, k: key, d: dir, c: comment })
            }).then(() => {
                commentBox.value = "";
                document.getElementById('confirm-zone').classList.add('hidden');
                document.getElementById('move-zone').classList.remove('hidden');
                state = "MOVE";
                document.getElementById('move-heading').focus();
            }).catch(e => {
                console.error("Failed to log data", e);
                // Reset state anyway so user can continue
                document.getElementById('confirm-zone').classList.add('hidden');
                document.getElementById('move-zone').classList.remove('hidden');
                state = "MOVE";
            });
        }
    </script>
</body>
</html>
"""

@echos_bp.route('/')
def index(): 
    return render_template_string(HTML_TEMPLATE)

@echos_bp.route('/log', methods=['POST'])
def log():
    try:
        data = request.json
        exists = CSV_FILE.is_file()
        with open(CSV_FILE, "a", newline="") as f:
            w = csv.writer(f)
            if not exists: 
                w.writerow(["Time", "User", "X", "Z", "Key", "Dir", "Comment"])
            w.writerow([time.ctime(), data.get('u'), data.get('x'), data.get('z'), data.get('k'), data.get('d'), data.get('c', '')])
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"Echos Calibrator Error: Failed to write to {CSV_FILE} - {e}")
        return jsonify({"status": "error", "message": "Failed to write data"}), 500
