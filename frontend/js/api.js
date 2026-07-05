// frontend/js/api.js

export class PharmAPI {
    constructor() {
        this.userKey = this.authenticate();
    }

    // 1. Handle Security
    authenticate() {
        let key = localStorage.getItem("pharma_secret_key");
        if (!key) {
            key = prompt("First Time Setup: Enter your Database API Key:");
            if (key) {
                localStorage.setItem("pharma_secret_key", key);
            } else {
                document.body.innerHTML = "<h2 style='text-align:center; margin-top: 50px;'>Access Denied. Please refresh and try again.</h2>";
                throw new Error("No API key provided."); 
            }
        }
        return key;
    }

    // 2. Fetch Data
    async fetchDatabase() {
        const response = await fetch("/api/database", {
            method: "GET",
            headers: {
                "X-API-Key": this.userKey, 
                "Content-Type": "application/json"
            }
        }); 
        
        if (!response.ok) throw new Error("Network response was not ok: " + response.status);
        return await response.json();
    }

    // 3. Utility
    resetKey() {
        localStorage.removeItem('pharma_secret_key');
        location.reload();
    }
}