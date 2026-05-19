// -------------------------------
// CAMERA
// -------------------------------
function startCamera() {
    document.getElementById("cameraFeed").src = "/video_feed";
    fetch("/start_camera");
}

function stopCamera() {
    document.getElementById("cameraFeed").src = "";
    fetch("/stop_camera");
}

// -------------------------------
// IMAGE UPLOAD
// -------------------------------
function uploadImage() {
    let file = document.getElementById("uploadImg").files[0];
    if (!file) return alert("Choose image!");

    let form = new FormData();
    form.append("image", file);

    fetch("/upload", {
        method: "POST",
        body: form
    })
        .then(res => res.json())
        .then(data => {
            document.getElementById("uploadResult").innerHTML = `
                <div style="background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 12px; border: 1px solid var(--border-color); text-align: center; margin-top: 1rem;">
                    <h4 style="color: var(--secondary); font-size: 1.2rem; margin-bottom: 0.25rem;">${data.category}</h4>
                    <p style="color: var(--text-muted); font-weight: 600; margin-bottom: 0.75rem;">${data.confidence.toFixed(2)}% Confidence</p>
                    <img src="${data.image}" style="width: 100%; border-radius: 8px; max-height: 250px; object-fit: contain;">
                </div>
            `;
        });
}

// -------------------------------
// USER HISTORY
// -------------------------------
function loadHistory() {
    fetch("/history")
        .then(res => res.json())
        .then(data => {
            let box = document.getElementById("historyBox");
            box.innerHTML = "";

            data.forEach(item => {
                box.innerHTML += `
                    <div class="history-item">
                        <img src="${item.image}">
                        <div class="history-text">
                            <div style="font-weight: 700; color: white; font-size: 1.1rem; margin-bottom: 2px;">${item.category}</div>
                            <div style="color: var(--primary); font-weight: 600;">${item.confidence.toFixed(1)}% Match</div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
                                <i class="far fa-clock"></i> ${item.timestamp}
                            </div>
                        </div>
                    </div>
                `;
            });
        });
}

setInterval(loadHistory, 2000);