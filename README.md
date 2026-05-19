# 🗑️ SmartBin: Intelligent Waste Management System

A high-end, AI-powered waste classification and bin level monitoring system. This project uses **YOLOv8** for real-time waste detection and **Firebase** for live data synchronization.

---

## 🚀 Key Features

*   **AI Waste Classification**: Real-time detection of Bio (Organic) vs. Non-Bio waste using a custom-trained YOLOv8 model.
*   **Live Bin Monitoring**: Dynamic progress bars and pulsing glow indicators for bin capacity (synced via Firebase).
*   **Ultra-Premium UI**: Glassmorphic design with animated mesh backgrounds, floating orbs, and interactive mouse trails.
*   **Advanced Analytics**: 
    *   **Waste Composition**: Doughnut chart showing the percentage of detected categories.
    *   **Filling Trends**: Real-time line chart tracking bin capacity over time.
*   **Admin & User Portals**: Role-based access with secure authentication.

---

## 🛠️ Project Structure

*   `app.py`: Main Flask application server.
*   `detector_yolov8.py`: Core AI detection engine (YOLOv8 + OpenCV).
*   `yolov8_model.pt`: The custom-trained AI model file.
*   `static/`:
    *   `style.css`: The "Ultra-Premium" design system.
    *   `admin.js` / `user.js`: Frontend logic for real-time updates and charts.
*   `templates/`: HTML5 templates for Login, Register, and Dashboards.
*   `users.db`: SQLite database for user accounts and detection history.

---

## ⚙️ Setup & Installation

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Firebase Configuration**:
    Since `firebase-admin.json` contains sensitive credentials, it is ignored by Git. You must obtain or generate this file to enable live features:
    *   **Option A**: Ask the project creator to securely share the existing `firebase-admin.json` credentials file and place it in the `Application/` directory.
    *   **Option B (Your own database)**: Create a Firebase project in the [Firebase Console](https://console.firebase.google.com/), navigate to **Project Settings** > **Service Accounts**, click **Generate new private key**, rename the downloaded JSON file to `firebase-admin.json`, and place it in the `Application/` directory.
3.  **Run the Application**:
    ```bash
    python app.py
    ```
4.  **Access Portals**:
    *   Login: `http://127.0.0.1:5000/`
    *   Admin Dashboard: Accessible after logging in as an admin.

---

## 📊 How it Works

1.  **Detection**: The system captures frames from the camera or allows image uploads.
2.  **Processing**: The image is cropped to the **Region of Interest (ROI)** and passed to the YOLOv8 model.
3.  **Action**: 
    *   The waste type is identified (BIO/NONBIO).
    *   The result is saved to the SQLite history.
    *   The classification is sent to Firebase to trigger hardware actions (if connected).
4.  **Visualization**: Charts update instantly to reflect the latest data.
