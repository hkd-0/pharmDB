// frontend/js/app.js

import { PharmAPI } from './api.js';
import { PharmUI, renderContextualDropdown } from './ui.js';
import { PharmSearchEngine } from './search.js';

class PharmApp {
    constructor() {
        this.api = new PharmAPI();
        this.ui = new PharmUI();
        this.search = new PharmSearchEngine();
        
        this.inventoryData = [];
        this.moleculeData = [];
    }

    async init() {
        // ALWAYS wire the reset button first to prevent lockouts!
        const resetBtn = document.getElementById('btn-reset-key');
        if (resetBtn) resetBtn.onclick = () => this.api.resetKey();

        try {
            // 1. Fetch the data securely
            const data = await this.api.fetchDatabase();
            this.inventoryData = data.medicinal_product || data.inventory || [];
            this.moleculeData = data.drug_molecule || data.molecules || [];
            
            // 2. Feed the search engine so it can build its index
            this.search.buildIndex(this.inventoryData, this.moleculeData);
            
            // 3. Update the UI statistics
            this.ui.updateStats(this.inventoryData, this.moleculeData);
            this.ui.showDashboard();
            
            // 4. Wire up all the interactive events
            this.bindEvents();

        } catch (error) {
            console.error("Initialization error:", error);
            this.ui.showError("Failed to connect to the database. Check console or reset your API key.");
        }
    }

    bindEvents() {
        // -- View Info (Modal) Wiring --
        this.ui.onViewClick = (productId) => {
            const product = this.inventoryData.find(p => p.Product_ID === productId);
            this.ui.renderModal(product, this.moleculeData);
        };

        // -- The Dropdown Element --
        const autocompleteDropdown = document.getElementById("autocomplete-dropdown");

        // -- Search Interactions --
        // This function handles the COMPLETE SEARCH (Deep dive table)
        const executeSearch = (query) => {
            if (autocompleteDropdown) autocompleteDropdown.style.display = "none";

            if (query.trim() === "") {
                this.ui.resultsContainer.style.display = "none";
                this.ui.renderRecents(this.search.getRecents(), handleRecentTagClick);
            } else {
                this.ui.recentContainer.style.display = "none";
                const results = this.search.search(query);
                this.ui.renderTable(results);
                this.ui.resultsContainer.style.display = "block"; 
            }
        };

        const handleRecentTagClick = (query) => {
            this.ui.searchBox.value = query;
            executeSearch(query);
            this.search.saveRecent(query); // Bump to top of recent list
            this.ui.recentContainer.style.display = "none";
        };

        // Show recents when clicking into the empty search box
        this.ui.searchBox.addEventListener("focus", () => {
            if (this.ui.searchBox.value.trim() === "") {
                this.ui.renderRecents(this.search.getRecents(), handleRecentTagClick);
            }
        });

        // The Debounced Live Search (Splitting Partial vs Complete)
        this.ui.searchBox.addEventListener("keyup", this.search.debounce((e) => {
            const query = e.target.value;

            // COMPLETE SEARCH: They hit the "Enter" key
            if (e.key === "Enter") {
                executeSearch(query);
                if (query.trim() !== "") {
                    this.search.saveRecent(query);
                }
                return;
            }

            // PARTIAL SEARCH: They are typing
            if (query.trim() === "") {
                if (autocompleteDropdown) autocompleteDropdown.style.display = "none";
                this.ui.resultsContainer.style.display = "none";
                this.ui.renderRecents(this.search.getRecents(), handleRecentTagClick);
            } else {
                // Hide recents and main table while they are typing!
                this.ui.recentContainer.style.display = "none";
                this.ui.resultsContainer.style.display = "none"; 
                
                // Trigger the imported UI function to draw the magic intent boxes
                renderContextualDropdown(query, this.search);
            }
        }, 250));

        // UTILITY: Hide dropdown if they click anywhere else on the page
        document.addEventListener("click", (e) => {
            if (autocompleteDropdown && !this.ui.searchBox.contains(e.target) && !autocompleteDropdown.contains(e.target)) {
                autocompleteDropdown.style.display = "none";
            }
        });
    }
}

// Boot up the application when the window loads
window.onload = () => {
    const app = new PharmApp();
    app.init();
};