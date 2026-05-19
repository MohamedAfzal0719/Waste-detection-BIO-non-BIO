// -------------------------------
// CAMERA CONTROL
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
// CAPTURE + DETECT
// -------------------------------
function captureImage() {
    fetch("/capture_detect")
        .then(res => res.json())
        .then(data => {
            document.getElementById("captureResult").innerHTML = `
                <div style="background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 12px; border: 1px solid var(--border-color); text-align: center;">
                    <h4 style="color: var(--primary); font-size: 1.2rem; margin-bottom: 0.25rem;">${data.category}</h4>
                    <p style="color: var(--text-muted); font-weight: 600;">${data.confidence.toFixed(2)}% Confidence</p>
                </div>
            `;
        });
}

// -------------------------------
// UPLOAD DETECT
// -------------------------------
function adminUploadImage() {
    let file = document.getElementById("adminUploadImg").files[0];
    if (!file) return alert("Choose image!");

    let form = new FormData();
    form.append("image", file);

    fetch("/upload", { method: "POST", body: form })
        .then(res => res.json())
        .then(data => {
            document.getElementById("adminUploadResult").innerHTML = `
                <div style="background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 12px; border: 1px solid var(--border-color); text-align: center;">
                    <h4 style="color: var(--secondary); font-size: 1.2rem; margin-bottom: 0.25rem;">${data.category}</h4>
                    <p style="color: var(--text-muted); font-weight: 600; margin-bottom: 0.75rem;">${data.confidence.toFixed(2)}% Confidence</p>
                    <img src="${data.image}" style="width: 100%; border-radius: 8px;">
                </div>
            `;
        });
}

// -------------------------------
// BIN LIVE STATUS
// -------------------------------
setInterval(() => {
    fetch("/api/bin")
        .then(res => res.json())
        .then(data => {
            document.getElementById("bin1-text").textContent = data.BIN1 + "%";
            document.getElementById("bin1-bar").style.width = data.BIN1 + "%";
            
            document.getElementById("bin2-text").textContent = data.BIN2 + "%";
            document.getElementById("bin2-bar").style.width = data.BIN2 + "%";
            
            // Add pulse glow if bin is full (> 80%)
            if (data.BIN1 > 80) document.getElementById("bin1-bar").parentElement.classList.add("glow-active");
            else document.getElementById("bin1-bar").parentElement.classList.remove("glow-active");
            
            if (data.BIN2 > 80) document.getElementById("bin2-bar").parentElement.classList.add("glow-active");
            else document.getElementById("bin2-bar").parentElement.classList.remove("glow-active");
        });
}, 1500);

// -------------------------------
// DETECTION HISTORY PIE CHART
// -------------------------------
let detectChart;

setInterval(() => {
    fetch("/history")
        .then(res => res.json())
        .then(data => {
            let bio = 0, nonbio = 0;
            data.forEach(x => x.category === "BIO" ? bio++ : nonbio++);

            if (detectChart) detectChart.destroy();

            detectChart = new Chart(document.getElementById("detectChart"), {
                type: "doughnut",
                data: {
                    labels: ["BIO", "NONBIO"],
                    datasets: [{
                        data: [bio, nonbio],
                        backgroundColor: ["#3b82f6", "#10b981"],
                        borderColor: "rgba(255,255,255,0.1)",
                        borderWidth: 2
                    }]
                },
                options: {
                    plugins: {
                        legend: { labels: { color: "#94a3b8", font: { family: "Inter" } } }
                    },
                    cutout: "70%"
                }
            });
        });
}, 3000);

// -------------------------------
// RESET ALL DATA
// -------------------------------
function resetAllData() {
    if (confirm("Are you sure you want to clear all detection history and bin levels?")) {
        fetch("/reset_data")
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    alert("Data reset successfully!");
                    location.reload();
                } else {
                    alert("Error: " + data.message);
                }
            });
    }
}

// -------------------------------
// BIN HISTORY CHART (LAST 20)
// -------------------------------
let binChart;

setInterval(() => {
    fetch("/api/bin_history")
        .then(res => res.json())
        .then(history => {

            let time = history.map(x => x.timestamp);
            let b1 = history.map(x => x.bin1);
            let b2 = history.map(x => x.bin2);

            if (binChart) binChart.destroy();

            binChart = new Chart(document.getElementById("binChart"), {
                type: "line",
                data: {
                    labels: time,
                    datasets: [
                        { 
                            label: "BIN1", 
                            data: b1, 
                            borderColor: "#3b82f6", 
                            backgroundColor: "rgba(59, 130, 246, 0.1)",
                            fill: true,
                            tension: 0.4 
                        },
                        { 
                            label: "BIN2", 
                            data: b2, 
                            borderColor: "#10b981", 
                            backgroundColor: "rgba(16, 185, 129, 0.1)",
                            fill: true,
                            tension: 0.4 
                        }
                    ]
                },
                options: {
                    scales: {
                        x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } },
                        y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" }, min: 0, max: 100 }
                    },
                    plugins: {
                        legend: { labels: { color: "#94a3b8" } }
                    },
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        });
}, 3000);